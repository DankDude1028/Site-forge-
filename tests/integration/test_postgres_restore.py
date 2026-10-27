"""Actual custom-format PostgreSQL fixture backup/restore, never a production drill."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError

from siteforge.contracts import ActionExecution, ActionRequest, TaskCreate
from siteforge.db import Base, Database, Site
from siteforge.policy import PolicyService
from siteforge.queue import QueueService


def snapshot(db):
    with db.engine.connect() as connection:
        return {table.name: sorted(json.dumps(dict(row), sort_keys=True, default=str)
                                  for row in connection.execute(table.select()).mappings())
                for table in Base.metadata.sorted_tables}


@pytest.mark.skipif(not os.environ.get("SITEFORGE_TEST_POSTGRES_URL"), reason="requires real PostgreSQL fixture service")
def test_actual_postgres_dump_restore_preserves_queue_receipts_and_guards(tmp_path, monkeypatch):
    url = make_url(os.environ["SITEFORGE_TEST_POSTGRES_URL"])
    assert url.host in {"localhost", "127.0.0.1", "::1"}, "Restore drill requires an explicit loopback test service"
    binary_root = os.environ.get("SITEFORGE_TEST_PG_BIN")
    binaries = {name: str(Path(binary_root) / name) if binary_root else shutil.which(name)
                for name in ("pg_dump", "pg_restore")}
    assert all(binaries.values()), "Install PostgreSQL client tools for the actual restore test"
    names = [f"siteforge_drill_{uuid4().hex}_{kind}" for kind in ("source", "restore")]
    created = []
    connections = []
    # Only these freshly created fixture databases may be dropped. Passwords are
    # passed in the subprocess environment, never CLI arguments or captured logs.
    admin = psycopg.connect(host=url.host, port=url.port or 5432, dbname=url.database,
                           user=url.username, password=url.password, autocommit=True)
    try:
        for name in names:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created.append(name)
        source_url = url.set(database=names[0]).render_as_string(hide_password=False)
        monkeypatch.setenv("SITEFORGE_DATABASE_URL", source_url)
        config = Config(str(Path(__file__).resolve().parents[2] / "infrastructure/migrations/alembic.ini"))
        command.upgrade(config, "head")
        source = Database(source_url)
        connections.append(source)
        org, site = str(uuid4()), str(uuid4())
        source.provision_org(org)
        with source.transaction() as session:
            session.add(Site(id=site, org_id=org, slug="restore-fixture"))
        queue, policy = QueueService(source), PolicyService(source)
        worker = queue.register_worker(org, "restore-worker", ["read_web"])["id"]
        task = queue.enqueue(org, TaskCreate(agent_type="research", capability="read_web", site_id=site,
                                            idempotency_key="restore-checkpoint"))
        lease = queue.lease(org, worker, seconds=600)
        assert lease and lease.id == task.id
        queue.start(org, worker, task.id, lease.lease_token)
        checkpoint = queue.checkpoint(org, worker, task.id, lease.lease_token, {"source_id": "fixture:S1"})
        request = ActionRequest(agent_type="developer", action="deploy_production", site_id=site,
                                payload={"commit_sha": "a" * 40}, idempotency_key="fixture-approval")
        approval = policy.request_approval(org, request, "fixture-agent")
        policy.decide(org, approval["id"], "fixture-owner", True)
        execution = ActionExecution(action=request.action, site_id=site, payload=request.payload,
                                    idempotency_key="fixture-intent")
        receipt = policy.authorize(org, approval["id"], execution, "fixture-owner")
        assert receipt["status"] == "reserved"  # No provider was contacted.
        expected = snapshot(source)
        env = {**os.environ, "PGHOST": url.host, "PGPORT": str(url.port or 5432),
               "PGUSER": url.username or "", "PGPASSWORD": url.password or "", "PGCONNECT_TIMEOUT": "10"}
        archive = tmp_path / "fixture.dump"
        subprocess.run([binaries["pg_dump"], "--format=custom", "--no-owner", "--no-acl", "--file", str(archive)],
                       env={**env, "PGDATABASE": names[0]}, check=True, capture_output=True, timeout=60)
        assert archive.stat().st_size > 0
        source.dispose()
        subprocess.run([binaries["pg_restore"], "--exit-on-error", "--no-owner", "--no-acl", "--dbname", names[1], str(archive)],
                       env=env, check=True, capture_output=True, timeout=60)
        restored = Database(url.set(database=names[1]).render_as_string(hide_password=False))
        connections.append(restored)
        assert snapshot(restored) == expected
        replay = PolicyService(restored).authorize(org, approval["id"], execution, "fixture-owner")
        assert replay["replay"] and replay["id"] == receipt["id"]
        assert QueueService(restored).latest_checkpoint(org, task.id) == checkpoint
        QueueService(restored).complete(org, worker, task.id, lease.lease_token, {"status": "completed"})
        with pytest.raises(DatabaseError, match="immutable audit"):
            with restored.transaction() as session:
                session.execute(text("TRUNCATE audit_events"))
        with pytest.raises(DatabaseError, match="immutable approval"):
            with restored.transaction() as session:
                session.execute(text("UPDATE approvals SET payload_hash = 'tampered'"))
        with restored.engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    finally:
        for db in connections:
            db.dispose()
        for name in reversed(created):
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()
