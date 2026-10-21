"""Local operator commands. Secrets are written only to the ignored .env file."""
from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx


def load_environment(path: Path = Path('.env')) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            if key.startswith(('SITEFORGE_', 'DATABASE_URL', 'LMSTUDIO_')):
                os.environ.setdefault(key, value.strip())


def initialize(args: argparse.Namespace) -> None:
    from .db import Database
    env_path = Path('.env')
    if env_path.exists():
        raise SystemExit('.env already exists. Reuse it; rotate credentials explicitly when needed.')
    Path('runtime/artifacts').mkdir(parents=True, exist_ok=True)
    org_id, worker_id = str(uuid4()), str(uuid4())
    values = {
        'SITEFORGE_DATABASE_URL': args.database,
        'SITEFORGE_ORG_ID': org_id,
        'SITEFORGE_OWNER_TOKEN': secrets.token_hex(32),
        'SITEFORGE_WORKER_TOKEN': secrets.token_hex(32),
        'SITEFORGE_WORKER_ID': worker_id,
        'SITEFORGE_WORKER_TOKEN_EXPIRES_AT': (datetime.now(timezone.utc)+timedelta(hours=8)).isoformat(),
        'SITEFORGE_API_URL': 'http://127.0.0.1:8080',
        'SITEFORGE_SUPERVISOR_URL': 'http://127.0.0.1:8080',
        'SITEFORGE_LMSTUDIO_URL': 'http://127.0.0.1:1234',
        'SITEFORGE_ARTIFACT_ROOT': 'runtime/artifacts',
        'SITEFORGE_EXTERNAL_BUDGET_USD': '0',
    }
    db = Database(args.database)
    # Schema bootstrap is for SQLite development. Production uses Alembic migrations.
    if db.engine.dialect.name == 'sqlite':
        db.create_schema()
    db.provision_org(org_id, 'SiteForge pilot')
    db.dispose()
    with env_path.open('x', encoding='utf-8') as file:
        file.write('# Local secrets. Never commit or attach this file.\n')
        file.write('\n'.join(f'{key}={value}' for key, value in values.items())+'\n')
    print(json.dumps({'environment_file': str(env_path.resolve()), 'org_id': org_id,
                      'worker_id': worker_id, 'worker_credential_hours': 8,
                      'external_spend_limit': 0}, indent=2))


def serve(_args: argparse.Namespace) -> None:
    import uvicorn
    load_environment()
    uvicorn.run('siteforge.api:app', host='127.0.0.1', port=8080)


def demo(_args: argparse.Namespace) -> None:
    from .agents import fixture_payload
    from .policy import AGENT_TOOLS
    from .worker import WindowsWorker, WorkerSettings
    load_environment()
    token = os.environ['SITEFORGE_OWNER_TOKEN']
    origin = os.environ.get('SITEFORGE_API_URL', 'http://127.0.0.1:8080')
    with httpx.Client(base_url=origin, headers={'Authorization': f'Bearer {token}'},
                      follow_redirects=False, trust_env=False, timeout=30) as client:
        def post(path: str, body: dict) -> dict:
            response = client.post(path, json=body)
            response.raise_for_status()
            return response.json()
        site = post('/v1/sites', {'slug':'label-roll-planner','config':{'mode':'fixture','commercial_launch':False}})
        workflow = post('/v1/workflows', {'type':'fixture_site','site_id':site['id'],
                                          'idempotency_key':'fixture-site-v1'})
        previous: list[str] = []
        for role in ('portfolio_director','research','developer','content','quality','growth','revenue'):
            task = post('/v1/tasks', {'agent_type':role, 'capability':sorted(AGENT_TOOLS[role])[0],
                'input':fixture_payload(), 'site_id':site['id'], 'workflow_id':workflow['id'],
                'dependencies':previous,'idempotency_key':f'fixture-v1-{role}'})
            previous=[task['id']]
    worker = WindowsWorker(WorkerSettings.from_env())
    worker.register()
    worker.start_heartbeat()
    try:
        count=0
        while count < 20 and worker.run_once():
            count+=1
        print(json.dumps({'processed_tasks':count,'site_id':site['id'], 'workflow_id':workflow['id'],
                          'artifacts':'runtime/artifacts/label-roll-planner', 'mode':'fixture',
                          'external_actions':0},indent=2))
    finally:
        worker.stop_event.set()
        worker.client.close()


def import_results(args: argparse.Namespace) -> None:
    from .benchmark_import import import_benchmarks
    from .db import Database
    load_environment()
    if args.path.stat().st_size > 100_000_000:
        raise SystemExit('Benchmark result file exceeds the import limit')
    document=json.loads(args.path.read_text(encoding='utf-8'))
    db=Database(os.environ['SITEFORGE_DATABASE_URL'])
    try:
        count=import_benchmarks(db,os.environ['SITEFORGE_ORG_ID'],document)
        print(json.dumps({'imported_runs':count}))
    finally:
        db.dispose()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    init=commands.add_parser('init')
    init.add_argument('--database', default='sqlite:///runtime/local.db')
    init.set_defaults(handler=initialize)
    commands.add_parser('serve').set_defaults(handler=serve)
    commands.add_parser('demo').set_defaults(handler=demo)
    results=commands.add_parser('import-benchmarks')
    results.add_argument('--path',type=Path,default=Path('benchmarks/results/results.json'))
    results.set_defaults(handler=import_results)
    args=parser.parse_args()
    args.handler(args)


if __name__=='__main__':
    main()
