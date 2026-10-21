from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from siteforge.contracts import ActionExecution, ActionRequest
from siteforge.db import Budget, Database, Receipt, Site
from siteforge.policy import AGENT_TOOLS, PolicyService, decision, money
from siteforge.queue import DomainError, QueueService


@pytest.fixture
def policy_system():
    db = Database("sqlite://")
    db.create_schema()
    org = str(uuid4())
    db.provision_org(org)
    site_id = str(uuid4())
    with db.transaction() as session:
        session.add(Site(id=site_id, org_id=org, slug="fixture"))
    time = [datetime(2026, 10, 21, tzinfo=timezone.utc)]
    service = PolicyService(db, clock=lambda: time[0])
    yield db, org, site_id, service, time
    db.dispose()


def approval_request(site, key="request", amount="0", **kwargs):
    return ActionRequest(agent_type="developer", action="deploy_production", site_id=site,
                         payload={"commit_sha": "a" * 40}, amount=amount, idempotency_key=key, **kwargs)


def execution(site, key="effect", amount="0", **kwargs):
    return ActionExecution(action="deploy_production", site_id=site,
                           payload={"commit_sha": "a" * 40}, amount=amount, idempotency_key=key, **kwargs)


def approve(service, org, request):
    item = service.request_approval(org, request, "agent")
    service.decide(org, item["id"], "owner", True)
    return item["id"]


def test_all_seven_agents_default_deny_and_restricted():
    assert len(AGENT_TOOLS) == 7
    for agent, tools in AGENT_TOOLS.items():
        for tool in tools:
            assert decision(agent, tool)[0] == "allowed"
        assert decision(agent, "shell")[0] == "denied"
        assert decision(agent, "spend_money")[0] == "approval_required"
        assert decision(agent, "spend_money", kill_switch=True)[0] == "denied"


def test_exact_immutable_binding_and_one_time_use(policy_system):
    db, org, site, service, _ = policy_system
    identifier = approve(service, org, approval_request(site))
    changed = execution(site).model_copy(update={"payload": {"commit_sha": "b" * 40}})
    with pytest.raises(DomainError, match="exact action"):
        service.authorize(org, identifier, changed, "owner")
    receipt = service.authorize(org, identifier, execution(site), "owner")
    assert receipt["status"] == "reserved" and not receipt["replay"]
    assert service.authorize(org, identifier, execution(site), "owner")["replay"]
    with pytest.raises(DomainError, match="unconsumed"):
        service.authorize(org, identifier, execution(site, "effect-again"), "owner")
    with db.session() as session:
        assert len(session.scalars(select(Receipt)).all()) == 1


def test_spend_zero_default_daily_monthly_reservation_and_reconciliation(policy_system):
    db, org, site, service, _ = policy_system
    identifier = approve(service, org, approval_request(site, amount="0.100001"))
    with pytest.raises(DomainError, match="defaults to zero"):
        service.authorize(org, identifier, execution(site, amount="0.100001"), "owner")
    service.set_budget(org, "2026-10", "0.200002", "owner")
    service.set_budget(org, "2026-10-21", "0.100001", "owner")
    receipt = service.authorize(org, identifier, execution(site, amount="0.100001"), "owner")
    with db.session() as session:
        for budget in session.scalars(select(Budget)).all():
            assert budget.reserved_amount == Decimal("0.100001")
    service.reconcile(org, receipt["id"], "unknown", "provider:request-1", "owner")
    with db.session() as session:
        assert session.scalar(select(Budget)).reserved_amount == Decimal("0.100001")
    service.reconcile(org, receipt["id"], "succeeded", "provider:request-1", "owner")
    service.reconcile(org, receipt["id"], "succeeded", "provider:request-1", "owner")
    with db.session() as session:
        for budget in session.scalars(select(Budget)).all():
            assert budget.used_amount == Decimal("0.100001") and budget.reserved_amount == 0
    second = approve(service, org, approval_request(site, "second", amount="0.000001"))
    with pytest.raises(DomainError, match="ceiling exceeded"):
        service.authorize(org, second, execution(site, "second-effect", amount="0.000001"), "owner")


def test_expiration_kill_switch_and_rejection(policy_system):
    db, org, site, service, time = policy_system
    identifier = approve(service, org, approval_request(site, expires_in_seconds=60))
    QueueService(db).set_kill_switch(org, True)
    with pytest.raises(DomainError, match="kill switch"):
        service.authorize(org, identifier, execution(site), "owner")
    QueueService(db).set_kill_switch(org, False)
    time[0] += timedelta(seconds=61)
    with pytest.raises(DomainError, match="expired"):
        service.authorize(org, identifier, execution(site), "owner")


def test_atomic_budget_reservation_under_competing_actions(policy_system):
    db, org, site, service, _ = policy_system
    service.set_budget(org, "2026-10", "1", "owner")
    service.set_budget(org, "2026-10-21", "1", "owner")
    identifiers = [approve(service, org, approval_request(site, str(n), amount="0.6")) for n in range(8)]
    def attempt(item):
        try:
            return service.authorize(org, item, execution(site, item, amount="0.6"), "owner")
        except DomainError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, identifiers))
    assert sum(result is not None for result in results) == 1
    with db.session() as session:
        assert all(b.reserved_amount == Decimal("0.6") for b in session.scalars(select(Budget)).all())


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.0000001", "1000000000000", 0.1])
def test_invalid_money_is_rejected(value):
    with pytest.raises(DomainError):
        money(value)
