"""Actual process crashes test OS lock release; no inference server is contacted."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import siteforge.inference_lock as module
from siteforge.inference_lock import InferenceBusy, InferenceLock, ensure_inference_available


def child_process(root: Path, *, legacy=False):
    script = '''import json, os, sys
from pathlib import Path
from siteforge.inference_lock import InferenceLock
root = Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=True)
marker = root / ".run.lock"
if sys.argv[2] == "legacy":
    descriptor = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(descriptor, json.dumps({"pid": os.getpid(), "owner": "legacy-test"}).encode("utf-8"))
    os.close(descriptor)
    (root / "ready").write_text("ready", encoding="utf-8")
    sys.stdin.read(1)
else:
    with InferenceLock(marker, owner="crash-test"):
        (root / "ready").write_text("ready", encoding="utf-8")
        if sys.stdin.read(1) == "!":
            os._exit(23)
'''
    child = subprocess.Popen([sys.executable, "-c", script, str(root), "legacy" if legacy else "new"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.monotonic() + 10
    while not (root / "ready").exists() and child.poll() is None and time.monotonic() < deadline:
        time.sleep(.025)
    if not (root / "ready").exists():
        child.kill()
        _, error = child.communicate(timeout=10)
        raise AssertionError("Child could not acquire inference lock: " + error)
    return child


def stop_child(child):
    if child.poll() is None:
        child.kill()
    child.communicate(timeout=10)


def test_os_mutex_blocks_concurrent_owner_and_recovers_after_real_crash(tmp_path):
    child = child_process(tmp_path)
    marker = tmp_path / ".run.lock"
    original = marker.read_bytes()
    try:
        with pytest.raises(InferenceBusy):
            ensure_inference_available(marker)
        with pytest.raises(InferenceBusy):
            with InferenceLock(marker, owner="contender"):
                pass
        assert marker.read_bytes() == original
        # os._exit proves abrupt process termination without __exit__/finally.
        # Parent kill followed immediately by communicate can close stdin first
        # on Windows and inadvertently allow a normal context-manager exit.
        child.communicate(input="!", timeout=10)
        assert child.returncode == 23
    finally:
        stop_child(child)
    assert marker.exists()
    with InferenceLock(marker, owner="recovered"):
        assert json.loads(marker.read_text())["pid"] == os.getpid()
    assert not marker.exists()
    assert (tmp_path / ".inference.mutex").is_file()


def test_live_legacy_marker_is_preserved_then_recovered_only_after_child_exit(tmp_path):
    child = child_process(tmp_path, legacy=True)
    marker = tmp_path / ".run.lock"
    original = marker.read_bytes()
    try:
        with pytest.raises(InferenceBusy, match="alive"):
            with InferenceLock(marker, owner="new-contender"):
                pass
        with pytest.raises(InferenceBusy):
            ensure_inference_available(marker)
        assert marker.read_bytes() == original
        assert child.poll() is None
    finally:
        stop_child(child)
    ensure_inference_available(marker)
    assert not marker.exists()
    with InferenceLock(marker, owner="after-legacy"):
        assert json.loads(marker.read_text())["lock_protocol"] == "os-mutex-v1"


@pytest.mark.parametrize("content", ["{broken", "{}", '{"pid":true}', '{"pid":-1}', '{"pid":0}', '"not-object"'])
def test_unknown_marker_ownership_fails_closed_without_deletion(tmp_path, content):
    marker = tmp_path / ".run.lock"
    marker.write_text(content, encoding="utf-8")
    with pytest.raises(InferenceBusy):
        ensure_inference_available(marker)
    with pytest.raises(InferenceBusy):
        with InferenceLock(marker, owner="uncertain"):
            pass
    assert marker.read_text() == content


def test_unverifiable_process_status_cannot_recover_marker(tmp_path, monkeypatch):
    marker = tmp_path / ".run.lock"
    marker.write_text('{"pid":12345}', encoding="utf-8")
    monkeypatch.setattr(module, "process_state", lambda _pid: "unknown")
    with pytest.raises(InferenceBusy, match="unknown"):
        with InferenceLock(marker, owner="uncertain"):
            pass
    assert json.loads(marker.read_text())["pid"] == 12345


def test_exception_releases_marker_and_mutex_for_next_owner(tmp_path):
    marker = tmp_path / ".run.lock"
    with pytest.raises(ValueError):
        with InferenceLock(marker, owner="raising"):
            raise ValueError("fixture failure")
    assert not marker.exists()
    with InferenceLock(marker, owner="next"):
        assert json.loads(marker.read_text())["owner"] == "next"


def test_replaced_marker_is_not_deleted_by_old_owner(tmp_path):
    marker = tmp_path / ".run.lock"
    with InferenceLock(marker, owner="original"):
        marker.write_text(json.dumps({"pid": os.getpid(), "token": "different-owner"}), encoding="utf-8")
    assert json.loads(marker.read_text())["token"] == "different-owner"
    with pytest.raises(InferenceBusy):
        ensure_inference_available(marker)
