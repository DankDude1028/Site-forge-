"""Outbound-only, serial Windows worker. No arbitrary-command endpoint exists."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import ValidationError

from siteforge.agents import AGENTS, AgentRunner
from siteforge.contracts import AgentContext, AgentResult, AgentType, TaskView
from siteforge.inference_lock import InferenceBusy, ensure_inference_available
from siteforge.lmstudio import LMStudioClient, LMStudioError
from siteforge.model_router import ModelRouter
from siteforge.policy import KNOWN_TOOLS
from siteforge.queue import digest
from siteforge.site_factory import scoped_path

LOG = logging.getLogger("siteforge.worker")


class WorkerProtocolError(RuntimeError):
    pass


class LeaseLost(RuntimeError):
    pass


def validate_supervisor_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Supervisor URL must be a configured origin without credentials")
    if parsed.path not in {"", "/"}:
        raise ValueError("Supervisor URL must be an origin")
    try:
        loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = parsed.hostname == "localhost"
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ValueError("Supervisor requires TLS except for loopback development")
    return value.rstrip("/")


@dataclass(frozen=True)
class WorkerSettings:
    supervisor_url: str
    token: str
    worker_id: str
    artifact_root: Path
    name: str = "siteforge-windows"
    capabilities: tuple[str, ...] = tuple(sorted(KNOWN_TOOLS))
    heartbeat_seconds: float = 30
    lease_seconds: int = 120
    poll_seconds: float = 5
    reconnect_attempts: int = 3

    def __post_init__(self) -> None:
        validate_supervisor_url(self.supervisor_url)
        UUID(self.worker_id)
        if len(self.token) < 20:
            raise ValueError("Provide a scoped worker token through the environment")
        if not self.capabilities or not set(self.capabilities) <= KNOWN_TOOLS:
            raise ValueError("Unknown or empty worker capabilities")
        if not 15 <= self.lease_seconds <= 600 or not 0 < self.heartbeat_seconds < self.lease_seconds / 2:
            raise ValueError("Heartbeat must leave room to renew the lease")
        if not 1 <= self.reconnect_attempts <= 5 or self.poll_seconds <= 0:
            raise ValueError("Invalid retry or polling configuration")

    @classmethod
    def from_env(cls) -> WorkerSettings:
        return cls(supervisor_url=os.environ.get("SITEFORGE_SUPERVISOR_URL") or os.environ.get(
                       "SITEFORGE_API_URL", "http://127.0.0.1:8080"),
                   token=os.environ["SITEFORGE_WORKER_TOKEN"], worker_id=os.environ["SITEFORGE_WORKER_ID"],
                   artifact_root=Path(os.environ.get("SITEFORGE_ARTIFACT_ROOT", "artifacts/worker")),
                   name=os.environ.get("SITEFORGE_WORKER_NAME", "siteforge-windows"),
                   capabilities=tuple(filter(None, os.environ.get("SITEFORGE_WORKER_CAPABILITIES",
                                                               ",".join(sorted(KNOWN_TOOLS))).split(","))))


class WindowsWorker:
    def __init__(self, settings: WorkerSettings, *, client: httpx.Client | None = None,
                 runner: AgentRunner | None = None, sleeper: Any = time.sleep) -> None:
        self.settings = settings
        self.client = client or httpx.Client(base_url=validate_supervisor_url(settings.supervisor_url),
                                            headers={"Authorization": f"Bearer {settings.token}"},
                                            timeout=20, follow_redirects=False, trust_env=False)
        self.runner = runner or AgentRunner(settings.artifact_root,
            model_client=LMStudioClient(base_url=os.environ.get("SITEFORGE_LMSTUDIO_URL", "http://127.0.0.1:1234"),
                                       api_key=os.environ.get("LM_STUDIO_API_KEY")),
            model_router=ModelRouter(os.environ.get("SITEFORGE_BENCHMARK_RESULTS", "benchmarks/results/results.json")))
        self.sleeper = sleeper
        self.stop_event = threading.Event()
        self.lease_lost = threading.Event()
        self._task: TaskView | None = None
        self._lock = threading.Lock()
        self._heartbeat: threading.Thread | None = None

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None,
                 *, retry_safe: bool = True) -> Any:
        attempts = self.settings.reconnect_attempts if retry_safe else 1
        for attempt in range(attempts):
            try:
                response = self.client.request(method, path, json=payload, follow_redirects=False,
                                               headers={"Authorization": f"Bearer {self.settings.token}"})
                if response.status_code in {408, 429, 500, 502, 503, 504} and attempt + 1 < attempts:
                    self.sleeper(min(2 ** attempt, 8))
                    continue
                if response.status_code in {401, 403, 409, 410}:
                    raise LeaseLost(f"Supervisor rejected scoped request ({response.status_code})")
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as error:
                    raise WorkerProtocolError("Supervisor returned malformed JSON") from error
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt + 1 >= attempts:
                    raise
                self.sleeper(min(2 ** attempt, 8))
        raise WorkerProtocolError("Retry exhausted")

    def register(self) -> None:
        value = self._request("POST", "/v1/workers/register", {
            "name": self.settings.name, "capabilities": list(self.settings.capabilities), "version": "0.1.0"})
        if not isinstance(value, dict) or value.get("id") != self.settings.worker_id:
            raise WorkerProtocolError("Worker token identity does not match registration")

    def heartbeat_once(self) -> None:
        self._request("POST", f"/v1/workers/{self.settings.worker_id}/heartbeat", {})
        with self._lock:
            task = self._task
        if task is not None:
            value = self._request("POST", f"/v1/tasks/{task.id}/renew", {
                **self._claim(task), "seconds": self.settings.lease_seconds})
            renewed = TaskView.model_validate(value)
            if renewed.lease_token != task.lease_token:
                raise LeaseLost("Supervisor changed the current fencing token")

    def _heartbeat_loop(self) -> None:
        while not self.stop_event.wait(self.settings.heartbeat_seconds):
            try:
                self.heartbeat_once()
            except (httpx.HTTPError, WorkerProtocolError, LeaseLost, ValidationError):
                # Reversible work may finish locally, but cannot complete after uncertain lease ownership.
                with self._lock:
                    if self._task is not None:
                        self.lease_lost.set()
                LOG.warning("Heartbeat or lease renewal unavailable; current claim fenced locally")

    def start_heartbeat(self) -> None:
        if self._heartbeat is None:
            self._heartbeat = threading.Thread(target=self._heartbeat_loop, name="siteforge-heartbeat", daemon=True)
            self._heartbeat.start()

    def _claim(self, task: TaskView) -> dict[str, Any]:
        return {"worker_id": self.settings.worker_id, "lease_token": task.lease_token}

    def _recover_result(self, task: TaskView, checkpoint: Any) -> AgentResult | None:
        if checkpoint is None:
            return None
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("data"), dict):
            raise WorkerProtocolError("Malformed checkpoint")
        data = checkpoint["data"]
        if checkpoint.get("sha256") != digest(data):
            raise WorkerProtocolError("Checkpoint checksum mismatch")
        if data.get("stage") != "result" or data.get("task_id") != task.id:
            return None
        result = AgentResult.model_validate(data.get("result"))
        # Failed/blocked snapshots are diagnostic evidence, not reusable work.
        # Native tools must reenter their receipt/policy/source validation on
        # every attempt. Fixture previews and QA likewise depend on a mutable
        # source tree that hashing their JSON manifest/report cannot prove.
        if (result.status != "completed" or task.input.get("mode") != "fixture"
                or task.agent_type in {AgentType.developer.value, AgentType.quality.value}
                or not result.artifacts):
            return None
        for artifact in result.artifacts:
            path = scoped_path(self.settings.artifact_root, artifact["uri"])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                return None
        return result

    def run_once(self) -> bool:
        # Backpressure before leasing preserves the durable attempt budget while
        # a benchmark/agent holds inference. The runner still acquires its own
        # lock after leasing, closing the race without holding a mutex over HTTP.
        model_router = getattr(self.runner, "model_router", None)
        if model_router is not None:
            try:
                ensure_inference_available(model_router.results_path.with_name(".run.lock"))
            except InferenceBusy:
                return False
        # Never retry a lease request after an uncertain response: another lease might be issued.
        value = self._request("POST", "/v1/tasks/lease", {
            "worker_id": self.settings.worker_id, "seconds": self.settings.lease_seconds}, retry_safe=False)
        if value is None:
            return False
        task = TaskView.model_validate(value)
        if task.lease_worker_id != self.settings.worker_id or not task.lease_token:
            raise WorkerProtocolError("Leased task belongs to a different worker or lacks a fence")
        try:
            role = AgentType(task.agent_type)
        except ValueError as error:
            raise WorkerProtocolError("Unknown agent role") from error
        if task.capability not in self.settings.capabilities or task.capability not in AGENTS[role].tools:
            raise WorkerProtocolError("Task capability is outside this worker contract")
        self.lease_lost.clear()
        with self._lock:
            self._task = task
        try:
            checkpoint = self._request("GET", f"/v1/tasks/{task.id}/checkpoint")
            self._request("POST", f"/v1/tasks/{task.id}/start", self._claim(task))
            result = self._recover_result(task, checkpoint)
            if result is None:
                context = AgentContext(task_id=UUID(task.id), site_id=UUID(task.site_id) if task.site_id else None,
                    allowed_tools=sorted(AGENTS[AgentType(task.agent_type)].tools & set(self.settings.capabilities)),
                    budget_remaining=task.budget_cap,
                    deadline=task.deadline or datetime.now(timezone.utc) + timedelta(minutes=10),
                    source_requirements=task.input.get("source_requirements", []))
                self._request("POST", f"/v1/tasks/{task.id}/checkpoint", {
                    **self._claim(task), "data": {"stage": "started", "task_id": task.id}})
                result = self.runner.run(task.agent_type, context, task.input,
                                         checkpoint=checkpoint["data"] if checkpoint else None)
                if self.lease_lost.is_set():
                    raise LeaseLost("Lease renewal was unavailable during task execution")
                self._request("POST", f"/v1/tasks/{task.id}/checkpoint", {
                    **self._claim(task), "data": {"stage": "result", "task_id": task.id,
                                                 "result": result.model_dump(mode="json")}})
            if self.lease_lost.is_set():
                raise LeaseLost("Lease ownership is uncertain")
            if result.status != "completed":
                self._request("POST", f"/v1/tasks/{task.id}/fail", {
                    **self._claim(task),
                    "error": result.error_code if result.error_code != "none" else f"agent_{result.status}: owner review required",
                    "retryable": result.retryable})
            else:
                self._request("POST", f"/v1/tasks/{task.id}/complete", {
                    **self._claim(task), "result": result.model_dump(mode="json")})
            return True
        except LMStudioError:
            self._request("POST", f"/v1/tasks/{task.id}/fail", {
                **self._claim(task), "error": "local_model_unavailable", "retryable": True})
            return True
        except (ValueError, PermissionError, WorkerProtocolError, KeyError, TypeError) as error:
            self._request("POST", f"/v1/tasks/{task.id}/fail", {
                **self._claim(task), "error": f"invalid_output:{type(error).__name__}", "retryable": False})
            return True
        finally:
            with self._lock:
                self._task = None

    def run_forever(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.register()
                break
            except (httpx.HTTPError, LeaseLost, WorkerProtocolError, ValidationError) as error:
                LOG.warning("Initial worker registration waiting (%s)", type(error).__name__)
                self.stop_event.wait(self.settings.poll_seconds)
        if self.stop_event.is_set():
            return
        self.start_heartbeat()
        while not self.stop_event.is_set():
            try:
                did_work = self.run_once()
                if not did_work:
                    self.stop_event.wait(self.settings.poll_seconds)
            except (httpx.HTTPError, LeaseLost, WorkerProtocolError, ValidationError) as error:
                LOG.warning("Worker reconnect waiting (%s)", type(error).__name__)
                self.stop_event.wait(self.settings.poll_seconds)
                try:
                    self.register()
                except (httpx.HTTPError, LeaseLost, WorkerProtocolError):
                    continue

    def close(self) -> None:
        self.stop_event.set()
        if self._heartbeat is not None:
            self._heartbeat.join(timeout=25)
        self.client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the outbound SiteForge Windows worker")
    parser.add_argument("--once", action="store_true", help="Register and process at most one task")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    worker = WindowsWorker(WorkerSettings.from_env())
    try:
        if args.once:
            worker.register()
            worker.start_heartbeat()
            worker.run_once()
        else:
            worker.run_forever()
    except KeyboardInterrupt:
        LOG.info("Worker stopping; unfinished leased work will recover after expiry")
    finally:
        worker.close()


if __name__ == "__main__":
    main()
