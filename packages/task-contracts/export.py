"""Regenerate inspectable versioned task and agent JSON schemas."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from siteforge.contracts import AgentContext, AgentResult, TaskCreate, TaskView


if __name__ == "__main__":
    schema = {"schema_version": 1, "contracts": {
        model.__name__: model.model_json_schema() for model in (AgentContext, AgentResult, TaskCreate, TaskView)}}
    Path(__file__).with_name("schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
