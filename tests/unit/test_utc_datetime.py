"""SQLite must preserve the same aware UTC instants as production PostgreSQL."""
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Column, DateTime, Integer, MetaData, Table, insert, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import StatementError

from siteforge.agents import AGENTS, AgentRunner, fixture_payload
from siteforge.api import create_app
from siteforge.contracts import AgentType, TaskCreate, TaskView
from siteforge.db import Base, Database, UTCDateTime
from siteforge.policy import KNOWN_TOOLS
from siteforge.worker import WindowsWorker, WorkerSettings


def test_all_mapped_timestamps_use_aware_utc_file_sqlite_round_trip(tmp_path):
    db = Database("sqlite:///" + (tmp_path / "timestamps.db").as_posix())
    columns = [(table.name, column) for table in Base.metadata.tables.values() for column in table.columns
               if isinstance(column.type, (DateTime, UTCDateTime))]
    assert len(columns) >= 40
    assert all(isinstance(column.type, UTCDateTime) for _, column in columns)
    probe = Table("timestamp_probe", MetaData(), Column("id", Integer, primary_key=True), *[
        Column(f"{table}__{column.name}", column.type.copy(), nullable=column.nullable)
        for table, column in columns])
    probe.create(db.engine)
    original = datetime(2026, 10, 21, 11, 42, 13, 123456, tzinfo=timezone(timedelta(hours=-5)))
    expected = original.astimezone(timezone.utc)
    values = {column.name: original for column in probe.columns if column.name != "id"}
    try:
        with db.engine.begin() as connection:
            connection.execute(insert(probe).values(id=1, **values))
        # A fresh connection ensures SQLite's stored representation is decoded.
        with db.engine.connect() as connection:
            row = connection.execute(select(probe).where(probe.c.id == 1)).mappings().one()
            for name in values:
                assert row[name] == expected
                assert row[name].tzinfo is timezone.utc
        with pytest.raises(StatementError, match="must include a timezone"):
            with db.engine.begin() as connection:
                connection.execute(insert(probe).values(id=2, **{name: value.replace(tzinfo=None) for name, value in values.items()}))
    finally:
        db.dispose()


def test_type_preserves_postgres_aware_utc_and_only_repairs_sqlite_naive_reads():
    utc_type = UTCDateTime()
    offset = datetime(2026, 10, 21, 12, tzinfo=timezone(timedelta(hours=9)))
    assert utc_type.process_bind_param(offset, postgresql.dialect()) == offset.astimezone(timezone.utc)
    assert utc_type.process_result_value(offset, postgresql.dialect()).tzinfo is timezone.utc
    assert utc_type.process_result_value(offset.replace(tzinfo=None), sqlite.dialect()).tzinfo is timezone.utc
    with pytest.raises(ValueError, match="without a timezone"):
        utc_type.process_result_value(offset.replace(tzinfo=None), postgresql.dialect())
    for dialect in (postgresql.dialect(), sqlite.dialect()):
        assert utc_type.process_bind_param(None, dialect) is None
        assert utc_type.process_result_value(None, dialect) is None
        with pytest.raises(ValueError, match="must include a timezone"):
            utc_type.process_bind_param(offset.replace(tzinfo=None), dialect)
    assert str(utc_type.compile(dialect=postgresql.dialect())) == "TIMESTAMP WITH TIME ZONE"
    assert str(utc_type.compile(dialect=sqlite.dialect())) == "DATETIME"


@pytest.fixture
def file_supervisor(tmp_path):
    db = Database("sqlite:///" + (tmp_path / "supervisor.db").as_posix())
    db.create_schema()
    org, worker_id = str(uuid4()), str(uuid4())
    db.provision_org(org)
    token = "utc-worker-token-with-local-scope"
    tokens = {
        hashlib.sha256(b"utc-owner").hexdigest(): {"subject": "owner", "org_id": org, "role": "owner"},
        hashlib.sha256(token.encode()).hexdigest(): {"subject": "worker", "org_id": org, "role": "worker",
            "worker_id": worker_id, "capabilities": sorted(KNOWN_TOOLS),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)},
    }
    with TestClient(create_app(db, tokens), base_url="http://127.0.0.1:8080") as client:
        settings = WorkerSettings("http://127.0.0.1:8080", token, worker_id, tmp_path / "artifacts")
        worker = WindowsWorker(settings, client=client, runner=AgentRunner(settings.artifact_root))
        worker.register()
        yield client, worker, {"Authorization": "Bearer utc-owner"}
    db.dispose()


@pytest.mark.parametrize("offset_hours", [0, -5, 9.5])
def test_future_deadline_remains_aware_utc_through_http_lease(file_supervisor, offset_hours):
    client, worker, owner = file_supervisor
    expected = datetime.now(timezone.utc) + timedelta(minutes=5)
    submitted = expected.astimezone(timezone(timedelta(hours=offset_hours)))
    response = client.post("/v1/tasks", headers=owner, json={"agent_type": "research", "capability": "read_sources",
        "input": fixture_payload(), "idempotency_key": "offset-deadline", "deadline": submitted.isoformat()})
    assert response.status_code == 200, response.text
    leased = client.post("/v1/tasks/lease", headers={"Authorization": f"Bearer {worker.settings.token}"},
                         json={"worker_id": worker.settings.worker_id})
    assert leased.status_code == 200, leased.text
    value = TaskView.model_validate(leased.json())
    assert value.deadline == expected
    assert value.deadline.utcoffset() == timedelta(0)
    assert value.deadline > datetime.now(timezone.utc)
    assert value.available_at.utcoffset() == timedelta(0)
    assert value.lease_expires_at.utcoffset() == timedelta(0)


def test_actual_fixture_worker_completes_future_explicit_offset_deadline(file_supervisor):
    client, worker, owner = file_supervisor
    deadline = (datetime.now(timezone.utc) + timedelta(minutes=5)).astimezone(timezone(timedelta(hours=-5)))
    created = client.post("/v1/tasks", headers=owner, json={"agent_type": "research",
        "capability": sorted(AGENTS[AgentType.research].tools)[0], "input": fixture_payload(),
        "idempotency_key": "worker-explicit-deadline", "deadline": deadline.isoformat()})
    assert created.status_code == 200, created.text
    assert worker.run_once()
    completed = client.get(f"/v1/jobs/{created.json()['id']}", headers=owner).json()
    assert completed["status"] == "completed", completed
    assert completed["result"]["status"] == "completed"
    assert completed["result"]["retryable"] is False
    assert datetime.fromisoformat(completed["deadline"].replace("Z", "+00:00")) == deadline


def test_naive_task_deadline_is_rejected_before_storage(file_supervisor):
    client, _, owner = file_supervisor
    payload = {"agent_type": "research", "capability": "read_sources", "idempotency_key": "naive",
               "deadline": "2026-10-21T23:59:00"}
    with pytest.raises(ValidationError, match="timezone"):
        TaskCreate.model_validate(payload)
    assert client.post("/v1/tasks", headers=owner, json=payload).status_code == 422


def test_utc_binding_requires_no_change_to_frozen_migration(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "migration.db").as_posix()
    monkeypatch.setenv("SITEFORGE_DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[2] / "infrastructure/migrations/alembic.ini"))
    command.upgrade(config, "head")
    command.check(config)
