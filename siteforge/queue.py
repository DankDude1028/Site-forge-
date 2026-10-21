"""Single durable queue authority with fenced, renewable worker leases."""
from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .contracts import TaskCreate, TaskView
from .db import (
    Artifact, Attempt, Checkpoint, Database, Dependency, Lease, Organization,
    Site, Task, Worker, Workflow, audit, new_id, utcnow,
)


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, default=str).encode()).hexdigest()


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def tenant_row(session: Session, model: Any, org_id: str, identifier: str,
               *, lock: bool = False) -> Any:
    statement = select(model).where(model.id == str(identifier), model.org_id == org_id)
    if lock:
        statement = statement.with_for_update()
    row = session.scalar(statement)
    if row is None:
        raise DomainError("record not found", 404)
    return row


def task_view(task: Task, *, include_token: bool = True) -> TaskView:
    result = TaskView.model_validate(task)
    if not include_token:
        result.lease_token = None
    return result


class QueueService:
    def __init__(self, db: Database, *, clock: Callable[[], datetime] = utcnow,
                 retry_backoff: tuple[int, ...] = (30, 120, 600)):
        self.db = db
        self.clock = clock
        self.retry_backoff = retry_backoff

    def _organization(self, session: Session, org_id: str) -> Organization:
        org = session.get(Organization, org_id)
        if org is None:
            raise DomainError("organization not provisioned", 403)
        return org

    def register_worker(self, org_id: str, name: str, capabilities: list[str],
                        worker_id: str | None = None, version: str = "0.1.0") -> dict[str, Any]:
        from .policy import KNOWN_TOOLS
        if not capabilities or not set(capabilities) <= KNOWN_TOOLS:
            raise DomainError("unknown or empty worker capabilities", 422)
        with self.db.transaction() as session:
            self._organization(session, org_id)
            worker = session.get(Worker, worker_id) if worker_id else None
            if worker is not None and worker.org_id != org_id:
                raise DomainError("record not found", 404)
            existing = session.scalar(select(Worker).where(Worker.org_id == org_id, Worker.name == name))
            if existing is not None and (worker_id is None or existing.id != worker_id):
                raise DomainError("worker name already registered")
            if worker is None:
                worker = Worker(id=worker_id or new_id(), org_id=org_id, name=name,
                                capabilities=sorted(set(capabilities)), version=version)
                session.add(worker)
            else:
                worker.name = name
                worker.capabilities = sorted(set(capabilities))
                worker.version = version
            worker.last_heartbeat_at = self.clock()
            worker.status = "online"
            session.flush()
            audit(session, org_id, worker.id, "worker.register", worker.id)
            return self._worker(worker)

    @staticmethod
    def _worker(worker: Worker) -> dict[str, Any]:
        return {"id": worker.id, "name": worker.name, "capabilities": worker.capabilities,
                "status": worker.status, "version": worker.version,
                "last_heartbeat_at": worker.last_heartbeat_at}

    def heartbeat(self, org_id: str, worker_id: str) -> dict[str, Any]:
        with self.db.transaction() as session:
            worker = tenant_row(session, Worker, org_id, worker_id, lock=True)
            worker.last_heartbeat_at = self.clock()
            worker.status = "online"
            audit(session, org_id, worker_id, "worker.heartbeat", worker_id)
            return self._worker(worker)

    def enqueue(self, org_id: str, spec: TaskCreate, actor: str = "owner") -> TaskView:
        from .policy import AGENT_TOOLS
        if spec.capability not in AGENT_TOOLS[spec.agent_type.value]:
            raise DomainError("agent capability denied", 403)
        request_hash = digest(spec.model_dump(mode="json"))
        with self.db.transaction() as session:
            # Serialize idempotency creation for this tenant, not worker claims.
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            existing = session.scalar(select(Task).where(Task.org_id == org_id,
                                                         Task.idempotency_key == spec.idempotency_key))
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise DomainError("idempotency key is bound to a different task")
                return task_view(existing, include_token=False)
            if spec.site_id:
                tenant_row(session, Site, org_id, str(spec.site_id))
            if spec.workflow_id:
                workflow = tenant_row(session, Workflow, org_id, str(spec.workflow_id))
                if workflow.site_id != (str(spec.site_id) if spec.site_id else None):
                    raise DomainError("task and workflow site differ", 422)
            deps = [tenant_row(session, Task, org_id, str(dep)) for dep in set(spec.dependencies)]
            task = Task(
                org_id=org_id, site_id=str(spec.site_id) if spec.site_id else None,
                workflow_id=str(spec.workflow_id) if spec.workflow_id else None,
                agent_type=spec.agent_type.value, capability=spec.capability, input=spec.input,
                input_hash=digest(spec.input), request_hash=request_hash,
                idempotency_key=spec.idempotency_key, max_attempts=spec.max_attempts,
                deadline=spec.deadline, budget_cap=spec.budget_cap,
                status="pending" if any(dep.status != "completed" for dep in deps) else "ready",
                available_at=self.clock(), updated_at=self.clock(),
            )
            session.add(task)
            session.flush()
            for dependency in deps:
                session.add(Dependency(task_id=task.id, depends_on_id=dependency.id))
            audit(session, org_id, actor, "task.enqueue", task.id, state=task.status)
            return task_view(task, include_token=False)

    def _finish_attempt(self, session: Session, task: Task, status: str, error: str | None = None) -> None:
        attempt = session.scalar(select(Attempt).where(Attempt.task_id == task.id,
                                                       Attempt.number == task.attempt))
        if attempt is not None:
            attempt.status, attempt.error, attempt.finished_at = status, error, self.clock()
        if task.lease_token:
            lease = session.scalar(select(Lease).where(Lease.token_hash == digest(task.lease_token)))
            if lease is not None:
                lease.released_at = self.clock()

    def _retry(self, session: Session, task: Task, error: str, retryable: bool) -> None:
        self._finish_attempt(session, task, "failed", error)
        task.error_code = error
        if retryable and task.attempt < task.max_attempts:
            task.status = "retry_scheduled"
            task.available_at = self.clock() + timedelta(seconds=self.retry_backoff[min(task.attempt - 1, len(self.retry_backoff) - 1)])
        else:
            task.status = "failed"
        task.lease_expires_at = None
        task.lease_token = None
        task.lease_worker_id = None
        task.updated_at = self.clock()
        audit(session, task.org_id, "supervisor", "task.retry" if task.status == "retry_scheduled" else "task.dead_letter",
              task.id, state=task.status, error=error)

    def _recover(self, session: Session, org_id: str | None) -> int:
        now = self.clock()
        deadlines = select(Task).where(
            Task.status.in_(["pending", "ready", "leased", "running", "retry_scheduled", "waiting_approval"]),
            Task.deadline <= now)
        if org_id is not None:
            deadlines = deadlines.where(Task.org_id == org_id)
        for task in session.scalars(deadlines.with_for_update(skip_locked=True)).all():
            self._finish_attempt(session, task, "failed", "deadline_expired")
            task.status, task.error_code, task.updated_at = "failed", "deadline_expired", now
            task.lease_token, task.lease_expires_at, task.lease_worker_id = None, None, None
            audit(session, task.org_id, "supervisor", "task.deadline", task.id)
        stmt = select(Task).where(Task.status.in_(["leased", "running"]), Task.lease_expires_at <= now)
        if org_id is not None:
            stmt = stmt.where(Task.org_id == org_id)
        expired = session.scalars(stmt.with_for_update(skip_locked=True)).all()
        for task in expired:
            self._retry(session, task, "lease_expired", True)
        pending = select(Task).where(Task.status == "pending")
        if org_id is not None:
            pending = pending.where(Task.org_id == org_id)
        for task in session.scalars(pending.with_for_update(skip_locked=True)).all():
            statuses = session.scalars(select(Task.status).join(Dependency, Dependency.depends_on_id == Task.id)
                                      .where(Dependency.task_id == task.id)).all()
            if any(status in {"failed", "cancelled", "blocked"} for status in statuses):
                task.status = "blocked"
                task.error_code = "dependency_failed"
                audit(session, task.org_id, "supervisor", "task.blocked", task.id)
            elif all(status == "completed" for status in statuses):
                task.status = "ready"
                audit(session, task.org_id, "supervisor", "task.ready", task.id)
        return len(expired)

    def recover_expired(self, org_id: str | None = None) -> int:
        with self.db.transaction() as session:
            return self._recover(session, org_id)

    def lease(self, org_id: str, worker_id: str, seconds: int = 120) -> TaskView | None:
        if not 15 <= seconds <= 600:
            raise DomainError("lease seconds must be between 15 and 600", 422)
        with self.db.transaction() as session:
            organization = self._organization(session, org_id)
            worker = tenant_row(session, Worker, org_id, worker_id)
            self._recover(session, org_id)
            if organization.kill_switch:
                return None
            now = self.clock()
            candidates = select(Task).where(
                Task.org_id == org_id, Task.status.in_(["ready", "retry_scheduled"]),
                Task.available_at <= now, Task.capability.in_(worker.capabilities),
            ).order_by(Task.created_at, Task.id).limit(1).with_for_update(skip_locked=True)
            for task in session.scalars(candidates).all():
                if task.deadline and aware(task.deadline) <= now:
                    task.status, task.error_code = "failed", "deadline_expired"
                    audit(session, org_id, "supervisor", "task.deadline", task.id)
                    continue
                task.status = "leased"
                task.attempt += 1
                task.lease_worker_id = worker_id
                task.lease_token = secrets.token_urlsafe(32)
                task.lease_expires_at = now + timedelta(seconds=seconds)
                task.updated_at = now
                session.add(Attempt(org_id=org_id, task_id=task.id, worker_id=worker_id,
                                    number=task.attempt, status="leased"))
                session.add(Lease(org_id=org_id, task_id=task.id, worker_id=worker_id,
                                  token_hash=digest(task.lease_token), expires_at=task.lease_expires_at))
                audit(session, org_id, worker_id, "task.lease", task.id, attempt=task.attempt)
                return task_view(task)
            return None

    def _claim(self, session: Session, org_id: str, worker_id: str, task_id: str, token: str) -> Task:
        task = tenant_row(session, Task, org_id, task_id, lock=True)
        if task.status not in {"leased", "running"} or task.lease_worker_id != worker_id:
            raise DomainError("worker does not hold this task")
        if not task.lease_token or not secrets.compare_digest(task.lease_token, token):
            raise DomainError("lease fencing token rejected", 403)
        if not task.lease_expires_at or aware(task.lease_expires_at) <= self.clock():
            raise DomainError("lease has expired")
        if task.deadline and aware(task.deadline) <= self.clock():
            raise DomainError("task deadline has expired")
        return task

    def start(self, org_id: str, worker_id: str, task_id: str, lease_token: str) -> TaskView:
        with self.db.transaction() as session:
            task = self._claim(session, org_id, worker_id, task_id, lease_token)
            if task.status == "leased":
                task.status, task.updated_at = "running", self.clock()
                attempt = session.scalar(select(Attempt).where(Attempt.task_id == task.id, Attempt.number == task.attempt))
                if attempt is None:
                    raise DomainError("attempt record missing")
                attempt.status = "running"
                audit(session, org_id, worker_id, "task.start", task.id)
            return task_view(task)

    def renew(self, org_id: str, worker_id: str, task_id: str, lease_token: str, seconds: int = 120) -> TaskView:
        if not 15 <= seconds <= 600:
            raise DomainError("lease seconds must be between 15 and 600", 422)
        with self.db.transaction() as session:
            task = self._claim(session, org_id, worker_id, task_id, lease_token)
            task.lease_expires_at = self.clock() + timedelta(seconds=seconds)
            lease = session.scalar(select(Lease).where(Lease.token_hash == digest(lease_token)))
            if lease is None:
                raise DomainError("lease record missing")
            lease.expires_at = task.lease_expires_at
            audit(session, org_id, worker_id, "task.renew", task.id)
            return task_view(task)

    def checkpoint(self, org_id: str, worker_id: str, task_id: str, lease_token: str,
                   data: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as session:
            task = self._claim(session, org_id, worker_id, task_id, lease_token)
            item = Checkpoint(org_id=org_id, task_id=task.id, attempt=task.attempt,
                              data=data, sha256=digest(data))
            session.add(item)
            session.flush()
            audit(session, org_id, worker_id, "task.checkpoint", task.id, sha256=item.sha256)
            return {"id": item.id, "data": data, "sha256": item.sha256, "attempt": task.attempt}

    def latest_checkpoint(self, org_id: str, task_id: str) -> dict[str, Any] | None:
        with self.db.session() as session:
            tenant_row(session, Task, org_id, task_id)
            item = session.scalar(select(Checkpoint).where(Checkpoint.org_id == org_id, Checkpoint.task_id == task_id)
                                  .order_by(Checkpoint.created_at.desc(), Checkpoint.id.desc()))
            return {"id": item.id, "data": item.data, "sha256": item.sha256, "attempt": item.attempt} if item else None

    def complete(self, org_id: str, worker_id: str, task_id: str, lease_token: str,
                 result: dict[str, Any]) -> TaskView:
        if "status" in result and result["status"] != "completed":
            raise DomainError("non-completed agent results cannot satisfy task dependencies", 422)
        with self.db.transaction() as session:
            existing = tenant_row(session, Task, org_id, task_id, lock=True)
            if (existing.status == "completed" and existing.lease_worker_id == worker_id
                    and existing.lease_token and secrets.compare_digest(existing.lease_token, lease_token)):
                if digest(existing.result) != digest(result):
                    raise DomainError("completion replay result differs")
                return task_view(existing)
            task = self._claim(session, org_id, worker_id, task_id, lease_token)
            task.status, task.result, task.updated_at = "completed", result, self.clock()
            task.error_code = None
            self._finish_attempt(session, task, "completed")
            # Preserve the completed claim as a replay fence, never lease it again.
            task.lease_expires_at = None
            for artifact in result.get("artifacts", []):
                if isinstance(artifact, dict) and {"kind", "uri", "sha256"} <= artifact.keys():
                    session.add(Artifact(org_id=org_id, task_id=task.id, kind=artifact["kind"],
                                         uri=artifact["uri"], sha256=artifact["sha256"]))
            audit(session, org_id, worker_id, "task.complete", task.id, result_hash=digest(result))
            session.flush()
            self._recover(session, org_id)
            return task_view(task)

    def fail(self, org_id: str, worker_id: str, task_id: str, lease_token: str,
             error: str, retryable: bool = True) -> TaskView:
        with self.db.transaction() as session:
            task = self._claim(session, org_id, worker_id, task_id, lease_token)
            self._retry(session, task, error[:500], retryable)
            session.flush()
            self._recover(session, org_id)
            return task_view(task, include_token=False)

    def cancel(self, org_id: str, task_id: str, actor: str = "owner") -> TaskView:
        with self.db.transaction() as session:
            task = tenant_row(session, Task, org_id, task_id, lock=True)
            if task.status in {"completed", "failed"}:
                raise DomainError("terminal task cannot be cancelled")
            if task.status != "cancelled":
                self._finish_attempt(session, task, "cancelled")
                task.status, task.lease_token, task.lease_expires_at = "cancelled", None, None
                audit(session, org_id, actor, "task.cancel", task.id)
                session.flush()
                self._recover(session, org_id)
            return task_view(task, include_token=False)

    def set_kill_switch(self, org_id: str, enabled: bool, actor: str = "owner") -> None:
        with self.db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            org.kill_switch = enabled
            audit(session, org_id, actor, "policy.kill_switch", org_id, enabled=enabled)
