"""Real orchestration and persistence with explicitly mocked Netlify transports."""
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from siteforge.contracts import ActionExecution, ActionRequest
from siteforge.db import Approval, Budget, Database, Deployment, Receipt, Site
from siteforge.policy import PolicyService
from siteforge.providers import NetlifyReleaseAdapter, ProviderError
from siteforge.queue import DomainError, QueueService
from siteforge.release import ReleaseConfig, ReleaseService


class FakeNetlify:
    def __init__(self, provider_site, content):
        self.site, self.content = provider_site, content
        self.published = "previousdeploy"
        self.deploys = {self.published: self.deploy(self.published, "previous", draft=False)}
        self.calls = []
        self.drop_create = False
        self.lose_create_response = False
        self.lose_upload_response = False
        self.lose_promotion_response = False
        self.drop_promotion = False
        self.protected = True
        self.public_healthy = True
        self.crash_after_upload = False

    def deploy(self, identifier, title, draft=True):
        return {"id": identifier, "site_id": self.site, "state": "ready", "title": title,
                "commit_ref": None, "deploy_ssl_url": f"https://{identifier}--fixture.netlify.app",
                "published_at": None if draft else "2026-10-21T00:00:00Z", "draft": draft, "required": []}

    def api(self, request):
        self.calls.append((request.method, request.url.path))
        assert request.url.host == "api.netlify.com"
        assert request.headers["authorization"] == "Bearer fixture-provider-token"
        suffix = request.url.path.removeprefix(f"/api/v1/sites/{self.site}")
        if request.method == "GET" and suffix == "":
            return httpx.Response(200, json={"id": self.site, "name": "fixture", "ssl_url": "https://fixture.netlify.app",
                                           "password": "fixture-private-provider-field-never-returned"})
        if request.method == "GET" and suffix == "/deploys":
            values = [self.deploys[self.published]] if request.url.params.get("latest-published") else list(self.deploys.values())
            return httpx.Response(200, json=values)
        if request.method == "POST" and suffix == "/deploys":
            if self.drop_create:
                raise httpx.ReadTimeout("fixture unknown creation", request=request)
            identifier = "draft" + str(len(self.deploys))
            value = self.deploy(identifier, request.url.params["title"])
            body = json.loads(request.content)
            assert body["draft"] is True and set(body) == {"draft", "files"}
            value["required"] = list(body["files"].values())
            value["state"] = "uploading"
            self.deploys[identifier] = value
            if self.lose_create_response:
                raise httpx.ReadTimeout("fixture lost response after creation", request=request)
            return httpx.Response(201, json=value)
        if request.method == "GET" and suffix.startswith("/deploys/"):
            value = self.deploys.get(suffix.split("/")[-1])
            return httpx.Response(200 if value else 404, json=value or {})
        if request.method == "PUT" and request.url.path.startswith("/api/v1/deploys/"):
            identifier = request.url.path.split("/")[4]
            assert request.content == self.content
            self.deploys[identifier].update(required=[], state="ready")
            if self.crash_after_upload:
                raise SystemExit("fixture process death after provider upload")
            if self.lose_upload_response:
                raise httpx.ReadTimeout("fixture lost upload acknowledgment", request=request)
            return httpx.Response(204)
        if request.method == "POST" and suffix.endswith("/restore"):
            identifier = suffix.split("/")[-2]
            if self.drop_promotion:
                raise httpx.ReadTimeout("fixture unknown publication", request=request)
            self.published = identifier
            self.deploys[identifier].update(draft=False, published_at="2026-10-21T19:00:00Z")
            if self.lose_promotion_response:
                raise httpx.ReadTimeout("fixture lost publication acknowledgment", request=request)
            return httpx.Response(201, json=self.deploys[identifier])
        raise AssertionError((request.method, request.url.path))

    def health(self, request):
        assert request.headers.get("authorization") != "Bearer fixture-provider-token"
        assert request.headers.get("authorization") in {None, "Basic Zml4dHVyZTpwYXNz"}
        assert "cookie" not in request.headers
        if request.url.host == "fixture.netlify.app":
            return httpx.Response(200 if self.public_healthy else 500, content=self.content)
        assert request.url.host.endswith("--fixture.netlify.app")
        if request.headers.get("authorization") == "Basic Zml4dHVyZTpwYXNz":
            return httpx.Response(200, content=self.content)
        return httpx.Response(401 if self.protected else 200, content=b"private" if self.protected else self.content)

    def mutations(self, verb=None):
        return [call for call in self.calls if call[0] in {"POST", "PUT"} and (verb is None or call[0] == verb)]


