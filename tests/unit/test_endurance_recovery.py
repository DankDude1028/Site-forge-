"""Crash replay and actual OS file-lock checks; these are smoke tests, not 72 hours."""
import argparse
import json
import os
import subprocess
import sys
import time

import pytest
from sqlalchemy import func, select

from siteforge.db import Artifact, Attempt, Receipt, Task
from siteforge.endurance import Simulation, run, stamp


def counts(simulation):
    with simulation.db.session() as session:
        return {model.__name__: session.scalar(select(func.count()).select_from(model))
                for model in (Task, Attempt, Artifact, Receipt)}


def test_restart_after_receipt_before_cycle_then_replay_completed_cycle(tmp_path):
    simulation = Simulation(tmp_path)
    try:
        simulation.guards(0)
        assert counts(simulation)["Receipt"] == 1
        # A hard stop can occur after an intent exists but before cycle JSON is written.
        simulation.restart()
        first = simulation.cycle(0)
        persisted = counts(simulation)
        assert persisted["Task"] == 3
        assert persisted["Artifact"] >= 3
        assert persisted["Receipt"] == 1
        simulation.restart()
        replay = simulation.cycle(0)
        assert replay["task_ids"] == first["task_ids"]
        assert counts(simulation) == persisted
    finally:
        simulation.db.dispose()


def test_actual_os_lock_excludes_second_process_and_releases(tmp_path):
    script = '''import argparse, sys
from pathlib import Path
import siteforge.endurance as endurance
root = Path(sys.argv[1])
def hold(args):
    (root / "lock-held").write_text("ready", encoding="utf-8")
    sys.stdin.read(1)
    return {"held": True}
endurance._run = hold
endurance.run(argparse.Namespace(root=root))
'''
    environment = dict(os.environ, PYTHONUTF8="1")
    child = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "lock-held").exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        assert (tmp_path / "lock-held").exists(), "Child did not acquire the file lock"
        with pytest.raises(RuntimeError, match="already owns"):
            run(argparse.Namespace(root=tmp_path))
        child.communicate(input="x", timeout=10)
        assert child.returncode == 0
        # A normal short run after process exit proves the OS lock was released.
        resumed = run(argparse.Namespace(root=tmp_path, hours=.000001, interval=0, cycles=1))
        assert resumed["kind"] == "smoke"
        assert resumed["status"] == "smoke_passed"
        assert resumed["full_acceptance_status"].startswith("PENDING")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)


def test_historical_failure_cannot_become_passed_on_resume(tmp_path):
    state = {"run_id": "fixture-history", "started_at": stamp(), "status": "failed", "kind": "smoke",
             "active_seconds": 1, "cycles": 0, "completed_tasks": 0,
             "failures": [{"type": "InjectedFailure", "error": "historical failure"}],
             "injected": {}, "recovered": {}}
    (tmp_path / "report.json").write_text(json.dumps(state), encoding="utf-8")
    resumed = run(argparse.Namespace(root=tmp_path, hours=.000001, interval=0, cycles=1))
    assert resumed["status"] == "failed"
    assert resumed["failures"] == state["failures"]
    assert resumed["full_acceptance_status"].startswith("PENDING")
