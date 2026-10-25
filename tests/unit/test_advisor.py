import json
import struct
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from siteforge.advisor import (ADVISOR_MODEL, FALLBACK_BETA, FALLBACK_MODEL, build_request, ensure_budgets,
                               load_request, max_cost, measured_cost, request_approval, run_review,
                               save_request)
from siteforge.db import Budget, Database, Receipt, Site
from siteforge.policy import PolicyService
from siteforge.queue import DomainError, QueueService

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")


def png(width=1280, height=800):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"


def usage(input_tokens=1200, output_tokens=900, iterations=None):
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens, cache_creation_input_tokens=0,
                           cache_read_input_tokens=0, iterations=iterations)


def response(stop_reason="end_turn", text=None, used=None):
    review = {"verdict": "needs_changes", "summary": "Fix the unit label.", "findings": [], "design": {
        "distinctiveness": "generic", "generic_patterns": ["pill-shaped buttons"], "direction": "Use #1F3B2D."}}
    content = [] if stop_reason == "refusal" else [SimpleNamespace(type="text", text=text or json.dumps(review))]
    return SimpleNamespace(id="msg_fixture", model=ADVISOR_MODEL, stop_reason=stop_reason, content=content,
                           usage=used or usage())


class FakeClient:
    """Records calls; never touches the network."""

    def __init__(self, result=None, error=None, counted=1000):
        self.calls, self.options, self.counts = [], [], 0
        self.result, self.error, self.counted = result or response(), error, counted
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.messages = SimpleNamespace(count_tokens=self._count)

    def with_options(self, **options):
        self.options.append(options)
        return self

    def _count(self, **_kwargs):
        self.counts += 1
        return SimpleNamespace(input_tokens=self.counted)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def advisor_system(tmp_path):
    db = Database("sqlite://")
    db.create_schema()
    org, site = str(uuid4()), str(uuid4())
    db.provision_org(org)
    with db.transaction() as session:
        session.add(Site(id=site, org_id=org, slug="label-roll-planner"))
    policy = PolicyService(db, clock=lambda: datetime(2026, 10, 22, tzinfo=timezone.utc))
    yield db, org, site, policy, tmp_path
    db.dispose()


def proposal(policy, org, site, root, approve=True):
    document = build_request("site_review", site, "Label roll calculator for small print shops.",
                             documents=[("home.txt", "Rolls needed: 12 at 3 in core")],
                             screenshots=[("home.png", png())])
    path = save_request(document, root / "advisor")
    approval = request_approval(policy, org, document, "advisor-cli")
    if approve:
        policy.decide(org, approval["id"], "owner", True)
    return document, path, approval["id"]


def budget_totals(db, org):
    with db.transaction() as session:
        rows = session.scalars(select(Budget).where(Budget.org_id == org)).all()
        return {row.period: (row.used_amount, row.reserved_amount) for row in rows}


def test_request_binds_exact_bytes_and_worst_case_cost(advisor_system):
    _, org, site, policy, root = advisor_system
    document, path, approval_id = proposal(policy, org, site, root, approve=False)
    params = document["params"]
    assert params["model"] == ADVISOR_MODEL and params["output_config"]["effort"] == "medium"
    assert params["output_config"]["format"]["schema"]["properties"]["design"]
    assert document["fallbacks"] == [{"model": FALLBACK_MODEL}]
    assert Decimal(document["max_cost"]) == max_cost(document["input_token_bound"], 16_000)
    assert load_request(path) == document
    tampered = dict(document, nonce="changed")
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(DomainError, match="hash"):
        load_request(path)
    with pytest.raises(DomainError, match="unconsumed owner approval"):
        run_review(policy, org, approval_id, save_request(document, root / "advisor"), FakeClient(),
                   results_root=root / "advisor")


def test_worst_case_covers_full_output_on_both_models():
    # 10k input and 16k output on Opus 5.5 ($5 max input, $20 output) then Opus 4.8 ($6.25, $25).
    assert max_cost(10_000, 16_000) == Decimal("0.832500")


def test_measured_cost_prices_each_attempt_at_its_own_rates():
    attempts = [SimpleNamespace(type="message", model=ADVISOR_MODEL, input_tokens=1000, output_tokens=500,
                                cache_creation_input_tokens=0, cache_read_input_tokens=0),
                SimpleNamespace(type="fallback_message", model=FALLBACK_MODEL, input_tokens=1000,
                                output_tokens=800, cache_creation_input_tokens=0, cache_read_input_tokens=0)]
    cost, recorded = measured_cost(usage(iterations=attempts))
    assert cost == Decimal("0.039000") and [item["model"] for item in recorded] == [ADVISOR_MODEL, FALLBACK_MODEL]
    assert measured_cost(usage(1000, 500))[0] == Decimal("0.014000")


@pytest.mark.parametrize("kwargs, message", [
    ({"documents": [("notes.txt", "api_key = sk-ant-abcdefghijklmnopqrstuvwx")]}, "credential"),
    ({"screenshots": [("home.jpg", b"\xff\xd8\xff" + bytes(40))]}, "PNG"),
    ({"screenshots": [(f"{index}.png", png()) for index in range(7)]}, "at most"),
])
def test_unsafe_or_unsupported_inputs_are_refused_before_approval(kwargs, message):
    with pytest.raises(DomainError, match=message):
        build_request("site_review", uuid4(), "brief", **kwargs)


