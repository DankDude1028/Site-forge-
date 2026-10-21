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
