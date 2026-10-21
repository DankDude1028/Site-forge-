"""An isolated, actual loopback HTTP/process recovery drill, never a 72h claim.

Only fixture tasks execute. The subprocess API uses zero retry backoff so the
drill can observe a real minimum-length lease expiry without another 30s wait.
It never reads .env, starts inference, or contacts an external provider.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import sysconfig
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import httpx

from .agents import AgentRunner, fixture_payload
from .contracts import AgentContext, AgentResult, AgentType
from .db import Database, Task
from .policy import KNOWN_TOOLS
from .site_factory import read_artifact, write_artifact
from .worker import WindowsWorker, WorkerSettings

LEASE_SECONDS = 15
REPOSITORY = Path(__file__).resolve().parents[1]


class RuntimeDrillError(RuntimeError):
    pass


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _database_url(root: Path) -> str:
    return "sqlite:///" + (root / "fixture.sqlite").as_posix()


def _fixture_root() -> Path:
    root = Path(os.environ["SITEFORGE_RUNTIME_DRILL_ROOT"]).resolve(strict=True)
    marker = read_artifact(root, "drill.json")
    if (marker.get("run_id") != os.environ.get("SITEFORGE_RUNTIME_DRILL_ID")
            or os.environ.get("SITEFORGE_DATABASE_URL") != _database_url(root)):
        raise RuntimeDrillError("Refusing a non-fixture drill database")
    return root


def create_drill_app() -> Any:
    """Subprocess-only factory, bound to this drill's existing SQLite fixture."""
    root = _fixture_root()
    from .api import create_app
    app = create_app()
    app.state.queue.retry_backoff = (0, 0, 0)
    write_artifact(root, "supervisor-process.json", {"pid": os.getpid(), "at": _stamp()})
    return app


def _worker(phase: str) -> None:
    root = _fixture_root()
    config = WorkerSettings(os.environ["SITEFORGE_SUPERVISOR_URL"], os.environ["SITEFORGE_WORKER_TOKEN"],
        os.environ["SITEFORGE_WORKER_ID"], root / "artifacts", heartbeat_seconds=2,
        lease_seconds=LEASE_SECONDS, poll_seconds=.1)
    if phase == "checkpoint":
        class CheckpointRunner(AgentRunner):
            def run(self, role: AgentType | str, context: AgentContext, payload: dict[str, Any],
                    checkpoint: dict[str, Any] | None = None) -> AgentResult:
                result = super().run(role, context, payload, checkpoint)
                task = worker._task
                if role != "research" or result.status != "completed" or task is None:
                    raise RuntimeDrillError("Unexpected checkpoint task")
                data = {"stage": "result", "task_id": task.id, "result": result.model_dump(mode="json")}
                stored = worker._request("POST", f"/v1/tasks/{task.id}/checkpoint", {
                    **worker._claim(task), "data": data})
                write_artifact(root, "worker-checkpoint.json", {"pid": os.getpid(), "at": _stamp(),
                    "task_id": task.id, "checkpoint_id": stored["id"], "checkpoint_sha256": stored["sha256"]})
                # The parent kills only this owned process after observing the
                # durable checkpoint. The heartbeat remains active until then.
                threading.Event().wait(90)
                raise RuntimeDrillError("Parent did not stop checkpoint worker")

        runner: AgentRunner = CheckpointRunner(config.artifact_root)
    else:
        runner = AgentRunner(config.artifact_root)
    worker = WindowsWorker(config, runner=runner)
    try:
        worker.register()
        worker.start_heartbeat()
        if phase == "checkpoint":
            worker.run_once()
        else:
            processed = 0
            deadline = time.monotonic() + 15
            while processed < 3 and time.monotonic() < deadline:
                if worker.run_once():
                    processed += 1
                else:
                    time.sleep(.1)
            if processed != 3:
                raise RuntimeDrillError("Recovery worker did not finish the fixture chain")
            write_artifact(root, "worker-complete.json", {"pid": os.getpid(), "at": _stamp(),
                "processed_tasks": processed})
    finally:
        worker.close()


