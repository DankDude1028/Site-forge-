import json
from uuid import uuid4

import httpx
import pytest

from siteforge.release_client import ReleaseClient


def test_client_binds_exact_reviewed_commit_and_stable_request():
    site, preview, approval = map(str, (uuid4(), uuid4(), uuid4()))
    seen = []
    def transport(request):
        seen.append((request.url.path, json.loads(request.content)))
        assert request.headers['Authorization'] == 'Bearer fixture-token'
        if request.url.path.endswith('/lookup'):
            return httpx.Response(200, json={'found':False})
        if request.url.path.endswith('promotion-plan'):
            return httpx.Response(200, json={'action':'deploy_production', 'site_id':site,
                'payload':{'commit_sha':'a'*40}, 'amount':'0.000001', 'currency':'USD'})
        return httpx.Response(200, json={'id':str(uuid4()), 'status':'healthy'})
    client = ReleaseClient('https://supervisor.example', 'fixture-token', transport=httpx.MockTransport(transport))
    try:
        assert client.promote(preview, approval, 'a'*40, 'stable-release')['status'] == 'healthy'
        assert seen[2][1]['idempotency_key'] == 'stable-release'
        assert seen[2][1]['amount'] == '0.000001'
        assert seen[2][0] == f'/v1/releases/{approval}/production'
    finally:
        client.close()


def test_changed_commit_or_redirect_never_dispatches_mutation():
    calls = []
    def transport(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/lookup'):
            return httpx.Response(200, json={'found':False})
        return httpx.Response(200, json={'action':'deploy_production', 'payload':{'commit_sha':'b'*40}})
    client = ReleaseClient('http://127.0.0.1:8080', 'fixture-token', transport=httpx.MockTransport(transport))
    try:
        with pytest.raises(RuntimeError, match='exact reviewed commit'):
            client.promote(str(uuid4()), str(uuid4()), 'a'*40, 'stable')
        assert calls == ['/v1/releases/lookup', '/v1/releases/promotion-plan']
    finally:
        client.close()
    client = ReleaseClient('https://supervisor.example', 'fixture-token',
        transport=httpx.MockTransport(lambda request: httpx.Response(307, headers={'Location':'https://other.example'})))
    try:
        with pytest.raises(RuntimeError, match='307'):
            client.reconcile(str(uuid4()))
    finally:
        client.close()


@pytest.mark.parametrize('origin', ['http://public.example', 'https://user:password@host.example',
                                    'https://host.example/arbitrary', 'https://host.example?secret=x'])
def test_client_refuses_unsafe_origin(origin):
    with pytest.raises(ValueError):
        ReleaseClient(origin, 'fixture-token')


def test_health_wait_reconciles_with_reads_without_repeating_promotion(monkeypatch):
    from siteforge import release_client
    deployed = str(uuid4())
    paths = []
    def transport(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={'id':deployed, 'status':'healthy'})
    client = ReleaseClient('https://supervisor.example', 'fixture-token', transport=httpx.MockTransport(transport))
    monkeypatch.setattr(release_client.time, 'sleep', lambda seconds: None)
    try:
        assert client.wait_for_status({'id':deployed, 'status':'unknown'}, 1)['status'] == 'healthy'
        assert paths == [f'/v1/releases/{deployed}/reconcile']
    finally:
        client.close()


def test_stable_cli_replay_only_reconciles_original_deployment():
    preview, approval, deployed = map(str, (uuid4(),uuid4(),uuid4()))
    paths = []
    def transport(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/lookup'):
            return httpx.Response(200,json={'found':True,'deployment':{'id':deployed,
                'commit_sha':'a'*40,'approval_id':approval,'environment':'production',
                'data':{'execution':{'idempotency_key':'stable','payload':{'preview_deployment_id':preview}}}}})
        return httpx.Response(200,json={'id':deployed,'status':'healthy'})
    client = ReleaseClient('https://supervisor.example','fixture-token',transport=httpx.MockTransport(transport))
    try:
        assert client.promote(preview,approval,'a'*40,'stable')['status']=='healthy'
        assert paths==['/v1/releases/lookup',f'/v1/releases/{deployed}/reconcile']
        with pytest.raises(RuntimeError,match='different approved action'):
            client.promote(preview,approval,'b'*40,'stable')
        assert paths[-1]=='/v1/releases/lookup'
        with pytest.raises(RuntimeError,match='different approved action'):
            client.promote(str(uuid4()),approval,'a'*40,'stable')
        assert paths[-1]=='/v1/releases/lookup'
    finally:
        client.close()


def test_preview_client_uses_exact_approved_plan_and_reconciles_stable_replay():
    site, approval, deployed=map(str,(uuid4(),uuid4(),uuid4()))
    paths=[]
    saved={}
    def transport(request):
        path=request.url.path
        paths.append(path)
        data=json.loads(request.content)
        if path.endswith('/lookup'):
            return httpx.Response(200,json={'found':True,'deployment':saved} if saved else {'found':False})
        if path.endswith('/preview-plan'):
            assert data=={'site_id':site,'commit_sha':'a'*40,'relative_directory':'reviewed-dist'}
            return httpx.Response(200,json={'action':'deploy_preview','site_id':site,'amount':'0','currency':'USD',
                'payload':{'commit_sha':'a'*40,'artifact_directory':'reviewed-dist'}})
        if path.endswith('/preview'):
            saved.update(id=deployed,site_id=site,approval_id=approval,environment='preview',commit_sha='a'*40,
                         data={'execution':data},status='ready')
        return httpx.Response(200,json=saved)
    client=ReleaseClient('https://supervisor.example','fixture-token',transport=httpx.MockTransport(transport))
    try:
        assert client.preview(site,'a'*40,'reviewed-dist',approval,'stable-preview')['status']=='ready'
        assert client.preview(site,'a'*40,'reviewed-dist',approval,'stable-preview')['status']=='ready'
        assert paths[-2:]==['/v1/releases/lookup',f'/v1/releases/{deployed}/reconcile']
        assert sum(path.endswith('/preview') for path in paths)==1
        with pytest.raises(RuntimeError,match='different approved action'):
            client.preview(site,'a'*40,'changed-dist',approval,'stable-preview')
        assert paths[-1]=='/v1/releases/lookup'
    finally:
        client.close()
