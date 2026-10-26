import json
from uuid import uuid4

import httpx
import pytest

from siteforge.providers import GitHubAdapter, NetlifyPreviewAdapter, ProviderError, ProviderOutcomeUnknown


def test_provider_repository_allowlist_and_default_write_gate(monkeypatch):
    with pytest.raises(ValueError):
        GitHubAdapter("other/repo", frozenset({"owner/site"}))
    with pytest.raises(ValueError):
        GitHubAdapter("https://evil.example/owner/site", frozenset())
    adapter = GitHubAdapter("owner/site", frozenset({"owner/site"}))
    with pytest.raises(ProviderError, match="disabled"):
        adapter.open_draft_pr(title="Draft", body="Review", head="feature", base="main",
                              head_sha="a" * 40, idempotency_key="fixture")
    adapter.close()


def test_github_reads_and_idempotent_draft_use_fixed_repo_and_scoped_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-only-token")
    pulls = []
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer fixture-only-token"
        assert request.headers["x-github-api-version"] == "2026-03-10"
        if request.url.path.endswith("/branches/feature"):
            return httpx.Response(200, json={"name": "feature", "commit": {"sha": "a" * 40}})
        if request.url.path.endswith("/pulls"):
            if request.method == "GET":
                return httpx.Response(200, json=pulls)
            value = json.loads(request.content)
            assert value["draft"] and value["maintainer_can_modify"] is False
            pulls.append({"number": 7, "html_url": "https://github.com/owner/site/pull/7",
                          "draft": True, "body": value["body"]})
            return httpx.Response(201, json=pulls[-1])
        return httpx.Response(200, json={"full_name": "owner/site", "private": True, "default_branch": "main"})
    adapter = GitHubAdapter("owner/site", frozenset({"owner/site"}), writes_enabled=True,
                            client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert adapter.read_repository()["private"]
    arguments = {"title": "Useful utility", "body": "Tested print planner", "head": "feature", "base": "main",
                 "head_sha": "a" * 40, "idempotency_key": "fixture-one"}
    first = adapter.open_draft_pr(**arguments)
    replay = adapter.open_draft_pr(**arguments)
    assert first.resource_id == "7" and replay.replay
    assert sum(request.method == "POST" for request in calls) == 1
    with pytest.raises(ProviderError):
        adapter.open_draft_pr(**{**arguments, "body": "Changed request"})
    adapter.close()


def test_provider_redirects_malformed_results_and_unknown_mutation_are_safe(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-only-token")
    calls = []
    def redirect(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://evil.example/"})
    adapter = GitHubAdapter("owner/site", frozenset({"owner/site"}), client=httpx.Client(
        transport=httpx.MockTransport(redirect), follow_redirects=True))
    with pytest.raises(ProviderError, match="redirect"):
        adapter.read_repository()
    assert len(calls) == 1
    adapter.close()
    def timeout(request):
        raise httpx.ReadTimeout("simulated uncertain response", request=request)
    adapter = GitHubAdapter("owner/site", frozenset({"owner/site"}), client=httpx.Client(
        transport=httpx.MockTransport(timeout)))
    with pytest.raises(ProviderOutcomeUnknown, match="reconcile"):
        adapter._request("POST", "/repos/owner/site/pulls", mutation=True, json={"draft": True})
    adapter.close()


def test_netlify_preview_exact_static_artifact_digest_default_gate_and_no_production(tmp_path, monkeypatch):
    monkeypatch.setenv("NETLIFY_AUTH_TOKEN", "fixture-only-token")
    site = str(uuid4())
    output = tmp_path / "dist"
    output.mkdir()
    (output / "index.html").write_text('<html><meta name="robots" content="noindex, nofollow"></html>')
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "api.netlify.com"
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["draft"] is True
            assert request.url.path == f"/api/v1/sites/{site}/deploys"
            return httpx.Response(201, json={"id": "fixturedeploy", "site_id": site,
                "required": list(body["files"].values()),
                "deploy_ssl_url": "https://fixturedeploy--fixture-site.netlify.app"})
        return httpx.Response(204)
    adapter = NetlifyPreviewAdapter(site, tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    plan = adapter.plan("dist")
    with pytest.raises(ProviderError, match="disabled"):
        adapter.create_draft_preview(plan)
    assert calls == []
    adapter.close()
    allowed = NetlifyPreviewAdapter(site, tmp_path, operator_authorized=True, cost_authorized=True,
        protected_preview_verified=True, client=httpx.Client(transport=httpx.MockTransport(handler)))
    receipt = allowed.create_draft_preview(plan)
    assert receipt.operation == "create_draft_preview" and receipt.request_hash == plan.request_hash
    assert receipt.state.startswith("processing_pending") and len(calls) == 2
    (output / "index.html").write_text("changed")
    with pytest.raises((ProviderError, ValueError)):
        allowed.create_draft_preview(plan)
    assert len(calls) == 2
    assert not hasattr(allowed, "publish_production")
    allowed.close()


def test_netlify_rejects_unsafe_preview_paths_and_secrets(tmp_path):
    adapter = NetlifyPreviewAdapter(str(uuid4()), tmp_path)
    with pytest.raises(ValueError):
        adapter.plan("../outside")
    output = tmp_path / "dist"
    output.mkdir()
    (output / "index.html").write_text('<meta content="noindex, nofollow">')
    (output / ".env").write_text("fixture-secret")
    with pytest.raises(ValueError, match="Sensitive"):
        adapter.plan("dist")
    adapter.close()
