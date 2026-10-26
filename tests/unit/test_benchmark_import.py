from uuid import uuid4

from sqlalchemy import func, select

from siteforge.benchmark_import import import_benchmarks
from siteforge.db import BenchmarkResult, BenchmarkRun, Database, Model


def test_import_is_idempotent_and_keeps_tenants_and_aliases_separate():
    db=Database('sqlite:///:memory:')
    db.create_schema()
    org1,org2=str(uuid4()),str(uuid4())
    for org in (org1,org2):
        db.provision_org(org)
    run={'run_id':str(uuid4()),'source_model':'fixture/a','model':'shared-alias',
         'quantization':'Q4_K_M','status':'complete','results':[{'task_id':'tool-01','trial':0,'passed':True}]}
    document={'runs':[run]}
    import_benchmarks(db,org1,document)
    import_benchmarks(db,org1,document)
    import_benchmarks(db,org2,document)
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(BenchmarkRun))==2
        assert session.scalar(select(func.count()).select_from(BenchmarkResult))==2
        assert session.scalar(select(func.count()).select_from(Model))==2
    db.dispose()
