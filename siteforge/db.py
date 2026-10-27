"""PostgreSQL is the production authority; SQLite is a local simulation backend."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterator
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, Uuid, create_engine, event, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class UTCDateTime(TypeDecorator[datetime]):
    """Preserve aware UTC instants across PostgreSQL and SQLite round trips.

    SQLite drops timezone offsets in its DATETIME representation. Bind UTC
    values only, then restore that known UTC timezone when reading SQLite.
    The underlying SQL type is unchanged from DateTime(timezone=True).
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Database timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            if dialect.name != "sqlite":
                raise ValueError("Database returned a timestamp without a timezone")
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class Entity:
    id: Mapped[str] = mapped_column(String(36).with_variant(Uuid(as_uuid=False), "postgresql"), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Tenant(Entity):
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Organization(Entity, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(100))
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Tenant, Base):
    __tablename__ = "users"
    subject: Mapped[str] = mapped_column(String(100), unique=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")


class Site(Tenant, Base):
    __tablename__ = "sites"
    slug: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), default="draft")
    config: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    __table_args__ = (UniqueConstraint("org_id", "slug"),)


class Worker(Tenant, Base):
    __tablename__ = "workers"
    name: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    last_heartbeat_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    status: Mapped[str] = mapped_column(String(30), default="online")
    version: Mapped[str] = mapped_column(String(40), default="0.1.0")
    __table_args__ = (UniqueConstraint("org_id", "name"),)


class Agent(Tenant, Base):
    __tablename__ = "agents"
    type: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(30), default="1")
    config: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class Workflow(Tenant, Base):
    __tablename__ = "workflows"
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"))
    type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="ready")
    policy_version: Mapped[str] = mapped_column(String(40), default="1")
    idempotency_key: Mapped[str] = mapped_column(String(160))
    __table_args__ = (UniqueConstraint("org_id", "idempotency_key"),)


class Task(Tenant, Base):
    __tablename__ = "tasks"
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflows.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"))
    agent_type: Mapped[str] = mapped_column(String(40))
    capability: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="ready")
    input: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    input_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_worker_id: Mapped[str | None] = mapped_column(ForeignKey("workers.id"))
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lease_token: Mapped[str | None] = mapped_column(String(100))
    deadline: Mapped[datetime | None] = mapped_column(UTCDateTime())
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    budget_cap: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    error_code: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key"),
        CheckConstraint("attempt >= 0 AND max_attempts BETWEEN 1 AND 3"),
        CheckConstraint("budget_cap >= 0 AND actual_cost >= 0"),
        CheckConstraint("status IN ('pending','ready','leased','running','completed','blocked','waiting_approval','retry_scheduled','failed','cancelled')"),
        Index("ix_tasks_status_created", "status", "created_at"),
        Index("ix_tasks_lease_expiry", "lease_expires_at"),
    )


class Dependency(Base):
    __tablename__ = "dependencies"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    __table_args__ = (CheckConstraint("task_id <> depends_on_id"),)


class Attempt(Tenant, Base):
    __tablename__ = "attempts"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"))
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="leased")
    error: Mapped[str | None] = mapped_column(String(500))
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    __table_args__ = (UniqueConstraint("task_id", "number"),)


class Lease(Tenant, Base):
    __tablename__ = "leases"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    released_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Checkpoint(Tenant, Base):
    __tablename__ = "checkpoints"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    sha256: Mapped[str] = mapped_column(String(64))


class Artifact(Tenant, Base):
    __tablename__ = "artifacts"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    uri: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))


class Approval(Tenant, Base):
    __tablename__ = "approvals"
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    agent_type: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    payload_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    requester: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    approved_by: Mapped[str | None] = mapped_column(String(100))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reason: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key"),
        CheckConstraint("amount >= 0"),
        Index("ix_approvals_status_expiry", "status", "expires_at"),
    )


class Budget(Tenant, Base):
    __tablename__ = "budgets"
    period: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    used_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    reserved_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    __table_args__ = (
        UniqueConstraint("org_id", "period", "currency"),
        CheckConstraint("limit_amount >= 0 AND used_amount >= 0 AND reserved_amount >= 0 AND used_amount + reserved_amount <= limit_amount"),
    )


class Receipt(Tenant, Base):
    __tablename__ = "irreversible_receipts"
    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(80))
    payload_hash: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(40), default="reserved")
    budget_periods: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("org_id", "idempotency_key"),)


class AuditEvent(Tenant, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(40), default="allowed")
    detail: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    __table_args__ = (Index("ix_audit_created", "created_at"),)


class PolicyDecision(Tenant, Base):
    __tablename__ = "policy_decisions"
    action: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(500))
    context: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class RevenueEvent(Tenant, Base):
    __tablename__ = "revenue_events"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    provider: Mapped[str] = mapped_column(String(80))
    external_ref: Mapped[str] = mapped_column(String(160))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    verification_status: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    __table_args__ = (UniqueConstraint("org_id", "provider", "external_ref"),)


class Expense(Tenant, Base):
    __tablename__ = "expenses"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    provider: Mapped[str] = mapped_column(String(80))
    external_ref: Mapped[str] = mapped_column(String(160))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    verification_status: Mapped[str] = mapped_column(String(30), default="verified")
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    __table_args__ = (UniqueConstraint("org_id", "provider", "external_ref"),)


# Catalog records deliberately keep provider-specific data in JSON, never credentials.
class Opportunity(Tenant, Base):
    __tablename__ = "opportunities"
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    data: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class Evidence(Tenant, Base):
    __tablename__ = "evidence"
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("opportunities.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"))
    url: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime())
    sha256: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class Capability(Tenant, Base):
    __tablename__ = "capabilities"
    name: Mapped[str] = mapped_column(String(80))
    config: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    __table_args__ = (UniqueConstraint("org_id", "name"),)


