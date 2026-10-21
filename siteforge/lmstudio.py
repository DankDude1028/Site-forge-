"""Loopback-only LM Studio OpenAI adapter with measured streaming timings.

No implicit paid fallback, model download, or model loading is performed here.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class LMStudioError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    latency_seconds: float
    time_to_first_token_seconds: float | None
    output_tokens: int | None
    tokens_per_second: float | None
    finish_reason: str | None
    usage: dict[str, Any]
    chunks: int
    reasoning_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LMStudioClient:
    def __init__(self, base_url: str = "http://127.0.0.1:1234", *, timeout: float = 120,
                 api_key: str | None = None) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("LM Studio requires a plain loopback HTTP endpoint")
        try:
            local = ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            local = parsed.hostname == "localhost"
        if not local:
            raise ValueError("LM Studio must remain on loopback")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def _request(self, path: str, payload: dict[str, Any] | None = None):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self.base_url + path, headers=headers,
                          data=None if payload is None else json.dumps(payload).encode())
        try:
            # Ignore proxy environment variables and reject redirects off loopback.
            return build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=self.timeout)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            # Never expose response bodies, which could contain secrets or untrusted instructions.
            raise LMStudioError(f"LM Studio request failed: {type(error).__name__}") from error

    def list_models(self) -> list[dict[str, Any]]:
        with self._request("/v1/models") as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise LMStudioError("Malformed LM Studio model list")
        return payload["data"]

    def model_metadata(self) -> dict[str, Any]:
        """Native metadata is best effort; absent information stays explicitly unknown."""
        for path in ("/api/v1/models", "/api/v0/models"):
            try:
                with self._request(path) as response:
                    return {"endpoint": path, "response": json.load(response)}
            except (LMStudioError, ValueError):
                continue
        return {"endpoint": None, "response": None}

    def complete(self, messages: list[dict[str, str]], model: str, *,
                 max_tokens: int = 512, temperature: float = 0,
                 tools: list[dict[str, Any]] | None = None,
                 response_schema: dict[str, Any] | None = None,
                 seed: int = 17) -> Completion:
        if not model or not messages or max_tokens < 1 or max_tokens > 32768:
            raise ValueError("Invalid completion request")
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature,
                                   "max_tokens": max_tokens, "seed": seed, "stream": True,
                                   "stream_options": {"include_usage": True}}
        if tools:
            payload["tools"] = tools
        if response_schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "siteforge_response", "strict": True, "schema": response_schema}}
        start = time.perf_counter()
        first: float | None = None
        parts: list[str] = []
        reasoning: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        usage: dict[str, Any] = {}
        finish: str | None = None
        actual_model = model
        chunks = 0
        try:
            with self._request("/v1/chat/completions", payload) as response:
                for raw in response:
                    if not raw.startswith(b"data:"):
                        continue
                    data = raw[5:].strip()
                    if data == b"[DONE]":
                        break
                    event = json.loads(data)
                    if not isinstance(event, dict):
                        raise LMStudioError("Malformed stream event")
                    if event.get("error"):
                        raise LMStudioError("LM Studio returned a stream error")
                    actual_model = event.get("model", actual_model)
                    if event.get("usage"):
                        usage = event["usage"]
                    for choice in event.get("choices", []):
                        delta = choice.get("delta", {})
                        content = delta.get("content") or ""
                        thought = delta.get("reasoning_content") or delta.get("reasoning") or ""
                        calls = delta.get("tool_calls") or []
                        if content or thought or calls:
                            if first is None:
                                first = time.perf_counter() - start
                            chunks += 1
                        parts.append(content)
                        reasoning.append(thought)
                        for call in calls:
                            index = call.get("index", 0)
                            current = tool_calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                            if call.get("id"):
                                current["id"] += call["id"]
                            for key in ("name", "arguments"):
                                current["function"][key] += call.get("function", {}).get(key, "")
                        finish = choice.get("finish_reason") or finish
        except (ValueError, TimeoutError, OSError, AttributeError, TypeError) as error:
            raise LMStudioError(f"Invalid or incomplete completion stream: {type(error).__name__}") from error
        elapsed = time.perf_counter() - start
        if finish is None:
            raise LMStudioError("Stream ended without a finish reason")
        output_tokens = usage.get("completion_tokens")
        if not isinstance(output_tokens, int):
            output_tokens = None
        rate = output_tokens / (elapsed - first) if output_tokens and first is not None and elapsed > first else None
        result_text = "".join(parts)
        if tool_calls:
            result_text = json.dumps({"tool_calls": list(tool_calls.values())})
        return Completion(result_text, actual_model, elapsed, first, output_tokens, rate,
                          finish, usage, chunks, "".join(reasoning))

    async def acomplete(self, *args: Any, **kwargs: Any) -> Completion:
        return await asyncio.to_thread(self.complete, *args, **kwargs)

    async def generate(self, prompt: str, model: str, **kwargs: Any) -> str:
        result = await self.acomplete([{"role": "user", "content": prompt}], model, **kwargs)
        return result.text
