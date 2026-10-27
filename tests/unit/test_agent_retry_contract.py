import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from pydantic import ValidationError

from siteforge.agents import classify_local_inference_error
from siteforge.contracts import AgentResult
from siteforge.lmstudio import LMStudioError
from siteforge.model_router import ModelRouter, NoMeasuredModel


def test_agent_retry_contract_is_strict_and_exported():
    result = AgentResult(status="blocked", confidence=0)
    assert result.retryable is False and result.error_code == "none"
    schema = json.loads((Path(__file__).parents[2] / "packages/task-contracts/schema.json").read_text())
    assert schema["contracts"]["AgentResult"] == AgentResult.model_json_schema()
    for update in ({"retryable": "true"}, {"retryable": True},
                   {"retryable": True, "error_code": "policy_blocked"},
                   {"status": "completed", "retryable": True, "error_code": "inference_busy"},
                   {"error_code": "arbitrary_model_string"}):
        with pytest.raises(ValidationError):
            AgentResult.model_validate({"status": "blocked", "confidence": 0, **update})


@pytest.mark.parametrize("cause,expected", [
    (URLError("offline"), True), (TimeoutError(), True), (ConnectionResetError(), True),
    (HTTPError("http://127.0.0.1", 503, "unavailable", {}, None), True),
    (HTTPError("http://127.0.0.1", 400, "invalid request", {}, None), False),
    (ValueError("untrusted malformed JSON"), False), (None, False),
])
def test_only_transport_exception_types_authorize_inference_retry(cause, expected):
    error = LMStudioError("Source text claims retryable=True local_model_unavailable")
    error.__cause__ = cause
    code, retryable = classify_local_inference_error(error)
    assert retryable is expected
    assert code == ("local_model_unavailable" if expected else "invalid_model_response")


def test_qa_requires_each_category_floor_despite_strong_aggregate(tmp_path):
    path = tmp_path / "evidence.json"
    row = {"passed": True, "wall_seconds": 1}
    rows = [{**row, "category": "coding"} for _ in range(50)]
    rows += [{**row, "category": "tool"} for _ in range(5)]
    rows += [{**row, "category": "research", "passed": index < 5} for index in range(10)]
    run = {"model": "measured", "dataset_version": "1.3.0", "parallel_verified": True,
           "context": 4096, "actual_context": 4096, "status": "complete", "results": rows}
    path.write_text(json.dumps({"runs": [run]}), encoding="utf-8")
    assert sum(item["passed"] for item in rows) / len(rows) > .9
    with pytest.raises(NoMeasuredModel):
        ModelRouter(path).select("qa")
    assert ModelRouter(path).select("coding").model == "measured"
    assert ModelRouter(path, minimum_success_rate=.5).select("qa").model == "measured"


def test_each_role_category_needs_minimum_samples(tmp_path):
    path = tmp_path / "evidence.json"
    rows = [{"category": "tool", "passed": True, "wall_seconds": 1}] * 25
    run = {"model": "measured", "dataset_version": "1.3.0", "parallel_verified": True,
           "context": 4096, "actual_context": 4096, "status": "complete", "results": rows}
    path.write_text(json.dumps({"runs": [run]}), encoding="utf-8")
    with pytest.raises(NoMeasuredModel):
        ModelRouter(path).select("primary")