def _wait_for(condition: Callable[[], bool], timeout: float, stage: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(.1)
    raise RuntimeDrillError(f"Timed out during {stage}")


def run_drill(root: Path, *, startup_timeout: float = 30) -> dict[str, Any]:
    """Run against a fresh directory; retain its DB/artifacts and safe evidence.

    SQLite is deliberate. A PostgreSQL URL is not accepted, so this cannot touch
    an operator's database or imply PostgreSQL process/endurance acceptance.
    """
    if not 1 <= startup_timeout <= 90:
        raise ValueError("startup_timeout must be between 1 and 90 seconds")
    if root.is_symlink():
        raise ValueError("Drill directory cannot be linked")
    root = root.resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("Drill requires a new or empty directory; existing evidence is preserved")
    root.mkdir(parents=True, exist_ok=True)
    run_id, org_id, worker_id = (str(uuid4()) for _ in range(3))
    write_artifact(root, "drill.json", {"run_id": run_id, "started_at": _stamp()})
    database = Database(_database_url(root))
    database.create_schema()
    database.provision_org(org_id, "Isolated runtime drill fixture")
    database.dispose()
    owner_token, worker_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    tokens = {
        _hash_token(owner_token): {"subject": "drill-owner", "org_id": org_id, "role": "owner"},
        _hash_token(worker_token): {"subject": "drill-worker", "org_id": org_id, "role": "worker",
            "worker_id": worker_id, "capabilities": sorted(KNOWN_TOOLS),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
    }
    with socket.socket() as port_probe:
        port_probe.bind(("127.0.0.1", 0))
        port = port_probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    # Do not inherit provider tokens, user .env or a real database connection.
    allowed_environment = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
                           "USERPROFILE", "APPDATA", "LOCALAPPDATA"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed_environment}
    environment.update({"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1", "PYTHONPATH": os.pathsep.join((str(REPOSITORY), sysconfig.get_path("purelib"))),
        "SITEFORGE_RUNTIME_DRILL_ROOT": str(root), "SITEFORGE_RUNTIME_DRILL_ID": run_id,
        "SITEFORGE_DATABASE_URL": _database_url(root), "SITEFORGE_AUTH_TOKENS": json.dumps(tokens),
        "SITEFORGE_SUPERVISOR_URL": origin, "SITEFORGE_WORKER_TOKEN": worker_token,
        "SITEFORGE_WORKER_ID": worker_id})
    started = time.monotonic()
    report: dict[str, Any] = {"run_id": run_id, "status": "running", "started_at": _stamp(),
        "scope": "actual isolated SQLite supervisor and HTTP WindowsWorker subprocess fault drill",
        "is_72_hour_acceptance": False, "postgresql_tested": False,
        "lease_seconds": LEASE_SECONDS, "fixture_retry_backoff_seconds": [0, 0, 0],
        "events": [], "processes": [], "external_provider_calls": 0, "model_calls": 0}
    processes: list[tuple[subprocess.Popen[bytes], dict[str, Any]]] = []
    # Windows venv python.exe may be a redirector with a second interpreter PID.
    # Launch the actual runtime with this venv's packages explicitly on its path.
    interpreter = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve(strict=True))

    def event(name: str, **values: Any) -> None:
        report["events"].append({"event": name, "at": _stamp(),
            "elapsed_seconds": round(time.monotonic() - started, 3), **values})
        # Preserve owned PIDs even if the parent is interrupted mid-drill.
        write_artifact(root, "report.json", report)

    def launch(kind: str, arguments: list[str]) -> subprocess.Popen[bytes]:
        process = subprocess.Popen([interpreter, *arguments], cwd=REPOSITORY, env=environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        record = {"kind": kind, "pid": process.pid, "started_at": _stamp(), "exit_code": None}
        processes.append((process, record))
        report["processes"].append(record)
        event("process_started", kind=kind, pid=process.pid)
        return process

    def stop(process: subprocess.Popen[bytes], *, abrupt: bool) -> None:
        record = next(record for owned, record in processes if owned is process)
        if record["exit_code"] is not None:
            return
        if process.poll() is None:
            process.kill() if abrupt else process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)
        record.update(exit_code=process.returncode, stopped_at=_stamp())
        event("process_stopped", pid=process.pid, abrupt=abrupt, exit_code=process.returncode)

    def api() -> subprocess.Popen[bytes]:
        return launch("supervisor", ["-m", "uvicorn", "siteforge.runtime_drill:create_drill_app", "--factory",
            "--host", "127.0.0.1", "--port", str(port), "--no-access-log", "--log-level", "error"])

    stage = "start"
    failure: Exception | None = None
    with httpx.Client(base_url=origin, timeout=1, trust_env=False, follow_redirects=False,
                      headers={"Authorization": "Bearer " + owner_token}) as client:
        def ready() -> bool:
            try:
                return client.get("/readyz").status_code == 200
            except httpx.HTTPError:
                return False

        def request(method: str, path: str, **kwargs: Any) -> Any:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        def alive_until(process: subprocess.Popen[bytes], condition: Callable[[], bool]) -> bool:
            if process.poll() is not None:
                raise RuntimeDrillError("Owned subprocess exited before its readiness evidence")
            return condition()

        try:
            supervisor = api()
            stage = "initial API readiness"
            _wait_for(lambda: alive_until(supervisor, ready), startup_timeout, stage)
            if read_artifact(root, "supervisor-process.json")["pid"] != supervisor.pid:
                raise RuntimeDrillError("Supervisor runtime PID differs from its owned process")
            event("supervisor_ready", pid=supervisor.pid)
            previous = None
            identifiers = []
            for role, capability in (("research", "read_sources"), ("developer", "edit_sandbox"),
                                     ("quality", "inspect_preview")):
                task = request("POST", "/v1/tasks", json={"agent_type": role, "capability": capability,
                    "input": fixture_payload("runtime-drill-planner"), "dependencies": [previous] if previous else [],
                    "idempotency_key": f"runtime-drill:{run_id}:{role}"})
                previous = task["id"]
                identifiers.append(previous)
            report["task_ids"] = identifiers
            checkpoint_worker = launch("checkpoint_worker", ["-m", "siteforge.runtime_drill", "--worker-phase", "checkpoint"])
            stage = "durable worker checkpoint"
            _wait_for(lambda: alive_until(checkpoint_worker, lambda: (root / "worker-checkpoint.json").is_file()),
                      startup_timeout, stage)
            checkpoint = read_artifact(root, "worker-checkpoint.json")
            if checkpoint["pid"] != checkpoint_worker.pid or checkpoint["task_id"] != identifiers[0]:
                raise RuntimeDrillError("Checkpoint process or task identity mismatch")
            report["checkpoint"] = checkpoint
            event("checkpoint_persisted", task_id=identifiers[0], sha256=checkpoint["checkpoint_sha256"])
            stage = "owned process interruption"
            stop(checkpoint_worker, abrupt=True)
            stop(supervisor, abrupt=True)
            # Retain the old fence in memory only; never persist a task credential.
            # Both writers are stopped before reading the final committed expiry.
            database = Database(_database_url(root))
            with database.session() as session:
                row = session.get(Task, identifiers[0])
                if row is None or not row.lease_token or row.lease_worker_id != worker_id:
                    raise RuntimeDrillError("Checkpoint lacks its durable worker lease")
                old_token, expires_at = row.lease_token, row.lease_expires_at
            database.dispose()
            if expires_at is None:
                raise RuntimeDrillError("Checkpoint lacks lease expiry")
            try:
                client.get("/readyz")
            except (httpx.NetworkError, httpx.TimeoutException) as error:
                event("http_outage_observed", error_type=type(error).__name__)
            else:
                raise RuntimeDrillError("Owned API stop did not produce an HTTP outage")
            supervisor = api()
            stage = "restarted API readiness"
            _wait_for(lambda: alive_until(supervisor, ready), startup_timeout, stage)
            if read_artifact(root, "supervisor-process.json")["pid"] != supervisor.pid:
                raise RuntimeDrillError("Restarted supervisor PID differs from its owned process")
            event("supervisor_restarted", pid=supervisor.pid)
            restored = request("GET", f"/v1/tasks/{identifiers[0]}/checkpoint")
            if restored["sha256"] != checkpoint["checkpoint_sha256"]:
                raise RuntimeDrillError("Checkpoint changed across supervisor process restart")
            event("checkpoint_survived_process_restart", sha256=restored["sha256"])
            stage = "real lease expiry"
            _wait_for(lambda: datetime.now(timezone.utc) > expires_at + timedelta(milliseconds=100),
                      LEASE_SECONDS + 5, stage)
            event("lease_expired", persisted_expires_at=expires_at.isoformat())
            recovery_worker = launch("recovery_worker", ["-m", "siteforge.runtime_drill", "--worker-phase", "complete"])
            stage = "reconnected HTTP worker chain"
            _wait_for(lambda: recovery_worker.poll() is not None, startup_timeout, stage)
            if recovery_worker.returncode != 0:
                raise RuntimeDrillError("Recovery worker subprocess failed")
            completion = read_artifact(root, "worker-complete.json")
            if completion["pid"] != recovery_worker.pid or completion["processed_tasks"] != 3:
                raise RuntimeDrillError("Recovery worker evidence mismatch")
            records = [request("GET", f"/v1/tasks/{identifier}") for identifier in identifiers]
            if any(record["status"] != "completed" or record["result"]["status"] != "completed" for record in records):
                raise RuntimeDrillError("Fixture task chain did not complete")
            attempts = [record["attempt"] for record in records]
            if attempts != [2, 1, 1]:
                raise RuntimeDrillError("Lease expiry did not produce the expected durable retry")
            quality = read_artifact(root / "artifacts", "runtime-drill-planner/quality/report.json")
            if quality["static_passed"] is not True:
                raise RuntimeDrillError("Trusted preview failed actual static QA")
            stale = client.post(f"/v1/tasks/{identifiers[0]}/complete", headers={
                "Authorization": "Bearer " + worker_token}, json={"worker_id": worker_id,
                "lease_token": old_token, "result": {"status": "completed", "forged": True}})
            if stale.status_code not in {403, 409}:
                raise RuntimeDrillError("Expired worker fence was accepted")
            event("stale_completion_rejected", status_code=stale.status_code)
            report["tasks"] = [{"id": record["id"], "agent_type": record["agent_type"],
                "status": record["status"], "attempt": record["attempt"],
                "artifact_hashes": [artifact["sha256"] for artifact in record["result"]["artifacts"]]}
                for record in records]
            report["quality_static_passed"] = True
            report["recovery_worker"] = completion
            event("fixture_chain_completed", attempts=attempts)
            report["status"] = "passed"
        except Exception as error:
            failure = error
            report.update(status="failed", failed_stage=stage, error_type=type(error).__name__)
        finally:
            for process, _ in reversed(processes):
                stop(process, abrupt=False)
            report["owned_subprocesses_cleaned"] = all(process.poll() is not None for process, _ in processes)
            report["finished_at"] = _stamp()
            report["elapsed_seconds"] = round(time.monotonic() - started, 3)
            write_artifact(root, "report.json", report)
    if failure is not None:
        raise RuntimeDrillError(f"Runtime drill failed during {stage}; inspect its retained report.json") from None
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--worker-phase", choices=("checkpoint", "complete"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_phase:
        _worker(args.worker_phase)
        return
    if args.root is None:
        parser.error("--root requires a new or empty isolated evidence directory")
    try:
        report = run_drill(args.root)
    except (RuntimeDrillError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps({key: report[key] for key in ("run_id", "status", "elapsed_seconds", "is_72_hour_acceptance")}))


if __name__ == "__main__":
    main()
