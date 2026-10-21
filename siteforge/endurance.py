"""Durable wall-clock endurance runner. Short runs are always smoke tests.

No external providers are invoked. Local queue faults exercise recovery paths;
the report names these fixture injections instead of claiming real outages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psutil
from sqlalchemy import select

from .contracts import ActionExecution, ActionRequest, AgentContext, AgentType, TaskCreate, TaskView
from .db import Database, Site, Task
from .policy import AGENT_TOOLS, PolicyService
from .queue import DomainError, QueueService
from .queue import aware

ACCEPTANCE_SECONDS = 72 * 60 * 60
THRESHOLDS = {
    "minimum_active_seconds": ACCEPTANCE_SECONDS,
    "minimum_completed_tasks": 900,
    "unauthorized_effects": 0,
    "duplicate_effects": 0,
    "lost_tasks": 0,
    "maximum_rss_growth_mib": 256,
    "maximum_queue_latency_seconds": 30,
    "all_injected_failures_recovered": True,
}


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, default=str) + '\n', encoding='utf-8')
    temporary.replace(path)


def implementation_hash() -> str:
    """Bind a soak to source bytes, including the trusted template dependency lock."""
    from .site_factory import IGNORED, TEMPLATE_ROOT
    base=Path(__file__).resolve().parent.parent
    files=list((base/'siteforge').glob('*.py'))
    for directory, folders, names in os.walk(TEMPLATE_ROOT,followlinks=False):
        folders[:]=[name for name in folders if name not in IGNORED]
        files.extend(Path(directory)/name for name in names if not name.startswith('.env'))
    digest=hashlib.sha256()
    for file in sorted(files):
        if file.is_symlink() or not file.resolve().is_relative_to(base):
            raise ValueError('Implementation snapshot must remain inside the repository')
        digest.update(file.relative_to(base).as_posix().encode())
        digest.update(hashlib.sha256(file.read_bytes()).digest())
    return digest.hexdigest()


class Simulation:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.url = 'sqlite:///' + (self.root / 'durable.db').as_posix()
        self.org_id = '00000000-0000-0000-0000-000000000072'
        self.worker_id = '00000000-0000-0000-0000-000000000073'
        self.db = Database(self.url)
        self.db.create_schema()
        self.db.provision_org(self.org_id, 'Endurance fixture tenant')
        self.queue = QueueService(self.db, retry_backoff=(0, 0, 0))
        self.queue.register_worker(self.org_id, 'endurance-fixture', sorted(set().union(*AGENT_TOOLS.values())), self.worker_id)
        self.queue.set_kill_switch(self.org_id, False, 'fixture-recovery')
        with self.db.transaction() as session:
            site = session.scalar(select(Site).where(Site.org_id == self.org_id, Site.slug == 'fixture-guards'))
            if site is None:
                site = Site(org_id=self.org_id, slug='fixture-guards', status='preview')
                session.add(site)
                session.flush()
            self.guard_site_id = site.id

    def restart(self) -> None:
        self.db.dispose()
        self.db = Database(self.url)
        self.queue = QueueService(self.db, retry_backoff=(0, 0, 0))

    def claim(self, task: TaskView) -> tuple[str, str, str, str]:
        if not task.lease_token:
            raise AssertionError('Lease fencing token missing')
        return self.org_id, self.worker_id, task.id, task.lease_token

    def next_task(self) -> TaskView:
        task = self.queue.lease(self.org_id, self.worker_id)
        if task is None:
            raise AssertionError('Durable task was not available')
        return task

    def guards(self, index: int) -> list[str]:
        policy = PolicyService(self.db)
        spec = ActionRequest(agent_type=AgentType.revenue, action='spend_money',
            payload={'fixture': True, 'cycle': index}, site_id=UUID(self.guard_site_id),
            amount=Decimal('1'), idempotency_key=f'budget-guard-{index}')
        approval = policy.request_approval(self.org_id, spec, 'fixture-requester')
        execution = ActionExecution(action=spec.action, payload=spec.payload, site_id=spec.site_id,
            amount=spec.amount, idempotency_key=f'budget-execution-{index}')
        try:
            policy.authorize(self.org_id, approval['id'], execution, 'fixture-owner')
        except DomainError:
            pass
        else:
            raise AssertionError('Unapproved action authorized')
        if approval['status'] == 'pending':
            policy.decide(self.org_id, approval['id'], 'fixture-owner', True, 'Fixture policy test only')
        try:
            policy.authorize(self.org_id, approval['id'], execution, 'fixture-owner')
        except DomainError:
            pass
        else:
            raise AssertionError('Zero external budget bypassed')
        # Zero-dollar intent tests durable approval consumption and replay only;
        # it invokes no production adapter and cannot publish a site.
        zero = spec.model_copy(update={'amount': Decimal('0'), 'action': 'deploy_production',
                                       'idempotency_key': f'receipt-guard-{index}'})
        approved = policy.request_approval(self.org_id, zero, 'fixture-requester')
        if approved['status'] == 'pending':
            policy.decide(self.org_id, approved['id'], 'fixture-owner', True, 'Fixture receipt test only')
        intent = execution.model_copy(update={'amount': Decimal('0'), 'action': 'deploy_production',
                                             'idempotency_key': f'receipt-execution-{index}'})
        first = policy.authorize(self.org_id, approved['id'], intent, 'fixture-owner')
        replay = policy.authorize(self.org_id, approved['id'], intent, 'fixture-owner')
        if first['id'] != replay['id'] or not replay['replay']:
            raise AssertionError('Duplicate irreversible action intent')
        return ['blocked_approval', 'budget_ceiling', 'receipt_replay']

    def cycle(self, index: int) -> dict:
        from .agents import AgentRunner, fixture_payload
        role_order = ('research', 'developer', 'quality')
        previous: list[UUID] = []
        ids = []
        payload = fixture_payload(f'fixture-{index % 3 + 1}')
        for role in role_order:
            spec = TaskCreate(agent_type=AgentType(role), capability=sorted(AGENT_TOOLS[role])[0],
                              input=payload, dependencies=previous,
                              idempotency_key=f'endurance-{index}-{role}')
            enqueued = self.queue.enqueue(self.org_id, spec)
            ids.append(enqueued.id)
            previous = [UUID(enqueued.id)]
        injected = self.guards(index)
        recovered = list(injected)
        queue_waits: list[float] = []
        runner = AgentRunner(self.root / 'artifacts')
        for position, role in enumerate(role_order):
            started = time.monotonic()
            with self.db.session() as session:
                persisted = session.get(Task, ids[position])
                assert persisted is not None
                saved = TaskView.model_validate(persisted)
            if saved.status == 'completed':
                continue
            if (saved.status in {'leased', 'running'} and saved.lease_worker_id == self.worker_id
                    and saved.lease_expires_at is not None
                    and aware(saved.lease_expires_at) > datetime.now(timezone.utc)):
                task = saved
            else:
                task = self.next_task()
            if task.id != ids[position]:
                raise AssertionError('Queue returned a task from an unexpected workflow step')
            queue_waits.append(max(0,(datetime.now(timezone.utc)-aware(task.available_at)).total_seconds()))
            if queue_waits[-1] > THRESHOLDS['maximum_queue_latency_seconds']:
                raise AssertionError('Queue latency exceeded threshold')
            claim = self.claim(task)
            self.queue.start(*claim)
            self.queue.checkpoint(*claim, {'phase': role, 'cycle': index})
            if position == 0:
                # Kill switch must stop new leases even with durable work ready.
                self.queue.set_kill_switch(self.org_id, True)
                if self.queue.lease(self.org_id, self.worker_id) is not None:
                    raise AssertionError('Kill switch failed')
                self.queue.set_kill_switch(self.org_id, False)
                injected.append('kill_switch')
                recovered.append('kill_switch')
            if position == index % 3:
                fault = ('model_failure', 'network_loss', 'malformed_output')[index % 3]
                self.queue.fail(*claim, fault, retryable=True)
                injected.append(fault)
                self.restart()
                task = self.next_task()
                if not self.queue.latest_checkpoint(self.org_id, task.id):
                    raise AssertionError('Checkpoint lost on supervisor reconnect')
                claim = self.claim(task)
                self.queue.start(*claim)
                recovered.append(fault)
                injected.append('supervisor_restart')
                recovered.append('supervisor_restart')
            if index % 7 == 0 and position == 1:
                old_claim = claim
                # Force persisted lease expiration; no machine-clock manipulation.
                with self.db.transaction() as session:
                    row = session.get(Task, task.id)
                    assert row is not None
                    row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                self.queue.recover_expired(self.org_id)
                task = self.next_task()
                try:
                    self.queue.complete(*old_claim, {'forged': True})
                except DomainError:
                    pass
                else:
                    raise AssertionError('Stale lease completed after reconnect')
                claim = self.claim(task)
                self.queue.start(*claim)
                injected.append('lease_expiration')
                recovered.append('lease_expiration')
            context = AgentContext(task_id=UUID(task.id), allowed_tools=sorted(AGENT_TOOLS[role]),
                                   budget_remaining=Decimal('0'), deadline=datetime.now(timezone.utc)+timedelta(minutes=5))
            result = runner.run(role, context, payload)
            if result.status != 'completed':
                raise AssertionError(f'{role} failed: {result.risks}')
            encoded = result.model_dump(mode='json')
            self.queue.complete(*claim, encoded)
            # Lost-ack replay must not create a second artifact record or attempt.
            self.queue.complete(*claim, encoded)
            if time.monotonic() - started > THRESHOLDS['maximum_queue_latency_seconds']:
                raise AssertionError('Local workflow latency exceeded threshold')
        with self.db.session() as session:
            statuses = list(session.scalars(select(Task.status).where(Task.id.in_(ids))))
            if statuses != ['completed'] * 3:
                raise AssertionError('A durable task was lost')
        return {'task_ids': ids, 'injected': injected, 'recovered': recovered,
                'queue_latency_seconds': max(queue_waits,default=0)}


def _run(args: argparse.Namespace) -> dict:
    args.root.mkdir(parents=True, exist_ok=True)
    state_path = args.root / 'report.json'
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state.get('status') == 'passed':
            return state
    else:
        state = {'run_id': str(uuid4()), 'started_at': stamp(), 'status': 'running',
                 'implementation_sha256': implementation_hash(),
                 'kind': '72-hour fixture endurance' if args.hours >= 72 else 'smoke',
                 'thresholds': THRESHOLDS, 'active_seconds': 0, 'cycles': 0,
                 'completed_tasks': 0, 'failures': [], 'injected': {}, 'recovered': {},
                 'unauthorized_effects': 0, 'duplicate_effects': 0, 'lost_tasks': 0,
                 'external_network_calls': 0,
                 'scope': 'SQLite fixture agent pipeline; injected model/network errors, persisted lease expiry, DB reconnect. PostgreSQL/service/OS/network acceptance separate.'}
    simulation = Simulation(args.root)
    process = psutil.Process()
    state.setdefault('baseline_rss_mib', process.memory_info().rss / 2**20)
    target_seconds = args.hours * 3600
    last = time.monotonic()
    next_cycle = last
    last_cycles = state['cycles']
    try:
        while state['active_seconds'] < target_seconds:
            now = time.monotonic()
            # Only time actually observed by this process counts; downtime never does.
            state['active_seconds'] += max(0, now-last)
            last = now
            if now >= next_cycle:
                if state.get('implementation_sha256') != implementation_hash():
                    raise AssertionError('Implementation changed during the soak; start a fresh run directory')
                result = simulation.cycle(state['cycles'])
                for key in ('injected', 'recovered'):
                    for name in result[key]:
                        state[key][name] = state[key].get(name, 0) + 1
                state['cycles'] += 1
                state['completed_tasks'] += len(result['task_ids'])
                state['maximum_queue_latency_seconds_observed']=max(
                    state.get('maximum_queue_latency_seconds_observed',0),result['queue_latency_seconds'])
                next_cycle = now + args.interval
            state['pid'] = os.getpid()
            state['heartbeat_at'] = stamp()
            state['rss_mib'] = process.memory_info().rss / 2**20
            state['rss_growth_mib'] = state['rss_mib']-state['baseline_rss_mib']
            if state['rss_growth_mib'] > THRESHOLDS['maximum_rss_growth_mib']:
                raise AssertionError('Memory growth threshold exceeded')
            atomic_json(state_path, state)
            if args.cycles and state['cycles']-last_cycles >= args.cycles:
                break
            time.sleep(min(5, max(.05, target_seconds-state['active_seconds'])))
        real_elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(state['started_at'])).total_seconds()
        eligible = (state['active_seconds'] >= ACCEPTANCE_SECONDS and real_elapsed >= ACCEPTANCE_SECONDS
                    and state['completed_tasks'] >= THRESHOLDS['minimum_completed_tasks']
                    and state.get('implementation_sha256') == implementation_hash()
                    and state['injected'] == state['recovered'] and not state['failures'])
        # A successful fixture soak still cannot certify untested production layers.
        state['status'] = 'failed' if state['failures'] else ('fixture_soak_passed' if eligible else 'smoke_passed')
        state['full_acceptance_status'] = 'PENDING: PostgreSQL/service faults, blocked approvals/budgets and mandatory checks must also pass'
    except KeyboardInterrupt:
        state['status'] = 'interrupted'
    except Exception as error:
        state['status'] = 'failed'
        state['failures'].append({'at': stamp(), 'type': type(error).__name__, 'error': str(error)[:500]})
        raise
    finally:
        state['finished_at'] = stamp()
        atomic_json(state_path, state)
        simulation.db.dispose()
    return state


def run(args: argparse.Namespace) -> dict:
    """Use an OS-released file lock so a crash cannot leave a stale PID lock."""
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / 'runner.lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            except OSError as error:
                raise RuntimeError('An endurance runner already owns this root') from error
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
            except OSError as error:
                raise RuntimeError('An endurance runner already owns this root') from error
        return _run(args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('runtime/endurance'))
    parser.add_argument('--hours', type=float, default=72)
    parser.add_argument('--interval', type=float, default=600, help='Seconds between fixture workflows')
    parser.add_argument('--cycles', type=int, help='Stop after N additional cycles (smoke only)')
    args = parser.parse_args()
    if args.hours <= 0 or args.interval < 0 or (args.cycles is not None and args.cycles < 1):
        parser.error('hours/cycles must be positive; interval cannot be negative')
    print(json.dumps(run(args), indent=2))


if __name__ == '__main__':
    main()