@pytest.fixture
def release_system(tmp_path, monkeypatch):
    monkeypatch.setenv("NETLIFY_AUTH_TOKEN", "fixture-provider-token")
    db = Database("sqlite:///" + (tmp_path / "release.db").as_posix())
    db.create_schema()
    org, site, provider_site = (str(uuid4()) for _ in range(3))
    db.provision_org(org)
    with db.transaction() as session:
        session.add(Site(id=site, org_id=org, slug="fixture"))
    output = tmp_path / "dist"
    output.mkdir()
    content = b'<html><meta name="robots" content="noindex, nofollow"><h1>Useful fixture</h1></html>'
    (output / "index.html").write_bytes(content)
    fake = FakeNetlify(provider_site, content)
    config = ReleaseConfig(enabled=True, production_enabled=True, allowed_sites={site: provider_site},
        preview_root=tmp_path, protected_sites=frozenset({provider_site}), known_cost_usd=Decimal("0"),
        production_origins={provider_site: "https://fixture.netlify.app"}, exclusive_publisher_verified=True,
        preview_authorization="Basic Zml4dHVyZTpwYXNz", resume_uploads_enabled=True, resume_cost_usd=Decimal("0"))
    adapter = NetlifyReleaseAdapter(provider_site, tmp_path, operator_authorized=True, cost_authorized=True,
        protected_preview_verified=True, production_enabled=True, production_origin="https://fixture.netlify.app",
        exclusive_publisher_verified=True, preview_authorization=config.preview_authorization,
        client=httpx.Client(transport=httpx.MockTransport(fake.api)),
        health_client=httpx.Client(transport=httpx.MockTransport(fake.health), auth=("fixture-default-user", "fixture-secret"),
                                  headers={"Cookie": "fixture-default-stripped"}))
    policy = PolicyService(db)
    service = ReleaseService(db, adapter, config, policy=policy)
    yield db, org, site, service, fake
    service.close()
    db.dispose()


def approved(service, org, plan, key="preview"):
    request = ActionRequest(agent_type="developer", **plan, idempotency_key="approval-" + key)
    approval = service.policy.request_approval(org, request, "requester")
    service.policy.decide(org, approval["id"], "owner", True)
    return approval["id"], ActionExecution(**plan, idempotency_key="effect-" + key)


def preview(service, org, site, key="preview"):
    plan = service.plan_preview(site, "a" * 40, "dist")
    approval, execution = approved(service, org, plan, key)
    return service.execute_preview(org, approval, execution, "owner"), approval, execution


def test_default_disabled_and_blank_cost_do_not_read_credentials(release_system, monkeypatch):
    db, _, site, _, fake = release_system
    monkeypatch.delenv("SITEFORGE_RELEASE_ENABLED", raising=False)
    monkeypatch.setenv("SITEFORGE_RELEASE_KNOWN_COST_USD", "")
    assert ReleaseConfig.from_environment().known_cost_usd is None
    with pytest.raises(ProviderError, match="disabled"):
        ReleaseService.from_environment(db, site)
    assert fake.calls == []


def test_ready_preview_is_durable_exact_and_replay_never_creates(release_system):
    db, org, site, service, fake = release_system
    result, approval, execution = preview(service, org, site)
    assert result["status"] == "ready" and fake.published == "previousdeploy"
    assert result["data"]["health"]["protection_observed"]
    assert len(fake.mutations("POST")) == len(fake.mutations("PUT")) == 1
    restarted = ReleaseService(db, service.adapter, service.config)
    assert restarted.execute_preview(org, approval, execution, "owner")["id"] == result["id"]
    assert len(fake.mutations("POST")) == 1
    with db.session() as session:
        assert session.scalar(select(Receipt)).status == "succeeded"
        assert session.scalar(select(Approval)).status == "consumed"
        assert len(session.scalars(select(Deployment)).all()) == 1
    public = json.dumps(result)
    assert "fixture-provider-token" not in public and "Zml4dHVyZTpwYXNz" not in public
    assert "fixture-private-provider-field" not in public


