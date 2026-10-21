"""Real bounded filesystem transfers; no provider, shell, credentials, or network."""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from filelock import FileLock, Timeout

import siteforge.bundles as module
from siteforge.bundles import BundleFile, BundleManifest, BundleStore, inspect_bundle
from siteforge.queue import digest


def files(mode="preview", origin="https://preview.invalid"):
    robots = "index, follow" if mode == "production" else "noindex, nofollow"
    def html(route):
        return (f'<!doctype html><html><head><meta name="robots" content="{robots}">'
                f'<link rel="canonical" href="{origin}{route}"></head><body>Utility</body></html>').encode()
    return {"index.html": html("/"), "privacy/index.html": html("/privacy/"),
            "_astro/planner.ab12.js": b"console.log('browser-only calculator');",
            "robots.txt": ((f"User-agent: *\nAllow: /\nSitemap: {origin}/sitemap.xml\n")
                           if mode == "production" else "User-agent: *\nDisallow: /\n").encode(),
            "sitemap.xml": ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f'<url><loc>{origin}/</loc></url><url><loc>{origin}/privacy/</loc></url></urlset>').encode()}


def manifest(contents=None, *, mode="preview", site=None, origin="https://preview.invalid"):
    contents = files(mode, origin) if contents is None else contents
    return BundleManifest(site_id=site or uuid4(), commit_sha="a" * 40, mode=mode, canonical_origin=origin,
        preview_deployment_id=uuid4() if mode == "production" else None,
        source_preview_tree_sha256="b" * 64 if mode == "production" else None,
        files=[BundleFile(path=path, sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
               for path, content in contents.items()])


@pytest.fixture
def identity():
    return {"org_id": str(uuid4()), "uploader": "authenticated-release-ci"}


def transfer(store, model, contents, identity):
    begun = store.begin(model, **identity)
    for path, content in contents.items():
        store.upload(begun["bundle_id"], path, content, **identity)
    return store.finalize(begun["bundle_id"], **identity)


def test_real_transfer_replay_exact_tree_and_private_provenance(tmp_path, identity):
    store = BundleStore(tmp_path, enabled=True)
    content = files()
    model = manifest(content)
    result = transfer(store, model, content, identity)
    assert result["status"] == "sealed"
    assert result["tree_sha256"] == digest(tuple(sorted((path, hashlib.sha1(data).hexdigest(),
        hashlib.sha256(data).hexdigest(), len(data)) for path, data in content.items())))
    assert inspect_bundle(tmp_path, result["relative_directory"]) == result
    assert store.finalize(result["bundle_id"], **identity) == result
    assert store.begin(model, **identity)["status"] == "sealed"
    assert store.describe(result["bundle_id"], **identity)["manifest"] == model.model_dump(mode="json")
    assert store.upload(result["bundle_id"], "index.html", content["index.html"], **identity)["bytes"] > 0
    deployed = tmp_path / result["relative_directory"]
    assert sorted(path.relative_to(deployed).as_posix() for path in deployed.rglob("*") if path.is_file()) == sorted(content)
    assert not any(identity["uploader"].encode() in data for data in content.values())
    assert (deployed.parent / "manifest.json").is_file()
    assert "not independent GitHub attestation" in result["assurance"]


def test_production_requires_server_origin_and_reviewed_preview(tmp_path, identity):
    site = uuid4()
    content = files("production", "https://rollwise.net")
    model = manifest(content, mode="production", site=site, origin="https://rollwise.net")
    with pytest.raises(ValueError, match="allowlisted"):
        BundleStore(tmp_path, enabled=True).begin(model, **identity)
    store = BundleStore(tmp_path, enabled=True, allowed_origins={str(site): "https://rollwise.net/"})
    result = transfer(store, model, content, identity)
    assert result["preview_deployment_id"] == str(model.preview_deployment_id)
    assert result["source_preview_tree_sha256"] == "b" * 64
    with pytest.raises(ValueError, match="reviewed source"):
        BundleManifest.model_validate({**model.model_dump(mode="json"), "preview_deployment_id": None})


@pytest.mark.parametrize("path", ["../out.html", "/index.html", "C:/out.html", "a\\out.html", ".env", ".env.json",
    ".git/config.json", "a/../index.html", "a//b.html", "con.txt", "NUL.html", "a/LPT1.json", "foo./x.html",
    "x.ps1", "x.py", "x.exe", "x.dll", "x.sh", "x.zip", "x.map", "functions/x.js", "secrets/a.json"])
def test_reject_unsafe_static_paths(path):
    with pytest.raises(ValueError):
        BundleFile(path=path, sha256="a" * 64, bytes=0)


@pytest.mark.parametrize("origin", ["http://rollwise.net", "https://u:p@rollwise.net", "https://rollwise.net/path",
    "https://rollwise.net?token=secret", "https://rollwise.net/#x", "https://localhost", "https://rollwise.net:444"])
def test_canonical_rejects_credentials_paths_and_non_https(origin):
    with pytest.raises(ValueError):
        manifest(origin=origin)


def test_casefold_file_directory_collisions_and_size_bounds():
    data = manifest().model_dump(mode="json")
    data["files"].append({**data["files"][0], "path": data["files"][0]["path"].upper()})
    with pytest.raises(ValueError, match="Duplicate"):
        BundleManifest.model_validate(data)
    with pytest.raises(ValueError):
        BundleFile(path="a.js", sha256="a" * 64, bytes=True)
    with pytest.raises(ValueError):
        BundleFile(path="a.js", sha256="a" * 64, bytes=4_000_001)
    data = manifest().model_dump(mode="json")
    data["files"] += [{"path": f"big{i}.js", "sha256": "a" * 64, "bytes": 4_000_000} for i in range(5)]
    with pytest.raises(ValueError, match="total bundle"):
        BundleManifest.model_validate(data)


def test_disabled_has_no_filesystem_effect(tmp_path, identity):
    root = tmp_path / "absent"
    with pytest.raises(ValueError, match="disabled"):
        BundleStore(root).begin(manifest(), **identity)
    assert not root.exists()


def test_identity_cross_tenant_wrong_bytes_and_incomplete_fail_closed(tmp_path, identity):
    store = BundleStore(tmp_path, enabled=True)
    begun = store.begin(manifest(), **identity)
    identifier = begun["bundle_id"]
    for changed in ({**identity, "org_id": str(uuid4())}, {**identity, "uploader": "other"}):
        with pytest.raises(ValueError, match="another authenticated"):
            store.describe(identifier, **changed)
        with pytest.raises(ValueError, match="another authenticated"):
            store.upload(identifier, "index.html", b"wrong", **changed)
    with pytest.raises(ValueError, match="differs"):
        store.upload(identifier, "index.html", b"wrong", **identity)
    with pytest.raises(ValueError, match="incomplete"):
        store.finalize(identifier, **identity)
    assert not (tmp_path / "b" / identifier).exists()


@pytest.mark.parametrize("tamper", ["noindex", "canonical", "sitemap", "robots", "secret"])
def test_invalid_compiled_evidence_never_published(tmp_path, identity, tamper):
    site = uuid4()
    content = files("production", "https://rollwise.net")
    if tamper == "noindex":
        content["privacy/index.html"] = content["privacy/index.html"].replace(b"index, follow", b"noindex, nofollow")
    elif tamper == "canonical":
        content["index.html"] = content["index.html"].replace(b"https://rollwise.net/", b"https://evil.net/")
    elif tamper == "sitemap":
        content["sitemap.xml"] = content["sitemap.xml"].replace(b"/privacy/", b"/missing/")
    elif tamper == "robots":
        content["robots.txt"] = b"User-agent: *\nDisallow: /\n"
    else:
        content["secret.json"] = b'{"client_secret":"fixture-should-not-upload"}'
    model = manifest(content, mode="production", site=site, origin="https://rollwise.net")
    store = BundleStore(tmp_path, enabled=True, allowed_origins={str(site): "https://rollwise.net"})
    with pytest.raises(ValueError):
        transfer(store, model, content, identity)
    assert not any((tmp_path / "b").iterdir())


def test_tampered_sealed_tree_and_manifest_are_detected(tmp_path, identity):
    store = BundleStore(tmp_path, enabled=True)
    result = transfer(store, manifest(), files(), identity)
    directory = tmp_path / result["relative_directory"]
    (directory / "extra.js").write_bytes(b"unreviewed")
    with pytest.raises(ValueError, match="unexpected"):
        inspect_bundle(tmp_path, result["relative_directory"])
    with pytest.raises(ValueError):
        store.begin(BundleManifest.model_validate(store._metadata(result["bundle_id"], **identity)[1]["manifest"]), **identity)
    (directory / "extra.js").unlink()
    metadata_path = directory.parent / "manifest.json"
    data = json.loads(metadata_path.read_text())
    data["manifest"]["commit_sha"] = "c" * 40
    metadata_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="binding changed"):
        inspect_bundle(tmp_path, result["relative_directory"])


