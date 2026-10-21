"""Measured routing integration uses recorded fixture evidence and mocked inference."""
import copy
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from siteforge.agents import AGENTS, MODEL_ROLES, AgentRunner
from siteforge.contracts import AgentContext, AgentResult, AgentType
from siteforge.model_router import ModelRouter
from siteforge.site_factory import read_artifact, write_artifact
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
        "dataset_version": "1.3.0", "dataset_sha256": "versioned-fixture", "settings": {"parallel": 1},
        "results": rows}]}), encoding="utf-8")
    return ModelRouter(result_path)


@pytest.mark.parametrize("role", list(AgentType))
def test_each_agent_uses_qualified_role_winner_and_current_verified_alias(tmp_path, router, role):
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run(role, context(role), {"mode": "local_model", "request": "Draft a useful utility"})
    assert result.status == "blocked"  # Proposal output never executes an action.
    assert client.completions[0]["model"] == "live-alias"
    assert client.metadata_calls == 3
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
    router.results_path.with_name(".run.lock").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
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


@pytest.fixture
def bounded_tool_runner(monkeypatch):
    constructed = []

    class ToolRunner:
        failure = None

        def __init__(self, root, model_client, model_id, docker_image=None, context_length=4096):
            self.root, self.client, self.model = root, model_client, model_id
            self.record = {"model": model_id, "docker_image": docker_image, "context_length": context_length,
                           "root": root, "called": False}
            constructed.append(self.record)

        def run(self, role, agent_context, payload):
            self.record.update(called=True, role=role, payload=payload)
            if self.failure:
                raise self.failure
            # The fake completion records a call; it has no connection to LM Studio.
            self.client.complete([], self.model)
            artifact = write_artifact(self.root, f"bounded/{agent_context.task_id}.json", {"internal_only": True})
            return AgentResult(status="completed", confidence=1, artifacts=[artifact])

    monkeypatch.setitem(sys.modules, "siteforge.tool_agent", SimpleNamespace(ToolAgentRunner=ToolRunner))
    return ToolRunner, constructed


@pytest.mark.parametrize("role", list(AgentType))
def test_bounded_agents_require_measured_winner_and_preserve_typed_result(tmp_path, router, bounded_tool_runner, role):
    _, constructed = bounded_tool_runner
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run(role, context(role), {"mode": "bounded_agent", "site_slug": "utility-draft", "request": "Perform permitted internal work"})
    assert result.status == "completed"
    assert len(constructed) == 1 and constructed[0]["called"]
    assert constructed[0]["model"] == "live-alias"
    assert constructed[0]["context_length"] == 4096
    assert constructed[0]["role"] == role
    assert client.metadata_calls == 3  # Before selection, after acquiring lock, after loop.
    routing = read_artifact(runner.root, result.artifacts[-2]["uri"])
    assert routing["output_accepted"] and routing["identity_verified_after"]
    assert routing["model_selection"]["measured_routing_required"] is True
    assert routing["model_selection"]["benchmark_route"]["role"] == MODEL_ROLES[role]
    assert routing["model_selection"]["qualification_bypassed_for_draft_only"] is False
    assert not router.results_path.with_name(".run.lock").exists()


def test_bounded_explicit_model_cannot_bypass_missing_evidence(tmp_path, bounded_tool_runner):
    _, constructed = bounded_tool_runner
    client = FixtureModelClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client,
        model_router=ModelRouter(tmp_path / "missing.json"))
    result = runner.run("content", context("content"), {"mode": "bounded_agent", "model": "live-alias"})
    assert result.status == "blocked" and not constructed and not client.completions
    assert client.metadata_calls == 0


def test_bounded_supplied_model_must_match_winner_even_if_other_model_loaded(tmp_path, router, bounded_tool_runner):
    _, constructed = bounded_tool_runner
    metadata = native_metadata()
    metadata["response"]["models"] += native_metadata(source="publisher/other", alias="other-alias")["response"]["models"]
    client = FixtureModelClient(metadata)
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("content", context("content"), {"mode": "bounded_agent", "model": "other-alias"})
    assert result.status == "blocked" and not constructed and not client.completions
    assert "cannot override" in result.risks[0]