class Model(Tenant, Base):
    __tablename__ = "models"
    model_id: Mapped[str] = mapped_column(String(200))
    config: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class BenchmarkRun(Tenant, Base):
    __tablename__ = "benchmark_runs"
    model_id: Mapped[str | None] = mapped_column(ForeignKey("models.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    config: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class BenchmarkResult(Tenant, Base):
    __tablename__ = "benchmark_results"
    run_id: Mapped[str] = mapped_column(ForeignKey("benchmark_runs.id"))
    task_key: Mapped[str] = mapped_column(String(100))
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)


class Deployment(Tenant, Base):
    __tablename__ = "deployments"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approvals.id"))
    environment: Mapped[str] = mapped_column(String(30), default="preview")
    commit_sha: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    data: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class AnalyticsSnapshot(Tenant, Base):
    __tablename__ = "analytics_snapshots"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    provider: Mapped[str] = mapped_column(String(80))
    source_record_id: Mapped[str] = mapped_column(String(160))
    period_start: Mapped[datetime] = mapped_column(UTCDateTime())
    period_end: Mapped[datetime] = mapped_column(UTCDateTime())
    data: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    __table_args__ = (UniqueConstraint("org_id", "provider", "source_record_id"),)


class Experiment(Tenant, Base):
    __tablename__ = "experiments"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    hypothesis: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    data: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class Notification(Tenant, Base):
    __tablename__ = "notifications"
    kind: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    data: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


def audit(session: Session, org_id: str, actor: str, action: str, target: str,
          outcome: str = "allowed", **detail: Any) -> None:
    session.add(AuditEvent(org_id=org_id, actor_id=actor, action=action,
                           target_id=target, outcome=outcome, detail=detail))


# DDL is also used by Alembic; immutability does not depend on application hooks.
SQLITE_AUDIT_DDL = [
    "CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'immutable audit event'); END",
    "CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'immutable audit event'); END",
    "CREATE TRIGGER IF NOT EXISTS approval_binding_immutable BEFORE UPDATE OF org_id, task_id, site_id, agent_type, action, payload, payload_hash, request_hash, amount, currency, requester, expires_at, idempotency_key ON approvals BEGIN SELECT RAISE(ABORT, 'immutable approval binding'); END",
    "CREATE TRIGGER IF NOT EXISTS approval_operator_immutable BEFORE UPDATE OF approved_by, decided_at ON approvals WHEN OLD.approved_by IS NOT NULL BEGIN SELECT RAISE(ABORT, 'immutable approval operator'); END",
]
POSTGRES_AUDIT_DDL = [
    "CREATE OR REPLACE FUNCTION siteforge_reject_audit_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable audit event'; END; $$",
    "CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION siteforge_reject_audit_change()",
    "CREATE OR REPLACE FUNCTION siteforge_reject_approval_binding_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF ROW(NEW.org_id, NEW.task_id, NEW.site_id, NEW.agent_type, NEW.action, NEW.payload::text, NEW.payload_hash, NEW.request_hash, NEW.amount, NEW.currency, NEW.requester, NEW.expires_at, NEW.idempotency_key) IS DISTINCT FROM ROW(OLD.org_id, OLD.task_id, OLD.site_id, OLD.agent_type, OLD.action, OLD.payload::text, OLD.payload_hash, OLD.request_hash, OLD.amount, OLD.currency, OLD.requester, OLD.expires_at, OLD.idempotency_key) THEN RAISE EXCEPTION 'immutable approval binding'; END IF; IF OLD.approved_by IS NOT NULL AND ROW(NEW.approved_by, NEW.decided_at) IS DISTINCT FROM ROW(OLD.approved_by, OLD.decided_at) THEN RAISE EXCEPTION 'immutable approval operator'; END IF; RETURN NEW; END; $$",
    "CREATE TRIGGER approval_binding_immutable BEFORE UPDATE ON approvals FOR EACH ROW EXECUTE FUNCTION siteforge_reject_approval_binding_change()",
]


def install_audit_guards(connection: Any) -> None:
    statements = SQLITE_AUDIT_DDL if connection.dialect.name == "sqlite" else POSTGRES_AUDIT_DDL
    for statement in statements:
        connection.execute(text(statement))


class Database:
    def __init__(self, url: str, *, echo: bool = False):
        options: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in url or url == "sqlite://":
                options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)
        self._lock = threading.RLock()
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def sqlite_foreign_keys(connection: Any, _record: Any) -> None:
                connection.execute("PRAGMA foreign_keys=ON")

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            if self.engine.dialect.name == "postgresql":
                connection.execute(text("DROP TRIGGER IF EXISTS audit_no_mutation ON audit_events"))
                connection.execute(text("DROP TRIGGER IF EXISTS approval_binding_immutable ON approvals"))
            install_audit_guards(connection)

    def provision_org(self, org_id: str, name: str = "SiteForge pilot") -> None:
        with self.transaction() as session:
            if session.get(Organization, org_id) is None:
                session.add(Organization(id=org_id, name=name))

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        # BEGIN IMMEDIATE serializes SQLite writers across processes. PostgreSQL
        # uses row locks, including SKIP LOCKED for competing worker claims.
        with self._lock if self.engine.dialect.name == "sqlite" else _NullLock():
            with self._sessions() as session:
                try:
                    if self.engine.dialect.name == "sqlite":
                        session.execute(text("BEGIN IMMEDIATE"))
                    yield session
                    session.commit()
                except BaseException:
                    session.rollback()
                    raise

    def dispose(self) -> None:
        self.engine.dispose()


class _NullLock:
    def __enter__(self) -> None:
        pass

    def __exit__(self, *_args: Any) -> None:
        pass
