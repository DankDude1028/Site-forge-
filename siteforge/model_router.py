"""Role routing based solely on recorded local benchmark evidence."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class NoMeasuredModel(RuntimeError):
    pass


ROLE_CATEGORIES = {
    "primary": {"tool", "workflow"}, "worker": {"tool", "efficiency"},
    "coding": {"coding"}, "research": {"research"}, "content": {"content"},
    "qa": {"coding", "research", "tool"},
}
QUALIFIED_DATASET_VERSIONS = frozenset({"1.3.0"})


@dataclass(frozen=True)
class Route:
    role: str
    model: str
    context: int
    success_per_hour: float
    success_rate: float
    samples: int
    evidence: str
    inference_identifier: str | None = None
    quantization: str = "UNKNOWN"
    dataset_version: str | None = None


class ModelRouter:
    def __init__(self, results_path: str | Path = "benchmarks/results/results.json", *,
                 minimum_success_rate: float = 0.8, minimum_samples: int = 5) -> None:
        self.results_path = Path(results_path)
        self.minimum_success_rate = minimum_success_rate
        self.minimum_samples = minimum_samples

    def select(self, role: str, *, available_models: set[str] | None = None,
               context: int | None = None, minimum_context: int | None = None) -> Route:
        if role not in ROLE_CATEGORIES:
            raise ValueError("Unknown model role; paid escalation requires separate approval")
        if minimum_context is not None and (type(minimum_context) is not int or not 1024 <= minimum_context <= 32768):
            raise ValueError("Minimum context must be an integer from 1024 through 32768")
        try:
            payload = json.loads(self.results_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise NoMeasuredModel("No measured benchmark evidence available") from error
        groups: dict[tuple[str, int, str, str, str], list[dict[str, Any]]] = {}
        metadata: dict[tuple[str, int, str, str, str], dict[str, Any]] = {}
        # Partial runs do not establish winners. Error attempts are counted as failed tasks.
        for run in payload.get("runs", []):
            if (run.get("status") != "complete" or run.get("synthetic", False)
                    or run.get("actual_context") != run.get("context")
                    or run.get("dataset_version") not in QUALIFIED_DATASET_VERSIONS
                    or not run.get("parallel_verified", run.get("loaded_model_metadata", {}).get("parallel") == run.get("settings", {}).get("parallel", 1))):
                continue
            # Aliases are reused when loading candidates. The downloaded source
            # identity, quantization and settings distinguish those candidates.
            model = run.get("source_model") or run.get("model")
            setting = run.get("context")
            if available_models is not None and model not in available_models:
                continue
            if context is not None and setting != context:
                continue
            if minimum_context is not None and (type(setting) is not int or setting < minimum_context):
                continue
            rows = [row for row in run.get("results", [])
                    if row.get("category") in ROLE_CATEGORIES[role] and not row.get("warmup")]
            key = (model, setting, run.get("quantization", "UNKNOWN"),
                   run.get("dataset_sha256", "unknown"), json.dumps(run.get("settings", {}), sort_keys=True))
            groups.setdefault(key, []).extend(rows)
            metadata[key] = run
        routes = []
        for key, rows in groups.items():
            model, setting, quantization, _, _ = key
            run = metadata[key]
            successes = sum(bool(row.get("passed")) for row in rows)
            seconds = sum(float(row.get("wall_seconds", 0)) for row in rows)
            rate = successes / len(rows) if rows else 0
            if len(rows) >= self.minimum_samples and rate >= self.minimum_success_rate and seconds > 0:
                routes.append(Route(role, model, setting, successes * 3600 / seconds, rate,
                                    len(rows), str(self.results_path), run.get("model"),
                                    quantization, run.get("dataset_version")))
        if not routes:
            raise NoMeasuredModel(f"No qualified measured local model for {role}")
        return max(routes, key=lambda route: (route.success_per_hour, route.success_rate))
