import hashlib
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from fastapi.testclient import TestClient

from siteforge.api import create_app
from siteforge.contracts import ActionExecution, ActionRequest, TaskCreate
from siteforge.db import Database, Deployment, Site, utcnow
from siteforge.policy import PolicyService
from siteforge.queue import QueueService
from siteforge.release import ReleaseService


@pytest.fixture
def release_api():
    db = Database('sqlite://')
    db.create_schema()
    org, other, first, second = map(str, (uuid4(), uuid4(), uuid4(), uuid4()))
    db.provision_org(org)
    db.provision_org(other)
    with db.transaction() as session:
        session.add_all([Site(id=first, org_id=org, slug='first'), Site(id=second, org_id=org, slug='second')])
    def token(role, **extra):
        return {'subject':'owner', 'org_id':org, 'role':role, **extra}
    config = {
        'owner':token('owner'), 'observer':token('observer'),
        'release':token('release',site_ids=[first],capabilities=['plan_release','deploy_production','reconcile_release'],
                        expires_at=utcnow()+timedelta(hours=1)),
        'invalid':token('release',site_ids=[first],capabilities=['plan_release']),
        'guard':token('release',site_ids=[first],capabilities=['guard_production'],
                      expires_at=utcnow()+timedelta(hours=1)),
        'other':{'subject':'other','org_id':other,'role':'owner'},
    }
    client = TestClient(create_app(db, {hashlib.sha256(key.encode()).hexdigest():value for key,value in config.items()}))
    yield client, db, org, first, second
    client.close()
    db.dispose()


def auth(value):
    return {'Authorization':'Bearer '+value}


def test_delegated_release_scope_cannot_read_control_plane_or_other_sites(release_api, monkeypatch):
    client, db, org, first, second = release_api
    calls = []
    class Fake:
        def plan_preview(self, site_id, commit, directory, *, org_id=None):
            calls.append(site_id)
            return {'action':'deploy_preview','site_id':site_id,'payload':{'commit_sha':commit},'amount':'0','currency':'USD'}
        def close(self): pass
    monkeypatch.setattr(ReleaseService, 'from_environment', classmethod(lambda cls, db, site: Fake()))
    body = {'site_id':first,'commit_sha':'a'*40,'relative_directory':'reviewed-dist'}
    assert client.post('/v1/releases/preview-plan',headers=auth('release'),json=body).status_code==200
    assert client.post('/v1/releases/preview-plan',headers=auth('release'),json={**body,'site_id':second}).status_code==403
    assert client.post('/v1/releases/preview-plan',headers=auth('observer'),json=body).status_code==403
    assert client.post('/v1/releases/preview-plan',headers=auth('invalid'),json=body).status_code==401
    assert calls==[first]
    task=QueueService(db).enqueue(org,TaskCreate(agent_type='research',capability='read_sources',idempotency_key='private'))
    for path in ('/v1/sites','/v1/budgets','/metrics',f'/v1/tasks/{task.id}',f'/v1/tasks/{task.id}/checkpoint'):
        assert client.get(path,headers=auth('release')).status_code==403
    assert client.post('/v1/kill-switch',headers=auth('release'),json={'enabled':True}).status_code==403


def test_release_lookup_is_tenant_scoped_and_preserves_orphan_intents(release_api):
    client, db, org, first, _ = release_api
    policy=PolicyService(db)
    payload={'commit_sha':'a'*40}
    request=ActionRequest(agent_type='developer',action='deploy_production',site_id=first,payload=payload,idempotency_key='approve')
    approval=policy.request_approval(org,request,'owner')
    policy.decide(org,approval['id'],'owner',True)
    execute=ActionExecution(action='deploy_production',site_id=first,payload=payload,idempotency_key='stable')
    receipt=policy.authorize(org,approval['id'],execute,'owner')
    lookup='/v1/releases/lookup'
    assert client.post(lookup,headers=auth('release'),json={'idempotency_key':'stable'}).json()['intent_only'] is True
    identifier=str(uuid5(NAMESPACE_URL,'siteforge:release:'+receipt['id']))
    with db.transaction() as session:
        session.add(Deployment(id=identifier,org_id=org,site_id=first,approval_id=approval['id'],
            environment='production',commit_sha='a'*40,status='unknown',data={'execution':execute.model_dump(mode='json')}))
    recorded=client.post(lookup,headers=auth('release'),json={'idempotency_key':'stable'}).json()
    assert recorded['deployment']['id']==identifier and recorded['deployment']['status']=='unknown'
    assert client.post(lookup,headers=auth('other'),json={'idempotency_key':'stable'}).json()=={'found':False}
    assert client.post(lookup,headers=auth('observer'),json={'idempotency_key':'stable'}).status_code==403


def test_release_factory_stays_disabled_without_server_configuration(release_api, monkeypatch):
    client, _, _, first, _ = release_api
    monkeypatch.setenv('SITEFORGE_RELEASE_ENABLED','false')
    monkeypatch.delenv('SITEFORGE_RELEASE_KNOWN_COST_USD',raising=False)
    result=client.post('/v1/releases/preview-plan',headers=auth('owner'),json={
        'site_id':first,'commit_sha':'a'*40,'relative_directory':'approved-dist'})
    assert result.status_code==503
    assert result.json()['detail']=='Release service is not configured for this site'


def test_rollback_guard_requires_separate_site_capability_and_tenant(release_api, monkeypatch):
    client, db, org, first, second = release_api
    identifier, other_id = str(uuid4()), str(uuid4())
    with db.transaction() as session:
        session.add_all([Deployment(id=identifier, org_id=org, site_id=first, environment='production',
                                    commit_sha='a'*40, status='health_failed', data={}),
                         Deployment(id=other_id, org_id=org, site_id=second, environment='production',
                                    commit_sha='a'*40, status='health_failed', data={})])
    calls = []
    class Fake:
        def guard_production(self, org_id, deployment_id, actor):
            calls.append((org_id, deployment_id, actor))
            return {'id': deployment_id, 'status': 'rolled_back'}
        def close(self): pass
    monkeypatch.setattr(ReleaseService, 'from_environment', classmethod(lambda cls, db, site: Fake()))
    url = f'/v1/releases/{identifier}/guard-production'
    assert client.post(url, headers=auth('release'), json={}).status_code == 403
    assert client.post(url, headers=auth('observer'), json={}).status_code == 403
    assert client.post(url, headers=auth('other'), json={}).status_code == 404
    assert client.post(f'/v1/releases/{other_id}/guard-production', headers=auth('guard'), json={}).status_code == 403
    assert client.post(url, headers=auth('guard'), json={}).json()['status'] == 'rolled_back'
    assert calls == [(org, identifier, 'owner')]
