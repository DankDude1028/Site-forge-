import json
from collections import Counter

import pytest

from benchmarks.evaluators.grade import grade
from benchmarks.evaluators.safe_python import SafePython, UnsafeCode
from benchmarks.runners.report import write_reports
from benchmarks.runners.run import load_tasks
from benchmarks.runners.schemas import response_schema
from siteforge.model_router import ModelRouter, NoMeasuredModel


def test_versioned_dataset_and_real_category_counts():
    tasks, manifest = load_tasks()
    assert Counter(t["category"] for t in tasks) == {"tool": 25, "research": 20, "coding": 20, "content": 15, "workflow": 15, "efficiency": 5}
    assert len({t["prompt"] for t in tasks}) == 100
    assert manifest["tasks"] == 100
    for task in tasks:
        if task["category"] in {"tool", "research", "workflow", "efficiency"}:
            response = task["expected"]
            if task["evaluator"] == "native_tool":
                response = {"tool_calls": [{"id": "fixture-call", "type": "function", "function": {"name": response["action"], "arguments": json.dumps(response["arguments"])}}]}
            assert grade(task, json.dumps(response))["passed"]


REFERENCE = [
    'result = []\n    for item in value:\n        if item not in result:\n            result.append(item)\n    return result',
    'return "-".join(value.lower().split())',
    'return max(value[1], min(value[2], value[0]))',
    'return sum(value)',
    'return [x for x in value if x > 0]',
    'items = [x for x in value if x is not None]\n    return sum(items) / len(items) if items else None',
    'result = {}\n    for item in value.lower().split():\n        result[item] = result.get(item, 0) + 1\n    return result',
    'return [value["items"][i:i+value["size"]] for i in range(0, len(value["items"]), value["size"])]',
    'seen = []\n    for x in value:\n        if x in seen:\n            return x\n        seen.append(x)\n    return None',
    'delay = 30\n    for i in range(value):\n        delay = min(delay * 2, 600)\n    return delay',
    'out = []\n    total = 0\n    for x in value:\n        total += x\n        out.append(total)\n    return out',
    'out = {}\n    for row in value:\n        for k, v in row.items():\n            out[k] = out.get(k, 0) + v\n    return out',
    'return sorted(set(value))',
    'return round(value["demand"] * 0.25 + value["competition"] * 0.20 + value["commercial"] * 0.25 + value["value"] * 0.20 + value["maintenance"] * 0.10, 2)',
    'return value.lower().endswith(".csv") or value.lower().endswith(".tsv")',
    'return [x for row in value for x in row]',
    'seen = set()\n    out = []\n    for row in value:\n        if row["id"] not in seen:\n            seen.add(row["id"])\n            out.append(row)\n    return out',
    'return {"hours":value // 3600,"minutes":value % 3600 // 60,"seconds":value % 60}',
    'return round(value[0] / value[1], 4) if value[1] else None',
    'return [list(row) for row in zip(*value)] if value else []',
]


@pytest.mark.parametrize("index", range(20))
def test_coding_fixture_executable_tests_have_satisfiable_reference(index):
    tasks, _ = load_tasks()
    task = [task for task in tasks if task["category"] == "coding"][index]
    # Transpose reference avoids argument expansion, which is deliberately not allowed.
    body = REFERENCE[index] if index != 19 else 'return [[value[r][c] for r in range(len(value))] for c in range(len(value[0]))] if value else []'
    result = grade(task, json.dumps({"code": "def solve(value):\n    " + body}))
    assert result["passed"], (task["id"], result)
    assert result["tests_passed"] == len(task["tests"])


@pytest.mark.parametrize("code", [
    'import os\ndef solve(value): return os.getcwd()',
    'def solve(value): return __import__("os").system("whoami")',
    'def solve(value): return value.__class__',
    'def solve(value): return open("secret")',
    'def solve(value): return (lambda: 1)()',
    'def solve(value): return solve(value)',
    '@print\ndef solve(value): return value',
    'def solve(value):\n    while True: pass',
    'def solve(value): return [1] * 1000000000',
    'def solve(value): return list(range(1000000000))',
    'def solve(value): return 2 ** 1000000000',
])
def test_model_code_cannot_escape_interpreter(code):
    with pytest.raises((UnsafeCode, TypeError)):
        SafePython(code).solve(None)


def test_operation_budget_stops_nested_loops():
    interpreter = SafePython('def solve(value):\n    return [[i for i in range(1024)] for j in range(1024)]', operation_limit=200)
    with pytest.raises(UnsafeCode):
        interpreter.solve(None)


def test_injection_does_not_grant_capability_and_citations_fail_closed():
    tasks, _ = load_tasks()
    task = next(t for t in tasks if t["label"] == "injected webpage")
    assert not grade(task, '{"action":"send_email","arguments":{"to":"thief.invalid"}}')["passed"]
    source = next(t for t in tasks if t["label"] == "unsupported citation")
    assert not grade(source, '{"answer":true,"citations":["S88"]}')["passed"]
    assert not grade(source, 'Here is JSON: {"answer":null,"citations":[]}')["schema_valid"]


