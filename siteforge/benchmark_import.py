"""Import measured benchmark summaries into a tenant's authenticated dashboard."""
from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from .db import BenchmarkResult, BenchmarkRun, Database, Model, Organization, audit
from .queue import DomainError


def import_benchmarks(db: Database, org_id: str, document: dict[str, Any]) -> int:
    runs = document.get('runs')
    if not isinstance(runs, list):
        raise ValueError('Benchmark document requires a runs array')
    with db.transaction() as session:
        org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
        if org is None:
            raise DomainError('organization not provisioned', 403)
        for run in runs:
            source = run.get('source_model')
            if not isinstance(source, str) or not source or len(source)>200:
                raise ValueError('Exact source model identity is required')
            quant = str(run.get('quantization', 'UNKNOWN'))
            model_id = str(uuid5(NAMESPACE_URL, f'siteforge:{org_id}:model:{source}:{quant}'))
            model = session.get(Model, model_id)
            if model is None:
                model=Model(id=model_id, org_id=org_id, model_id=source,
                            config={'quantization':quant,'inference_identifier':run.get('model')})
                session.add(model)
                session.flush()
            identifier=str(uuid5(NAMESPACE_URL, f'siteforge:{org_id}:run:{run["run_id"]}'))
            stored=session.get(BenchmarkRun, identifier)
            if stored is None:
                stored=BenchmarkRun(id=identifier,org_id=org_id,model_id=model_id)
                session.add(stored)
            stored.status=run['status']
            stored.config={key:run.get(key) for key in ('run_id','source_model','quantization','context',
                'actual_context','settings','summary','dataset_version','dataset_sha256','started_at','finished_at')}
            session.flush()
            for row in run.get('results',[]):
                if row.get('warmup'):
                    continue
                key=f'{row["task_id"]}:trial-{row["trial"]}'
                row_id=str(uuid5(NAMESPACE_URL, f'{identifier}:{key}'))
                if session.get(BenchmarkResult,row_id) is None:
                    measurements={name:row.get(name) for name in ('category','passed','schema_valid','score',
                        'wall_seconds','reason','prompt_sha256','response_sha256')}
                    measurements['completion_metrics']={name:row.get('completion',{}).get(name) for name in
                        ('latency_seconds','time_to_first_token_seconds','output_tokens','tokens_per_second')}
                    session.add(BenchmarkResult(id=row_id,org_id=org_id,run_id=identifier,
                                                task_key=key,measurements=measurements))
            audit(session, org_id, 'operator', 'benchmark.import', identifier, status=stored.status)
    return len(runs)
