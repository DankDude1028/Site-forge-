import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from siteforge.api import create_app
from siteforge.db import AuditEvent, Database, Site, utcnow


def auth(token):
    return {"Authorization": "Bearer " + token}


@pytest.fixture
def bundle_api(tmp_path, monkeypatch):
    db = Database("sqlite://")
    db.create_schema()
    org, other_org, site, other_site, provider_site = (str(uuid4()) for _ in range(5))
    db.provision_org(org)
    db.provision_org(other_org)
    with db.transaction() as session:
        session.add(Site(id=site, org_id=org, slug="bundle-site"))
        session.add(Site(id=other_site, org_id=org, slug="other-site"))
    def token(role, **kwargs):
        return {"role": role, "subject": "reviewing-owner", "org_id": org, **kwargs}
    config = {
        "owner": token("owner"), "observer": token("observer"),
        "transfer": token("release", site_ids=[site], capabilities=["upload_bundle"],
                          expires_at=utcnow() + timedelta(hours=1)),
        "wrong-site": token("release", site_ids=[other_site], capabilities=["upload_bundle"],
                            expires_at=utcnow() + timedelta(hours=1)),
        "no-capability": token("release", site_ids=[site], capabilities=["plan_release"],
                               expires_at=utcnow() + timedelta(hours=1)),
        "other-org": {"role": "owner", "subject": "reviewing-owner", "org_id": other_org},
    }
    import json
    monkeypatch.setenv("SITEFORGE_BUNDLES_ENABLED", "true")
    monkeypatch.setenv("SITEFORGE_PREVIEW_ROOT", str(tmp_path / "bundles"))
    monkeypatch.setenv("SITEFORGE_RELEASE_SITE_BINDINGS", json.dumps({site: provider_site}))
    monkeypatch.setenv("SITEFORGE_RELEASE_PRODUCTION_ORIGINS", json.dumps({provider_site: "https://rollwise.example"}))
    client = TestClient(create_app(db, {hashlib.sha256(key.encode()).hexdigest(): value
                                      for key, value in config.items()}))
    files = {
        "index.html": b'<html><head><meta name="robots" content="noindex, nofollow"><link rel="canonical" href="https://rollwise.example/"></head><body>Reviewed preview</body></html>',
        "robots.txt": b"User-agent: *\nDisallow: /\n",
        "sitemap.xml": b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://rollwise.example/</loc></url></urlset>',
    }
    manifest = {"version": 1, "site_id": site, "commit_sha": "a" * 40, "mode": "preview",
                "canonical_origin": "https://rollwise.example",
                "files": [{"path": path, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
                          for path, content in sorted(files.items())]}
    yield client, db, org, site, manifest, files
    client.close()
    db.dispose()


def test_authenticated_static_transfer_seals_exact_bytes_without_provider_effect(bundle_api, tmp_path):
    client, db, org, site, manifest, files = bundle_api
    begun = client.post("/v1/bundles", headers=auth("transfer"), json=manifest)
    assert begun.status_code == 200, begun.json()
    result = begun.json()
    identifier = result["bundle_id"]
    assert result["status"] == "staging"
    for path, content in files.items():
        sent = client.put(f"/v1/bundles/{identifier}/files", params={"path": path}, content=content,
                          headers={**auth("transfer"), "Content-Type": "application/octet-stream"})
        assert sent.status_code == 200, sent.json()
    sealed = client.post(f"/v1/bundles/{identifier}/finalize", headers=auth("transfer"), json={})
    assert sealed.status_code == 200, sealed.json()
    binding = sealed.json()
    assert binding["status"] == "sealed"
    output = tmp_path / "bundles" / binding["relative_directory"]
    assert {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()} == set(files)
    assert all((output / path).read_bytes() == content for path, content in files.items())
    assert client.post("/v1/bundles", headers=auth("transfer"), json=manifest).json()["bundle_id"] == identifier
    with db.session() as session:
        events = session.scalars(select(AuditEvent).where(AuditEvent.org_id == org)).all()
        assert {"bundle.begin", "bundle.upload", "bundle.seal"} <= {event.action for event in events}
        assert all("release.dispatch" not in event.action for event in events)


def test_transfer_principal_site_tenant_capability_and_kill_switch_are_enforced(bundle_api):
    client, _, _, _, manifest, files = bundle_api
    for token in ("observer", "wrong-site", "no-capability", "other-org"):
        assert client.post("/v1/bundles", headers=auth(token), json=manifest).status_code in {403, 404}
    identifier = client.post("/v1/bundles", headers=auth("transfer"), json=manifest).json()["bundle_id"]
    for token in ("wrong-site", "no-capability", "other-org"):
        assert client.get(f"/v1/bundles/{identifier}", headers=auth(token)).status_code in {403, 404}
    assert client.post("/v1/kill-switch", headers=auth("owner"), json={"enabled": True}).status_code == 200
    sent = client.put(f"/v1/bundles/{identifier}/files", params={"path": "index.html"},
                      content=files["index.html"], headers={**auth("transfer"), "Content-Type": "application/octet-stream"})
    assert sent.status_code == 403
    assert client.post(f"/v1/bundles/{identifier}/finalize", headers=auth("transfer"), json={}).status_code == 403


def test_transfer_rejects_disabled_unknown_digest_wrong_type_and_oversized_body(bundle_api, monkeypatch):
    client, _, _, _, manifest, files = bundle_api
    monkeypatch.setenv("SITEFORGE_BUNDLES_ENABLED", "false")
    assert client.post("/v1/bundles", headers=auth("owner"), json=manifest).status_code == 503
    monkeypatch.setenv("SITEFORGE_BUNDLES_ENABLED", "true")
    identifier = client.post("/v1/bundles", headers=auth("transfer"), json=manifest).json()["bundle_id"]
    url = f"/v1/bundles/{identifier}/files"
    assert client.put(url, params={"path": "index.html"}, headers=auth("transfer"),
                      content=files["index.html"]).status_code == 415
    headers = {**auth("transfer"), "Content-Type": "application/octet-stream"}
    assert client.put(url, params={"path": "index.html"}, headers=headers, content=b"changed").status_code == 422
    assert client.put(url, params={"path": "../escape"}, headers=headers, content=b"x").status_code == 422
    assert client.put(url, params={"path": "index.html"}, headers=headers, content=b"x" * 4_000_001).status_code == 413
    assert client.post(f"/v1/bundles/{identifier}/finalize", headers=auth("transfer"), json={}).status_code == 422