def test_link_and_windows_junction_rejection(tmp_path, identity):
    store = BundleStore(tmp_path, enabled=True)
    begun = store.begin(manifest(), **identity)
    target = tmp_path / ".u" / begun["bundle_id"] / "files" / "privacy"
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        target.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("Symlinks unavailable")
        import subprocess
        completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(outside)],
                                   capture_output=True, check=False)
        if completed.returncode:
            pytest.skip("Neither symlink nor junction creation available")
    with pytest.raises(ValueError, match="links|reparse"):
        store.upload(begun["bundle_id"], "privacy/index.html", files()["privacy/index.html"], **identity)
    assert list(outside.iterdir()) == []


def test_actual_long_windows_workspace_rejected_before_any_bundle_files(tmp_path, identity):
    root = tmp_path / ("workspace-" + "x" * 65)
    store = BundleStore(root, enabled=True)
    model = manifest()
    model.files.append(BundleFile(path="a" * 75 + ".html", sha256="a" * 64, bytes=0))
    with pytest.raises(ValueError, match="Windows absolute"):
        store.begin(model, **identity)
    assert list((root / ".u").iterdir()) == []


def test_capacity_and_cross_process_lock_fences(tmp_path, identity, monkeypatch):
    store = BundleStore(tmp_path, enabled=True)
    monkeypatch.setattr(module, "MAX_STAGING", 1)
    begun = store.begin(manifest(), **identity)
    with pytest.raises(ValueError, match="capacity"):
        store.begin(manifest(), **identity)
    with FileLock(str(tmp_path / ".l" / (begun["bundle_id"][:2] + ".lock")), timeout=0):
        with pytest.raises(Timeout):
            store.upload(begun["bundle_id"], "index.html", files()["index.html"], **identity)


