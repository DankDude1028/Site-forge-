"""Authenticated control API. No endpoint executes arbitrary model commands."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, NAMESPACE_URL, uuid5

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from sqlalchemy import func, select, text

from .contracts import (
    ActionExecution, ActionRequest, CheckpointRequest, CompleteRequest, FailureRequest,
    LeaseRequest, Principal, RenewRequest, StrictModel, TaskClaim, TaskCreate, WorkerRegister,
)
from .bundles import BundleManifest, BundleStore
from .db import (
    Agent, AnalyticsSnapshot, Approval, AuditEvent, BenchmarkResult, BenchmarkRun,
    Budget, Database, Deployment, Experiment, Model, Notification, Opportunity, Organization,
    PolicyDecision, Receipt, Site, Task, Worker, Workflow, audit, utcnow,
)
from .economics import EconomicsService
from .integrations import AnalyticsImport, AnalyticsIngestor, RevenueImport
from .policy import KNOWN_TOOLS, PolicyService
from .queue import DomainError, QueueService, aware, digest, task_view, tenant_row
from .providers import ProviderError
from .release import ReleaseConfig, ReleaseService


class SiteCreate(StrictModel):
    slug: str = Field(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(StrictModel):
    type: str = Field(min_length=1, max_length=80)
    site_id: UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=160)


class ApprovalDecision(StrictModel):
    reason: str = Field(default="", max_length=500)


class BudgetConfiguration(StrictModel):
    period: str = Field(pattern="^\\d{4}-\\d{2}(-\\d{2})?$")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    limit_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=6)


class KillSwitch(StrictModel):
    enabled: bool


class Reconciliation(StrictModel):
    status: str = Field(pattern="^(succeeded|failed|unknown)$")
    provider_reference: str = Field(min_length=1, max_length=200)


class PreviewPlanRequest(StrictModel):
    site_id: UUID
    commit_sha: str = Field(pattern="^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    relative_directory: str = Field(min_length=1, max_length=240)


class PromotionPlanRequest(StrictModel):
    preview_deployment_id: UUID


class ReleaseLookupRequest(StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=160)


class Candidate(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    demand: float = Field(ge=0, le=1)
    low_competition: float = Field(ge=0, le=1)
    commercial_intent: float = Field(ge=0, le=1)
    original_value: float = Field(ge=0, le=1)
    low_maintenance: float = Field(ge=0, le=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


def row_dict(row: Any) -> dict[str, Any]:
    return api_json({column.name: getattr(row, column.name) for column in row.__table__.columns
                     if column.name not in {"lease_token", "token_hash"}})


def api_json(value: Any) -> Any:
    """Money crosses the API as decimal strings, without a binary-float hop."""
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def create_app(db: Database | None = None,
               token_config: dict[str, dict[str, Any] | Principal] | None = None) -> FastAPI:
    db = db or Database(os.environ.get("SITEFORGE_DATABASE_URL") or os.environ.get("DATABASE_URL", "sqlite:///siteforge-local.db"))
    config = token_config if token_config is not None else json.loads(os.environ.get("SITEFORGE_AUTH_TOKENS", "{}"))
    if token_config is None and not config:
        org_id = os.environ.get("SITEFORGE_ORG_ID", "")
        owner_token = os.environ.get("SITEFORGE_OWNER_TOKEN", "")
        worker_token = os.environ.get("SITEFORGE_WORKER_TOKEN", "")
        if owner_token and org_id:
            config[hashlib.sha256(owner_token.encode()).hexdigest()] = {
                "subject": "owner", "org_id": org_id, "role": "owner"}
        if worker_token and org_id:
            config[hashlib.sha256(worker_token.encode()).hexdigest()] = {
                "subject": "windows-worker", "org_id": org_id, "role": "worker",
                "worker_id": os.environ.get("SITEFORGE_WORKER_ID"),
                "expires_at": os.environ.get("SITEFORGE_WORKER_TOKEN_EXPIRES_AT") or None,
                "capabilities": sorted(KNOWN_TOOLS),
            }
    # Only SHA-256 digests are accepted in configuration. Constant-time comparisons
    # also avoid exposing which configured identity failed authentication.
    if any(len(key) != 64 or any(c not in "0123456789abcdef" for c in key) for key in config):
        raise ValueError("SITEFORGE_AUTH_TOKENS keys must be lowercase SHA-256 digests")
    principals = [(key, value if isinstance(value, Principal) else Principal.model_validate(value))
                  for key, value in config.items()]
    queue, policy, economics = QueueService(db), PolicyService(db), EconomicsService(db)
    ingestor = AnalyticsIngestor(db)
    app = FastAPI(title="SiteForge Supervisor", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db, app.state.queue, app.state.policy = db, queue, policy

    def record_denial(request: Request, reason: str) -> None:
        identity = getattr(request.state, "identity", None)
        if identity is not None:
            with db.transaction() as session:
                if session.get(Organization, identity.org_id) is not None:
                    audit(session, identity.org_id, identity.subject, "api.denied", request.url.path,
                          "denied", reason=reason[:500])

    @app.exception_handler(DomainError)
    async def domain_exception(request: Request, exc: DomainError) -> JSONResponse:
        record_denial(request, exc.message)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(ProviderError)
    async def provider_exception(request: Request, exc: ProviderError) -> JSONResponse:
        # Provider payloads, URLs and exception chains may carry credentials.
        return JSONResponse(status_code=502, content={
            "detail": "Provider result unavailable; inspect and reconcile the durable release record."})

    @app.exception_handler(HTTPException)
    async def scope_exception(request: Request, exc: HTTPException) -> Any:
        if exc.status_code == 403:
            record_denial(request, str(exc.detail))
        return await http_exception_handler(request, exc)

    def principal(request: Request, authorization: Annotated[str | None, Header()] = None) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "bearer authentication required", headers={"WWW-Authenticate": "Bearer"})
        supplied = hashlib.sha256(authorization[7:].encode()).hexdigest()
        identity = next((identity for key, identity in principals if secrets.compare_digest(key, supplied)), None)
        if identity is None:
            raise HTTPException(401, "invalid credential")
        if identity.expires_at and aware(identity.expires_at) <= utcnow():
            raise HTTPException(401, "credential expired")
        if identity.role == "worker":
            if not identity.worker_id or not identity.expires_at:
                raise HTTPException(401, "worker credential requires bound identity and expiry")
            if aware(identity.expires_at) > utcnow() + timedelta(hours=24):
                raise HTTPException(401, "worker credential validity exceeds 24 hours")
        if identity.role == "release":
            if (not identity.expires_at or not identity.site_ids
                    or aware(identity.expires_at) > utcnow() + timedelta(hours=24)):
                raise HTTPException(401, "release credential requires explicit sites and expiry within 24 hours")
        request.state.identity = identity
        return identity

    def owner(identity: Principal = Depends(principal)) -> Principal:
        if identity.role != "owner":
            raise HTTPException(403, "owner scope required")
        return identity

    def release_operator(identity: Principal = Depends(principal)) -> Principal:
        if identity.role not in {"owner", "release"}:
            raise HTTPException(403, "release operator scope required")
        return identity

    def release_scope(identity: Principal, site_id: str, capability: str) -> None:
        if identity.role == "owner":
            return
        if site_id not in {str(value) for value in identity.site_ids} or capability not in identity.capabilities:
            raise HTTPException(403, "release credential does not permit this site or operation")

    def reader(identity: Principal = Depends(principal)) -> Principal:
        if identity.role not in {"owner", "observer"}:
            raise HTTPException(403, "portfolio read scope required")
        return identity

    def worker_scope(identity: Principal, worker_id: str) -> None:
        if identity.role != "worker" or identity.worker_id != str(worker_id):
            raise HTTPException(403, "worker credential is bound to another identity")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> JSONResponse:
        try:
            with db.session() as session:
                session.execute(text("SELECT 1"))
                session.execute(select(Organization.id).limit(1))
            return JSONResponse({"status": "ready"})
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    @app.get("/metrics")
    def prometheus_metrics(identity: Principal = Depends(owner)) -> Response:
        def label(value: str) -> str:
            return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

        lines: list[str] = []
        with db.session() as session:
            org = session.get(Organization, identity.org_id)
            if org is None:
                raise DomainError("organization not provisioned", 403)
            lines += ["# TYPE siteforge_kill_switch gauge", f"siteforge_kill_switch {int(org.kill_switch)}"]
            lines.append("# TYPE siteforge_tasks gauge")
            for state, count in session.execute(select(Task.status, func.count()).where(
                Task.org_id == identity.org_id).group_by(Task.status)):
                lines.append(f'siteforge_tasks{{state="{label(state)}"}} {count}')
            lines.append("# TYPE siteforge_workers gauge")
            for state, count in session.execute(select(Worker.status, func.count()).where(
                Worker.org_id == identity.org_id).group_by(Worker.status)):
                lines.append(f'siteforge_workers{{state="{label(state)}"}} {count}')
            expired = session.scalar(select(func.count()).select_from(Task).where(
                Task.org_id == identity.org_id, Task.status.in_(["leased", "running"]), Task.lease_expires_at <= utcnow()))
            approvals = session.scalar(select(func.count()).select_from(Approval).where(
                Approval.org_id == identity.org_id, Approval.status == "pending", Approval.expires_at > utcnow()))
            lines += ["# TYPE siteforge_expired_leases gauge", f"siteforge_expired_leases {expired or 0}",
                      "# TYPE siteforge_pending_approvals gauge", f"siteforge_pending_approvals {approvals or 0}"]
            for measure in ("limit", "used", "reserved"):
                lines.append(f"# TYPE siteforge_budget_{measure} gauge")
            for budget in session.scalars(select(Budget).where(Budget.org_id == identity.org_id)):
                tags = f'currency="{label(budget.currency)}",period="{label(budget.period)}"'
                for measure in ("limit", "used", "reserved"):
                    value = getattr(budget, measure + "_amount")
                    lines.append(f"siteforge_budget_{measure}{{{tags}}} {value:.6f}")
        return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    @app.post("/v1/workers/register")
    def register(body: WorkerRegister, identity: Principal = Depends(principal)) -> dict[str, Any]:
        if identity.role != "worker":
            raise HTTPException(403, "worker scope required")
        if not set(body.capabilities) <= set(identity.capabilities):
            raise HTTPException(403, "registered capabilities exceed credential scope")
        return queue.register_worker(identity.org_id, body.name, body.capabilities,
                                     worker_id=identity.worker_id, version=body.version)

    @app.post("/v1/workers/{worker_id}/heartbeat")
    def heartbeat(worker_id: UUID, identity: Principal = Depends(principal)) -> dict[str, Any]:
        worker_scope(identity, str(worker_id))
        return queue.heartbeat(identity.org_id, str(worker_id))

    @app.post("/v1/tasks/lease")
    def lease(body: LeaseRequest, identity: Principal = Depends(principal)) -> Any:
        worker_scope(identity, str(body.worker_id))
        return queue.lease(identity.org_id, str(body.worker_id), body.seconds)

    @app.post("/v1/tasks")
    @app.post("/v1/jobs")
    def enqueue(body: TaskCreate, identity: Principal = Depends(owner)) -> Any:
        return queue.enqueue(identity.org_id, body, identity.subject)

    @app.post("/v1/tasks/{task_id}/start")
    def start(task_id: UUID, body: TaskClaim, identity: Principal = Depends(principal)) -> Any:
        worker_scope(identity, str(body.worker_id))
        return queue.start(identity.org_id, str(body.worker_id), str(task_id), body.lease_token)

    @app.post("/v1/tasks/{task_id}/renew")
    def renew(task_id: UUID, body: RenewRequest, identity: Principal = Depends(principal)) -> Any:
        worker_scope(identity, str(body.worker_id))
        return queue.renew(identity.org_id, str(body.worker_id), str(task_id), body.lease_token, body.seconds)

    @app.post("/v1/tasks/{task_id}/checkpoint")
    def checkpoint(task_id: UUID, body: CheckpointRequest, identity: Principal = Depends(principal)) -> Any:
        worker_scope(identity, str(body.worker_id))
        return queue.checkpoint(identity.org_id, str(body.worker_id), str(task_id), body.lease_token, body.data)

    @app.get("/v1/tasks/{task_id}/checkpoint")
    def read_checkpoint(task_id: UUID, identity: Principal = Depends(principal)) -> Any:
        if identity.role not in {"owner", "observer", "worker"}:
            raise HTTPException(403, "task read scope required")
        with db.session() as session:
            task = tenant_row(session, Task, identity.org_id, str(task_id))
            if identity.role == "worker" and task.lease_worker_id != identity.worker_id:
                raise HTTPException(403, "task is not leased to this identity")
        return queue.latest_checkpoint(identity.org_id, str(task_id))

    @app.post("/v1/tasks/{task_id}/complete")
    def complete(task_id: UUID, body: CompleteRequest, identity: Principal = Depends(principal)) -> Any:
        worker_scope(identity, str(body.worker_id))
        return queue.complete(identity.org_id, str(body.worker_id), str(task_id), body.lease_token, body.result)

    @app.post("/v1/tasks/{task_id}/fail")
    def fail(task_id: UUID, body: FailureRequest, identity: Principal = Depends(principal)) -> Any:
        worker_scope(identity, str(body.worker_id))
        return queue.fail(identity.org_id, str(body.worker_id), str(task_id), body.lease_token, body.error, body.retryable)

    @app.get("/v1/tasks/{task_id}")
    @app.get("/v1/jobs/{task_id}")
    def read_task(task_id: UUID, identity: Principal = Depends(principal)) -> Any:
        if identity.role not in {"owner", "observer", "worker"}:
            raise HTTPException(403, "task read scope required")
        with db.session() as session:
            task = tenant_row(session, Task, identity.org_id, str(task_id))
            if identity.role == "worker" and task.lease_worker_id != identity.worker_id:
                raise HTTPException(403, "task is not leased to this identity")
            return task_view(task, include_token=False)

    @app.post("/v1/tasks/{task_id}/cancel")
    @app.post("/v1/jobs/{task_id}/cancel")
    def cancel(task_id: UUID, identity: Principal = Depends(owner)) -> Any:
        return queue.cancel(identity.org_id, str(task_id), identity.subject)

    @app.post("/v1/maintenance/recover")
    def recover(identity: Principal = Depends(owner)) -> dict[str, int]:
        return {"expired_leases_recovered": queue.recover_expired(identity.org_id)}

    @app.post("/v1/sites")
    def create_site(body: SiteCreate, identity: Principal = Depends(owner)) -> dict[str, Any]:
        with db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == identity.org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            site = session.scalar(select(Site).where(Site.org_id == identity.org_id, Site.slug == body.slug))
            if site is not None:
                if digest(site.config) != digest(body.config):
                    raise DomainError("site slug already binds a different configuration")
                return row_dict(site)
            site = Site(org_id=identity.org_id, slug=body.slug, config=body.config)
            session.add(site)
            session.flush()
            audit(session, identity.org_id, identity.subject, "site.create", site.id)
            return row_dict(site)

    @app.get("/v1/sites/{site_id}")
    def read_site(site_id: UUID, identity: Principal = Depends(reader)) -> dict[str, Any]:
        with db.session() as session:
            return row_dict(tenant_row(session, Site, identity.org_id, str(site_id)))

    @app.post("/v1/workflows")
    def workflow(body: WorkflowCreate, identity: Principal = Depends(owner)) -> dict[str, Any]:
        with db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == identity.org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            if body.site_id:
                tenant_row(session, Site, identity.org_id, str(body.site_id))
            row = session.scalar(select(Workflow).where(Workflow.org_id == identity.org_id,
                                                        Workflow.idempotency_key == body.idempotency_key))
            if row:
                if row.type != body.type or row.site_id != (str(body.site_id) if body.site_id else None):
                    raise DomainError("workflow idempotency key conflict")
                return row_dict(row)
            row = Workflow(org_id=identity.org_id, type=body.type, site_id=str(body.site_id) if body.site_id else None,
                           idempotency_key=body.idempotency_key)
            session.add(row)
            session.flush()
            audit(session, identity.org_id, identity.subject, "workflow.create", row.id)
            return row_dict(row)

    @app.post("/v1/candidates/evaluate")
    def candidate(body: Candidate, identity: Principal = Depends(owner)) -> dict[str, Any]:
        score = sum(getattr(body, key) * weight for key, weight in {
            "demand": .25, "low_competition": .20, "commercial_intent": .25,
            "original_value": .20, "low_maintenance": .10}.items())
        data = body.model_dump()
        data.update(score=score, evidence_status="unverified", estimates=True)
        with db.transaction() as session:
            if session.get(Organization, identity.org_id) is None:
                raise DomainError("organization not provisioned", 403)
            opportunity = Opportunity(org_id=identity.org_id, name=body.name, data=data)
            session.add(opportunity)
            session.flush()
            audit(session, identity.org_id, identity.subject, "candidate.evaluate", opportunity.id)
            return row_dict(opportunity)

    @app.post("/v1/approvals")
    def request_approval(body: ActionRequest, identity: Principal = Depends(principal)) -> Any:
        if identity.role not in {"owner", "worker"}:
            raise HTTPException(403, "approval request scope required")
        return api_json(policy.request_approval(identity.org_id, body, identity.subject))

    @app.post("/v1/approvals/{approval_id}/approve")
    def approve(approval_id: UUID, body: ApprovalDecision, identity: Principal = Depends(owner)) -> Any:
        return api_json(policy.decide(identity.org_id, str(approval_id), identity.subject, True, body.reason))

    @app.post("/v1/approvals/{approval_id}/reject")
    def reject(approval_id: UUID, body: ApprovalDecision, identity: Principal = Depends(owner)) -> Any:
        return api_json(policy.decide(identity.org_id, str(approval_id), identity.subject, False, body.reason))

    @app.post("/v1/approvals/{approval_id}/authorize")
    def authorize(approval_id: UUID, body: ActionExecution, identity: Principal = Depends(owner)) -> Any:
        return api_json(policy.authorize(identity.org_id, str(approval_id), body, identity.subject))

    @app.post("/v1/receipts/{receipt_id}/reconcile")
    def reconcile(receipt_id: UUID, body: Reconciliation, identity: Principal = Depends(owner)) -> Any:
        return api_json(policy.reconcile(identity.org_id, str(receipt_id), body.status, body.provider_reference, identity.subject))

    def release_service(identity: Principal, site_id: str) -> ReleaseService:
        with db.session() as session:
            tenant_row(session, Site, identity.org_id, site_id)
        try:
            return ReleaseService.from_environment(db, site_id)
        except (ValueError, ProviderError) as error:
            raise DomainError("Release service is not configured for this site", 503) from error

    def deployment_site(identity: Principal, deployment_id: str) -> str:
        with db.session() as session:
            return tenant_row(session, Deployment, identity.org_id, deployment_id).site_id

    def bundle_store() -> BundleStore:
        try:
            if os.environ.get("SITEFORGE_BUNDLES_ENABLED", "false") != "true":
                raise ValueError("Bundle transfer disabled")
            configured = ReleaseConfig.from_environment()
            if configured.preview_root is None or not configured.allowed_sites:
                raise ValueError("Bundle scope not configured")
            origins = {site_id: configured.production_origins[provider_id]
                       for site_id, provider_id in configured.allowed_sites.items()
                       if provider_id in configured.production_origins}
            return BundleStore(configured.preview_root, enabled=True, allowed_origins=origins)
        except (ValueError, OSError) as error:
            raise DomainError("Bundle transfer is not configured", 503) from error

    def bundle_write_scope(identity: Principal, site_id: str, session: Any) -> None:
        release_scope(identity, site_id, "upload_bundle")
        tenant_row(session, Site, identity.org_id, site_id)
        organization = session.scalar(select(Organization).where(
            Organization.id == identity.org_id).with_for_update())
        if organization is None:
            raise DomainError("Organization not provisioned", 403)
        if organization.kill_switch:
            raise DomainError("Bundle writes paused by kill switch", 403)
        configured = ReleaseConfig.from_environment()
        if site_id not in configured.allowed_sites:
            raise DomainError("Bundle site is not configured", 403)

    @app.post("/v1/bundles")
    def begin_bundle(body: BundleManifest, identity: Principal = Depends(release_operator)) -> Any:
        store = bundle_store()
        try:
            with db.transaction() as session:
                bundle_write_scope(identity, str(body.site_id), session)
                result = store.begin(body, org_id=identity.org_id, uploader=identity.subject)
                audit(session, identity.org_id, identity.subject, "bundle.begin", result["bundle_id"],
                      site_id=str(body.site_id), manifest_sha256=result["manifest_sha256"])
            return result
        except (ValueError, OSError) as error:
            raise DomainError("Bundle manifest or storage binding rejected", 422) from error

    @app.get("/v1/bundles/{bundle_id}")
    def describe_bundle(bundle_id: str, identity: Principal = Depends(release_operator)) -> Any:
        try:
            result = bundle_store().describe(bundle_id, org_id=identity.org_id, uploader=identity.subject)
            release_scope(identity, str(result["site_id"]), "upload_bundle")
            with db.session() as session:
                tenant_row(session, Site, identity.org_id, str(result["site_id"]))
            return result
        except (ValueError, OSError) as error:
            raise DomainError("Bundle binding unavailable", 404) from error

    @app.put("/v1/bundles/{bundle_id}/files")
    async def upload_bundle_file(bundle_id: str, request: Request,
                                 path: str = Query(min_length=1, max_length=160),
                                 identity: Principal = Depends(release_operator)) -> Any:
        store = bundle_store()
        try:
            binding = store.describe(bundle_id, org_id=identity.org_id, uploader=identity.subject)
            release_scope(identity, str(binding["site_id"]), "upload_bundle")
            if request.headers.get("content-type", "").split(";", 1)[0] != "application/octet-stream":
                raise DomainError("Bundle files require application/octet-stream", 415)
            chunks: list[bytes] = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 4_000_000:
                    raise DomainError("Bundle file exceeds transfer limit", 413)
                chunks.append(chunk)
            with db.transaction() as session:
                bundle_write_scope(identity, str(binding["site_id"]), session)
                result = store.upload(bundle_id, path, b"".join(chunks), org_id=identity.org_id,
                                      uploader=identity.subject)
                audit(session, identity.org_id, identity.subject, "bundle.upload", bundle_id,
                      path=path, bytes=size)
            return result
        except (ValueError, OSError) as error:
            raise DomainError("Bundle file or principal binding rejected", 422) from error

    @app.post("/v1/bundles/{bundle_id}/finalize")
    def finalize_bundle(bundle_id: str, identity: Principal = Depends(release_operator)) -> Any:
        store = bundle_store()
        try:
            binding = store.describe(bundle_id, org_id=identity.org_id, uploader=identity.subject)
            with db.transaction() as session:
                bundle_write_scope(identity, str(binding["site_id"]), session)
                result = store.finalize(bundle_id, org_id=identity.org_id, uploader=identity.subject)
                audit(session, identity.org_id, identity.subject, "bundle.seal", bundle_id,
                      manifest_sha256=result["manifest_sha256"], site_id=str(binding["site_id"]))
            return result
        except (ValueError, OSError) as error:
            raise DomainError("Bundle integrity, SEO or principal binding rejected", 422) from error

    @app.post("/v1/releases/lookup")
    def lookup_release(body: ReleaseLookupRequest, identity: Principal = Depends(release_operator)) -> Any:
        with db.session() as session:
            receipt = session.scalar(select(Receipt).where(Receipt.org_id == identity.org_id,
                Receipt.idempotency_key == body.idempotency_key))
            if receipt is None:
                return {"found": False}
            approval = tenant_row(session, Approval, identity.org_id, receipt.approval_id)
            release_scope(identity, approval.site_id, "reconcile_release")
            identifier = str(uuid5(NAMESPACE_URL, "siteforge:release:" + receipt.id))
            deployment = session.get(Deployment, identifier)
            if deployment is None:
                return {"found": True, "intent_only": True, "receipt_id": receipt.id}
            if deployment.org_id != identity.org_id or deployment.site_id != approval.site_id:
                raise DomainError("Release lookup binding differs", 403)
            return {"found": True, "deployment": row_dict(deployment)}

    @app.post("/v1/releases/preview-plan")
    def preview_plan(body: PreviewPlanRequest, identity: Principal = Depends(release_operator)) -> Any:
        release_scope(identity, str(body.site_id), "plan_release")
        service = release_service(identity, str(body.site_id))
        try:
            return service.plan_preview(str(body.site_id), body.commit_sha, body.relative_directory,
                                        org_id=identity.org_id)
        finally:
            service.close()

    @app.post("/v1/releases/{approval_id}/preview")
    def execute_preview(approval_id: UUID, body: ActionExecution, identity: Principal = Depends(release_operator)) -> Any:
        release_scope(identity, str(body.site_id), "deploy_preview")
        service = release_service(identity, str(body.site_id))
        try:
            return service.execute_preview(identity.org_id, str(approval_id), body, identity.subject)
        finally:
            service.close()

    @app.post("/v1/releases/promotion-plan")
    def promotion_plan(body: PromotionPlanRequest, identity: Principal = Depends(release_operator)) -> Any:
        site_id = deployment_site(identity, str(body.preview_deployment_id))
        release_scope(identity, site_id, "plan_release")
        service = release_service(identity, site_id)
        try:
            return service.plan_promotion(identity.org_id, str(body.preview_deployment_id), identity.subject)
        finally:
            service.close()

    @app.post("/v1/releases/{approval_id}/production")
    def execute_production(approval_id: UUID, body: ActionExecution, identity: Principal = Depends(release_operator)) -> Any:
        release_scope(identity, str(body.site_id), "deploy_production")
        service = release_service(identity, str(body.site_id))
        try:
            return service.execute_promotion(identity.org_id, str(approval_id), body, identity.subject)
        finally:
            service.close()

    @app.post("/v1/releases/{deployment_id}/reconcile")
    def reconcile_release(deployment_id: UUID, identity: Principal = Depends(release_operator)) -> Any:
        site_id = deployment_site(identity, str(deployment_id))
        release_scope(identity, site_id, "reconcile_release")
        service = release_service(identity, site_id)
        try:
            return service.reconcile(identity.org_id, str(deployment_id), identity.subject)
        finally:
            service.close()

    @app.post("/v1/releases/{deployment_id}/resume-preview")
    def resume_preview(deployment_id: UUID, identity: Principal = Depends(owner)) -> Any:
        service = release_service(identity, deployment_site(identity, str(deployment_id)))
        try:
            return service.resume_preview(identity.org_id, str(deployment_id), identity.subject)
        finally:
            service.close()

    @app.post("/v1/releases/{deployment_id}/guard-production")
    def guard_production(deployment_id: UUID, identity: Principal = Depends(release_operator)) -> Any:
        site_id = deployment_site(identity, str(deployment_id))
        release_scope(identity, site_id, "guard_production")
        service = release_service(identity, site_id)
        try:
            return service.guard_production(identity.org_id, str(deployment_id), identity.subject)
        finally:
            service.close()

    @app.post("/v1/budgets")
    def configure_budget(body: BudgetConfiguration, identity: Principal = Depends(owner)) -> Any:
        return api_json(policy.set_budget(identity.org_id, body.period, body.limit_amount, identity.subject, body.currency))

    @app.post("/v1/kill-switch")
    def kill_switch(body: KillSwitch, identity: Principal = Depends(owner)) -> dict[str, bool]:
        queue.set_kill_switch(identity.org_id, body.enabled, identity.subject)
        return {"enabled": body.enabled}

    @app.get("/v1/kill-switch")
    def kill_state(identity: Principal = Depends(reader)) -> dict[str, bool]:
        with db.session() as session:
            org = session.get(Organization, identity.org_id)
            if org is None:
                raise DomainError("organization not provisioned", 403)
            return {"enabled": org.kill_switch}

    @app.get("/v1/sites/{site_id}/economics")
    def site_economics(site_id: UUID, currency: str = "USD", identity: Principal = Depends(reader)) -> Any:
        return api_json(economics.summary(identity.org_id, str(site_id), currency))

    @app.post("/v1/imports/analytics")
    def import_analytics(body: AnalyticsImport, identity: Principal = Depends(owner)) -> Any:
        return ingestor.ingest(identity.org_id, body, identity.subject)

    @app.post("/v1/imports/revenue")
    def import_revenue(body: RevenueImport, identity: Principal = Depends(owner)) -> Any:
        return ingestor.ingest_revenue(identity.org_id, body, identity.subject)

    @app.get("/v1/sites/{site_id}/analytics-coverage")
    def analytics_coverage(site_id: UUID, provider: str, identity: Principal = Depends(reader)) -> Any:
        return ingestor.coverage(identity.org_id, str(site_id), provider)

    @app.get("/v1/dashboard-summary")
    def dashboard_summary(identity: Principal = Depends(reader)) -> dict[str, int]:
        with db.session() as session:
            counts = {name: int(session.scalar(select(func.count()).select_from(model).where(
                model.org_id == identity.org_id)) or 0)
                for name, model in (("sites", Site), ("tasks", Task), ("workers", Worker), ("audit_events", AuditEvent))}
            counts["pending_approvals"] = int(session.scalar(select(func.count()).select_from(Approval).where(
                Approval.org_id == identity.org_id, Approval.status == "pending")) or 0)
            return counts

    catalogs = {
        "sites": Site, "workers": Worker, "tasks": Task, "jobs": Task,
        "agents": Agent, "workflows": Workflow, "approvals": Approval, "budgets": Budget,
        "audit": AuditEvent, "opportunities": Opportunity, "models": Model,
        "benchmark-runs": BenchmarkRun, "benchmark-results": BenchmarkResult,
        "metrics": AnalyticsSnapshot, "deployments": Deployment, "experiments": Experiment,
        "notifications": Notification, "policy-decisions": PolicyDecision, "receipts": Receipt,
    }

    def catalog_endpoint(model: Any) -> Any:
        def endpoint(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                     status: str | None = Query(None, min_length=1, max_length=80),
                     identity: Principal = Depends(reader)) -> list[dict[str, Any]]:
            with db.session() as session:
                statement = select(model).where(model.org_id == identity.org_id)
                if status is not None:
                    if not hasattr(model, "status"):
                        raise HTTPException(422, "This catalog has no status filter")
                    statement = statement.where(model.status == status)
                rows = session.scalars(statement
                                       .order_by(model.created_at.desc(), model.id).limit(limit).offset(offset)).all()
                return [row_dict(row) for row in rows]
        return endpoint

    for name, model in catalogs.items():
        app.add_api_route("/v1/" + name, catalog_endpoint(model), methods=["GET"], name="list_" + name)
    dashboard = Path(__file__).resolve().parent.parent / "apps" / "dashboard" / "dist"
    if dashboard.is_dir():
        app.mount("/", StaticFiles(directory=str(dashboard), html=True), name="dashboard")
    return app


app = create_app()
