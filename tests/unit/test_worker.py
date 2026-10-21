from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from siteforge.agents import fixture_payload
from siteforge.contracts import AgentResult
from siteforge.queue import digest
from siteforge.worker import LeaseLost, WindowsWorker, WorkerProtocolError, WorkerSettings, validate_supervisor_url


def settings(tmp_path):
    return WorkerSettings("http://127.0.0.1:8000", "unit-worker-token-long-enough", str(uuid4()), tmp_path)


def test_worker_waits_for_supervisor_when_started_offline(tmp_path, monkeypatch):
    from dataclasses import replace
    config=replace(settings(tmp_path),poll_seconds=.001)
    worker=WindowsWorker(config)
    attempts=[]
    def register():
        attempts.append(1)
        if len(attempts)==1:
            raise httpx.ConnectError('fixture supervisor unavailable')
        worker.stop_event.set()
    monkeypatch.setattr(worker,'register',register)
    worker.run_forever()
    assert len(attempts)==2
    worker.close()


def task_for(worker):
    return {"id": str(uuid4()), "org_id": str(uuid4()), "agent_type": "research", "capability": "write_evidence",
        "input": fixture_payload(), "status": "leased", "idempotency_key": "unit-fixture", "site_id": None,
        "workflow_id": None, "attempt": 1, "max_attempts": 3, "deadline": None,
        "available_at": datetime.now(timezone.utc).isoformat(), "lease_worker_id": worker.worker_id,
        "lease_expires_at": datetime.now(timezone.utc).isoformat(), "lease_token": "long-fencing-token-for-test",
        "budget_cap": "0", "result": None, "error_code": None}


@pytest.mark.parametrize("url", ["http://example.com", "ftp://127.0.0.1", "https://user:secret@example.com",
    "https://example.com/x", "https://example.com?token=x"])
def test_worker_rejects_plain_remote_origins_and_embedded_secrets(url):
    with pytest.raises(ValueError):
        validate_supervisor_url(url)


def test_worker_accepts_tls_or_loopback():
    assert validate_supervisor_url("https://control.example.com/") == "https://control.example.com"
    assert validate_supervisor_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_worker_runs_research_through_real_contract_and_checkpoints(tmp_path):
    config = settings(tmp_path)
    task = task_for(config)
    calls = []
    checkpoints = []

    def handler(request):
        import json
        calls.append(request.url.path)
        if request.url.path.endswith("register"):
            return httpx.Response(200, json={"id": config.worker_id})
        if request.url.path.endswith("/lease"):
            return httpx.Response(200, json=task)
        if request.url.path.endswith("/checkpoint"):
            if request.method == "GET":
                return httpx.Response(200, content=b"null", headers={"content-type": "application/json"})
            value = json.loads(request.content)["data"]
            checkpoints.append(value)
            return httpx.Response(200, json={"data": value, "sha256": digest(value)})
        if request.url.path.endswith(("/start", "/complete")):
            return httpx.Response(200, json=task)
        raise AssertionError(request.url)

    worker = WindowsWorker(config, client=httpx.Client(transport=httpx.MockTransport(handler), base_url=config.supervisor_url))
    worker.register()
    assert worker.run_once()
    assert [item["stage"] for item in checkpoints] == ["started", "result"]
    assert checkpoints[-1]["result"]["status"] == "completed"
    assert calls[-1].endswith("/complete")
    assert (tmp_path / "label-roll-planner/evidence/research.json").exists()
    worker.close()


def test_uncertain_lease_is_not_retried(tmp_path):
    config = settings(tmp_path)
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("simulated response loss", request=request)
    worker = WindowsWorker(config, client=httpx.Client(transport=httpx.MockTransport(handler), base_url=config.supervisor_url),
                           sleeper=lambda _: None)
    with pytest.raises(httpx.ReadTimeout):
        worker.run_once()
    assert len(calls) == 1
    worker.close()


def test_reconnect_is_bounded_and_malformed_output_fails_closed(tmp_path):
    config = settings(tmp_path)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503)
    worker = WindowsWorker(config, client=httpx.Client(transport=httpx.MockTransport(handler), base_url=config.supervisor_url),
                           sleeper=lambda _: None)
    with pytest.raises(httpx.HTTPStatusError):
        worker.register()
    assert len(calls) == 3
    worker.close()
    bad = WindowsWorker(config, client=httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text="not JSON")), base_url=config.supervisor_url))
    with pytest.raises(WorkerProtocolError):
        bad.register()
    bad.close()


