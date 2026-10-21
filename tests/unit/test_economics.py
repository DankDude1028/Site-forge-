from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from siteforge.db import Database, Site
from siteforge.economics import EconomicsService
from siteforge.queue import DomainError


def test_verified_revenue_adjustments_deduplication_and_no_missing_zeros():
    db = Database("sqlite://")
    db.create_schema()
    org, site = str(uuid4()), str(uuid4())
    db.provision_org(org)
    with db.transaction() as session:
        session.add(Site(id=site, org_id=org, slug="utility"))
    service = EconomicsService(db)
    assert service.summary(org, site)["verified_revenue"] is None
    common = {"provider": "fixture", "currency": "USD", "occurred_at": datetime.now(timezone.utc)}
    service.record(org, site, external_ref="estimate", amount="500", verification_status="estimated", **common)
    assert service.summary(org, site)["verified_revenue"] is None
    one = service.record(org, site, external_ref="verified", amount="0.100001", **common)
    assert service.record(org, site, external_ref="verified", amount="0.100001", **common) == one
    service.record(org, site, external_ref="adjustment", amount="-0.000001", **common)
    service.record(org, site, external_ref="cost", amount="0.03", expense=True, **common)
    result = service.summary(org, site)
    assert result["verified_revenue"] == Decimal("0.1")
    assert result["estimated_revenue"] == 500
    assert result["operating_contribution"] == Decimal("0.07")
    assert result["coverage"] == "partial"
    with pytest.raises(DomainError, match="conflicts"):
        service.record(org, site, external_ref="verified", amount="1", **common)
    db.dispose()
