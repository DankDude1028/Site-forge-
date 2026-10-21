"""Measured routing integration uses recorded fixture evidence and mocked inference."""
import copy
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from siteforge.agents import AGENTS, MODEL_ROLES, AgentRunner
from siteforge.contracts import AgentContext, AgentType
from siteforge.model_router import ModelRouter
from siteforge.site_factory import read_artifact
from siteforge.worker import WindowsWorker, WorkerSettings


def context(role):
    return AgentContext(task_id=uuid4(), allowed_tools=sorted(AGENTS[AgentType(role)].tools),
        budget_remaining=Decimal("0"), deadline=datetime.now(timezone.utc) + timedelta(minutes=5))


def native_metadata(source="publisher/winner", *, quantization="Q4_K_M", context_length=4096,
                    parallel=1, alias="live-alias", loaded=True):
    return {"endpoint": "/api/v1/models", "response": {"models": [{"type": "llm", "key": source,
        "quantization": {"name": quantization}, "selected_variant": source + "@" + quantization.lower(),
        "loaded_instances": [{"id": alias, "config": {"context_length": context_length, "parallel": parallel}}] if loaded else []}]}}


class FixtureModelClient:
    def __init__(self, metadata=None, *, metadata_after=None):
        self.metadata = metadata or native_metadata()
        self.metadata_after = metadata_after
        self.completions = []
        self.metadata_calls = 0

    def model_metadata(self):
        self.metadata_calls += 1
        return copy.deepcopy(self.metadata_after if self.completions and self.metadata_after is not None else self.metadata)

    def complete(self, messages, model, **settings):
        self.completions.append({"messages": messages, "model": model, "settings": settings})
        return SimpleNamespace(text=json.dumps({"summary": "Draft proposal only", "suggested_actions": ["purchase_domain"],
            "evidence_ids": [], "risks": ["Needs owner review"]}), model=model, latency_seconds=.01)


@pytest.fixture
def router(tmp_path):
    result_path = tmp_path / "benchmark-evidence" / "results.json"
    result_path.parent.mkdir()
    rows = [{"category": category, "passed": True, "wall_seconds": 1}
            for category in ("tool", "coding", "research", "content", "workflow", "efficiency") for _ in range(5)]
    result_path.write_text(json.dumps({"runs": [{"status": "complete", "synthetic": False,
        "model": "old-benchmark-alias", "source_model": "publisher/winner", "quantization": "Q4_K_M",
        "context": 4096, "actual_context": 4096, "parallel_verified": True,
        "dataset_version": "1.2.0", "dataset_sha256": "versioned-fixture", "settings": {"parallel": 1},
        "results": rows}]}), encoding="utf-8")
    return ModelRouter(result_path)


@pytest.mark.parametrize("role", list(AgentType))
def test_each_agent_uses_qualified_role_winner_and_current_verified_alias(tmp_path, router, role):
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run(role, context(role), {"mode": "local_model", "request": "Draft a useful utility"})
    assert result.status == "blocked"  # Proposal output never executes an action.
    assert client.completions[0]["model"] == "live-alias"
    assert client.metadata_calls == 2
    proposal = read_artifact(runner.root, result.artifacts[0]["uri"])
    selection = proposal["model_selection"]
    assert selection["selection"] == "measured_role_winner"
    assert selection["benchmark_route"]["role"] == MODEL_ROLES[role]
    assert selection["benchmark_route"]["inference_identifier"] == "old-benchmark-alias"
    assert selection["loaded_model"]["inference_identifier"] == "live-alias"
    assert not selection["model_auto_load"] and not selection["paid_fallback"]
    assert proposal["executed"] is False
    assert client.completions[0]["settings"]["response_schema"]["type"] == "object"


