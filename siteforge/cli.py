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
            if key.startswith(('SITEFORGE_', 'DATABASE_URL', 'LMSTUDIO_')) or key == 'ANTHROPIC_API_KEY':
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


def demo(args: argparse.Namespace) -> None:
    from .agents import fixture_payload
    from .policy import AGENT_TOOLS
    from .worker import WindowsWorker, WorkerSettings
    load_environment()
    revision=args.revision
    slug='label-roll-planner' if revision=='v1' else f'label-roll-planner-{revision}'
    token = os.environ['SITEFORGE_OWNER_TOKEN']
    origin = os.environ.get('SITEFORGE_API_URL', 'http://127.0.0.1:8080')
    with httpx.Client(base_url=origin, headers={'Authorization': f'Bearer {token}'},
                      follow_redirects=False, trust_env=False, timeout=30) as client:
        def post(path: str, body: dict) -> dict:
            response = client.post(path, json=body)
            response.raise_for_status()
            return response.json()
        site = post('/v1/sites', {'slug':slug,'config':{'mode':'fixture','commercial_launch':False}})
        workflow = post('/v1/workflows', {'type':'fixture_site','site_id':site['id'],
                                          'idempotency_key':f'fixture-site-{revision}'})
        previous: list[str] = []
        for role in ('portfolio_director','research','developer','content','quality','growth','revenue'):
            task = post('/v1/tasks', {'agent_type':role, 'capability':sorted(AGENT_TOOLS[role])[0],
                'input':fixture_payload(slug), 'site_id':site['id'], 'workflow_id':workflow['id'],
                'dependencies':previous,'idempotency_key':f'fixture-{revision}-{role}'})
            previous=[task['id']]
    worker = WindowsWorker(WorkerSettings.from_env())
    worker.register()
    worker.start_heartbeat()
    try:
        count=0
        while count < 20 and worker.run_once():
            count+=1
        print(json.dumps({'processed_tasks':count,'site_id':site['id'], 'workflow_id':workflow['id'],
                          'artifacts':str(Path(os.environ.get('SITEFORGE_ARTIFACT_ROOT','runtime/artifacts'))/slug), 'mode':'fixture',
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


ADVISOR_ROOT = Path('runtime/advisor')


def advisor_command(args: argparse.Namespace) -> None:
    from .advisor import (advisor_settings, build_request, ensure_budgets, file_stem, request_approval, run_review,
                          save_request)
    from .db import Database
    from .policy import PolicyService
    from .queue import DomainError
    load_environment()
    db = Database(os.environ['SITEFORGE_DATABASE_URL'])
    policy, org = PolicyService(db), os.environ['SITEFORGE_ORG_ID']
    try:
        if args.action == 'propose':
            document = build_request(
                args.kind.replace('-', '_'), args.site_id, args.brief.read_text(encoding='utf-8'),
                documents=[(path.name, path.read_text(encoding='utf-8')) for path in args.text],
                screenshots=[(path.name, path.read_bytes()) for path in args.screenshot],
                effort=args.effort, max_tokens=args.max_tokens)
            path = save_request(document, ADVISOR_ROOT)
            approval = request_approval(policy, org, document, 'advisor-cli')
            print(json.dumps({'approval_id': approval['id'], 'request': str(path),
                              'worst_case_usd': document['max_cost'], 'status': approval['status'],
                              'next': 'Review and approve it on the dashboard Approvals page, then run '
                                      'siteforge advisor run with this approval id and request path.'},
                             indent=2, default=str))
            return
        settings = advisor_settings()
        if settings['enabled'] != 'true':
            raise SystemExit('Paid advisor calls are off. Set SITEFORGE_ADVISOR_ENABLED=true in .env to allow them.')
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise SystemExit('Set ANTHROPIC_API_KEY in the ignored .env file; never commit or paste it elsewhere.')
        ensure_budgets(policy, org, monthly=settings['monthly'], daily=settings['daily'])
        import anthropic
        result = run_review(policy, org, args.approval_id, args.request, anthropic.Anthropic(),
                            results_root=ADVISOR_ROOT)
        print(json.dumps({key: result[key] for key in ('status', 'served_by', 'measured_cost', 'approved_max_cost')}
                         | {'result': str(ADVISOR_ROOT / f"{file_stem(result['request_sha256'])}.result.json")}, indent=2))
    except DomainError as error:
        raise SystemExit(f'Advisor stopped: {error}') from error
    finally:
        db.dispose()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    init=commands.add_parser('init')
    init.add_argument('--database', default='sqlite:///runtime/local.db')
    init.set_defaults(handler=initialize)
    commands.add_parser('serve').set_defaults(handler=serve)
    demo_parser=commands.add_parser('demo')
    demo_parser.add_argument('--revision',default='v1',help='Use a fresh bounded slug for a new template revision')
    demo_parser.set_defaults(handler=demo)
    results=commands.add_parser('import-benchmarks')
    results.add_argument('--path',type=Path,default=Path('benchmarks/results/results.json'))
    results.set_defaults(handler=import_results)
    advisor=commands.add_parser('advisor', help='Owner-approved, capped Claude Opus 5.5 checkpoint reviews')
    actions=advisor.add_subparsers(dest='action', required=True)
    propose=actions.add_parser('propose', help='Prepare a review and request owner approval; sends nothing')
    propose.add_argument('--kind', choices=['site-review', 'research-check'], required=True)
    propose.add_argument('--site-id', required=True)
    propose.add_argument('--brief', type=Path, required=True, help='Who the site or packet serves and why')
    propose.add_argument('--text', type=Path, action='append', default=[], help='Page text or evidence packet; repeatable')
    propose.add_argument('--screenshot', type=Path, action='append', default=[], help='PNG screenshot; repeatable')
    propose.add_argument('--effort', choices=['low', 'medium', 'high'], default='medium')
    propose.add_argument('--max-tokens', type=int, default=16000)
    run=actions.add_parser('run', help='Send one owner-approved review')
    run.add_argument('--approval-id', required=True)
    run.add_argument('--request', type=Path, required=True)
    advisor.set_defaults(handler=advisor_command)
    args=parser.parse_args()
    args.handler(args)


if __name__=='__main__':
    main()
