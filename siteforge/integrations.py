"""Read-only provider export ingestion; no provider writes or automatic forecasts.

These contracts ingest owner-supplied, reconciled provider records. They do not
claim that an external account was connected or that an import was independently
verified by a live provider integration.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator
from sqlalchemy import select

from .contracts import StrictModel
from .db import AnalyticsSnapshot, Database, Expense, Organization, RevenueEvent, Site, audit, utcnow
from .queue import DomainError, aware, digest, tenant_row

Provider = Literal["ga4", "google_search_console", "netlify", "microsoft_clarity", "stripe",
                   "google_adsense", "affiliate_report", "lead_report", "fixture"]
Verification = Literal["verified", "estimated", "pending"]
METRIC_UNITS = {
    "pageviews": "count", "sessions": "count", "users": "count", "impressions": "count",
    "clicks": "count", "conversions": "count", "visits": "count", "errors": "count",
    "calculation_completions": "count", "uptime_seconds": "seconds", "bounce_rate": "ratio",
}
DIMENSIONS = frozenset({"channel", "device_category", "country", "site_environment"})
REVENUE_PROVIDERS = frozenset({"stripe", "google_adsense", "affiliate_report", "lead_report", "fixture"})


class Provenance(StrictModel):
    source_type: Literal["provider_export", "provider_api", "synthetic_fixture", "forecast"]
    reference: str = Field(min_length=1, max_length=200)
    retrieved_at: datetime
    evidence_sha256: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    reconciled: bool = False

    @field_validator("retrieved_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        return value


class MetricValue(StrictModel):
    value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    unit: Literal["count", "seconds", "ratio"]

    @model_validator(mode="after")
    def validate_value(self) -> MetricValue:
        if self.value is not None:
            if self.unit == "count" and self.value != self.value.to_integral_value():
                raise ValueError("counts must be whole numbers")
            if self.unit == "ratio" and self.value > 1:
                raise ValueError("ratios must be between zero and one")
        return self


class PeriodImport(StrictModel):
    site_id: UUID
    provider: Provider
    source_record_id: str = Field(min_length=1, max_length=160)
    period_start: datetime
    period_end: datetime
    verification_status: Verification
    source: Provenance

    @field_validator("period_start", "period_end")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("period timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_period_and_provenance(self) -> PeriodImport:
        if self.period_start >= self.period_end:
            raise ValueError("period_start must precede period_end")
        if self.verification_status == "verified":
            if self.source.source_type not in {"provider_export", "provider_api"}:
                raise ValueError("forecasts and fixtures cannot be verified actual observations")
            if not self.source.reconciled or self.source.evidence_sha256 is None:
                raise ValueError("verified imports require reconciled provider evidence and its hash")
            if self.source.retrieved_at < self.period_end:
                raise ValueError("verified period must end before evidence was retrieved")
        if self.source.source_type == "forecast" and self.verification_status != "estimated":
            raise ValueError("forecasts must remain estimates")
        if self.provider == "fixture" and self.source.source_type != "synthetic_fixture":
            raise ValueError("fixture provider requires synthetic provenance")
        return self


class AnalyticsImport(PeriodImport):
    metrics: dict[str, MetricValue] = Field(min_length=1, max_length=30)
    coverage: Literal["complete", "partial", "missing"]
    dimensions: dict[str, str] = Field(default_factory=dict, max_length=4)

    @model_validator(mode="after")
    def validate_metrics(self) -> AnalyticsImport:
        for name, metric in self.metrics.items():
            if name not in METRIC_UNITS or metric.unit != METRIC_UNITS[name]:
                raise ValueError("metric name or unit is outside the documented allowlist")
        if self.coverage == "complete" and any(metric.value is None for metric in self.metrics.values()):
            raise ValueError("complete coverage cannot contain missing values")
        if self.coverage == "missing" and any(metric.value is not None for metric in self.metrics.values()):
            raise ValueError("missing coverage must use null values, not fabricated zeros")
        if not set(self.dimensions) <= DIMENSIONS or any(len(value) > 80 for value in self.dimensions.values()):
            raise ValueError("dimensions must be bounded aggregate metadata; user identifiers are unsupported")
        return self


class RevenueImport(PeriodImport):
    amount: Decimal = Field(max_digits=18, decimal_places=6)
    currency: str = Field(pattern="^[A-Z]{3}$")
    occurred_at: datetime
    expense: bool = False

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_revenue(self) -> RevenueImport:
        if self.provider not in REVENUE_PROVIDERS:
            raise ValueError("provider is not an allowlisted ledger source")
        if not self.period_start <= self.occurred_at < self.period_end:
            raise ValueError("occurred_at must fall within the reported period")
        return self


def semantic_payload(record: PeriodImport) -> dict[str, Any]:
    # Different export retrieval times do not create a second observation. The
    # first attestation remains durable; changing values or verification conflicts.
    payload = record.model_dump(mode="json")
    payload["source"].pop("retrieved_at")
    payload["period_start"] = record.period_start.astimezone(timezone.utc).isoformat()
    payload["period_end"] = record.period_end.astimezone(timezone.utc).isoformat()
    if isinstance(record, AnalyticsImport):
        for name, metric in record.metrics.items():
            if metric.value is not None:
                payload["metrics"][name]["value"] = format(metric.value.normalize(), "f") if metric.value else "0"
    elif isinstance(record, RevenueImport):
        payload["amount"] = format(record.amount.normalize(), "f") if record.amount else "0"
        payload["occurred_at"] = record.occurred_at.astimezone(timezone.utc).isoformat()
    return payload


class AnalyticsIngestor:
    def __init__(self, db: Database, *, clock: Callable[[], datetime] = utcnow):
        self.db, self.clock = db, clock

    def _validate_time(self, record: PeriodImport) -> None:
        now = self.clock()
        if record.source.retrieved_at > now + timedelta(minutes=5):
            raise DomainError("provider evidence retrieval time is in the future", 422)
        if record.verification_status == "verified" and record.period_end > now:
            raise DomainError("future periods cannot be verified actual observations", 422)

    def ingest(self, org_id: str, record: AnalyticsImport, actor: str = "owner") -> dict[str, Any]:
        record = AnalyticsImport.model_validate(record.model_dump())
        self._validate_time(record)
        bound_hash = digest(semantic_payload(record))
        with self.db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            tenant_row(session, Site, org_id, str(record.site_id))
            existing = session.scalar(select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.org_id == org_id, AnalyticsSnapshot.provider == record.provider,
                AnalyticsSnapshot.source_record_id == record.source_record_id))
            if existing is not None:
                if existing.data.get("semantic_hash") != bound_hash:
                    raise DomainError("provider record conflicts with its stored semantic observation")
                return {"id": existing.id, "replay": True, "verification_status": record.verification_status}
            data = record.model_dump(mode="json")
            data.update(schema_version=1, kind="analytics", semantic_hash=bound_hash,
                        imported_at=self.clock().isoformat(),
                        verification_basis="owner-attested provider reconciliation; no live provider connection claimed")
            snapshot = AnalyticsSnapshot(org_id=org_id, site_id=str(record.site_id), provider=record.provider,
                                         source_record_id=record.source_record_id, period_start=record.period_start,
                                         period_end=record.period_end, data=data)
            session.add(snapshot)
            session.flush()
            audit(session, org_id, actor, "analytics.import", snapshot.id,
                  provider=record.provider, source_record_id=record.source_record_id,
                  verification_status=record.verification_status, semantic_hash=bound_hash)
            return {"id": snapshot.id, "replay": False, "verification_status": record.verification_status}

    def ingest_revenue(self, org_id: str, record: RevenueImport, actor: str = "owner") -> dict[str, Any]:
        record = RevenueImport.model_validate(record.model_dump())
        self._validate_time(record)
        bound_hash = digest(semantic_payload(record))
        source_key = "ledger:" + digest({"source_record_id": record.source_record_id, "expense": record.expense})
        with self.db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            tenant_row(session, Site, org_id, str(record.site_id))
            provenance = session.scalar(select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.org_id == org_id, AnalyticsSnapshot.provider == record.provider,
                AnalyticsSnapshot.source_record_id == source_key))
            if provenance is not None:
                if provenance.data.get("semantic_hash") != bound_hash:
                    raise DomainError("ledger reference conflicts with its stored semantic observation")
                return {"id": provenance.data["ledger_id"], "provenance_id": provenance.id, "replay": True}
            model: Any = Expense if record.expense else RevenueEvent
            existing = session.scalar(select(model).where(model.org_id == org_id, model.provider == record.provider,
                                                           model.external_ref == record.source_record_id))
            if existing is not None:
                # An older unprovenanced import is never silently relabeled verified.
                raise DomainError("ledger reference already exists without this provenance; reconcile explicitly")
            ledger = model(org_id=org_id, site_id=str(record.site_id), provider=record.provider,
                           external_ref=record.source_record_id, amount=record.amount, currency=record.currency,
                           verification_status=record.verification_status, occurred_at=record.occurred_at)
            session.add(ledger)
            session.flush()
            data = record.model_dump(mode="json")
            data.update(schema_version=1, kind="expense_provenance" if record.expense else "revenue_provenance",
                        semantic_hash=bound_hash, ledger_id=ledger.id, imported_at=self.clock().isoformat(),
                        verification_basis="owner-attested provider reconciliation; no live provider connection claimed")
            provenance = AnalyticsSnapshot(org_id=org_id, site_id=str(record.site_id), provider=record.provider,
                                            source_record_id=source_key, period_start=record.period_start,
                                            period_end=record.period_end, data=data)
            session.add(provenance)
            session.flush()
            audit(session, org_id, actor, "expense.import" if record.expense else "revenue.import", ledger.id,
                  provider=record.provider, source_record_id=record.source_record_id,
                  amount=str(record.amount), currency=record.currency,
                  verification_status=record.verification_status, semantic_hash=bound_hash)
            return {"id": ledger.id, "provenance_id": provenance.id, "replay": False}

    def coverage(self, org_id: str, site_id: str, provider: str) -> dict[str, Any]:
        with self.db.session() as session:
            tenant_row(session, Site, org_id, site_id)
            rows = session.scalars(select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.org_id == org_id, AnalyticsSnapshot.site_id == site_id,
                AnalyticsSnapshot.provider == provider).order_by(AnalyticsSnapshot.period_start)).all()
            records = [row for row in rows if row.data.get("kind") == "analytics"]
            observations = [row for row in records if row.data.get("verification_status") == "verified"]
            gaps = []
            previous_end: datetime | None = None
            for record in observations:
                start, end = aware(record.period_start), aware(record.period_end)
                if previous_end is not None and start > previous_end:
                    gaps.append({"start": previous_end.isoformat(), "end": start.isoformat()})
                previous_end = max(previous_end, end) if previous_end is not None else end
            return {"provider": provider, "records": len(records), "verified_observations": len(observations),
                    "estimated_records": sum(row.data.get("verification_status") == "estimated" for row in records),
                    "coverage": "missing" if not observations else "partial",
                    "gaps": gaps, "latest_period_end": previous_end.isoformat() if previous_end else None,
                    "freshness_seconds": max(0.0, (self.clock() - previous_end).total_seconds()) if previous_end else None,
                    "warnings": ["Missing periods and null measurements are unknown, not zero.",
                                 "Coverage applies only to supplied imports; provider-wide completeness is not inferred."]}
