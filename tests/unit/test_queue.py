from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from siteforge.contracts import TaskCreate
from siteforge.db import Attempt, AuditEvent, Database, Task
from siteforge.queue import DomainError, QueueService


@pytest.fixture
def system(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'queue.db'}")
    db.create_schema()
    org = str(uuid4())
    db.provision_org(org)
    time = [datetime(2026, 10, 21, tzinfo=timezone.utc)]
    queue = QueueService(db, clock=lambda: time[0], retry_backoff=(1, 2, 3))
    worker = queue.register_worker(org, "test", ["read_web"])["id"]
    yield db, org, queue, worker, time
    db.dispose()


def task(key="one", **kwargs):
    return TaskCreate(agent_type="research", capability="read_web", idempotency_key=key, **kwargs)


def test_complete_checkpoint_and_idempotent_replay(system):
    db, org, queue, worker, _ = system
    created = queue.enqueue(org, task())
    assert queue.enqueue(org, task()).id == created.id
    leased = queue.lease(org, worker)
    assert leased.id == created.id and leased.attempt == 1
    assert queue.start(org, worker, leased.id, leased.lease_token).status == "running"
    queue.checkpoint(org, worker, leased.id, leased.lease_token, {"stage": "sources"})
    assert queue.latest_checkpoint(org, leased.id)["data"] == {"stage": "sources"}
    result = {"evidence": ["fixture:v1"]}
    assert queue.complete(org, worker, leased.id, leased.lease_token, result).status == "completed"
    assert queue.complete(org, worker, leased.id, leased.lease_token, result).status == "completed"
    with pytest.raises(DomainError, match="differs"):
        queue.complete(org, worker, leased.id, leased.lease_token, {"changed": True})
    assert queue.lease(org, worker) is None
    with db.session() as session:
        assert session.scalar(select(Attempt).where(Attempt.task_id == created.id)).status == "completed"
        assert session.scalars(select(AuditEvent).where(AuditEvent.target_id == created.id)).all()


def test_idempotency_conflict_and_capability_denial(system):
    _, org, queue, _, _ = system
    queue.enqueue(org, task(input={"version": 1}))
    with pytest.raises(DomainError, match="different task"):
        queue.enqueue(org, task(input={"version": 2}))
    with pytest.raises(DomainError, match="capability denied"):
        queue.enqueue(org, TaskCreate(agent_type="research", capability="edit_sandbox", idempotency_key="unsafe"))


def test_expired_fencing_retry_and_dead_letter(system):
    db, org, queue, worker, time = system
    created = queue.enqueue(org, task(max_attempts=2))
    first = queue.lease(org, worker, 15)
    queue.checkpoint(org, worker, first.id, first.lease_token, {"progress": 1})
    time[0] += timedelta(seconds=16)
    assert queue.recover_expired(org) == 1
    assert queue.lease(org, worker) is None
    time[0] += timedelta(seconds=1)
    second = queue.lease(org, worker)
    assert second.attempt == 2 and second.lease_token != first.lease_token
    with pytest.raises(DomainError):
        queue.complete(org, worker, first.id, first.lease_token, {})
    assert queue.latest_checkpoint(org, created.id)["data"]["progress"] == 1
    assert queue.fail(org, worker, second.id, second.lease_token, "model_unavailable").status == "failed"
    with db.session() as session:
        assert session.get(Task, created.id).status == "failed"
        assert len(session.scalars(select(Attempt).where(Attempt.task_id == created.id)).all()) == 2


def test_dependencies_and_failure_propagation(system):
    _, org, queue, worker, _ = system
    parent = queue.enqueue(org, task("parent"))
    child = queue.enqueue(org, task("child", dependencies=[parent.id]))
    assert child.status == "pending"
    leased = queue.lease(org, worker)
    assert leased.id == parent.id
    queue.complete(org, worker, leased.id, leased.lease_token, {})
    assert queue.lease(org, worker).id == child.id


def test_failed_dependency_blocks_child(system):
    db, org, queue, worker, _ = system
    parent = queue.enqueue(org, task("parent"))
    child = queue.enqueue(org, task("child", dependencies=[parent.id]))
    leased = queue.lease(org, worker)
    queue.fail(org, worker, leased.id, leased.lease_token, "permanent", retryable=False)
    with db.session() as session:
        assert session.get(Task, child.id).status == "blocked"


def test_deadline_kill_switch_and_renewal(system):
    _, org, queue, worker, time = system
    queue.enqueue(org, task(deadline=time[0] + timedelta(hours=1)))
    queue.set_kill_switch(org, True)
    assert queue.lease(org, worker) is None
    queue.set_kill_switch(org, False)
    leased = queue.lease(org, worker, 15)
    time[0] += timedelta(seconds=10)
    queue.renew(org, worker, leased.id, leased.lease_token, 120)
    time[0] += timedelta(seconds=10)
    assert queue.recover_expired(org) == 0
    assert queue.complete(org, worker, leased.id, leased.lease_token, {}).status == "completed"
    queue.enqueue(org, task("late", deadline=time[0] - timedelta(seconds=1)))
    assert queue.lease(org, worker) is None


def test_cross_tenant_dependency_and_worker_identity(system):
    db, org, queue, worker, _ = system
    other = str(uuid4())
    db.provision_org(other)
    parent = queue.enqueue(org, task())
    with pytest.raises(DomainError, match="not found"):
        queue.enqueue(other, task("cross", dependencies=[parent.id]))
    with pytest.raises(DomainError, match="not found"):
        queue.heartbeat(other, worker)


def test_competing_claims_have_no_duplicate_tasks(system):
    _, org, queue, _, _ = system
    workers = [queue.register_worker(org, f"worker-{n}", ["read_web"])["id"] for n in range(12)]
    for n in range(12):
        queue.enqueue(org, task(str(n)))
    with ThreadPoolExecutor(max_workers=12) as pool:
        leased = list(pool.map(lambda worker: queue.lease(org, worker), workers))
    assert len({result.id for result in leased}) == 12


def test_restart_preserves_tasks_and_checkpoints(system, tmp_path):
    db, org, queue, worker, time = system
    item = queue.enqueue(org, task())
    leased = queue.lease(org, worker)
    queue.checkpoint(org, worker, leased.id, leased.lease_token, {"saved": True})
    url = str(db.engine.url)
    db.dispose()
    restarted = Database(url)
    recovered = QueueService(restarted, clock=lambda: time[0])
    assert recovered.latest_checkpoint(org, item.id)["data"]["saved"]
    assert recovered.complete(org, worker, item.id, leased.lease_token, {}).status == "completed"
    restarted.dispose()


@pytest.mark.parametrize("status", ["blocked", "failed", "unknown"])
def test_noncompleted_agent_result_never_releases_dependents(system, status):
    db, org, queue, worker, _ = system
    created = queue.enqueue(org, task())
    dependent = queue.enqueue(org, task("child", dependencies=[created.id]))
    leased = queue.lease(org, worker)
    with pytest.raises(DomainError, match="cannot satisfy"):
        queue.complete(org, worker, leased.id, leased.lease_token, {"status": status})
    with db.session() as session:
        assert session.get(Task, dependent.id).status == "pending"
