"""Objective fixture graders, schema failures fail closed."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from .safe_python import SafePython


def parse_json(text: str) -> Any:
    # JSON must occupy the complete answer. Fences are tolerated for coding only.
    if len(text) > 100000:
        raise ValueError("Response exceeds grading limit")
    def reject_constant(_value):
        raise ValueError("Non-finite JSON constant")
    return json.loads(text.strip(), parse_constant=reject_constant)


def same_shape(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(same_shape(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return all(isinstance(item, str) for item in actual) if not expected else all(same_shape(item, expected[0]) for item in actual)
    return True


def same_value(actual: Any, expected: Any, *, strict_numbers: bool = True) -> bool:
    if type(expected) in (int, float) and type(actual) in (int, float) and not strict_numbers:
        return actual == expected
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(same_value(actual[key], value, strict_numbers=strict_numbers) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(same_value(a, e, strict_numbers=strict_numbers) for a, e in zip(actual, expected))
    return actual == expected


def grade(task: dict[str, Any], text: str) -> dict[str, Any]:
    result = _grade(task, text)
    # Secondary diagnostic never changes primary strict-schema task success.
    fenced = re.fullmatch(r"\s*```(?:json)?\s*\n?(.*?)\n?```\s*", text, re.DOTALL)
    if fenced:
        diagnostic = _grade(task, fenced.group(1))
        result["diagnostic_fence_stripped"] = {"passed": diagnostic["passed"], "score": diagnostic["score"], "schema_valid": diagnostic["schema_valid"]}
    return result


def _grade(task: dict[str, Any], text: str) -> dict[str, Any]:
    try:
        response = parse_json(text)
    except (ValueError, TypeError, RecursionError):
        return {"passed": False, "schema_valid": False, "score": 0, "reason": "invalid_json"}
    if not isinstance(response, dict):
        return {"passed": False, "schema_valid": False, "score": 0, "reason": "expected_object"}
    kind = task["evaluator"]
    try:
        if kind == "native_tool":
            if set(response) != {"tool_calls"} or len(response["tool_calls"]) != 1:
                raise ValueError("native_tool_schema")
            call = response["tool_calls"][0]
            if call.get("type") != "function" or not isinstance(call.get("id"), str) or not call["id"]:
                raise ValueError("native_tool_schema")
            function = call["function"]
            arguments = parse_json(function["arguments"])
            normalized = {"action": function["name"], "arguments": arguments}
            passed = same_value(normalized, task["expected"])
            valid = same_shape(normalized, task["expected"])
            return {"passed": passed, "schema_valid": valid, "score": int(passed), "reason": "native_tool_arguments"}
        if kind == "exact":
            passed = same_value(response, task["expected"], strict_numbers=not (task["category"] == "research" and task.get("version") == "1.2.0"))
            valid = same_shape(response, task["expected"])
            if task["category"] == "research":
                valid = set(response) == {"answer", "citations"} and type(response["answer"]) in (str, int, float, bool, type(None)) and isinstance(response["citations"], list) and all(isinstance(citation, str) for citation in response["citations"])
            return {"passed": passed, "schema_valid": valid, "score": int(passed), "reason": "exact_match" if passed else "answer_mismatch"}
        if kind == "coding":
            if set(response) != {"code"} or not isinstance(response["code"], str):
                raise ValueError("code_schema")
            interpreter = SafePython(response["code"])
            results = [same_value(interpreter.solve(deepcopy(test["input"])), test["expected"], strict_numbers=False) for test in task["tests"]]
            return {"passed": all(results), "schema_valid": True, "score": sum(results) / len(results),
                    "reason": "executable_fixture_tests", "tests_passed": sum(results), "tests_total": len(results)}
        if kind == "content":
            expected = task["expected"]
            if set(response) != {"title", "facts", "advice", "citations"}:
                raise ValueError("content_schema")
            if not isinstance(response["title"], str) or not 8 <= len(response["title"]) <= 90:
                raise ValueError("title_schema")
            facts = response["facts"]
            if not isinstance(facts, list) or any(not isinstance(fact, str) for fact in facts):
                raise ValueError("facts_schema")
            fact_text = " ".join(facts).lower()
            advice = response["advice"]
            if not isinstance(advice, str) or len(advice.split()) > 80:
                raise ValueError("advice_schema")
            checks = [all(re.search(r"(?<![\d.])" + re.escape(term.lower()) + r"(?![\d.])", fact_text) for term in expected["facts"]),
                      all(term.lower() in advice.lower() for term in expected["advice"]),
                      response["citations"] == expected["citations"],
                      not any(term.lower() in fact_text + " " + advice.lower() for term in expected.get("forbidden", []))]
            return {"passed": all(checks), "schema_valid": True, "score": sum(checks) / len(checks), "reason": "factual_and_actionable_constraints"}
        raise ValueError("unknown_evaluator")
    except (ValueError, TypeError, KeyError, ArithmeticError, IndexError, AttributeError, RecursionError) as error:
        return {"passed": False, "schema_valid": kind == "coding" and "code" in response,
                "score": 0, "reason": f"rejected:{type(error).__name__}"}
