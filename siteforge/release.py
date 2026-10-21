"""Durable, default-disabled exact-approval Netlify release orchestration.

A committed dispatch claim is an at-most-once boundary. After crash/uncertainty
only provider reads are permitted; absence in a bounded listing never proves
no effect. Availability is deliberately sacrificed rather than repeating it.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select

from .contracts import ActionExecution
from .db import Approval, Database, Deployment, Organization, Receipt, audit, utcnow
from .policy import PolicyService, money
from .providers import NetlifyReleaseAdapter, ProviderError, ProviderReceipt
from .queue import DomainError, aware, digest, tenant_row


@dataclass(frozen=True)
class ReleaseConfig:
    enabled: bool = False
    production_enabled: bool = False
    allowed_sites: dict[str, str] = field(default_factory=dict)
    preview_root: Path | None = None
    protected_sites: frozenset[str] = frozenset()
    known_cost_usd: Decimal | None = None
    max_cost_usd: Decimal = Decimal("0")
    preview_authorization: str | None = field(default=None, repr=False)
    production_origins: dict[str, str] = field(default_factory=dict)
    exclusive_publisher_verified: bool = False
    resume_uploads_enabled: bool = False
    resume_cost_usd: Decimal | None = None

    @classmethod
    def from_environment(cls) -> ReleaseConfig:
        def flag(name: str) -> bool:
            value = os.environ.get("SITEFORGE_RELEASE_" + name, "false").casefold()
            if value not in {"true", "false"}:
                raise ValueError("Release flags must be true or false")
            return value == "true"
        bindings = json.loads(os.environ.get("SITEFORGE_RELEASE_SITE_BINDINGS", "{}"))
        protected = json.loads(os.environ.get("SITEFORGE_RELEASE_PROTECTED_SITES", "[]"))
        origins = json.loads(os.environ.get("SITEFORGE_RELEASE_PRODUCTION_ORIGINS", "{}"))
        if (not isinstance(bindings, dict) or not isinstance(origins, dict) or not isinstance(protected, list)
                or any(type(key) is not str or type(value) is not str for key, value in bindings.items())
                or any(type(key) is not str or type(value) is not str for key, value in origins.items())
                or any(type(value) is not str for value in protected)):
            raise ValueError("Release allowlists must use exact configured identities")
        for value in [*bindings, *bindings.values(), *protected, *origins]:
            UUID(value)
        known = os.environ.get("SITEFORGE_RELEASE_KNOWN_COST_USD", "").strip()
        resume_cost = os.environ.get("SITEFORGE_RELEASE_RESUME_COST_USD", "").strip()
        root = os.environ.get("SITEFORGE_PREVIEW_ROOT")
        return cls(enabled=flag("ENABLED"), production_enabled=flag("PRODUCTION_ENABLED"),
            allowed_sites=bindings, protected_sites=frozenset(protected),
            preview_root=Path(root).resolve() if root else None,
            known_cost_usd=money(known) if known else None,
            max_cost_usd=money(os.environ.get("SITEFORGE_RELEASE_MAX_COST_USD", "0")),
            preview_authorization=os.environ.get("SITEFORGE_PREVIEW_AUTHORIZATION"),
            production_origins=origins, exclusive_publisher_verified=flag("EXCLUSIVE_PUBLISHER"),
            resume_uploads_enabled=flag("RESUME_UPLOADS_ENABLED"),
            resume_cost_usd=money(resume_cost) if resume_cost else None)


class ReleaseService:
    def __init__(self, db: Database, adapter: NetlifyReleaseAdapter, config: ReleaseConfig, *,
                 policy: PolicyService | None = None) -> None:
        self.db, self.adapter, self.config = db, adapter, config
        self.policy = policy or PolicyService(db)

    @classmethod
    def from_environment(cls, db: Database, site_id: str) -> ReleaseService:
        config = ReleaseConfig.from_environment()
        if not config.enabled:
            raise ProviderError("Release provider integration is disabled")
        provider_site = config.allowed_sites.get(str(site_id))
        if provider_site is None or config.preview_root is None:
            raise ValueError("Release site and scoped preview root must be configured")
        adapter = NetlifyReleaseAdapter(provider_site, config.preview_root,
            operator_authorized=config.enabled, cost_authorized=config.known_cost_usd is not None,
            protected_preview_verified=provider_site in config.protected_sites,
            preview_authorization=config.preview_authorization,
            production_enabled=config.production_enabled,
            production_origin=config.production_origins.get(provider_site),
            exclusive_publisher_verified=config.exclusive_publisher_verified)
        return cls(db, adapter, config)

    def close(self) -> None:
        self.adapter.close()

    def _scope(self, site_id: str) -> None:
        if not self.config.enabled:
            raise ProviderError("Release provider integration is disabled")
        if (self.config.allowed_sites.get(str(site_id)) != self.adapter.site_id
                or self.config.preview_root is None
                or self.config.preview_root.resolve() != self.adapter.root):
            raise DomainError("Release provider/site/artifact scope mismatch", 403)

    def _cost(self) -> Decimal:
        if self.config.known_cost_usd is None:
            raise DomainError("Provider operation cost is unknown; release disabled", 403)
        amount = money(self.config.known_cost_usd)
        if amount > money(self.config.max_cost_usd):
            raise DomainError("Server release cost cap exceeded", 403)
        return amount

    def _execution(self, execution: ActionExecution, action: str) -> None:
        self._scope(str(execution.site_id))
        if execution.action != action or execution.currency != "USD" or money(execution.amount) != self._cost():
            raise DomainError("Release action/currency/known cost binding differs", 403)

    @staticmethod
    def _commit(commit: str) -> str:
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
            raise DomainError("Release requires an exact commit SHA", 422)
        return commit

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise DomainError("Release payload is missing a required typed binding", 422)
        return value

    def plan_preview(self, site_id: str, commit_sha: str, relative_directory: str) -> dict[str, Any]:
        self._scope(site_id)
        amount = self._cost()
        commit_sha = self._commit(commit_sha)
        if not isinstance(relative_directory, str):
            raise DomainError("Preview requires a scoped artifact directory", 422)
        if self.adapter.site_id not in self.config.protected_sites:
            raise DomainError("Preview protection must be server configured", 403)
        try:
            plan = self.adapter.plan(relative_directory)
        except (ValueError, OSError) as error:
            raise DomainError("Preview artifacts must be valid static output inside the configured root", 422) from error
        payload = {"operation": "netlify_draft", "provider_site_id": self.adapter.site_id,
                   "commit_sha": commit_sha, "tree_sha256": digest(plan.files),
                   "artifact_directory": plan.directory.relative_to(self.adapter.root).as_posix(),
                   "files": [list(item) for item in plan.files],
                   "upload_resume": {"enabled": self.config.resume_uploads_enabled and self.config.resume_cost_usd == 0,
                                     "maximum_attempts": 2,
                                     "incremental_cost_usd": "0.000000" if self.config.resume_cost_usd == 0 else None}}
        return {"action": "deploy_preview", "site_id": str(site_id), "payload": payload,
                "amount": format(amount, ".6f"), "currency": "USD"}

    def _actor(self, org_id: str, approval_id: str, actor: str) -> None:
        with self.db.session() as session:
            approval = tenant_row(session, Approval, org_id, approval_id)
            if approval.approved_by != actor or not actor:
                raise DomainError("Release requires the exact approving operator", 403)

    def _existing(self, org_id: str, execution: ActionExecution) -> bool:
        with self.db.session() as session:
            return session.scalar(select(Receipt.id).where(Receipt.org_id == org_id,
                Receipt.idempotency_key == execution.idempotency_key)) is not None

    def _claim(self, org_id: str, approval_id: str, execution: ActionExecution, actor: str,
               receipt: dict[str, Any], environment: str) -> tuple[str, bool]:
        identifier = str(uuid5(NAMESPACE_URL, "siteforge:release:" + receipt["id"]))
        with self.db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("Organization not provisioned", 403)
            approval = tenant_row(session, Approval, org_id, approval_id, lock=True)
            intent = tenant_row(session, Receipt, org_id, receipt["id"], lock=True)
            row = session.get(Deployment, identifier)
            if row is None:
                # Org lock serializes all our site dispatches without JSON indexes.
                pending = session.scalars(select(Deployment).where(Deployment.org_id == org_id,
                    Deployment.site_id == str(execution.site_id),
                    Deployment.status.in_(["pending_dispatch", "dispatching", "unknown", "processing", "verifying", "resuming"]))).all()
                if pending:
                    raise DomainError("An unresolved release must be reconciled before another effect")
                row = Deployment(id=identifier, org_id=org_id, site_id=str(execution.site_id),
                    approval_id=approval_id, environment=environment, commit_sha=execution.payload["commit_sha"],
                    status="pending_dispatch", data={"receipt_id": intent.id,
                        "execution": execution.model_dump(mode="json"), "operator": actor,
                        "correlation_id": "siteforge:" + intent.id + ":" + intent.payload_hash,
                        "dispatch_claimed": False, "cost_scope": "server-attested complete operation cost"})
                session.add(row)
                session.flush()
            if row.org_id != org_id or row.approval_id != approval_id or row.data["execution"] != execution.model_dump(mode="json"):
                raise DomainError("Durable release binding differs", 403)
            dispatch = not receipt["replay"] and not row.data["dispatch_claimed"]
            if dispatch:
                if org.kill_switch or aware(approval.expires_at) <= self.policy.clock() or intent.status != "reserved":
                    raise DomainError("Release dispatch blocked by kill switch/expiry/intent state", 403)
                row.status = "dispatching"
                row.data = {**row.data, "dispatch_claimed": True, "dispatch_claimed_at": utcnow().isoformat()}
                audit(session, org_id, actor, "release.dispatch_claim", row.id, receipt_id=intent.id,
                      environment=environment, payload_hash=intent.payload_hash)
            return identifier, dispatch

    def get(self, org_id: str, deployment_id: str) -> dict[str, Any]:
        with self.db.session() as session:
            row = tenant_row(session, Deployment, org_id, deployment_id)
            return {key: getattr(row, key) for key in ("id", "site_id", "approval_id", "environment", "commit_sha", "status", "data")}

    def _store(self, org_id: str, identifier: str, actor: str, status: str, **patch: Any) -> dict[str, Any]:
        with self.db.transaction() as session:
            row = tenant_row(session, Deployment, org_id, identifier, lock=True)
            if (patch.get("provider_deploy_id") and row.data.get("provider_deploy_id")
                    and patch["provider_deploy_id"] != row.data["provider_deploy_id"]):
                raise DomainError("Provider effect identity cannot be rewritten")
            row.status = status
            row.data = {**row.data, **patch, "checked_at": utcnow().isoformat()}
            audit(session, org_id, actor, "release.reconcile", identifier, outcome=status,
                  provider_deploy_id=row.data.get("provider_deploy_id"))
        return self.get(org_id, identifier)

    def _settle(self, org_id: str, receipt_id: str, status: str, reference: str, actor: str) -> None:
        with self.db.session() as session:
            current = tenant_row(session, Receipt, org_id, receipt_id)
            if current.status in {"succeeded", "failed"}:
                if status != "unknown" and (current.status != status or current.provider_reference != reference):
                    raise DomainError("Final receipt conflicts with reconciled provider effect", 403)
                return
        try:
            self.policy.reconcile(org_id, receipt_id, status, reference, actor)
        except DomainError:
            with self.db.session() as session:
                current = tenant_row(session, Receipt, org_id, receipt_id)
                if (current.status not in {"succeeded", "failed"} or status != "unknown"
                        and (current.status != status or current.provider_reference != reference)):
                    raise

    def execute_preview(self, org_id: str, approval_id: str, execution: ActionExecution, actor: str) -> dict[str, Any]:
        self._execution(execution, "deploy_preview")
        self._actor(org_id, approval_id, actor)
        if not self._existing(org_id, execution):
            planned = self.plan_preview(str(execution.site_id), self._string(execution.payload, "commit_sha"),
                                        self._string(execution.payload, "artifact_directory"))
            if execution.payload != planned["payload"]:
                raise DomainError("Approved preview artifact tree differs", 403)
        receipt = self.policy.authorize(org_id, approval_id, execution, actor)
        try:
            identifier, dispatch = self._claim(org_id, approval_id, execution, actor, receipt, "preview")
        except DomainError:
            if not receipt["replay"]:
                self._settle(org_id, receipt["id"], "failed", "siteforge:no-dispatch:" + receipt["id"], actor)
            raise
        if dispatch:
            row = self.get(org_id, identifier)
            try:
                plan = self.adapter.plan(execution.payload["artifact_directory"])
                if (digest(plan.files) != execution.payload["tree_sha256"]
                        or [list(item) for item in plan.files] != execution.payload["files"]):
                    raise ValueError("Artifact changed after authorization")
            except (ValueError, OSError):
                self._settle(org_id, receipt["id"], "failed", "siteforge:no-effect:" + identifier, actor)
                return self._store(org_id, identifier, actor, "failed", no_provider_dispatch=True,
                                   last_error="artifact_changed_before_provider_dispatch")
            try:
                def created(effect: ProviderReceipt) -> None:
                    self._store(org_id, identifier, actor, "verifying", provider_deploy_id=effect.resource_id,
                                preview_url=effect.url)
                self.adapter.create_draft_preview(plan, correlation_id=row["data"]["correlation_id"], on_created=created)
            except ProviderError:
                self._store(org_id, identifier, actor, "unknown", last_error="provider_effect_or_response_uncertain")
        return self.reconcile(org_id, identifier, actor)

    def _production(self) -> None:
        if (not self.config.production_enabled or not self.config.exclusive_publisher_verified
                or self.adapter.site_id not in self.config.production_origins
                or self.adapter.production_origin != self.config.production_origins[self.adapter.site_id]):
            raise DomainError("Production and exclusive publisher attestation must be server configured", 403)

    def plan_promotion(self, org_id: str, preview_deployment_id: str) -> dict[str, Any]:
        row = self.get(org_id, preview_deployment_id)
        self._scope(row["site_id"])
        self._production()
        if row["environment"] != "preview" or row["status"] != "ready":
            raise DomainError("Promotion requires a reconciled protected ready preview", 403)
        bound = row["data"]["execution"]["payload"]
        payload = {"operation": "promote_ready_preview", "provider_site_id": self.adapter.site_id,
                   "preview_deployment_id": row["id"], "provider_deploy_id": row["data"]["provider_deploy_id"],
                   "commit_sha": row["commit_sha"], "tree_sha256": bound["tree_sha256"],
                   "previous_published_id": self.adapter.current_published_id()}
        return {"action": "deploy_production", "site_id": row["site_id"], "payload": payload,
                "amount": format(self._cost(), ".6f"), "currency": "USD"}

    def resume_preview(self, org_id: str, deployment_id: str, actor: str) -> dict[str, Any]:
        """Explicit bounded same-hash upload retry under the original approval.

        Never retries create/promotion. Reconciliation remains external-read-only.
        A stale attempt may finish its in-flight identical PUT, but cannot start
        another after its durable claim lease expires or another claim fences it.
        """
        row = self.get(org_id, deployment_id)
        self._scope(row["site_id"])
        if (row["environment"] != "preview" or not self.config.resume_uploads_enabled
                or self.config.resume_cost_usd is None or money(self.config.resume_cost_usd) != 0
                or row["data"]["execution"]["payload"].get("upload_resume") != {
                    "enabled": True, "maximum_attempts": 2, "incremental_cost_usd": "0.000000"}):
            raise DomainError("Upload recovery requires approved server-attested zero incremental cost", 403)
        self._actor(org_id, row["approval_id"], actor)
        self._execution(ActionExecution.model_validate(row["data"]["execution"]), "deploy_preview")
        identifier = row["data"].get("provider_deploy_id")
        if not identifier:
            raise DomainError("Reconcile the exact provider draft identity before upload recovery")
        deploy = self.adapter.read_deploy(identifier)
        if (deploy["title"] != row["data"]["correlation_id"] or deploy["draft"] is not True
                or deploy["published_at"] or self.adapter.current_published_id() == identifier):
            raise DomainError("Upload recovery requires the exact unpublished provider draft", 403)
        if not deploy["required"]:
            return self.reconcile(org_id, deployment_id, actor)
        bound = row["data"]["execution"]["payload"]
        plan = self.adapter.plan(bound["artifact_directory"])
        if digest(plan.files) != bound["tree_sha256"] or [list(item) for item in plan.files] != bound["files"]:
            raise DomainError("Recovery artifact differs from the approved tree", 403)
        token = uuid4().hex
        with self.db.transaction() as session:
            organization = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            current = tenant_row(session, Deployment, org_id, deployment_id, lock=True)
            approval = tenant_row(session, Approval, org_id, row["approval_id"], lock=True)
            receipt = tenant_row(session, Receipt, org_id, row["data"]["receipt_id"], lock=True)
            now = self.policy.clock()
            if (organization is None or organization.kill_switch or aware(approval.expires_at) <= now
                    or approval.approved_by != actor or receipt.status == "failed"):
                raise DomainError("Upload recovery blocked by approval/kill switch/receipt", 403)
            attempts = current.data.get("upload_resume_attempts", [])
            previous = current.data.get("upload_resume_claim")
            if previous and datetime.fromisoformat(previous["expires_at"]) > now:
                raise DomainError("Another bounded upload recovery claim is active")
            if len(attempts) >= 2:
                raise DomainError("Approved upload recovery attempts exhausted")
            claim = {"token": token, "expires_at": (now + timedelta(seconds=120)).isoformat()}
            current.status = "resuming"
            current.data = {**current.data, "upload_resume_claim": claim,
                "upload_resume_attempts": [*attempts, {"attempt": len(attempts) + 1,
                    "started_at": now.isoformat(), "required_digests": deploy["required"]}]}
            audit(session, org_id, actor, "release.upload_resume_claim", deployment_id,
                  attempt=len(attempts) + 1, incremental_cost_usd="0.000000")

        def before_upload() -> None:
            with self.db.session() as session:
                organization = session.get(Organization, org_id)
                current = tenant_row(session, Deployment, org_id, deployment_id)
                approval = tenant_row(session, Approval, org_id, row["approval_id"])
                claim = current.data.get("upload_resume_claim")
                if (organization is None or organization.kill_switch or not claim or claim["token"] != token
                        or datetime.fromisoformat(claim["expires_at"]) <= self.policy.clock()
                        or aware(approval.expires_at) <= self.policy.clock()):
                    raise DomainError("Upload recovery claim was fenced", 403)
        try:
            self.adapter.resume_draft_upload(plan, identifier, deploy["required"], before_upload=before_upload)
        except ProviderError:
            self._store(org_id, deployment_id, actor, "unknown", last_error="idempotent_upload_response_uncertain")
        finally:
            with self.db.transaction() as session:
                current = tenant_row(session, Deployment, org_id, deployment_id, lock=True)
                claim = current.data.get("upload_resume_claim")
                if claim and claim["token"] == token:
                    current.data = {**current.data, "upload_resume_claim": None}
        return self.reconcile(org_id, deployment_id, actor)

    def execute_promotion(self, org_id: str, approval_id: str, execution: ActionExecution, actor: str) -> dict[str, Any]:
        self._execution(execution, "deploy_production")
        self._actor(org_id, approval_id, actor)
        self._production()
        if not self._existing(org_id, execution):
            planned = self.plan_promotion(org_id, self._string(execution.payload, "preview_deployment_id"))
            if execution.payload != planned["payload"] or str(execution.site_id) != planned["site_id"]:
                raise DomainError("Exact preview/commit/tree/previous publication binding differs", 403)
            preview = self.get(org_id, execution.payload["preview_deployment_id"])
            deploy = self.adapter.read_deploy(execution.payload["provider_deploy_id"])
            if deploy["title"] != preview["data"]["correlation_id"] or deploy["published_at"]:
                raise DomainError("An older or unrelated deploy cannot be restored", 403)
            self.adapter.verify_preview(deploy, self._index(preview))
        receipt = self.policy.authorize(org_id, approval_id, execution, actor)
        try:
            identifier, dispatch = self._claim(org_id, approval_id, execution, actor, receipt, "production")
        except DomainError:
            if not receipt["replay"]:
                self._settle(org_id, receipt["id"], "failed", "siteforge:no-dispatch:" + receipt["id"], actor)
            raise
        if dispatch:
            self._store(org_id, identifier, actor, "dispatching", provider_deploy_id=execution.payload["provider_deploy_id"])
            try:
                self.adapter.promote_ready_preview(execution.payload["provider_deploy_id"],
                    execution.payload["previous_published_id"], receipt["payload_hash"])
            except ProviderError:
                self._store(org_id, identifier, actor, "unknown", last_error="publication_outcome_uncertain")
        return self.reconcile(org_id, identifier, actor)

    @staticmethod
    def _index(preview: dict[str, Any]) -> str:
        return next(item[2] for item in preview["data"]["execution"]["payload"]["files"] if item[0] == "index.html")

    def reconcile(self, org_id: str, deployment_id: str, actor: str) -> dict[str, Any]:
        row = self.get(org_id, deployment_id)
        self._scope(row["site_id"])
        data = row["data"]
        if not data["dispatch_claimed"] or data.get("no_provider_dispatch"):
            # Another concurrent caller may be between authorization and claim.
            # An orphaned authorization also must never trigger an automatic effect.
            return row
        if row["environment"] == "preview" and row["status"] == "promoted":
            return row
        try:
            identifier = data.get("provider_deploy_id")
            if row["environment"] == "preview":
                deploy = self.adapter.read_deploy(identifier) if identifier else self.adapter.find_draft(data["correlation_id"])
                if deploy is None or deploy["title"] != data["correlation_id"]:
                    raise ProviderError("No unique provider effect has been reconciled")
                if deploy["commit_ref"] and deploy["commit_ref"] != row["commit_sha"]:
                    raise ProviderError("Provider commit binding differs")
                if deploy["draft"] is not True or deploy["published_at"]:
                    raise ProviderError("Expected protected draft became a published deploy")
            else:
                identifier = data["execution"]["payload"]["provider_deploy_id"]
                deploy = self.adapter.read_deploy(identifier)
                preview = self.get(org_id, data["execution"]["payload"]["preview_deployment_id"])
                if (deploy["title"] != preview["data"]["correlation_id"]
                        or deploy["commit_ref"] and deploy["commit_ref"] != row["commit_sha"]):
                    raise ProviderError("Published provider artifact binding differs")
                if self.adapter.current_published_id() != identifier:
                    raise ProviderError("Approved publication not observed")
            identifier = deploy["id"]
            self._store(org_id, deployment_id, actor, "processing", provider_deploy_id=identifier,
                        provider_state=deploy["state"])
            # Settles the known mutation effect/cost, not a claim of healthy hosting.
            self._settle(org_id, data["receipt_id"], "succeeded", "netlify:deploy:" + identifier, actor)
            if deploy["state"] == "error":
                return self._store(org_id, deployment_id, actor, "failed", last_error="provider_deploy_error")
            if deploy["state"] != "ready" or deploy["required"]:
                return self.get(org_id, deployment_id)
            try:
                if row["environment"] == "preview":
                    health = self.adapter.verify_preview(deploy, self._index(row))
                    status = "ready"
                else:
                    preview = self.get(org_id, data["execution"]["payload"]["preview_deployment_id"])
                    health = self.adapter.verify_production(self._index(preview))
                    status = "healthy"
            except ProviderError:
                return self._store(org_id, deployment_id, actor, "health_failed", last_error="health_or_protection_not_verified")
            result = self._store(org_id, deployment_id, actor, status, health=health,
                cost_reconciled="server-attested mutation cost; not a provider invoice", last_error=None,
                **({"preview_url": deploy["deploy_ssl_url"]} if row["environment"] == "preview" else {}))
            if row["environment"] == "production":
                self._store(org_id, data["execution"]["payload"]["preview_deployment_id"], actor,
                            "promoted", promoted_deployment_id=deployment_id)
            return result
        except ProviderError:
            self._settle(org_id, data["receipt_id"], "unknown", "netlify:correlation:" + data["correlation_id"], actor)
            return self._store(org_id, deployment_id, actor, "unknown", last_error="provider_read_or_identity_unresolved")
