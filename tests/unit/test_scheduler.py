from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import select

from siteforge.contracts import TaskCreate
from siteforge.db import AuditEvent, Database, Site, Task, Worker, Workflow
from siteforge.queue import DomainError, QueueService
from siteforge.scheduler import Scheduler


@pytest.fixture
def scheduled(tmp_path):
    url = f"sqlite:///{tmp_path / 'scheduler.db'}"
    db = Database(url)
    db.create_schema()
    org = str(uuid4())
    db.provision_org(org)
    time = [datetime(2026, 10, 21, 12, tzinfo=timezone.utc)]
    yield db, org, time, url
    db.dispose()


def test_default_scheduler_does_not_schedule_or_contact_providers(scheduled):
    db, org, time, _ = scheduled
    result = Scheduler(db, org, clock=lambda: time[0]).run_once()
    assert result["external_actions"] == 0 and result["fixture_tasks_created"] == 0
    with db.session() as session:
        assert session.scalars(select(Task)).all() == []
        assert session.scalars(select(Site)).all() == []


def test_daily_fixture_chain_is_durable_and_idempotent_across_restart(scheduled):
    db, org, time, url = scheduled
    scheduler = Scheduler(db, org, enable_fixtures=True, clock=lambda: time[0])
    assert scheduler.run_once()["fixture_tasks_created"] == 3
    time[0] += timedelta(hours=2)
    assert scheduler.run_once()["fixture_tasks_created"] == 0
    restarted = Database(url)
    next_scheduler = Scheduler(restarted, org, enable_fixtures=True, clock=lambda: time[0])
    assert next_scheduler.run_once()["fixture_tasks_created"] == 0
    queue = QueueService(restarted, clock=lambda: time[0])
    worker = queue.register_worker(org, "fixture-worker", ["read_sources", "edit_sandbox", "inspect_preview"])["id"]
    for role in ("research", "developer", "quality"):
        task = queue.lease(org, worker)
        assert task.agent_type == role and task.input["mode"] == "fixture"
        queue.complete(org, worker, task.id, task.lease_token, {"status": "completed"})
    assert next_scheduler.run_once()["workflow_states_updated"] == 1
    with restarted.session() as session:
        assert session.scalar(select(Workflow)).status == "completed"
    time[0] += timedelta(days=1)
    assert next_scheduler.run_once()["fixture_tasks_created"] == 3
    with restarted.session() as session:
        assert len(session.scalars(select(Task)).all()) == 6
        assert len(session.scalars(select(Workflow)).all()) == 2
    restarted.dispose()


