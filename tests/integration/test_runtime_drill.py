"""Actual owned subprocesses and loopback HTTP, without model/provider access."""
import json
import os

import pytest

from siteforge import runtime_drill
from siteforge.runtime_drill import RuntimeDrillError, run_drill


def test_actual_api_and_worker_process_loss_preserves_checkpoint_and_recovers_chain(tmp_path, monkeypatch):
    # A real user environment must neither select the DB nor reach a provider.
    monkeypatch.setenv("SITEFORGE_DATABASE_URL", "postgresql://do-not-use.invalid/private")
    monkeypatch.setenv("GITHUB_TOKEN", "runtime-drill-must-not-inherit-provider-token")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "runtime-drill-must-not-inherit-model-token")
    launch = runtime_drill.subprocess.Popen
    launched = []

    def isolated_launch(arguments, **kwargs):
        child_environment = kwargs["env"]
        assert "GITHUB_TOKEN" not in child_environment and "LM_STUDIO_API_KEY" not in child_environment
        assert child_environment["SITEFORGE_DATABASE_URL"].startswith("sqlite:///")
        assert child_environment["PYTHONNOUSERSITE"] == "1"
        assert "Bearer" not in " ".join(arguments)
        launched.append(arguments)
        return launch(arguments, **kwargs)

    monkeypatch.setattr(runtime_drill.subprocess, "Popen", isolated_launch)
    root = tmp_path / "isolated-runtime-drill"
    report = run_drill(root)
    assert report["status"] == "passed"
    assert report["is_72_hour_acceptance"] is False and report["postgresql_tested"] is False
    assert report["model_calls"] == report["external_provider_calls"] == 0
    assert report["owned_subprocesses_cleaned"] is True
    assert len(launched) == 4
    assert report["quality_static_passed"] is True
    assert [record["attempt"] for record in report["tasks"]] == [2, 1, 1]
    assert all(record["status"] == "completed" and record["artifact_hashes"] for record in report["tasks"])
    assert len(report["processes"]) == 4
    assert len({record["pid"] for record in report["processes"]}) == 4
    assert all(record["pid"] != os.getpid() and record["exit_code"] is not None for record in report["processes"])
    events = [event["event"] for event in report["events"]]
    assert events.count("process_stopped") == 4
    assert events.index("checkpoint_persisted") < events.index("http_outage_observed")
    assert events.index("http_outage_observed") < events.index("checkpoint_survived_process_restart")
    assert events.index("lease_expired") < events.index("fixture_chain_completed")
    assert "stale_completion_rejected" in events
    stored = json.loads((root / "report.json").read_text(encoding="utf-8"))
    assert stored == report
    assert "lease_token" not in json.dumps(report) and "Bearer" not in json.dumps(report)
    assert not (root / ".env").exists()
    assert (root / "artifacts/runtime-drill-planner/source/src/pages/index.astro").is_file()


def test_drill_refuses_existing_evidence_without_overwriting_it(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    retained = existing / "report.json"
    retained.write_text("retained evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="new or empty"):
        run_drill(existing)
    assert retained.read_text(encoding="utf-8") == "retained evidence"


def test_failed_owned_server_start_is_bounded_cleaned_and_retained(tmp_path, monkeypatch):
    launch = runtime_drill.subprocess.Popen

    def invalid_server(arguments, **kwargs):
        return launch([*arguments, "--invalid-drill-option"], **kwargs)

    monkeypatch.setattr(runtime_drill.subprocess, "Popen", invalid_server)
    root = tmp_path / "failed-start"
    with pytest.raises(RuntimeDrillError, match="initial API readiness"):
        run_drill(root, startup_timeout=15)
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed" and report["failed_stage"] == "initial API readiness"
    assert report["owned_subprocesses_cleaned"] is True
    assert len(report["processes"]) == 1 and report["processes"][0]["exit_code"] != 0
    assert report["elapsed_seconds"] < 15