def test_reports_pending_and_xss_safe(tmp_path):
    payload = {"runs": []}
    write_reports(tmp_path, payload)
    assert "PENDING" in (tmp_path / "report.md").read_text()
    assert "PENDING" in (tmp_path / "model_comparison.html").read_text()
    assert (tmp_path / "results.csv").read_text().startswith("run_id,")
    with pytest.raises(NoMeasuredModel):
        ModelRouter(tmp_path / "results.json").select("coding")


def test_report_keeps_all_comparison_rows_before_details(tmp_path):
    common = {"model": "alias", "context": 4096, "quantization": "Q4", "settings": {},
              "status": "complete", "dataset_version": "1.2.0", "dataset_sha256": "fixture", "results": []}
    write_reports(tmp_path, {"runs": [{**common, "source_model": "candidate-a", "run_id": "run-a"},
                                     {**common, "source_model": "candidate-b", "run_id": "run-b"}]})
    report = (tmp_path / "report.md").read_text()
    assert report.index("| candidate-b / 4096") < report.index("## Run `run-a`")


def test_router_requires_complete_measured_qualified_results(tmp_path):
    path = tmp_path / "results.json"
    row = {"category": "coding", "passed": True, "wall_seconds": 2}
    runs = [{"model": "slow", "parallel_verified": True, "dataset_version": "1.2.0", "context": 4096, "actual_context": 4096, "status": "complete", "results": [row] * 5},
            {"model": "fast", "parallel_verified": True, "dataset_version": "1.2.0", "context": 4096, "actual_context": 4096, "status": "complete", "results": [{**row, "wall_seconds": 1}] * 5},
            {"model": "partial", "parallel_verified": True, "dataset_version": "1.2.0", "context": 4096, "actual_context": 4096, "status": "partial", "results": [{**row, "wall_seconds": .01}] * 5}]
    path.write_text(json.dumps({"runs": runs}))
    router = ModelRouter(path)
    assert router.select("coding").model == "fast"
    assert router.select("coding", available_models={"slow"}).model == "slow"
    with pytest.raises(NoMeasuredModel):
        router.select("research")
    with pytest.raises(ValueError):
        router.select("paid_cloud")


def test_structured_shapes_do_not_leak_fixture_answers():
    tasks, _ = load_tasks()
    for task in tasks:
        schema = response_schema(task)
        if task.get("tools"):
            assert schema is None
            continue
        serialized = json.dumps(schema)
        assert '"enum"' not in serialized
        assert '"const"' not in serialized
        assert '"default"' not in serialized
        if task["evaluator"] == "coding":
            assert schema["properties"] == {"code": {"type": "string"}}


def test_secondary_fence_diagnostic_preserves_primary_failure():
    task = {"category": "efficiency", "evaluator": "exact", "expected": {"ok": True}}
    result = grade(task, '```json\n{"ok":true}\n```')
    assert not result["passed"]
    assert not result["schema_valid"]
    assert result["diagnostic_fence_stripped"]["passed"]
    assert not grade(task, '{"ok":1}')["schema_valid"]
    assert not grade(task, '{"ok":NaN}')["schema_valid"]


def test_router_does_not_mix_candidates_sharing_alias(tmp_path):
    path = tmp_path / "results.json"
    common = {"model": "same-alias", "parallel_verified": True, "dataset_version": "1.2.0", "actual_context": 4096, "context": 4096, "status": "complete"}
    runs = [{**common, "source_model": "candidate-a", "results": [{"category": "tool", "passed": True, "wall_seconds": 1}] * 3},
            {**common, "source_model": "candidate-b", "results": [{"category": "tool", "passed": True, "wall_seconds": 1}] * 3}]
    path.write_text(json.dumps({"runs": runs}))
    with pytest.raises(NoMeasuredModel):
        ModelRouter(path).select("primary")


def test_router_minimum_context_excludes_faster_smaller_run_and_keeps_exact_filter(tmp_path):
    path = tmp_path / "results.json"
    common = {"source_model": "same-model", "model": "alias", "dataset_version": "1.2.0",
              "status": "complete", "parallel_verified": True, "quantization": "Q4_K_M"}
    path.write_text(json.dumps({"runs": [
        {**common, "context": 4096, "actual_context": 4096, "results": [{"category": "coding", "passed": True, "wall_seconds": 1}] * 5},
        {**common, "context": 8192, "actual_context": 8192, "results": [{"category": "coding", "passed": True, "wall_seconds": 2}] * 5}]}))
    router = ModelRouter(path)
    assert router.select("coding").context == 4096
    assert router.select("coding", minimum_context=8192).context == 8192
    assert router.select("coding", context=8192).context == 8192
    with pytest.raises(NoMeasuredModel):
        router.select("coding", context=4096, minimum_context=8192)
    with pytest.raises(NoMeasuredModel):
        router.select("coding", minimum_context=16384)


@pytest.mark.parametrize("value", [True, False, "8192", 8192.0, 0, 32769])
def test_router_rejects_invalid_minimum_context(value, tmp_path):
    with pytest.raises(ValueError, match="Minimum context"):
        ModelRouter(tmp_path / "missing.json").select("coding", minimum_context=value)
