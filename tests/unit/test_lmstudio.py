import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from siteforge.lmstudio import LMStudioClient, LMStudioError


@pytest.fixture
def lm_server():
    class Handler(BaseHTTPRequestHandler):
        mode = "ok"
        request_body = None

        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "fixture-model"}]}).encode())

        def do_POST(self):
            Handler.request_body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if Handler.mode == "http_error":
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            events = [{"model": "fixture-model", "choices": [{"delta": {"content": '{"ok":'}, "finish_reason": None}]},
                      {"choices": [{"delta": {"content": "true}"}, "finish_reason": "stop"}]},
                      {"choices": [], "usage": {"completion_tokens": 5, "prompt_tokens": 3}}]
            if Handler.mode == "missing_finish":
                events = events[:1]
            if Handler.mode == "tools":
                events = [{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "search", "arguments": '{"query":'}}]}, "finish_reason": None}]},
                          {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"roof"}'}}]}, "finish_reason": "tool_calls"}]}]
            if Handler.mode == "malformed":
                self.wfile.write(b"data: {broken\n\n")
                return
            for event in events:
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield LMStudioClient(f"http://127.0.0.1:{server.server_port}"), Handler
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.mark.parametrize("url", ["http://example.com:1234", "http://192.168.1.1:1234", "https://localhost", "http://user:password@localhost", "http://localhost?secret=a"])
def test_loopback_only(url):
    with pytest.raises(ValueError):
        LMStudioClient(url)


def test_stream_measurements_and_raw_usage(lm_server):
    client, handler = lm_server
    result = client.complete([{"role": "user", "content": "test"}], "fixture-model")
    assert result.text == '{"ok":true}'
    assert result.output_tokens == 5
    assert 0 <= result.time_to_first_token_seconds <= result.latency_seconds
    assert result.tokens_per_second > 0
    assert result.chunks == 2
    assert handler.request_body["stream_options"]["include_usage"] is True
    assert client.list_models() == [{"id": "fixture-model"}]


@pytest.mark.parametrize("mode", ["http_error", "malformed", "missing_finish"])
def test_stream_errors_fail_closed(lm_server, mode):
    client, handler = lm_server
    handler.mode = mode
    with pytest.raises(LMStudioError):
        client.complete([{"role": "user", "content": "test"}], "fixture-model")


def test_native_tool_fragments_reassembled(lm_server):
    client, handler = lm_server
    handler.mode = "tools"
    result = client.complete([{"role": "user", "content": "test"}], "fixture-model")
    call = json.loads(result.text)["tool_calls"][0]
    assert call["function"] == {"name": "search", "arguments": '{"query":"roof"}'}
    assert result.output_tokens is None
    assert result.tokens_per_second is None


def test_structured_response_schema_is_sent_without_answer_values(lm_server):
    client, handler = lm_server
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
    client.complete([{"role": "user", "content": "test"}], "fixture-model", response_schema=schema)
    assert handler.request_body["response_format"] == {"type": "json_schema", "json_schema": {"name": "siteforge_response", "strict": True, "schema": schema}}