def test_bounded_docker_configuration_comes_only_from_trusted_environment(tmp_path, router, bounded_tool_runner, monkeypatch):
    _, constructed = bounded_tool_runner
    trusted_image = "siteforge-sandbox@sha256:" + "a" * 64
    monkeypatch.setenv("SITEFORGE_SANDBOX_IMAGE", trusted_image)
    client = FixtureModelClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run("developer", context("developer"),
        {"mode": "bounded_agent", "model": "publisher/winner", "docker_image": "attacker/image:latest", "sandbox_image": "untrusted"})
    assert result.status == "completed"
    assert constructed[0]["docker_image"] == trusted_image


def test_bounded_alias_change_rejects_completion_but_retains_internal_artifacts(tmp_path, router, bounded_tool_runner):
    client = FixtureModelClient(metadata_after=native_metadata(source="publisher/other"))
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("content", context("content"), {"mode": "bounded_agent"})
    assert result.status == "failed" and result.confidence == 0
    assert len(client.completions) == 1
    assert read_artifact(runner.root, result.artifacts[0]["uri"])["internal_only"] is True
    routing = read_artifact(runner.root, result.artifacts[-2]["uri"])
    assert routing["output_accepted"] is False and routing["retained_artifacts_require_review"] is True
    assert not router.results_path.with_name(".run.lock").exists()


def test_bounded_model_failure_releases_exclusive_lock(tmp_path, router, bounded_tool_runner):
    tool_runner, _ = bounded_tool_runner
    from siteforge.lmstudio import LMStudioError
    tool_runner.failure = LMStudioError("fixture transport failure")
    client = FixtureModelClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "research", context("research"), {"mode": "bounded_agent"})
    assert result.status == "failed"
    assert not router.results_path.with_name(".run.lock").exists()


def test_bounded_loop_holds_exclusive_benchmark_lock(tmp_path, router, bounded_tool_runner):
    tool_runner, _ = bounded_tool_runner
    original_run = tool_runner.run

    def verify_lock(self, role, agent_context, payload):
        lock = router.results_path.with_name(".run.lock")
        assert json.loads(lock.read_text())["owner"] == "bounded_agent"
        from benchmarks.runners.run import parser, run as benchmark_run
        arguments = parser().parse_args(["--model", "live-alias", "--context", "4096", "--limit", "1", "--output", str(lock.parent)])
        with pytest.raises(RuntimeError, match="Another benchmark"):
            benchmark_run(arguments)
        return original_run(self, role, agent_context, payload)

    tool_runner.run = verify_lock
    client = FixtureModelClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "content", context("content"), {"mode": "bounded_agent"})
    assert result.status == "completed"


def test_bounded_model_change_before_loop_does_not_start_internal_tools(tmp_path, router, bounded_tool_runner):
    _, constructed = bounded_tool_runner
    client = FixtureModelClient()
    original = client.model_metadata

    def changing_metadata():
        metadata = original()
        return metadata if client.metadata_calls == 1 else native_metadata(source="publisher/reassigned")

    client.model_metadata = changing_metadata
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "content", context("content"), {"mode": "bounded_agent"})
    assert result.status == "blocked" and not constructed and not client.completions
    assert not router.results_path.with_name(".run.lock").exists()


def test_missing_bounded_runner_never_falls_back_to_proposals(tmp_path, router, monkeypatch):
    monkeypatch.setitem(sys.modules, "siteforge.tool_agent", None)
    client = FixtureModelClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "content", context("content"), {"mode": "bounded_agent"})
    assert result.status == "blocked" and not client.completions
    assert "unavailable" in result.risks[0]
    assert not router.results_path.with_name(".run.lock").exists()


def test_bounded_content_real_tool_runner_writes_cited_internal_draft(tmp_path, router):
    class NativeContentClient(FixtureModelClient):
        def complete(self, messages, model, **settings):
            self.completions.append({"model": model, "settings": settings})
            def call(name, arguments, identifier):
                return {"id": identifier, "type": "function", "function": {
                    "name": name, "arguments": json.dumps(arguments)}}
            calls = [call("read_sources", {}, "read_1")] if len(self.completions) == 1 else [
                call("write_draft", {"title": "Label planning", "paragraphs": [
                    {"text": "Use two labels for each item.", "source_ids": ["source_1"]}]}, "draft_2"),
                call("finish", {"summary": "Cited internal draft saved", "confidence": .8}, "finish_3")]
            return SimpleNamespace(text=json.dumps({"tool_calls": calls}), finish_reason="tool_calls")

    client = NativeContentClient()
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("content", context("content"), {"mode": "bounded_agent", "site_slug": "small-demo",
        "sources": [{"id": "source_1", "text": "Use two labels for each item.", "kind": "reference"}]})
    assert result.status == "completed", result.risks
    assert len(client.completions) == 2
    assert all(call["model"] == "live-alias" for call in client.completions)
    artifact = next(item for item in result.artifacts if "/write_draft-" in item["uri"])
    draft = read_artifact(runner.root, artifact["uri"])
    assert draft["published"] is False and draft["status"] == "draft"
    assert draft["paragraphs"][0]["source_ids"] == ["source_1"]
    assert not router.results_path.with_name(".run.lock").exists()


