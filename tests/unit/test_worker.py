from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from siteforge.agents import AGENTS, AgentRunner, fixture_payload
from siteforge.contracts import AgentContext, AgentResult, AgentType, TaskView
from siteforge.inference_lock import InferenceLock
from siteforge.model_router import ModelRouter
from siteforge.queue import digest
from siteforge.site_factory import read_artifact, write_artifact
from siteforge.worker import LeaseLost, WindowsWorker, WorkerProtocolError, WorkerSettings, validate_supervisor_url


def settings(tmp_path):
    return WorkerSettings("http://127.0.0.1:8000", "unit-worker-token-long-enough", str(uuid4()), tmp_path)


@pytest.fixture(autouse=True)
def isolate_inference_lock(tmp_path, monkeypatch):
    # Worker unit tests must never inspect/recover a real benchmark's live lock.
    monkeypatch.setenv("SITEFORGE_BENCHMARK_RESULTS", str(tmp_path / "benchmark" / "results.json"))


@pytest.fixture
def durable_supervisor(tmp_path):
    from fastapi.testclient import TestClient

    from siteforge.api import create_app
    from siteforge.db import Database
    from siteforge.policy import KNOWN_TOOLS

    config = settings(tmp_path / "artifacts")
    database = Database("sqlite:///" + (tmp_path / "reconnect.db").as_posix())
    database.create_schema()
    org_id = str(uuid4())
    database.provision_org(org_id)
    now = [datetime.now(timezone.utc)]
    tokens = {
        digest_token(config.token): {"subject": "worker", "org_id": org_id, "role": "worker",
            "worker_id": config.worker_id, "capabilities": sorted(KNOWN_TOOLS),
            "expires_at": now[0] + timedelta(hours=1)},
        digest_token("owner-test-token"): {"subject": "owner", "org_id": org_id, "role": "owner"},
    }
    app = create_app(database, tokens)
    app.state.queue.clock = lambda: now[0]
    clients = []

    def connection():
        client = TestClient(app, base_url=config.supervisor_url)
        clients.append(client)
        return client

    owner = connection()
    owner.headers["Authorization"] = "Bearer owner-test-token"
    yield config, owner, connection, now
    for client in clients:
        client.close()
    database.dispose()


def digest_token(value):
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()


def enqueue(owner, role="research", payload=None, key="reconnect"):
    response = owner.post("/v1/tasks", json={"agent_type": role,
        "capability": sorted(AGENTS[AgentType(role)].tools)[0], "input": payload or fixture_payload(),
        "idempotency_key": key})
    response.raise_for_status()
    return response.json()["id"]


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
    task = TaskView.model_validate(task_for(config))
    artifact = write_artifact(tmp_path, "immutable.json", {"fixture": "evidence"})
    result = AgentResult(status="completed", confidence=1, artifacts=[artifact]).model_dump(mode="json")
    data = {"stage": "result", "task_id": task.id, "result": result}
    assert worker._recover_result(task, {"data": data, "sha256": digest(data)}).status == "completed"
    with pytest.raises(WorkerProtocolError):
        worker._recover_result(task, {"data": data, "sha256": "corrupt"})
    wrong = {**data, "task_id": str(uuid4())}
    assert worker._recover_result(task, {"data": wrong, "sha256": digest(wrong)}) is None
    (tmp_path / "immutable.json").write_text("changed", encoding="utf-8")
    assert worker._recover_result(task, {"data": data, "sha256": digest(data)}) is None
    result["artifacts"] = [{"kind": "json", "uri": "missing.json", "sha256": "missing"}]
    assert worker._recover_result(task, {"data": data, "sha256": digest(data)}) is None
    worker.close()


@pytest.mark.parametrize("mode,role,status", [
    ("fixture", "research", "blocked"), ("fixture", "research", "failed"),
    ("bounded_agent", "research", "completed"), ("bounded_agent", "content", "completed"),
    ("fixture", "developer", "completed"), ("fixture", "quality", "completed"),
])
def test_recovery_reruns_noncompleted_or_mutable_work(tmp_path, mode, role, status):
    config = settings(tmp_path)
    worker = WindowsWorker(config, client=httpx.Client(base_url=config.supervisor_url))
    task = TaskView.model_validate({**task_for(config), "agent_type": role, "input": {"mode": mode}})
    artifact = write_artifact(tmp_path, "unchanged.json", {"fixture": "still unchanged"})
    result = AgentResult(status=status, confidence=1, artifacts=[artifact])
    data = {"stage": "result", "task_id": task.id, "result": result.model_dump(mode="json")}
    assert worker._recover_result(task, {"data": data, "sha256": digest(data)}) is None
    worker.close()