def test_checkpoint_cache_requires_checksum_identity_and_artifact_integrity(tmp_path):
    config = settings(tmp_path)
    worker = WindowsWorker(config, client=httpx.Client(base_url=config.supervisor_url))
    task = SimpleNamespace(id=str(uuid4()))
    result = AgentResult(status="completed", confidence=1).model_dump(mode="json")
    data = {"stage": "result", "task_id": task.id, "result": result}
    assert worker._recover_result(task, {"data": data, "sha256": digest(data)}).status == "completed"
    with pytest.raises(WorkerProtocolError):
        worker._recover_result(task, {"data": data, "sha256": "corrupt"})
    wrong = {**data, "task_id": str(uuid4())}
    assert worker._recover_result(task, {"data": wrong, "sha256": digest(wrong)}) is None
    result["artifacts"] = [{"kind": "json", "uri": "missing.json", "sha256": "missing"}]
    assert worker._recover_result(task, {"data": data, "sha256": digest(data)}) is None
    worker.close()


def test_scoped_rejection_never_retries(tmp_path):
    config = settings(tmp_path)
    worker = WindowsWorker(config, client=httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(403)), base_url=config.supervisor_url))
    with pytest.raises(LeaseLost):
        worker.register()
    worker.close()


def test_real_http_worker_to_supervisor_subprocess(tmp_path):
    """Real loopback HTTP and durable file DB; SQLite is not a PG concurrency claim."""
    import hashlib
    import json
    import os
    import socket
    import subprocess
    import sys
    import time
    from datetime import timedelta
    from pathlib import Path

    from siteforge.agents import AGENTS
    from siteforge.contracts import AgentType
    from siteforge.db import Database
    from siteforge.policy import KNOWN_TOOLS

    database_url = "sqlite:///" + (tmp_path / "http-worker.db").as_posix()
    db = Database(database_url)
    db.create_schema()
    org, worker_id = str(uuid4()), str(uuid4())
    db.provision_org(org)
    db.dispose()
    worker_token, owner_token = "worker-" + uuid4().hex, "owner-" + uuid4().hex
    def hashed(value):
        return hashlib.sha256(value.encode()).hexdigest()
    token_config = {
        hashed(worker_token): {"subject": "http-worker", "org_id": org, "role": "worker",
            "worker_id": worker_id, "capabilities": sorted(KNOWN_TOOLS),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()},
        hashed(owner_token): {"subject": "http-owner", "org_id": org, "role": "owner"},
    }
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    environment = {**os.environ, "SITEFORGE_DATABASE_URL": database_url,
                   "SITEFORGE_AUTH_TOKENS": json.dumps(token_config)}
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "siteforge.api:app", "--host", "127.0.0.1",
        "--port", str(port), "--no-access-log"], cwd=Path(__file__).resolve().parents[2], env=environment,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    worker = None
    try:
        with httpx.Client(base_url=origin, timeout=2, trust_env=False,
                          headers={"Authorization": f"Bearer {owner_token}"}) as owner:
            readiness_deadline = time.monotonic() + 45
            while time.monotonic() < readiness_deadline:
                try:
                    if owner.get("/readyz").status_code == 200:
                        break
                except (httpx.NetworkError, httpx.TimeoutException):
                    pass
                if process.poll() is not None:
                    raise AssertionError("Disposable supervisor exited before readiness")
                time.sleep(0.1)
            else:
                raise AssertionError("Disposable supervisor failed readiness")
            config = WorkerSettings(origin, worker_token, worker_id, tmp_path / "artifacts")
            worker = WindowsWorker(config)
            worker.register()
            worker.heartbeat_once()
            previous = None
            task_ids = []
            for role in (AgentType.research, AgentType.developer, AgentType.quality):
                response = owner.post("/v1/tasks", json={"agent_type": role.value,
                    "capability": sorted(AGENTS[role].tools)[0], "input": fixture_payload("http-planner"),
                    "idempotency_key": f"http-{role.value}", "dependencies": [previous] if previous else []})
                response.raise_for_status()
                previous = response.json()["id"]
                task_ids.append(previous)
            for _ in range(3):
                assert worker.run_once()
            assert not worker.run_once()
            for identifier in task_ids:
                value = owner.get(f"/v1/tasks/{identifier}").json()
                assert value["status"] == "completed" and value["result"]["status"] == "completed"
            assert (config.artifact_root / "http-planner/source/src/pages/index.astro").is_file()
            assert (config.artifact_root / "http-planner/quality/report.json").is_file()
            worker.close()
            # Same persistent worker identity reconnects without duplicate registration.
            worker = WindowsWorker(config)
            worker.register()
            worker.heartbeat_once()
            assert not worker.run_once()
    finally:
        if worker:
            worker.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
