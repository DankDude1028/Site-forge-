"""Real encrypted dump/restore on fresh UUID databases in the opt-in CI service."""
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

from siteforge.backups import backup, connection_from_env, restore
from siteforge.contracts import TaskCreate
from siteforge.db import Base, Database
from siteforge.queue import QueueService


def snapshot(database):
    with database.engine.connect() as connection:
        return {table.name: sorted(json.dumps(dict(row), sort_keys=True, default=str)
                for row in connection.execute(table.select()).mappings()) for table in Base.metadata.sorted_tables}


@pytest.mark.skipif(not os.environ.get("SITEFORGE_TEST_POSTGRES_URL"), reason="requires real PostgreSQL fixture service")
def test_actual_encrypted_backup_restore_preserves_all_tables_and_checkpoint(tmp_path, monkeypatch):
    url = make_url(os.environ["SITEFORGE_TEST_POSTGRES_URL"])
    assert url.host in {"localhost", "127.0.0.1", "::1"}, "Only explicit loopback fixture service may be used"
    source_name, target_name = "siteforge_backup_" + uuid4().hex, "siteforge_restore_" + uuid4().hex
    created, databases = [], []
    pg_bin = Path(os.environ["SITEFORGE_TEST_PG_BIN"]) if os.environ.get("SITEFORGE_TEST_PG_BIN") else None
    admin = psycopg.connect(host=url.host, port=url.port or 5432, dbname=url.database,
                           user=url.username, password=url.password, autocommit=True)
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(source_name)))
        created.append(source_name)
        source_url = url.set(database=source_name).render_as_string(hide_password=False)
        source = Database(source_url)
        databases.append(source)
        source.create_schema()
        org = str(uuid4())
        source.provision_org(org)
        queue = QueueService(source)
        worker = queue.register_worker(org, "encrypted-fixture-worker", ["read_sources"])["id"]
        task = queue.enqueue(org, TaskCreate(agent_type="research", capability="read_sources", idempotency_key="encrypted-fixture"))
        lease = queue.lease(org, worker, seconds=600)
        queue.start(org, worker, lease.id, lease.lease_token)
        checkpoint = queue.checkpoint(org, worker, lease.id, lease.lease_token, {"evidence": "fixture:S1"})
        expected = snapshot(source)
        source.dispose()
        for name, database in (("FIXTURE_SOURCE_URI", source_name), ("FIXTURE_TARGET_URI", target_name), ("FIXTURE_ADMIN_URI", "postgres")):
            monkeypatch.setenv(name, url.set(database=database).render_as_string(hide_password=False))
        root, key = tmp_path / "encrypted", os.urandom(32)
        manifest = backup(connection_from_env("FIXTURE_SOURCE_URI"), root, key=key, key_id="fixture-ci", pg_bin=pg_bin)
        assert manifest["dump_bytes"] > 5 and not list(root.glob("*.dump"))
        outcome = restore(root / manifest["file"], root, connection_from_env("FIXTURE_TARGET_URI"),
                          connection_from_env("FIXTURE_ADMIN_URI"), key=key, key_id="fixture-ci",
                          disposable=True, pg_bin=pg_bin)
        created.append(target_name)
        assert outcome["status"] == "restored_disposable" and not outcome["production_promoted"]
        restored = Database(url.set(database=target_name).render_as_string(hide_password=False))
        databases.append(restored)
        assert snapshot(restored) == expected
        assert QueueService(restored).latest_checkpoint(org, task.id) == checkpoint
        QueueService(restored).complete(org, worker, lease.id, lease.lease_token, {"restored": True})
    finally:
        for database in databases:
            database.dispose()
        for name in reversed(created):
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()