def test_unknown_create_never_reposts_after_restart(release_system):
    db, org, site, service, fake = release_system
    fake.drop_create = True
    result, approval, execution = preview(service, org, site)
    assert result["status"] == "unknown" and len(fake.mutations("POST")) == 1
    restarted = ReleaseService(db, service.adapter, service.config)
    assert restarted.execute_preview(org, approval, execution, "owner")["status"] == "unknown"
    assert len(fake.mutations("POST")) == 1
    with db.session() as session:
        assert session.scalar(select(Receipt)).status == "unknown"


@pytest.mark.parametrize("fault", ["lose_create_response", "lose_upload_response"])
def test_lost_acknowledgment_reconciles_actual_effect_without_reupload(release_system, fault):
    _, org, site, service, fake = release_system
    setattr(fake, fault, True)
    result, approval, execution = preview(service, org, site)
    if fault == "lose_create_response":
        assert result["status"] == "processing"  # Existing draft still lacks its bytes.
        assert not fake.mutations("PUT")
    else:
        assert result["status"] == "ready"
    before = len(fake.mutations())
    service.execute_preview(org, approval, execution, "owner")
    assert len(fake.mutations()) == before


def test_concurrent_replay_has_one_intent_and_at_most_one_dispatch(release_system):
    db, org, site, service, fake = release_system
    approval, execution = approved(service, org, service.plan_preview(site, "a" * 40, "dist"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda _: service.execute_preview(org, approval, execution, "owner"), range(6)))
    assert len({row["id"] for row in rows}) == 1 and len(fake.mutations("POST")) == 1
    assert service.reconcile(org, rows[0]["id"], "owner")["status"] == "ready"
    with db.session() as session:
        assert len(session.scalars(select(Receipt)).all()) == len(session.scalars(select(Deployment)).all()) == 1


def test_wrong_operator_tenant_payload_cost_and_kill_never_dispatch(release_system):
    db, org, site, service, fake = release_system
    approval, execution = approved(service, org, service.plan_preview(site, "a" * 40, "dist"))
    for actor, request in [("other-owner", execution), ("owner", execution.model_copy(update={"amount": Decimal("1")})),
                           ("owner", execution.model_copy(update={"payload": {**execution.payload, "tree_sha256": "b" * 64}}))]:
        with pytest.raises(DomainError):
            service.execute_preview(org, approval, request, actor)
    with pytest.raises(DomainError):
        service.execute_preview(str(uuid4()), approval, execution, "owner")
    QueueService(db).set_kill_switch(org, True)
    with pytest.raises(DomainError, match="kill switch"):
        service.execute_preview(org, approval, execution, "owner")
    assert fake.mutations() == []


def test_artifact_change_after_authorization_cannot_upload_new_bytes(release_system, monkeypatch):
    db, org, site, service, fake = release_system
    approval, execution = approved(service, org, service.plan_preview(site, "a" * 40, "dist"))
    original = service.policy.authorize
    def authorize(*args, **kwargs):
        receipt = original(*args, **kwargs)
        (service.adapter.root / "dist/index.html").write_bytes(fake.content + b"changed")
        return receipt
    monkeypatch.setattr(service.policy, "authorize", authorize)
    result = service.execute_preview(org, approval, execution, "owner")
    assert result["status"] == "failed" and fake.mutations() == []
    with db.session() as session:
        assert session.scalar(select(Receipt)).status == "failed"


def test_cost_unknown_cap_and_unprotected_site_fail_closed(release_system):
    _, _, site, service, fake = release_system
    for config in [replace(service.config, known_cost_usd=None),
                   replace(service.config, known_cost_usd=Decimal("1")),
                   replace(service.config, protected_sites=frozenset())]:
        candidate = ReleaseService(service.db, service.adapter, config)
        with pytest.raises(DomainError):
            candidate.plan_preview(site, "a" * 40, "dist")
    assert fake.mutations() == []


