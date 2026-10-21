"""Versioned contracts shared by the supervisor and outbound worker."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JobState(StrEnum):
    pending = "pending"
    ready = "ready"
    leased = "leased"
    running = "running"
    completed = "completed"
    blocked = "blocked"
    waiting_approval = "waiting_approval"
    retry_scheduled = "retry_scheduled"
    failed = "failed"
    cancelled = "cancelled"


class AgentType(StrEnum):
    portfolio_director = "portfolio_director"
    research = "research"
    developer = "developer"
    content = "content"
    quality = "quality"
    growth = "growth"
    revenue = "revenue"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class TaskCreate(StrictModel):
    agent_type: AgentType
    capability: str = Field(min_length=1, max_length=80)
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=160)
    site_id: UUID | None = None
    workflow_id: UUID | None = None
    dependencies: list[UUID] = Field(default_factory=list, max_length=50)
    max_attempts: int = Field(default=3, ge=1, le=3)
    deadline: datetime | None = None
    budget_cap: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)

    @field_validator("deadline")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("deadline must include a timezone")
        return value


class TaskView(StrictModel):
    id: str
    org_id: str
    agent_type: str
    capability: str
    input: dict[str, Any]
    status: JobState
    idempotency_key: str
    site_id: str | None
    workflow_id: str | None
    attempt: int
    max_attempts: int
    deadline: datetime | None
    available_at: datetime
    lease_worker_id: str | None
    lease_expires_at: datetime | None
    lease_token: str | None = None
    budget_cap: Decimal
    result: dict[str, Any] | None
    error_code: str | None


class WorkerRegister(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    capabilities: list[str] = Field(min_length=1, max_length=30)
    version: str = Field(default="0.1.0", max_length=40)


class LeaseRequest(StrictModel):
    worker_id: UUID
    seconds: int = Field(default=120, ge=15, le=600)


class TaskClaim(StrictModel):
    worker_id: UUID
    lease_token: str = Field(min_length=20, max_length=100)


class CheckpointRequest(TaskClaim):
    data: dict[str, Any]


class CompleteRequest(TaskClaim):
    result: dict[str, Any]


class FailureRequest(TaskClaim):
    error: str = Field(min_length=1, max_length=500)
    retryable: bool = True


class RenewRequest(TaskClaim):
    seconds: int = Field(default=120, ge=15, le=600)


class Principal(StrictModel):
    subject: str = Field(min_length=1, max_length=100)
    org_id: str
    role: Literal["owner", "worker", "observer", "release"]
    worker_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    site_ids: list[UUID] = Field(default_factory=list, max_length=100)
    expires_at: datetime | None = None


class ActionRequest(StrictModel):
    agent_type: AgentType
    action: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any]
    site_id: UUID
    task_id: UUID | None = None
    amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    idempotency_key: str = Field(min_length=1, max_length=160)
    expires_in_seconds: int = Field(default=3600, ge=60, le=86400)


class ActionExecution(StrictModel):
    action: str
    payload: dict[str, Any]
    site_id: UUID
    amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    idempotency_key: str = Field(min_length=1, max_length=160)


class AgentContext(StrictModel):
    task_id: UUID
    site_id: UUID | None = None
    allowed_tools: list[str]
    budget_remaining: Decimal = Field(ge=0)
    deadline: datetime
    policy_version: str = "1"
    source_requirements: list[str] = Field(default_factory=list)


AgentErrorCode = Literal["none", "local_model_unavailable", "inference_busy", "model_not_ready",
                         "model_identity_changed", "invalid_model_response", "policy_blocked",
                         "deadline_exceeded", "execution_limit", "context_limit", "tool_execution_failed"]
RETRYABLE_AGENT_ERRORS = frozenset({"local_model_unavailable", "inference_busy", "model_not_ready"})


class AgentResult(StrictModel):
    status: Literal["completed", "blocked", "failed"]
    retryable: bool = Field(default=False, strict=True)
    error_code: AgentErrorCode = "none"
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    costs: Decimal = Field(default=Decimal("0"), ge=0)
    confidence: float = Field(ge=0, le=1)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def retry_requires_transient_failure(self) -> AgentResult:
        if self.retryable and (self.status == "completed" or self.error_code not in RETRYABLE_AGENT_ERRORS):
            raise ValueError("Only typed transient agent failures can be retried")
        return self