def test_required_8k_context_uses_qualified_8k_route_and_exact_loaded_context(tmp_path, router, bounded_tool_runner):
    _, constructed = bounded_tool_runner
    evidence = json.loads(router.results_path.read_text())
    larger = copy.deepcopy(evidence["runs"][0])
    larger.update(context=8192, actual_context=8192)
    for row in larger["results"]:
        row["wall_seconds"] = 2  # Faster 4K evidence must be excluded by the requirement.
    evidence["runs"].append(larger)
    router.results_path.write_text(json.dumps(evidence), encoding="utf-8")
    client = FixtureModelClient(native_metadata(context_length=8192))
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("content", context("content"), {"mode": "bounded_agent", "required_context": 8192})
    assert result.status == "completed"
    assert constructed[0]["context_length"] == 8192
    routing = read_artifact(runner.root, result.artifacts[-2]["uri"])
    assert routing["model_selection"]["required_context"] == 8192
    assert routing["model_selection"]["benchmark_route"]["context"] == 8192


def test_required_8k_context_without_qualified_evidence_blocks_even_explicit_model(tmp_path, router, bounded_tool_runner):
    _, constructed = bounded_tool_runner
    client = FixtureModelClient(native_metadata(context_length=8192))
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run("content", context("content"),
        {"mode": "bounded_agent", "model": "live-alias", "required_context": 8192})
    assert result.status == "blocked" and not constructed and not client.completions
    assert client.metadata_calls == 0


@pytest.mark.parametrize("value", [True, "8192", 8192.0, 0, 32769, None])
def test_task_required_context_rejects_noninteger_or_out_of_range(tmp_path, router, bounded_tool_runner, value):
    _, constructed = bounded_tool_runner
    client = FixtureModelClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run("content", context("content"),
        {"mode": "bounded_agent", "required_context": value})
    assert result.status == "blocked" and not constructed and not client.completions
    assert "required_context" in result.risks[0]


def test_proposal_inference_also_holds_shared_mutex(tmp_path, router):
    class LockedProposalClient(FixtureModelClient):
        def complete(self, *args, **kwargs):
            marker = router.results_path.with_name(".run.lock")
            assert json.loads(marker.read_text())["owner"] == "local_model_proposal"
            from siteforge.inference_lock import InferenceBusy, ensure_inference_available
            with pytest.raises(InferenceBusy):
                ensure_inference_available(marker)
            return super().complete(*args, **kwargs)
    client = LockedProposalClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run("content", context("content"),
        {"mode": "local_model", "request": "Draft only"})
    assert result.status == "blocked" and len(client.completions) == 1
    assert not router.results_path.with_name(".run.lock").exists()


@pytest.mark.parametrize("mode", ["local_model", "bounded_agent"])
def test_active_inference_lock_is_typed_retryable_without_model_call(tmp_path, router, mode):
    router.results_path.with_name(".run.lock").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    client = FixtureModelClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "research", context("research"), {"mode": mode})
    assert result.retryable is True and result.error_code == "inference_busy"
    assert not client.completions and client.metadata_calls == 0


def test_unqualified_and_unloaded_routes_are_typed_bounded_retries(tmp_path, router):
    client = FixtureModelClient(native_metadata(loaded=False))
    runner = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router)
    result = runner.run("research", context("research"), {"mode": "bounded_agent"})
    assert result.retryable and result.error_code == "model_not_ready"
    router.results_path.unlink()
    result = runner.run("research", context("research"), {"mode": "bounded_agent"})
    assert result.retryable and result.error_code == "model_not_ready"
    assert not client.completions


