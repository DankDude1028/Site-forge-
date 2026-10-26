"""Export role manifests from the executable policy registry."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from siteforge.agents import AGENTS


if __name__ == "__main__":
    for role, spec in AGENTS.items():
        destination = Path(__file__).parent / role.value / "contract.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"schema_version": 1, "role": role.value,
            "allowed_tools": sorted(spec.tools), "max_attempts": spec.max_attempts,
            "max_cost_usd": str(spec.max_cost_usd), "escalation": spec.escalation,
            "inputs": "AgentContext", "outputs": "AgentResult", "fixture_mode_explicit": True,
            "model_proposals_execute": False}, indent=2) + "\n", encoding="utf-8")
