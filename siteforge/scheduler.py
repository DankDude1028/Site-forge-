"""Always-on maintenance and opt-in daily fixture workflows on the durable queue.

Run `python -m siteforge.scheduler --once` for one pass, or omit --once for
the periodic service. No provider requests or external actions are performed.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from .contracts import AgentType, TaskCreate
from .db import Database, Organization, Site, Task, Worker, Workflow, audit, utcnow
from .queue import DomainError, QueueService


class Scheduler:
    def __init__(self, db: Database, org_id: str, *, enable_fixtures: bool = False,
                 clock: Callable[[], datetime] = utcnow, stale_worker_seconds: int = 120):
        if stale_worker_seconds < 30:
            raise ValueError("stale worker threshold must be at least 30 seconds")
        self.db, self.org_id = db, org_id
        self.enable_fixtures, self.clock = enable_fixtures, clock
        self.stale_worker_seconds = stale_worker_seconds
        self.queue = QueueService(db, clock=clock)

    def _fixture_workflow(self, now: datetime) -> tuple[str, str, str] | None:
        day = now.astimezone(timezone.utc).date().isoformat()
        slug = f"scheduled-fixture-{day}"
        key = f"daily-fixture-v1:{day}"
        with self.db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == self.org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            if org.kill_switch:
                return None
            site = session.scalar(select(Site).where(Site.org_id == self.org_id, Site.slug == slug))
            config = {"mode": "fixture", "scheduled_date": day, "commercial_launch": False}
            if site is None:
                site = Site(org_id=self.org_id, slug=slug, status="draft", config=config)
                session.add(site)
                session.flush()
                audit(session, self.org_id, "scheduler", "site.create_fixture", site.id, scheduled_date=day)
            elif site.config != config:
                raise DomainError("scheduled fixture slug belongs to a different site configuration")
            workflow = session.scalar(select(Workflow).where(Workflow.org_id == self.org_id,
                                                              Workflow.idempotency_key == key))
            if workflow is None:
                workflow = Workflow(org_id=self.org_id, site_id=site.id, type="daily_fixture",
                                    idempotency_key=key, status="ready", policy_version="1")
                session.add(workflow)
                session.flush()
                audit(session, self.org_id, "scheduler", "workflow.schedule", workflow.id, scheduled_date=day)
            elif workflow.site_id != site.id or workflow.type != "daily_fixture":
                raise DomainError("scheduled workflow idempotency conflict")
            return site.id, workflow.id, slug

    def _schedule_fixture(self, now: datetime) -> int:
        planned = self._fixture_workflow(now)
        if planned is None:
            return 0
        site_id, workflow_id, slug = planned
        utc_day = now.astimezone(timezone.utc).date()
        # Deterministic deadline survives a scheduler crash partway through
        # enqueueing; it allows an offline local worker seven days to return.
        deadline = datetime.combine(utc_day + timedelta(days=7), time.min, tzinfo=timezone.utc)
        previous: list[UUID] = []
        count = 0
        for role, capability in (("research", "read_sources"), ("developer", "edit_sandbox"),
                                 ("quality", "inspect_preview")):
            key = f"daily-fixture-v1:{utc_day.isoformat()}:{role}"
            with self.db.session() as session:
                existed = session.scalar(select(Task.id).where(Task.org_id == self.org_id,
                                                                Task.idempotency_key == key)) is not None
            task = self.queue.enqueue(self.org_id, TaskCreate(
                agent_type=AgentType(role), capability=capability, idempotency_key=key,
                input={"mode": "fixture", "site_slug": slug, "fixture_version": "label-planner-v1"},
                site_id=UUID(site_id), workflow_id=UUID(workflow_id), dependencies=previous, deadline=deadline,
            ), actor="scheduler")
            previous = [UUID(task.id)]
            count += int(not existed)
        return count

    def run_once(self) -> dict[str, Any]:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("scheduler clock must include a timezone")
        with self.db.session() as session:
            if session.get(Organization, self.org_id) is None:
                raise DomainError("organization not provisioned", 403)
        recovered = self.queue.recover_expired(self.org_id)
        stale = 0
        with self.db.transaction() as session:
            workers = session.scalars(select(Worker).where(
                Worker.org_id == self.org_id, Worker.status == "online",
                Worker.last_heartbeat_at <= now - timedelta(seconds=self.stale_worker_seconds),
            ).with_for_update(skip_locked=True)).all()
            for worker in workers:
                worker.status = "offline"
                stale += 1
                audit(session, self.org_id, "scheduler", "worker.offline", worker.id,
                      stale_threshold_seconds=self.stale_worker_seconds)
        scheduled = self._schedule_fixture(now) if self.enable_fixtures else 0
        updated = 0
        with self.db.transaction() as session:
            workflows = session.scalars(select(Workflow).where(Workflow.org_id == self.org_id)
                                         .with_for_update(skip_locked=True)).all()
            for workflow in workflows:
                states = session.scalars(select(Task.status).where(Task.org_id == self.org_id,
                                                                     Task.workflow_id == workflow.id)).all()
                if not states:
                    continue
                if all(state == "completed" for state in states):
                    status = "completed"
                elif any(state == "failed" for state in states):
                    status = "failed"
                elif any(state == "blocked" for state in states):
                    status = "blocked"
                elif all(state == "cancelled" for state in states):
                    status = "cancelled"
                elif any(state == "waiting_approval" for state in states):
                    status = "waiting_approval"
                elif any(state in {"running", "leased"} for state in states):
                    status = "running"
                else:
                    status = "ready"
                if workflow.status != status:
                    workflow.status = status
                    updated += 1
                    audit(session, self.org_id, "scheduler", "workflow.project_state", workflow.id, state=status)
        return {"at": now.isoformat(), "expired_leases_recovered": recovered,
                "workers_marked_offline": stale, "fixture_tasks_created": scheduled,
                "workflow_states_updated": updated, "fixtures_enabled": self.enable_fixtures,
                "external_actions": 0}


def env_boolean(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw.lower() in {"1", "true", "yes"}:
        return True
    if raw.lower() in {"0", "false", "no", ""}:
        return False
    raise ValueError(f"{name} must be true or false")


def main() -> None:
    from .cli import load_environment
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=int(os.environ.get("SITEFORGE_SCHEDULER_INTERVAL_SECONDS", "30")))
    args = parser.parse_args()
    if not 5 <= args.interval_seconds <= 3600:
        parser.error("interval must be between 5 and 3600 seconds")
    org_id = os.environ.get("SITEFORGE_ORG_ID")
    url = os.environ.get("SITEFORGE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not org_id or not url:
        parser.error("SITEFORGE_ORG_ID and SITEFORGE_DATABASE_URL are required; initialize and migrate first")
    db = Database(url)
    scheduler = Scheduler(db, org_id, enable_fixtures=env_boolean("SITEFORGE_SCHEDULE_FIXTURES"))
    try:
        while True:
            try:
                print(json.dumps(scheduler.run_once(), sort_keys=True), flush=True)
            except Exception as exc:
                # No database URLs, credentials, payloads, or provider secrets in logs.
                print(json.dumps({"status": "error", "error_type": type(exc).__name__}), flush=True)
                if args.once:
                    raise
            if args.once:
                break
            threading.Event().wait(args.interval_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        db.dispose()


if __name__ == "__main__":
    main()
