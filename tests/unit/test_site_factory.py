import pytest

from siteforge.site_factory import create_preview, inspect_preview, plan_labels, scoped_path, write_artifact


def test_label_reference_math_rounding_stock_and_coverage():
    assert plan_labels(250, 2, 5, 500, 1) == {"base_labels": 500, "labels_needed": 525,
        "rolls_required": 2, "rolls_to_order": 1, "labels_left": 475}
    assert plan_labels(1, 1, 0.1, 1)["rolls_required"] == 2
    assert plan_labels(100, 1, 0, 100, 4)["rolls_to_order"] == 0


@pytest.mark.parametrize("args", [(0, 2, 5, 500), (1.5, 2, 5, 500), (True, 2, 5, 500),
    (250, 101, 5, 500), (250, 2, float("nan"), 500), (250, 2, 101, 500), (250, 2, 5, 0)])
def test_invalid_label_inputs(args):
    with pytest.raises(ValueError):
        plan_labels(*args)


def test_factory_builds_trusted_source_and_integrity_checks_detect_tampering(tmp_path):
    artifact = create_preview(tmp_path, "label-planner")
    assert artifact["sha256"] and (tmp_path / artifact["uri"]).is_file()
    assert inspect_preview(tmp_path, "label-planner")["static_passed"]
    (tmp_path / "label-planner/source/src/lib/planner.ts").write_text("changed", encoding="utf-8")
    report = inspect_preview(tmp_path, "label-planner")
    assert not report["static_passed"]
    assert any("integrity" in item for item in report["failures"])
    assert report["astro_build"] == "pending_separate_executable_check"


def test_default_preview_source_configuration_is_verified_without_claiming_a_build(tmp_path, monkeypatch):
    # Ambient operator variables never turn source generation into a deployment
    # or change the default trusted template copied by the deterministic factory.
    monkeypatch.setenv("SITEFORGE_BUILD_MODE", "production")
    monkeypatch.setenv("SITEFORGE_SITE_URL", "https://untrusted-input.invalid")
    create_preview(tmp_path, "label-planner")
    report = inspect_preview(tmp_path, "label-planner")
    assert report["static_passed"]
    assert report["static_checks"]["preview_noindex"]
    assert report["static_checks"]["preview_crawl_route"]
    assert report["production_authorized"] is False
    assert report["astro_build"] == "pending_separate_executable_check"
    assert report["browser_accessibility"] == "pending_separate_browser_check"


@pytest.mark.parametrize("relative", ["site-config.mjs", "src/pages/index.astro", "src/pages/robots.txt.ts"])
def test_crawl_configuration_tamper_fails_even_when_artifact_manifest_is_rehashed(tmp_path, relative):
    import hashlib
    import json

    create_preview(tmp_path, "label-planner")
    path = tmp_path / "label-planner/source" / relative
    path.write_text(path.read_text(encoding="utf-8") + "\n// unreviewed configuration\n", encoding="utf-8")
    manifest_path = tmp_path / "label-planner/build/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["files"]:
        if item["path"] == relative:
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            item["bytes"] = path.stat().st_size
    manifest_path.write_text(json.dumps(manifest))
    report = inspect_preview(tmp_path, "label-planner")
    assert not report["static_passed"]
    assert "trusted_build_configuration" in report["failures"]
    assert "preview_noindex" in report["failures"]


@pytest.mark.parametrize("value", ["../outside", "bad/slug", "BAD", "x", "C:/outside", None])
def test_factory_rejects_untrusted_paths(tmp_path, value):
    with pytest.raises(ValueError):
        create_preview(tmp_path, value)


def test_artifact_boundary(tmp_path):
    with pytest.raises(ValueError):
        write_artifact(tmp_path, "../outside.json", {"secret": "never_written"})
    with pytest.raises(ValueError):
        scoped_path(tmp_path, str(tmp_path.parent / "outside.json"))
    assert not (tmp_path.parent / "outside.json").exists()


def test_existing_link_cannot_escape_artifact_root(tmp_path):
    outside = tmp_path.parent / "outside-fixture"
    outside.mkdir(exist_ok=True)
    try:
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Windows symbolic link creation is unavailable")
    with pytest.raises(ValueError):
        write_artifact(tmp_path, "link/blocked.json", {})
    assert not (outside / "blocked.json").exists()


def test_windows_junction_cannot_escape_artifact_root(tmp_path):
    import os
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows junction behavior")
    root, outside = tmp_path / "sandbox", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    junction = root / "linked"
    result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                            capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        pytest.skip("Junction creation unavailable")
    assert junction.is_junction()
    with pytest.raises(ValueError):
        write_artifact(root, "linked/blocked.json", {})
    assert not (outside / "blocked.json").exists()