def test_anonymous_preview_content_cannot_be_ready(release_system):
    _, org, site, service, fake = release_system
    fake.protected = False
    result, _, _ = preview(service, org, site)
    assert result["status"] == "health_failed" and "health" not in result["data"]
    with pytest.raises(DomainError, match="ready preview"):
        service.plan_promotion(org, result["id"])


def test_exact_ready_preview_promotion_and_health_replay(release_system):
    _, org, site, service, fake = release_system
    ready, _, _ = preview(service, org, site)
    plan = service.plan_promotion(org, ready["id"])
    assert plan["payload"]["previous_published_id"] == "previousdeploy"
    approval, execution = approved(service, org, plan, "production")
    fake.lose_promotion_response = True
    result = service.execute_promotion(org, approval, execution, "owner")
    assert result["status"] == "healthy" and fake.published == ready["data"]["provider_deploy_id"]
    assert service.get(org, ready["id"])["status"] == "promoted"
    before = len(fake.mutations())
    assert service.execute_promotion(org, approval, execution, "owner")["status"] == "healthy"
    assert len(fake.mutations()) == before
    assert not hasattr(service, "rollback")


def test_previous_publication_change_and_older_deploy_rejected(release_system):
    _, org, site, service, fake = release_system
    ready, _, _ = preview(service, org, site)
    approval, execution = approved(service, org, service.plan_promotion(org, ready["id"]), "production")
    count = len(fake.mutations())
    fake.deploys["unexpected"] = fake.deploy("unexpected", "other", draft=False)
    fake.published = "unexpected"
    with pytest.raises(DomainError, match="binding differs"):
        service.execute_promotion(org, approval, execution, "owner")
    fake.published = "previousdeploy"
    fake.deploys[ready["data"]["provider_deploy_id"]]["published_at"] = "2026-10-20T00:00:00Z"
    with pytest.raises(DomainError, match="older"):
        service.execute_promotion(org, approval, execution, "owner")
    assert len(fake.mutations()) == count


def test_unknown_promotion_does_not_restore_again(release_system):
    _, org, site, service, fake = release_system
    ready, _, _ = preview(service, org, site)
    approval, execution = approved(service, org, service.plan_promotion(org, ready["id"]), "production")
    fake.drop_promotion = True
    result = service.execute_promotion(org, approval, execution, "owner")
    assert result["status"] == "unknown"
    before = len(fake.mutations())
    assert service.execute_promotion(org, approval, execution, "owner")["status"] == "unknown"
    assert len(fake.mutations()) == before


def test_conflicting_terminal_receipt_cannot_be_relabelled_healthy(release_system):
    db, org, site, service, fake = release_system
    fake.drop_create = True
    result, _, _ = preview(service, org, site)
    service.policy.reconcile(org, result["data"]["receipt_id"], "failed", "operator:conflicting", "owner")
    value = fake.deploy("lateprovider", result["data"]["correlation_id"])
    fake.deploys[value["id"]] = value
    with pytest.raises(DomainError, match="Final receipt conflicts"):
        service.reconcile(org, result["id"], "owner")
    assert service.get(org, result["id"])["status"] != "ready"
    with db.session() as session:
        assert session.scalar(select(Receipt)).status == "failed"


def test_positive_known_cost_reservation_survives_unknown(release_system):
    db, org, site, service, fake = release_system
    service.config = replace(service.config, known_cost_usd=Decimal("0.1"), max_cost_usd=Decimal("0.1"))
    for period in [service.policy.clock().strftime("%Y-%m"), service.policy.clock().strftime("%Y-%m-%d")]:
        service.policy.set_budget(org, period, "1", "owner")
    fake.drop_create = True
    result, _, _ = preview(service, org, site)
    assert result["status"] == "unknown"
    with db.session() as session:
        assert all(row.reserved_amount == Decimal("0.1") and row.used_amount == 0 for row in session.scalars(select(Budget)))