def test_concurrent_begins_cannot_exceed_disk_capacity(tmp_path, identity, monkeypatch):
    store = BundleStore(tmp_path, enabled=True)
    store._ready()
    monkeypatch.setattr(module, "MAX_STAGING", 1)
    def begin(_):
        try:
            return store.begin(manifest(), **identity)["bundle_id"]
        except (ValueError, Timeout):
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(begin, range(8)))
    assert len([value for value in results if value]) == 1
    assert len(list((tmp_path / ".u").iterdir())) == 1


def test_crash_before_atomic_publication_is_resumable_without_reupload(tmp_path, identity, monkeypatch):
    store = BundleStore(tmp_path, enabled=True)
    begun = store.begin(manifest(), **identity)
    identifier = begun["bundle_id"]
    for path, content in files().items():
        store.upload(identifier, path, content, **identity)
    real_replace = module.atomic_replace
    def crash(source, target):
        if Path(source).is_dir():
            raise OSError("fixture publication interruption")
        real_replace(source, target)
    monkeypatch.setattr(module, "atomic_replace", crash)
    with pytest.raises(OSError):
        store.finalize(identifier, **identity)
    assert store.describe(identifier, **identity)["status"] == "staging"
    assert not (tmp_path / "b" / identifier).exists()
    monkeypatch.setattr(module, "atomic_replace", real_replace)
    assert store.finalize(identifier, **identity)["status"] == "sealed"


def test_unknown_upload_ids_cannot_create_unbounded_lock_metadata(tmp_path, identity):
    store = BundleStore(tmp_path, enabled=True)
    for number in range(300):
        with pytest.raises(ValueError, match="metadata"):
            store.upload(hashlib.sha256(str(number).encode()).hexdigest(), "index.html", b"", **identity)
    assert len(list((tmp_path / ".l").iterdir())) <= 256
    assert list((tmp_path / ".u").iterdir()) == []