def test_no_budget_means_nothing_is_sent(advisor_system):
    _, org, site, policy, root = advisor_system
    _, path, approval_id = proposal(policy, org, site, root)
    client = FakeClient()
    with pytest.raises(DomainError, match="daily and monthly limits required"):
        run_review(policy, org, approval_id, path, client, results_root=root / "advisor")
    assert client.calls == [] and client.counts == 0


def test_kill_switch_blocks_paid_review(advisor_system):
    db, org, site, policy, root = advisor_system
    _, path, approval_id = proposal(policy, org, site, root)
    ensure_budgets(policy, org, monthly="15", daily="3")
    QueueService(db).set_kill_switch(org, True)
    client = FakeClient()
    with pytest.raises(DomainError, match="kill switch"):
        run_review(policy, org, approval_id, path, client, results_root=root / "advisor")
    assert client.calls == []


def test_successful_review_books_measured_cost_once(advisor_system):
    db, org, site, policy, root = advisor_system
    document, path, approval_id = proposal(policy, org, site, root)
    assert ensure_budgets(policy, org, monthly="15", daily="3") == ["2026-10", "2026-10-22"]
    client = FakeClient()
    result = run_review(policy, org, approval_id, path, client, results_root=root / "advisor")
    assert result["status"] == "complete" and result["review"]["verdict"] == "needs_changes"
    assert result["measured_cost"] == "0.022800"  # 1,200 x $4 + 900 x $20 per million
    assert client.options == [{"max_retries": 0}] and len(client.calls) == 1
    assert client.calls[0]["betas"] == [FALLBACK_BETA] and client.calls[0]["fallbacks"] == document["fallbacks"]
    totals = budget_totals(db, org)
    assert totals["2026-10"] == totals["2026-10-22"] == (Decimal("0.022800"), Decimal("0"))
    assert run_review(policy, org, approval_id, path, client, results_root=root / "advisor") == result
    assert len(client.calls) == 1


def test_token_count_above_bound_sends_nothing_and_releases_reservation(advisor_system):
    db, org, site, policy, root = advisor_system
    document, path, approval_id = proposal(policy, org, site, root)
    ensure_budgets(policy, org, monthly="15", daily="3")
    client = FakeClient(counted=document["input_token_bound"] + 1)
    with pytest.raises(DomainError, match="nothing was sent"):
        run_review(policy, org, approval_id, path, client, results_root=root / "advisor")
    assert client.calls == [] and budget_totals(db, org)["2026-10"] == (Decimal("0"), Decimal("0"))


def test_lost_connection_keeps_reservation_and_is_never_resent(advisor_system):
    db, org, site, policy, root = advisor_system
    document, path, approval_id = proposal(policy, org, site, root)
    ensure_budgets(policy, org, monthly="15", daily="3")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    client = FakeClient(error=anthropic.APIConnectionError(request=request))
    with pytest.raises(anthropic.APIConnectionError):
        run_review(policy, org, approval_id, path, client, results_root=root / "advisor")
    assert budget_totals(db, org)["2026-10"] == (Decimal("0"), Decimal(document["max_cost"]))
    with db.transaction() as session:
        assert session.scalar(select(Receipt.status)) == "unknown"
    with pytest.raises(DomainError, match="already have been sent"):
        run_review(policy, org, approval_id, path, client, results_root=root / "advisor")
    assert len(client.calls) == 1


def test_rejected_request_releases_reservation(advisor_system):
    db, org, site, policy, root = advisor_system
    _, path, approval_id = proposal(policy, org, site, root)
    ensure_budgets(policy, org, monthly="15", daily="3")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.BadRequestError("bad request", response=httpx2.Response(400, request=request), body=None)
    with pytest.raises(anthropic.BadRequestError):
        run_review(policy, org, approval_id, path, FakeClient(error=error), results_root=root / "advisor")
    assert budget_totals(db, org)["2026-10"] == (Decimal("0"), Decimal("0"))
    assert not list((root / "advisor").glob("*.sending"))


def test_refusal_is_recorded_and_billed_without_findings(advisor_system):
    db, org, site, policy, root = advisor_system
    _, path, approval_id = proposal(policy, org, site, root)
    ensure_budgets(policy, org, monthly="15", daily="3")
    result = run_review(policy, org, approval_id, path, FakeClient(result=response("refusal", used=usage(800, 0))),
                        results_root=root / "advisor")
    assert result["status"] == "refused" and result["review"] is None
    assert budget_totals(db, org)["2026-10"] == (Decimal("0.003200"), Decimal("0"))


def test_ensure_budgets_never_raises_an_existing_limit(advisor_system):
    db, org, _, policy, _ = advisor_system
    policy.set_budget(org, "2026-10", "10", "owner")
    assert ensure_budgets(policy, org, monthly="15", daily="3") == ["2026-10-22"]
    with db.transaction() as session:
        assert session.scalar(select(Budget.limit_amount).where(Budget.period == "2026-10")) == Decimal("10")