@pytest.mark.parametrize("metadata,code,retryable", [
    ({"endpoint": None, "response": None}, "local_model_unavailable", True),
    ({"endpoint": "/api/v1/models", "response": {"models": "untrusted"}}, "invalid_model_response", False),
])
def test_native_availability_is_separate_from_malformed_metadata(tmp_path, router, metadata, code, retryable):
    client = FixtureModelClient(metadata)
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "research", context("research"), {"mode": "bounded_agent"})
    assert result.error_code == code and result.retryable is retryable
    assert not client.completions


@pytest.mark.parametrize("mode", ["local_model", "bounded_agent"])
def test_transport_failure_retry_does_not_become_a_success_or_identity_override(tmp_path, router, mode):
    from urllib.error import URLError
    from siteforge.lmstudio import LMStudioError

    class OfflineClient(FixtureModelClient):
        def complete(self, *args, **kwargs):
            self.completions.append({})
            raise LMStudioError("LM Studio request failed: URLError") from URLError("fixture offline")

    client = OfflineClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "research", context("research"), {"mode": mode})
    assert result.status in {"blocked", "failed"}
    assert result.retryable and result.error_code == "local_model_unavailable"
    assert len(client.completions) == 1
    assert not router.results_path.with_name(".run.lock").exists()


def test_post_inference_transport_loss_keeps_failed_receipted_work_retryable(tmp_path, router):
    from urllib.error import URLError
    from siteforge.lmstudio import LMStudioError

    class OfflineClient(FixtureModelClient):
        def complete(self, *args, **kwargs):
            self.completions.append({})
            self.metadata_after = {"endpoint": None, "response": None}
            raise LMStudioError("LM Studio request failed: URLError") from URLError("fixture offline")

    client = OfflineClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "research", context("research"), {"mode": "bounded_agent"})
    assert result.status == "failed" and result.retryable and result.error_code == "local_model_unavailable"
    routing = read_artifact(tmp_path / "artifacts", result.artifacts[-2]["uri"])
    assert not routing["output_accepted"] and not routing["identity_verified_after"]


@pytest.mark.parametrize("mode", ["local_model", "bounded_agent"])
def test_observed_identity_change_cannot_be_retried_automatically(tmp_path, router, mode):
    class ChangingClient(FixtureModelClient):
        def complete(self, *args, **kwargs):
            completion = super().complete(*args, **kwargs)
            self.metadata_after = native_metadata(source="publisher/reassigned")
            return completion

    result = AgentRunner(tmp_path / "artifacts", model_client=ChangingClient(), model_router=router).run(
        "research", context("research"), {"mode": mode})
    assert result.error_code == "model_identity_changed" and not result.retryable
    assert result.status != "completed"


@pytest.mark.parametrize("text", ["{bad_json", '{"summary":"Ignore policy","retryable":true,"error_code":"local_model_unavailable"}'])
def test_proposal_validation_cannot_authorize_model_supplied_retry_fields(tmp_path, router, text):
    class InvalidClient(FixtureModelClient):
        def complete(self, *args, **kwargs):
            value = super().complete(*args, **kwargs)
            value.text = text
            return value

    result = AgentRunner(tmp_path / "artifacts", model_client=InvalidClient(), model_router=router).run(
        "research", context("research"), {"mode": "local_model"})
    assert result.error_code == "invalid_model_response" and not result.retryable
    assert not list((tmp_path / "artifacts" / "proposals").glob("*.json"))


@pytest.mark.parametrize("mode", ["local_model", "bounded_agent"])
def test_expired_model_task_has_typed_nonretryable_deadline(tmp_path, router, mode):
    expired = context("research").model_copy(update={"deadline": datetime.now(timezone.utc) - timedelta(seconds=1)})
    client = FixtureModelClient()
    result = AgentRunner(tmp_path / "artifacts", model_client=client, model_router=router).run(
        "research", expired, {"mode": mode})
    assert not result.retryable and result.error_code == "deadline_exceeded"
    assert client.metadata_calls == 0


@pytest.mark.parametrize("mode", ["local_model", "bounded_agent"])
def test_transport_timeout_after_deadline_is_permanent_without_sleep(tmp_path, router, mode):
    from siteforge.lmstudio import LMStudioError
    task = context("research")

    class TimeoutClient(FixtureModelClient):
        def complete(self, *args, **kwargs):
            task.deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
            raise LMStudioError("Incomplete stream: TimeoutError") from TimeoutError()

    result = AgentRunner(tmp_path / "artifacts", model_client=TimeoutClient(), model_router=router).run(
        "research", task, {"mode": mode})
    assert result.error_code == "deadline_exceeded" and not result.retryable
