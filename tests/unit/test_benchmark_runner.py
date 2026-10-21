"""Runner control-flow tests use in-memory model responses, never GPU inference."""
import json
import os
import re
import sys

import pytest

from benchmarks.runners import run as module
from siteforge.lmstudio import Completion
from benchmarks.runners.telemetry import command, windows_file_version


class NoHardwareTelemetry:
    samples = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def summary(self):
        return {"samples": 0, "measurement": "test_fixture"}


@pytest.fixture
def fake_environment(monkeypatch):
    tasks, _ = module.load_tasks()
    by_prompt = {task["prompt"]: task for task in tasks}
    calls = []

    class FakeClient:
        interrupt_at = None

        def __init__(self, *_args, **_kwargs):
            pass

        def model_metadata(self):
            return {"test_fixture": True}

        def list_models(self):
            return [{"id": "fixture-alias"}]

        def complete(self, messages, model, **kwargs):
            calls.append(messages)
            if self.interrupt_at == len(calls):
                raise KeyboardInterrupt()
            task = by_prompt[messages[-1]["content"]]
            expected = task["expected"]
            if task.get("tools"):
                expected = {"tool_calls": [{"id": "fixture-call", "type": "function", "function": {"name": expected["action"], "arguments": json.dumps(expected["arguments"])}}]}
            return Completion(json.dumps(expected), model, .02, .01, 5, 500, "stop", {"completion_tokens": 5}, 2)

    def host_inventory():
        return {"lms_loaded_models": {"exit_code": 0, "stdout": json.dumps([{
            "type": "llm", "modelKey": "fixture-source", "identifier": "fixture-alias",
            "contextLength": 4096, "parallel": 1, "quantization": {"name": "Q4_K_M"}}])}}

    monkeypatch.setattr(module, "LMStudioClient", FakeClient)
    monkeypatch.setattr(module, "Telemetry", NoHardwareTelemetry)
    monkeypatch.setattr(module, "inventory", host_inventory)
    return FakeClient, calls


def arguments(tmp_path):
    return module.parser().parse_args(["--model", "fixture-alias", "--source-model", "fixture-source",
        "--quantization", "Q4_K_M", "--context", "4096", "--limit", "2", "--warmups", "0",
        "--output", str(tmp_path), "--structured-json"])


def test_interruption_and_resume_skip_saved_pairs(tmp_path, fake_environment):
    client, calls = fake_environment
    client.interrupt_at = 2
    args = arguments(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        module.run(args)
    snapshot = json.loads((tmp_path / "results.json").read_text())
    assert snapshot["runs"][0]["status"] == "interrupted"
    assert len(snapshot["runs"][0]["results"]) == 1
    assert not (tmp_path / ".run.lock").exists()
    client.interrupt_at = None
    args.resume = True
    resumed = module.run(args)
    assert resumed["status"] == "partial"
    assert len(resumed["results"]) == 2
    assert len(calls) == 3
    assert resumed["actual_context"] == 4096
    assert resumed["summary"]["passed"] == 2
    assert len(json.loads((tmp_path / "results.json").read_text())["runs"]) == 1


def test_context_mismatch_is_recorded_and_fails_closed(tmp_path, fake_environment):
    args = arguments(tmp_path)
    args.context = 8192
    with pytest.raises(RuntimeError, match="context"):
        module.run(args)
    run = json.loads((tmp_path / "results.json").read_text())["runs"][0]
    assert run["status"] == "setup_failed"
    assert run["results"] == []
    assert not (tmp_path / ".run.lock").exists()


def test_exclusive_lock_prevents_concurrent_runs(tmp_path, fake_environment):
    (tmp_path / ".run.lock").write_text('{"pid":123}')
    with pytest.raises(RuntimeError, match="Another benchmark"):
        module.run(arguments(tmp_path))
    assert (tmp_path / ".run.lock").exists()


def test_subprocess_telemetry_decodes_unicode_and_malformed_bytes():
    result = command([sys.executable, "-c", "import sys;sys.stdout.buffer.write('✓模型'.encode('utf-8') + bytes([255]));sys.stderr.buffer.write('échec'.encode('utf-8'))"])
    assert result["exit_code"] == 0
    assert result["stdout"] == "✓模型\ufffd"
    assert result["stderr"] == "échec"


@pytest.mark.skipif(os.name != "nt", reason="Windows executable VERSIONINFO")
def test_actual_windows_executable_version_is_recorded():
    version = windows_file_version(os.path.join(os.environ["SystemRoot"], "System32", "kernel32.dll"))
    assert version is not None
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version["file_version"])
