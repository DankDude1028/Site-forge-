"""Secondary semantic diagnostics for immutable baseline outputs.

Writes a separate artifact and never changes primary scores or source results.
Usage: python -m benchmarks.runners.diagnose --results benchmarks/results/results.json
"""
import argparse
import json
import re
from pathlib import Path
from typing import Any

from ..evaluators.grade import grade
from .report import atomic_write
from .run import DATASET, load_tasks, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("benchmarks/results/results.json"))
    args = parser.parse_args()
    payload = json.loads(args.results.read_text(encoding="utf-8"))
    output: dict[str, Any] = {"diagnostic_version": "1.1.0", "generated_at": now(),
              "policy": "Primary immutable scores unchanged; this diagnostic only removes a complete outer markdown JSON fence.", "runs": []}
    for run in payload.get("runs", []):
        version = run["dataset_version"]
        dataset = DATASET.with_name("tasks.v1.jsonl" if version == "1.0.0" else f"tasks.v{version.removesuffix('.0')}.jsonl")
        tasks, manifest = load_tasks(dataset)
        if manifest["sha256"] != run["dataset_sha256"]:
            raise ValueError("Cannot diagnose a different dataset hash")
        by_id = {task["id"]: task for task in tasks}
        rows = []
        for row in run.get("results", []):
            if row.get("warmup"):
                continue
            text = row.get("completion", {}).get("text", "")
            result = grade(by_id[row["task_id"]], text)
            diagnostic = result.get("diagnostic_fence_stripped", result)
            item = {"task_id": row["task_id"], "trial": row["trial"], "primary_passed_original": row["passed"],
                    "semantic_diagnostic_passed": diagnostic["passed"], "semantic_diagnostic_score": diagnostic["score"]}
            expected = by_id[row["task_id"]].get("expected", {})
            if "action" in expected:
                try:
                    fence = re.fullmatch(r"\s*```(?:json)?\s*\n?(.*?)\n?```\s*", text, re.DOTALL)
                    parsed = json.loads(fence.group(1) if fence else text)
                    if "tool_calls" in parsed and len(parsed["tool_calls"]) == 1:
                        call = parsed["tool_calls"][0]["function"]
                        parsed = {"action": call["name"], "arguments": json.loads(call["arguments"])}
                    item["action_diagnostic_match"] = isinstance(parsed, dict) and parsed.get("action") == expected["action"]
                    if "reason" in expected:
                        item["literal_reason_diagnostic_match"] = isinstance(parsed, dict) and parsed.get("reason") == expected["reason"]
                except (ValueError, TypeError, KeyError, IndexError):
                    item["action_diagnostic_match"] = False
            rows.append(item)
        output["runs"].append({"run_id": run["run_id"], "source_model": run["source_model"],
                               "tasks": len(rows), "primary_passed_original": sum(row["primary_passed_original"] for row in rows),
                               "semantic_diagnostic_passed": sum(row["semantic_diagnostic_passed"] for row in rows),
                               "action_diagnostic_samples": sum("action_diagnostic_match" in row for row in rows),
                               "action_diagnostic_passed": sum(bool(row.get("action_diagnostic_match")) for row in rows), "rows": rows})
    destination = args.results.with_name("diagnostic_results.json")
    atomic_write(destination, json.dumps(output, indent=2) + "\n")
    print(json.dumps({"output": str(destination), "runs": [{key: value for key, value in run.items() if key != "rows"} for run in output["runs"]]}, indent=2))


if __name__ == "__main__":
    main()