def test_partial_enqueue_crash_resumes_same_workflow(scheduled, monkeypatch):
    db, org, time, _ = scheduled
    scheduler = Scheduler(db, org, enable_fixtures=True, clock=lambda: time[0])
    original = scheduler.queue.enqueue
    calls = [0]
    def injected(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 2:
            raise ConnectionError("injected scheduler interruption")
        return original(*args, **kwargs)
    monkeypatch.setattr(scheduler.queue, "enqueue", injected)
    with pytest.raises(ConnectionError):
        scheduler.run_once()
    time[0] += timedelta(minutes=4)
    recovered = Scheduler(db, org, enable_fixtures=True, clock=lambda: time[0])
    assert recovered.run_once()["fixture_tasks_created"] == 2
    with db.session() as session:
        assert len(session.scalars(select(Task)).all()) == 3
        assert len(session.scalars(select(Workflow)).all()) == 1


def test_deadlines_expired_leases_stale_workers_and_heartbeat_recovery(scheduled):
    db, org, time, _ = scheduled
    queue = QueueService(db, clock=lambda: time[0])
    worker = queue.register_worker(org, "offline-worker", ["read_web"])["id"]
    queued = queue.enqueue(org, TaskCreate(agent_type="research", capability="read_web", idempotency_key="lease"))
    late = queue.enqueue(org, TaskCreate(agent_type="research", capability="read_web", idempotency_key="deadline",
                                        deadline=time[0] + timedelta(seconds=10)))
    leased = queue.lease(org, worker, 15)
    time[0] += timedelta(seconds=121)
    scheduler = Scheduler(db, org, clock=lambda: time[0])
    result = scheduler.run_once()
    assert result["expired_leases_recovered"] == 1 and result["workers_marked_offline"] == 1
    with db.session() as session:
        assert session.get(Task, queued.id).status == "retry_scheduled"
        assert session.get(Task, late.id).error_code == "deadline_expired"
        assert session.get(Worker, worker).status == "offline"
    assert scheduler.run_once()["workers_marked_offline"] == 0
    with pytest.raises(DomainError):
        queue.complete(org, worker, leased.id, leased.lease_token, {})
    queue.heartbeat(org, worker)
    with db.session() as session:
        assert session.get(Worker, worker).status == "online"
        assert len(session.scalars(select(AuditEvent).where(AuditEvent.action == "worker.offline")).all()) == 1


def test_competing_schedulers_create_one_chain_and_respect_kill_switch(scheduled):
    db, org, time, _ = scheduled
    queue = QueueService(db, clock=lambda: time[0])
    queue.set_kill_switch(org, True)
    assert Scheduler(db, org, enable_fixtures=True, clock=lambda: time[0]).run_once()["fixture_tasks_created"] == 0
    queue.set_kill_switch(org, False)
    def run(_):
        return Scheduler(db, org, enable_fixtures=True, clock=lambda: time[0]).run_once()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run, range(4)))
    with db.session() as session:
        assert len(session.scalars(select(Task)).all()) == 3
        assert len(session.scalars(select(Workflow)).all()) == 1
        assert len(session.scalars(select(Site)).all()) == 1


def test_scheduler_once_command_runs_against_the_existing_database(scheduled, tmp_path):
    db, org, _, url = scheduled
    env = os.environ.copy()
    env.update(SITEFORGE_DATABASE_URL=url, SITEFORGE_ORG_ID=org, SITEFORGE_SCHEDULE_FIXTURES="true",
               PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    result = subprocess.run([sys.executable, "-m", "siteforge.scheduler", "--once"], cwd=tmp_path,
                            env=env, check=True, capture_output=True, text=True, timeout=30)
    report = json.loads(result.stdout)
    assert report["fixture_tasks_created"] == 3 and report["external_actions"] == 0
    with db.session() as session:
        assert len(session.scalars(select(Task)).all()) == 3


def test_weekly_review_is_opt_in_durable_and_retains_missing_economics(scheduled):
    from siteforge.db import Notification
    db, org, time, url = scheduled
    with db.transaction() as session:
        session.add(Site(org_id=org, slug='useful-site'))
    assert Scheduler(db, org, clock=lambda: time[0]).run_once()['weekly_reviews_created'] == 0
    assert Scheduler(db, org, enable_weekly_reviews=True, clock=lambda: time[0]).run_once()['weekly_reviews_created'] == 1
    restarted = Database(url)
    scheduler = Scheduler(restarted, org, enable_weekly_reviews=True, clock=lambda: time[0])
    assert scheduler.run_once()['weekly_reviews_created'] == 0
    with restarted.session() as session:
        notice = session.scalar(select(Notification).where(Notification.kind == 'portfolio.weekly'))
        assert notice.data['sites'][0]['economics']['verified_revenue'] is None
        assert notice.data['sites'][0]['economics']['coverage'] == 'missing'
        assert notice.data['external_delivery'] is False
    time[0] += timedelta(days=7)
    assert scheduler.run_once()['weekly_reviews_created'] == 1
    QueueService(restarted).set_kill_switch(org, True)
    time[0] += timedelta(days=7)
    assert scheduler.run_once()['weekly_reviews_created'] == 0
    restarted.dispose()
