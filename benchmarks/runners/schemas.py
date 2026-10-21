"""Response shape constraints contain no expected answer values or enumerations."""
from typing import Any


def shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"type": "object", "properties": {key: shape(item) for key, item in value.items()},
                "required": list(value), "additionalProperties": False}
    if isinstance(value, list):
        return {"type": "array", "items": shape(value[0]) if value else {"type": "string"}}
    if value is None:
        return {"type": ["string", "number", "boolean", "null"]}
    return {"type": "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int)
            else "number" if isinstance(value, float) else "string"}


def response_schema(task: dict[str, Any]) -> dict[str, Any] | None:
    if task.get("tools"):
        return None
    if task["evaluator"] == "coding":
        return shape({"code": ""})
    if task["evaluator"] == "content_slots":
        return shape({"title": "", "facts": [{"key": "", "value": 0.0, "unit": ""}], "advice": "", "citations": [""]})
    if task["evaluator"] == "content":
        return shape({"title": "", "facts": [""], "advice": "", "citations": [""]})
    if task["category"] == "research":
        # Broad nullable answer shape avoids encoding the expected factual type/value.
        schema = shape({"answer": None, "citations": [""]})
        if task.get("answer_json_types"):
            schema["properties"]["answer"] = {"type": task["answer_json_types"]}
        return schema
    return shape(task["expected"])
