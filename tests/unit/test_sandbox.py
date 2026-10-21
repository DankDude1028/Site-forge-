import os
import shutil
import subprocess

import pytest

from siteforge.sandbox import DockerSandbox, GitWorktrees, SandboxError, sanitized_environment


def test_sandbox_strips_host_credentials_and_git_command_overrides(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-secret")
    monkeypatch.setenv("NETLIFY_AUTH_TOKEN", "fixture-secret")
    monkeypatch.setenv("GIT_SSH_COMMAND", "untrusted-command")
    environment = sanitized_environment()
    assert "GITHUB_TOKEN" not in environment and "NETLIFY_AUTH_TOKEN" not in environment
    assert "GIT_SSH_COMMAND" not in environment
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_CONFIG_GLOBAL"] == os.devnull


def test_real_detached_git_worktree_and_no_automatic_cleanup(tmp_path):
    if not shutil.which("git"):
        pytest.skip("Git unavailable")
    repository = tmp_path / "repository"
    repository.mkdir()
    def git(*arguments):
        return subprocess.run(["git", "-C", str(repository), *arguments], check=True,
            capture_output=True, text=True, timeout=15).stdout.strip()
    git("init")
    (repository / "utility.txt").write_text("original utility", encoding="utf-8")
    git("add", "utility.txt")
    git("-c", "user.name=SiteForge Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    commit = git("rev-parse", "HEAD")
    manager = GitWorktrees(repository, tmp_path / "worktrees")
    target = manager.create("scoped-job", commit)
    assert (target / "utility.txt").read_text(encoding="utf-8") == "original utility"
    result = subprocess.run(["git", "-C", str(target), "symbolic-ref", "-q", "HEAD"],
                            capture_output=True, check=False, timeout=15)
    assert result.returncode == 1  # detached HEAD
    (target / "review-me.txt").write_text("preserve this work", encoding="utf-8")
    with pytest.raises(SandboxError):
        manager.create("scoped-job", commit)
    assert (target / "review-me.txt").exists()
    with pytest.raises(ValueError):
        manager.create("../outside", commit)
    with pytest.raises(ValueError):
        manager.create("safe-name", "main; arbitrary shell")
    git("config", "filter.fixture.smudge", "untrusted-filter")
    with pytest.raises(SandboxError, match="checkout filters"):
        GitWorktrees(repository, tmp_path / "other-worktrees")


def test_docker_command_is_fixed_offline_nonroot_readonly_and_limited(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    image = "node@sha256:" + "a" * 64
    sandbox = DockerSandbox(tmp_path, image)
    command = sandbox.command(job, "label_tests")
    for required in ["--network=none", "--cap-drop=ALL", "--read-only", "--user=65534:65534",
                     "--memory=512m", "--memory-swap=512m", "--cpus=1", "--pids-limit=128", "--pull=never"]:
        assert required in command
    assert command[-5:] == [image, "node", "--experimental-strip-types", "--test", "tests/planner.test.ts"]
    assert "readonly" in command[command.index("--mount") + 1]
    assert any(item.startswith("--name=siteforge-") for item in command)
    with pytest.raises(ValueError):
        sandbox.command(tmp_path.parent, "label_tests")
    with pytest.raises(ValueError):
        sandbox.command(job, "arbitrary shell")
    with pytest.raises(ValueError):
        DockerSandbox(tmp_path, "node:latest")


def test_docker_absent_does_not_fallback_to_host(tmp_path, monkeypatch):
    job = tmp_path / "job"
    job.mkdir()
    monkeypatch.setattr("siteforge.sandbox.shutil.which", lambda _: None)
    with pytest.raises(SandboxError, match="fallback is prohibited"):
        DockerSandbox(tmp_path, "node@sha256:" + "b" * 64).run(job, "label_tests")
