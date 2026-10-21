import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from siteforge.api import create_app
from siteforge.contracts import TaskCreate
from siteforge.db import Database, utcnow
from siteforge.queue import QueueService


@pytest.fixture
def api():
    db = Database("sqlite://")
    db.create_schema()
    org, other, worker_id, stranger_id = [str(uuid4()) for _ in range(4)]
    db.provision_org(org)
    db.provision_org(other)
    def hashed(value):
        return hashlib.sha256(value.encode()).hexdigest()
    tokens = {
        hashed("owner-secret"): {"subject": "owner", "org_id": org, "role": "owner"},
        hashed("other-secret"): {"subject": "other", "org_id": other, "role": "owner"},
        hashed("worker-secret"): {"subject": "worker", "org_id": org, "role": "worker",
            "worker_id": worker_id, "capabilities": ["read_web"], "expires_at": utcnow() + timedelta(hours=1)},
        hashed("stranger-secret"): {"subject": "stranger", "org_id": org, "role": "worker",
            "worker_id": stranger_id, "capabilities": ["read_web"], "expires_at": utcnow() + timedelta(hours=1)},
        hashed("observer-secret"): {"subject": "observer", "org_id": org, "role": "observer"},
        hashed("expired-secret"): {"subject": "expired", "org_id": org, "role": "worker",
            "worker_id": worker_id, "capabilities": ["read_web"], "expires_at": utcnow() - timedelta(seconds=1)},
    }
    client = TestClient(create_app(db, tokens))
    yield client, org, worker_id
    client.close()
    db.dispose()


def headers(role="owner"):
    return {"Authorization": f"Bearer {role}-secret"}


def test_worker_full_round_trip_and_tenant_reads(api):
    client, _, worker = api
    response = client.post("/v1/workers/register", headers=headers("worker"),
                           json={"name": "windows", "capabilities": ["read_web"]})
    assert response.status_code == 200 and response.json()["id"] == worker
    task = client.post("/v1/tasks", headers=headers(), json={"agent_type": "research", "capability": "read_web",
        "input": {"fixture": True}, "idempotency_key": "one"}).json()
    leased = client.post("/v1/tasks/lease", headers=headers("worker"), json={"worker_id": worker}).json()
    assert leased["id"] == task["id"]
    claim = {"worker_id": worker, "lease_token": leased["lease_token"]}
    assert client.post(f"/v1/workers/{worker}/heartbeat", headers=headers("worker"), json={}).status_code == 200
    assert client.post(f"/v1/tasks/{task['id']}/start", headers=headers("worker"), json=claim).status_code == 200
    assert client.post(f"/v1/tasks/{task['id']}/renew", headers=headers("worker"), json=claim).status_code == 200
    assert client.post(f"/v1/tasks/{task['id']}/checkpoint", headers=headers("worker"), json={**claim, "data": {"step": 1}}).status_code == 200
    assert client.get(f"/v1/tasks/{task['id']}/checkpoint", headers=headers("worker")).json()["data"] == {"step": 1}
    assert client.post(f"/v1/tasks/{task['id']}/complete", headers=headers("worker"), json={**claim, "result": {"ok": True}}).json()["status"] == "completed"
    assert client.get(f"/v1/jobs/{task['id']}", headers=headers("other")).status_code == 404
    assert client.get("/v1/jobs", headers=headers("other")).json() == []
    assert "lease_token" not in client.get("/v1/jobs", headers=headers()).json()[0]


def test_authentication_scope_and_identity_fences(api):
    client, _, worker = api
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    assert client.get("/v1/sites").status_code == 401
    assert client.get("/v1/sites", headers=headers("expired")).status_code == 401
    assert client.post("/v1/workers/register", headers=headers("worker"), json={"name": "windows", "capabilities": ["edit_sandbox"]}).status_code == 403
    assert client.post(f"/v1/workers/{worker}/heartbeat", headers=headers("stranger"), json={}).status_code == 403
    assert client.post("/v1/sites", headers=headers("observer"), json={"slug": "forbidden"}).status_code == 403
    assert client.post("/v1/kill-switch", headers=headers("worker"), json={"enabled": False}).status_code == 403
    assert client.get("/v1/audit", headers=headers("worker")).status_code == 403


def test_approval_requires_owner_binds_sha_and_no_default_spending(api):
    client, _, _ = api
    site = client.post("/v1/sites", headers=headers(), json={"slug": "original-utility"}).json()
    request = {"agent_type": "developer", "action": "deploy_production", "site_id": site["id"],
               "payload": {"commit_sha": "a" * 40}, "amount": "0", "idempotency_key": "request"}
    approval = client.post("/v1/approvals", headers=headers("worker"), json=request).json()
    assert client.post(f"/v1/approvals/{approval['id']}/approve", headers=headers("worker"), json={}).status_code == 403
    assert client.post(f"/v1/approvals/{approval['id']}/approve", headers=headers(), json={}).status_code == 200
    execution = {key: request[key] for key in ["action", "site_id", "payload", "amount"]}
    execution["idempotency_key"] = "provider-intent"
    changed = {**execution, "payload": {"commit_sha": "b" * 40}}
    assert client.post(f"/v1/approvals/{approval['id']}/authorize", headers=headers(), json=changed).status_code == 403
    assert client.post(f"/v1/approvals/{approval['id']}/authorize", headers=headers(), json=execution).json()["status"] == "reserved"
    assert client.post(f"/v1/approvals/{approval['id']}/authorize", headers=headers(), json=execution).json()["replay"]
    assert client.get("/v1/audit", headers=headers()).json()