@pytest.mark.parametrize("role,expected", [("developer", "completed"), ("quality", "failed")])
def test_reconnect_revalidates_changed_fixture_source(durable_supervisor, role, expected, monkeypatch):
    config, owner, connection, now = durable_supervisor
    runner = AgentRunner(config.artifact_root)
    slug = "reconnect-planner"
    payload = fixture_payload(slug)

    def context(agent_role, task_id=None):
        return AgentContext(task_id=task_id or uuid4(), allowed_tools=sorted(AGENTS[AgentType(agent_role)].tools),
            budget_remaining=0, deadline=datetime.now(timezone.utc) + timedelta(minutes=10))

    assert runner.run("research", context("research"), payload).status == "completed"
    assert runner.run("developer", context("developer"), payload).status == "completed"
    identifier = enqueue(owner, role, payload)
    first = WindowsWorker(config, client=connection(), runner=runner)
    first.register()
    task = TaskView.model_validate(first._request("POST", "/v1/tasks/lease", {
        "worker_id": config.worker_id, "seconds": config.lease_seconds}))
    first._request("POST", f"/v1/tasks/{identifier}/start", first._claim(task))
    result = runner.run(role, context(role, task.id), payload)
    assert result.status == "completed"
    first._request("POST", f"/v1/tasks/{identifier}/checkpoint", {**first._claim(task),
        "data": {"stage": "result", "task_id": identifier, "result": result.model_dump(mode="json")}})
    first.close()  # Disconnect after the result checkpoint, before completion.

    page = config.artifact_root / slug / "source/src/pages/index.astro"
    original = page.read_text(encoding="utf-8")
    page.write_text(original + "\n<!-- changed after the passing checkpoint -->", encoding="utf-8")
    now[0] += timedelta(seconds=config.lease_seconds + 1)
    restarted = WindowsWorker(config, client=connection(), runner=runner)
    restarted.register()
    assert not restarted.run_once()  # Expiry recovery schedules bounded backoff.
    now[0] += timedelta(seconds=31)
    calls = []
    run = runner.run
    def observed_run(*args, **kwargs):
        calls.append(args[0])
        return run(*args, **kwargs)
    monkeypatch.setattr(runner, "run", observed_run)
    assert restarted.run_once()
    record = owner.get(f"/v1/tasks/{identifier}").json()
    assert record["status"] == expected and record["attempt"] == 2
    assert calls == [role]
    if role == "developer":
        assert page.read_text(encoding="utf-8") == original
    else:
        assert not read_artifact(config.artifact_root, f"{slug}/quality/report.json")["static_passed"]
    restarted.close()


@pytest.mark.parametrize("error_code", ["local_model_unavailable", "inference_busy", "model_not_ready"])
def test_transient_agent_failure_retries_after_backoff_and_does_not_reuse_blocked_checkpoint(
        durable_supervisor, error_code):
    config, owner, connection, now = durable_supervisor
    identifier = enqueue(owner, payload={"mode": "bounded_agent"})

    class TransientRunner:
        model_router = None
        calls = 0

        def run(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return AgentResult(status="blocked", confidence=0, retryable=True, error_code=error_code)
            return AgentResult(status="completed", confidence=1, artifacts=[
                write_artifact(config.artifact_root, "retried.json", {"accepted": "internal artifact"})])

    runner = TransientRunner()
    worker = WindowsWorker(config, client=connection(), runner=runner)
    worker.register()
    assert worker.run_once()
    failed = owner.get(f"/v1/tasks/{identifier}").json()
    assert failed["status"] == "retry_scheduled" and failed["attempt"] == 1
    assert failed["error_code"] == error_code
    assert not worker.run_once()
    worker.close()
    now[0] += timedelta(seconds=31)
    restarted = WindowsWorker(config, client=connection(), runner=runner)
    restarted.register()
    assert restarted.run_once()
    completed = owner.get(f"/v1/tasks/{identifier}").json()
    assert completed["status"] == "completed" and completed["attempt"] == 2
    assert runner.calls == 2
    restarted.close()


@pytest.mark.parametrize("error_code", ["policy_blocked", "model_identity_changed"])
def test_permanent_agent_failure_does_not_enter_transient_retry(durable_supervisor, error_code):
    config, owner, connection, _ = durable_supervisor
    identifier = enqueue(owner, payload={"mode": "bounded_agent"})

    class PermanentRunner:
        model_router = None

        def run(self, *args, **kwargs):
            return AgentResult(status="blocked", confidence=0, error_code=error_code)

    worker = WindowsWorker(config, client=connection(), runner=PermanentRunner())
    worker.register()
    assert worker.run_once()
    record = owner.get(f"/v1/tasks/{identifier}").json()
    assert record["status"] == "failed" and record["error_code"] == error_code
    assert not worker.run_once()
    worker.close()


def test_inference_busy_backpressure_preserves_attempts_and_heartbeat(durable_supervisor, tmp_path):
    config, owner, connection, _ = durable_supervisor
    identifier = enqueue(owner)
    router = ModelRouter(tmp_path / "isolated-inference" / "results.json")
    runner = AgentRunner(config.artifact_root, model_router=router)
    worker = WindowsWorker(config, client=connection(), runner=runner)
    worker.register()
    with InferenceLock(router.results_path.with_name(".run.lock"), owner="unit-benchmark"):
        assert not worker.run_once()
        worker.heartbeat_once()
        queued = owner.get(f"/v1/tasks/{identifier}").json()
        assert queued["status"] == "ready" and queued["attempt"] == 0
        assert worker._task is None
    assert worker.run_once()
    assert owner.get(f"/v1/tasks/{identifier}").json()["status"] == "completed"
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