def test_restart_after_real_dispatch_crash_reuses_durable_identity(release_system):
    db, org, site, service, fake = release_system
    approval, execution = approved(service, org, service.plan_preview(site, "a" * 40, "dist"))
    fake.crash_after_upload = True
    with pytest.raises(SystemExit):
        service.execute_preview(org, approval, execution, "owner")
    with db.session() as session:
        assert session.scalar(select(Deployment)).data["provider_deploy_id"] == "draft1"
    fake.crash_after_upload = False
    restarted = ReleaseService(db, service.adapter, service.config)
    count = len(fake.mutations())
    assert restarted.execute_preview(org, approval, execution, "owner")["status"] == "ready"
    assert len(fake.mutations()) == count


def test_authorization_crash_before_claim_never_automatically_dispatches(release_system):
    _, org, site, service, fake = release_system
    approval, execution = approved(service, org, service.plan_preview(site, "a" * 40, "dist"))
    service.policy.authorize(org, approval, execution, "owner")
    result = service.execute_preview(org, approval, execution, "owner")
    assert result["status"] == "pending_dispatch" and not result["data"]["dispatch_claimed"]
    assert fake.mutations() == []


def test_missing_upload_explicitly_resumes_bound_put_without_repeat_create(release_system):
    _, org, site, service, fake = release_system
    fake.lose_create_response = True
    partial, _, _ = preview(service, org, site)
    assert partial["status"] == "processing" and not fake.mutations("PUT")
    count = len(fake.mutations("POST"))
    ready = service.resume_preview(org, partial["id"], "owner")
    assert ready["status"] == "ready" and len(fake.mutations("POST")) == count
    assert len(fake.mutations("PUT")) == 1
    assert len(ready["data"]["upload_resume_attempts"]) == 1
    assert ready["data"]["upload_resume_claim"] is None


@pytest.mark.parametrize("reason", ["wrong_operator", "kill", "expired", "changed_bytes", "unknown_resume_cost"])
def test_resume_preconditions_fail_without_put(release_system, reason):
    db, org, site, service, fake = release_system
    fake.lose_create_response = True
    partial, _, _ = preview(service, org, site)
    actor = "owner"
    if reason == "wrong_operator":
        actor = "other"
    elif reason == "kill":
        QueueService(db).set_kill_switch(org, True)
    elif reason == "expired":
        now = service.policy.clock()
        service.policy.clock = lambda: now + timedelta(days=2)
    elif reason == "changed_bytes":
        (service.adapter.root / "dist/index.html").write_bytes(fake.content + b"changed")
    else:
        service.config = replace(service.config, resume_cost_usd=None)
    with pytest.raises(DomainError):
        service.resume_preview(org, partial["id"], actor)
    assert not fake.mutations("PUT") and len(fake.mutations("POST")) == 1


def test_resume_attempts_are_durably_bounded_after_unknown_puts(release_system, monkeypatch):
    _, org, site, service, fake = release_system
    fake.lose_create_response = True
    partial, _, _ = preview(service, org, site)
    def lost_upload(*args, **kwargs):
        from siteforge.providers import ProviderOutcomeUnknown
        raise ProviderOutcomeUnknown("fixture uncertain idempotent upload")
    monkeypatch.setattr(service.adapter, "resume_draft_upload", lost_upload)
    for _ in range(2):
        assert service.resume_preview(org, partial["id"], "owner")["status"] == "processing"
    with pytest.raises(DomainError, match="attempts exhausted"):
        service.resume_preview(org, partial["id"], "owner")
    assert len(fake.mutations("POST")) == 1


@pytest.mark.parametrize("scope", ["foreign", "published"])
def test_adapter_independently_refuses_foreign_or_published_resume(release_system, scope):
    _, _, _, service, fake = release_system
    plan = service.adapter.plan("dist")
    value = fake.deploy("unsafe", "not-our-release", draft=scope != "published")
    if scope == "foreign":
        value["site_id"] = str(uuid4())
    value["required"] = [plan.files[0][1]]
    fake.deploys["unsafe"] = value
    with pytest.raises(ProviderError):
        service.adapter.resume_draft_upload(plan, "unsafe", value["required"], before_upload=lambda: None)
    assert not fake.mutations()
