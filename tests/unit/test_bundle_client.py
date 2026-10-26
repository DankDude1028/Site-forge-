import hashlib
import json
from uuid import uuid4

import httpx
import pytest

from siteforge.bundle_client import BundleClient, collect_manifest


def build(tmp_path):
    (tmp_path / "index.html").write_bytes(b"reviewed html")
    (tmp_path / "robots.txt").write_bytes(b"User-agent: *\nDisallow: /\n")
    (tmp_path / "sitemap.xml").write_bytes(b"reviewed sitemap")
    manifest = collect_manifest(tmp_path, site_id=str(uuid4()), commit_sha="a" * 40,
                                mode="preview", canonical_origin="https://preview.invalid")
    return manifest


def test_client_transfers_exact_static_bytes_and_seals_without_deploy(tmp_path):
    manifest = build(tmp_path)
    identifier = "b" * 64
    uploaded = []
    def request(req):
        assert req.headers["Authorization"] == "Bearer fixture-only"
        if req.url.path == "/v1/bundles":
            assert json.loads(req.content) == manifest.model_dump(mode="json")
            return httpx.Response(200, json={"bundle_id": identifier, "status": "staging"})
        if req.url.path.endswith("/files"):
            path = req.url.params["path"]
            item = next(item for item in manifest.files if item.path == path)
            assert hashlib.sha256(req.content).hexdigest() == item.sha256
            assert req.headers["Content-Type"] == "application/octet-stream"
            uploaded.append(path)
            return httpx.Response(200, json={"bundle_id": identifier})
        assert req.url.path == f"/v1/bundles/{identifier}/finalize"
        return httpx.Response(200, json={"bundle_id": identifier, "status": "sealed",
                                        "relative_directory": f"b/{identifier}/files"})
    client = BundleClient("https://supervisor.example", "fixture-only", transport=httpx.MockTransport(request))
    try:
        assert client.upload(tmp_path, manifest)["status"] == "sealed"
        assert sorted(uploaded) == [item.path for item in manifest.files]
    finally:
        client.close()


def test_client_sealed_replay_never_uploads_again(tmp_path):
    manifest = build(tmp_path)
    identifier = "b" * 64
    calls = []
    def request(req):
        calls.append(req.url.path)
        return httpx.Response(200, json={"bundle_id": identifier, "status": "sealed",
                                        "relative_directory": f"b/{identifier}/files"})
    client = BundleClient("https://supervisor.example", "fixture-only", transport=httpx.MockTransport(request))
    try:
        assert client.upload(tmp_path, manifest)["status"] == "sealed"
        assert calls == ["/v1/bundles"]
    finally:
        client.close()


def test_client_rejects_changed_bytes_before_upload(tmp_path):
    manifest = build(tmp_path)
    (tmp_path / "index.html").write_bytes(b"changed html")
    calls = []
    def request(req):
        calls.append(req.url.path)
        return httpx.Response(200, json={"bundle_id": "b" * 64, "status": "staging"})
    client = BundleClient("https://supervisor.example", "fixture-only", transport=httpx.MockTransport(request))
    try:
        with pytest.raises(ValueError, match="changed before transfer"):
            client.upload(tmp_path, manifest)
        assert calls == ["/v1/bundles"]
    finally:
        client.close()


def test_client_rejects_an_unbound_sealed_directory(tmp_path):
    manifest = build(tmp_path)
    client = BundleClient("https://supervisor.example", "fixture-only", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"bundle_id": "b" * 64, "status": "sealed",
                                                 "relative_directory": "unbound-directory"})))
    try:
        with pytest.raises(RuntimeError, match="exact sealed bundle"):
            client.upload(tmp_path, manifest)
    finally:
        client.close()


def test_client_never_prints_rejected_server_body_or_token(tmp_path):
    manifest = build(tmp_path)
    client = BundleClient("https://supervisor.example", "fixture-only", transport=httpx.MockTransport(
        lambda request: httpx.Response(403, text="secret-server-body fixture-only")))
    try:
        with pytest.raises(RuntimeError) as error:
            client.upload(tmp_path, manifest)
        assert "secret-server-body" not in str(error.value) and "fixture-only" not in str(error.value)
    finally:
        client.close()


def test_collect_manifest_rejects_forbidden_filename_and_unknown_source_identity(tmp_path):
    build(tmp_path)
    (tmp_path / ".env").write_bytes(b"fixture")
    with pytest.raises(ValueError):
        collect_manifest(tmp_path, site_id=str(uuid4()), commit_sha="a" * 40,
                         mode="preview", canonical_origin="https://preview.invalid")
    (tmp_path / ".env").unlink()
    with pytest.raises(ValueError):
        collect_manifest(tmp_path, site_id=str(uuid4()), commit_sha="main",
                         mode="preview", canonical_origin="https://preview.invalid")