@pytest.mark.parametrize("metadata", [
    native_metadata(source="publisher/other-model", alias="old-benchmark-alias"),
    native_metadata(quantization="Q5_K_M"),
    native_metadata(context_length=8192),
    native_metadata(parallel=4),
    native_metadata(loaded=False),
    {"endpoint": "/api/v0/models", "response": {"data": [{"id": "publisher/winner", "state": "loaded", "max_context_length": 4096}]}},
    {"endpoint": "/api/v1/models", "response": {"models": "malformed"}},
])
def test_unloaded_wrong_or_unverifiable_winner_blocks_without_model_request(tmp_path, router, metadata):
    client = FixtureModelClient(metadata)
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("research", context("research"), {"mode": "local_model", "request": "Draft"})
    assert result.status == "blocked"
    assert not client.completions
    artifact = read_artifact(runner.root, result.artifacts[0]["uri"])
    assert artifact["status"] == "blocked"
    assert artifact["model_auto_load"] is False
    assert artifact["paid_fallback"] is False


def test_no_qualified_evidence_does_not_fall_back_to_loaded_model(tmp_path):
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client,
        model_router=ModelRouter(tmp_path / "missing-results.json"))
    result = runner.run("developer", context("developer"), {"mode": "local_model", "request": "Draft"})
    assert result.status == "blocked"
    assert not client.completions and client.metadata_calls == 0
    assert "benchmark evidence" in result.risks[0]


@pytest.mark.parametrize("requested", ["live-alias", "publisher/winner", "publisher/winner@q4_k_m"])
def test_operator_override_is_loaded_only_and_recorded_for_draft(tmp_path, requested):
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client,
        model_router=ModelRouter(tmp_path / "no-qualified-evidence.json"))
    result = runner.run("content", context("content"), {"mode": "local_model", "model": requested, "request": "Draft"})
    proposal = read_artifact(runner.root, result.artifacts[0]["uri"])
    assert proposal["model_selection"]["selection"] == "operator_override"
    assert proposal["model_selection"]["requested_model"] == requested
    assert proposal["model_selection"]["qualification_bypassed_for_draft_only"] is True
    assert client.completions[0]["model"] == "live-alias"
    assert result.status == "blocked" and proposal["executed"] is False


@pytest.mark.parametrize("requested", ["publisher/unloaded", "", None, {"model": "publisher/winner"}])
def test_invalid_or_unloaded_explicit_override_cannot_trigger_autoload(tmp_path, requested):
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client)
    result = runner.run("research", context("research"), {"mode": "local_model", "model": requested})
    assert result.status == "blocked" and not client.completions


def test_alias_reassigned_during_inference_discards_proposal(tmp_path, router):
    client = FixtureModelClient(metadata_after=native_metadata(source="publisher/other-model"))
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("research", context("research"), {"mode": "local_model", "request": "Draft"})
    assert len(client.completions) == 1
    assert "identity changed" in result.risks[0]
    assert not list((runner.root / "proposals").glob("*.json"))
    assert result.status == "blocked"


def test_context_overflow_blocks_without_truncating_or_inference(tmp_path, router):
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("research", context("research"), {"mode": "local_model", "request": "🧪" * 3000})
    assert result.status == "blocked" and not client.completions
    assert "context budget" in result.risks[0]


def test_running_benchmark_prevents_worker_inference(tmp_path, router):
    router.results_path.with_name(".run.lock").write_text('{"pid":123}', encoding="utf-8")
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("research", context("research"), {"mode": "local_model", "model": "live-alias"})
    assert result.status == "blocked" and client.metadata_calls == 0 and not client.completions
    assert "inference lock" in result.risks[0]


def test_worker_constructor_configures_real_router_from_environment(tmp_path, monkeypatch):
    configured = tmp_path / "custom-evidence.json"
    monkeypatch.setenv("SITEFORGE_BENCHMARK_RESULTS", str(configured))
    settings = WorkerSettings(supervisor_url="http://127.0.0.1:8080", token="fixture-worker-token-long-enough",
        worker_id=str(uuid4()), artifact_root=tmp_path / "artifacts")
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))) as supervisor:
        worker = WindowsWorker(settings, client=supervisor)
        assert isinstance(worker.runner.model_router, ModelRouter)
        assert worker.runner.model_router.results_path == configured
