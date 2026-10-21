from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from siteforge.db import AnalyticsSnapshot, AuditEvent, Database, RevenueEvent, Site
from siteforge.economics import EconomicsService
from siteforge.integrations import AnalyticsImport, AnalyticsIngestor, RevenueImport
from siteforge.queue import DomainError


@pytest.fixture
def imports():
    db = Database("sqlite://")
    db.create_schema()
    org, site = str(uuid4()), str(uuid4())
    db.provision_org(org)
    with db.transaction() as session:
        session.add(Site(id=site, org_id=org, slug="utility"))
    now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
    yield db, org, site, AnalyticsIngestor(db, clock=lambda: now), now
    db.dispose()


def observation(site, key="day-one", **updates):
    body = {"site_id": site, "provider": "ga4", "source_record_id": key,
            "period_start": "2026-10-19T00:00:00Z", "period_end": "2026-10-20T00:00:00Z",
            "verification_status": "verified", "coverage": "partial",
            "metrics": {"pageviews": {"value": "12", "unit": "count"}, "users": {"value": None, "unit": "count"}},
            "source": {"source_type": "provider_export", "reference": "ga4-export-2026-10-20",
                       "retrieved_at": "2026-10-20T12:00:00Z", "evidence_sha256": "a" * 64, "reconciled": True}}
    body.update(updates)
    return AnalyticsImport.model_validate(body)


def receipt(site, key="payment-one", **updates):
    body = {"site_id": site, "provider": "stripe", "source_record_id": key,
            "period_start": "2026-10-19T00:00:00Z", "period_end": "2026-10-20T00:00:00Z",
            "occurred_at": "2026-10-19T12:00:00Z", "amount": "0.100001", "currency": "USD",
            "verification_status": "verified",
            "source": {"source_type": "provider_export", "reference": "stripe-reconciled-balance-export",
                       "retrieved_at": "2026-10-20T12:00:00Z", "evidence_sha256": "b" * 64, "reconciled": True}}
    body.update(updates)
    return RevenueImport.model_validate(body)


def test_snapshot_semantic_idempotency_normalizes_decimals_and_timezones(imports):
    db, org, site, ingestor, _ = imports
    first = observation(site)
    created = ingestor.ingest(org, first)
    changed_export = first.model_dump(mode="json")
    changed_export["source"]["retrieved_at"] = "2026-10-21T11:00:00Z"
    changed_export["period_start"] = "2026-10-18T19:00:00-05:00"
    changed_export["metrics"]["pageviews"]["value"] = "12.000000"
    replay = ingestor.ingest(org, AnalyticsImport.model_validate(changed_export))
    assert replay["id"] == created["id"] and replay["replay"]
    changed_export["metrics"]["pageviews"]["value"] = "13"
    with pytest.raises(DomainError, match="conflicts"):
        ingestor.ingest(org, AnalyticsImport.model_validate(changed_export))
    with db.session() as session:
        row = session.scalar(select(AnalyticsSnapshot))
        assert row.data["metrics"]["users"]["value"] is None
        assert len(session.scalars(select(AuditEvent).where(AuditEvent.action == "analytics.import")).all()) == 1


def test_revenue_provenance_adjustments_expenses_and_estimates_remain_separate(imports):
    db, org, site, ingestor, _ = imports
    first = ingestor.ingest_revenue(org, receipt(site))
    assert ingestor.ingest_revenue(org, receipt(site))["id"] == first["id"]
    ingestor.ingest_revenue(org, receipt(site, "refund", amount="-0.000001"))
    ingestor.ingest_revenue(org, receipt(site, "cost", amount="0.03", expense=True))
    forecast = receipt(site, "forecast", amount="500", verification_status="estimated",
                       source={"source_type": "forecast", "reference": "owner scenario", "retrieved_at": "2026-10-21T00:00:00Z"})
    ingestor.ingest_revenue(org, forecast)
    totals = EconomicsService(db).summary(org, site)
    assert totals["verified_revenue"] == Decimal("0.1")
    assert totals["operating_contribution"] == Decimal("0.07")
    assert totals["estimated_revenue"] == 500
    with db.session() as session:
        assert len(session.scalars(select(RevenueEvent)).all()) == 3
        assert len(session.scalars(select(AnalyticsSnapshot)).all()) == 4


def test_competing_imports_make_one_observation_and_one_ledger_receipt(imports):
    db, org, site, ingestor, _ = imports
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ingestor.ingest_revenue(org, receipt(site)), range(8)))
    assert len({item["id"] for item in results}) == 1
    with db.session() as session:
        assert len(session.scalars(select(RevenueEvent)).all()) == 1


@pytest.mark.parametrize("updates", [
    {"period_start": "2026-10-19T00:00:00"},
    {"provider": "unreviewed-provider"},
    {"period_end": "2026-10-18T00:00:00Z"},
    {"coverage": "complete"},
    {"coverage": "missing"},
    {"metrics": {"fake_traffic": {"value": 100, "unit": "count"}}},
    {"metrics": {"bounce_rate": {"value": "1.1", "unit": "ratio"}}},
    {"metrics": {"pageviews": {"value": "1.1", "unit": "count"}}},
    {"dimensions": {"email": "person@example.invalid"}},
    {"source": {"source_type": "forecast", "reference": "projection", "retrieved_at": "2026-10-20T12:00:00Z"}},
    {"source": {"source_type": "synthetic_fixture", "reference": "fixture", "retrieved_at": "2026-10-20T12:00:00Z", "reconciled": True, "evidence_sha256": "a" * 64}},
])
def test_invalid_or_unverified_data_cannot_be_labeled_actual(imports, updates):
    _, _, site, _, _ = imports
    with pytest.raises(ValidationError):
        observation(site, **updates)


def test_missing_coverage_and_gaps_are_explicit_not_zeros(imports):
    _, org, site, ingestor, _ = imports
    assert ingestor.coverage(org, site, "ga4")["coverage"] == "missing"
    ingestor.ingest(org, observation(site))
    later = observation(site, "day-three", period_start="2026-10-21T00:00:00Z", period_end="2026-10-21T06:00:00Z",
                        source={"source_type": "provider_export", "reference": "third-day-export",
                                "retrieved_at": "2026-10-21T11:00:00Z", "reconciled": True, "evidence_sha256": "c" * 64})
    ingestor.ingest(org, later)
    coverage = ingestor.coverage(org, site, "ga4")
    assert len(coverage["gaps"]) == 1 and coverage["verified_observations"] == 2
    assert coverage["freshness_seconds"] == 6 * 3600 and coverage["coverage"] == "partial"


def test_tenancy_changed_ledger_values_and_future_evidence_are_rejected(imports):
    db, org, site, ingestor, now = imports
    other = str(uuid4())
    db.provision_org(other)
    with pytest.raises(DomainError, match="not found"):
        ingestor.ingest(other, observation(site))
    ingestor.ingest_revenue(org, receipt(site))
    with pytest.raises(DomainError, match="conflicts"):
        ingestor.ingest_revenue(org, receipt(site, amount="1"))
    future = observation(site, "future").model_dump(mode="json")
    future["source"]["retrieved_at"] = (now + timedelta(days=1)).isoformat()
    with pytest.raises(DomainError, match="future"):
        ingestor.ingest(org, AnalyticsImport.model_validate(future))