def test_validation_rejects_command_payload_fields(api):
    client, _, _ = api
    response = client.post("/v1/tasks", headers=headers(), json={"agent_type": "research", "capability": "read_web",
        "idempotency_key": "injection", "shell": "remove everything"})
    assert response.status_code == 422
    response = client.post("/v1/tasks", headers=headers(), json={"agent_type": "research", "capability": "shell",
        "idempotency_key": "injection"})
    assert response.status_code == 403


def test_owner_can_observe_and_pause_without_revealing_worker_tokens(api):
    client, _, _ = api
    assert client.post("/v1/kill-switch", headers=headers(), json={"enabled": True}).json() == {"enabled": True}
    assert client.get("/v1/kill-switch", headers=headers("observer")).json()["enabled"]
    for path in ["sites", "workers", "models", "benchmark-runs", "benchmark-results", "metrics", "budgets", "approvals", "audit"]:
        response = client.get("/v1/" + path, headers=headers())
        assert response.status_code == 200 and isinstance(response.json(), list)


def test_prometheus_requires_owner_and_reports_current_tenant_only(api):
    client, _, _ = api
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers=headers("worker")).status_code == 403
    client.post("/v1/tasks", headers=headers(), json={"agent_type": "research", "capability": "read_web",
        "idempotency_key": "metrics-visible"})
    response = client.get("/metrics", headers=headers())
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/plain")
    assert 'siteforge_tasks{state="ready"} 1' in response.text
    assert "siteforge_kill_switch 0" in response.text and "secret" not in response.text
    other = client.get("/metrics", headers=headers("other"))
    assert 'siteforge_tasks{state="ready"} 1' not in other.text


def test_owner_export_import_requires_provenance_and_blocks_worker_writes(api):
    client, _, _ = api
    site = client.post("/v1/sites", headers=headers(), json={"slug": "analytics-site"}).json()
    record = {"site_id": site["id"], "provider": "ga4", "source_record_id": "daily-import",
              "period_start": "2026-10-18T00:00:00Z", "period_end": "2026-10-19T00:00:00Z",
              "verification_status": "verified", "coverage": "complete",
              "metrics": {"sessions": {"value": "12", "unit": "count"}},
              "source": {"source_type": "provider_export", "reference": "reviewed-export",
                         "retrieved_at": "2026-10-20T00:00:00Z", "evidence_sha256": "e" * 64, "reconciled": True}}
    assert client.post("/v1/imports/analytics", headers=headers("worker"), json=record).status_code == 403
    created = client.post("/v1/imports/analytics", headers=headers(), json=record)
    assert created.status_code == 200 and not created.json()["replay"]
    assert client.post("/v1/imports/analytics", headers=headers(), json=record).json()["replay"]
    unreviewed = {**record, "source_record_id": "forecast", "source": {**record["source"], "source_type": "forecast"}}
    assert client.post("/v1/imports/analytics", headers=headers(), json=unreviewed).status_code == 422
    coverage = client.get(f"/v1/sites/{site['id']}/analytics-coverage", headers=headers(), params={"provider": "ga4"})
    assert coverage.json()["verified_observations"] == 1


def test_production_requires_migrations_and_no_fallback_credentials():
    db = Database("sqlite://")
    client = TestClient(create_app(db, {}))
    assert client.get("/readyz").status_code == 503
    assert client.get("/v1/sites", headers=headers()).status_code == 401
    db.dispose()


def test_frozen_migration_creates_full_schema_and_guards(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import DatabaseError
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("SITEFORGE_DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "infrastructure/migrations/alembic.ini"))
    command.upgrade(config, "head")
    command.check(config)
    db = Database(url)
    assert len(inspect(db.engine).get_table_names()) == 30  # 29 entities + Alembic version
    org = str(uuid4())
    db.provision_org(org)
    QueueService(db).set_kill_switch(org, True)
    with pytest.raises(DatabaseError, match="immutable audit"):
        with db.transaction() as session:
            session.execute(text("DELETE FROM audit_events"))
    db.dispose()


@pytest.mark.skipif(not os.environ.get("SITEFORGE_TEST_POSTGRES_URL"), reason="requires real PostgreSQL service")
def test_postgres_atomic_skip_locked_claims_and_audit_trigger(monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select, text
    from sqlalchemy.exc import DatabaseError
    from siteforge.db import Task
    url = os.environ["SITEFORGE_TEST_POSTGRES_URL"]
    monkeypatch.setenv("SITEFORGE_DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "infrastructure/migrations/alembic.ini"))
    command.upgrade(config, "head")
    db = Database(url)
    org = str(uuid4())
    db.provision_org(org)
    queue = QueueService(db)
    workers = [queue.register_worker(org, f"pg-worker-{n}", ["read_web"])["id"] for n in range(8)]
    ids = {queue.enqueue(org, TaskCreate(agent_type="research", capability="read_web",
             idempotency_key=f"pg-task-{n}")).id for n in range(20)}
    def consume(worker):
        claimed = []
        while (item := queue.lease(org, worker)) is not None:
            queue.start(org, worker, item.id, item.lease_token)
            queue.complete(org, worker, item.id, item.lease_token, {"status": "completed"})
            claimed.append(item.id)
        return claimed
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = [item for group in pool.map(consume, workers) for item in group]
    assert len(claims) == len(set(claims)) == 20 and set(claims) == ids
    with db.session() as session:
        assert all(t.status == "completed" for t in session.scalars(select(Task).where(Task.org_id == org)).all())
    with pytest.raises(DatabaseError, match="immutable audit"):
        with db.transaction() as session:
            session.execute(text("TRUNCATE audit_events"))
    db.dispose()
