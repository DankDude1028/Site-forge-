"""Trusted Git worktree management and fixed, offline container test recipes.

No model-generated command is ever executed on the Windows host.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from siteforge.site_factory import scoped_path


class SandboxError(RuntimeError):
    pass


def sanitized_environment() -> dict[str, str]:
    """Keep OS runtime necessities, discard provider tokens and command overrides."""
    permitted = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "COMSPEC"}
    result = {key: value for key, value in os.environ.items() if key.upper() in permitted}
    result.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                  GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never", PYTHONDONTWRITEBYTECODE="1")
    return result


class GitWorktrees:
    """Create detached worktrees from an operator-configured local repository."""
    def __init__(self, repository: Path, worktree_root: Path) -> None:
        self.repository = repository.resolve(strict=True)
        self.root = worktree_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.git = shutil.which("git")
        if not self.git:
            raise SandboxError("Git is unavailable")
        if os.name == "nt" and Path(self.git).suffix.lower() != ".exe":
            raise SandboxError("Use the native Git executable, not a shell wrapper")
        self.hooks = self.root / ".hooks-disabled"
        self.hooks.mkdir(exist_ok=True)
        if self.hooks.is_symlink() or self.hooks.resolve() != self.hooks or any(self.hooks.iterdir()):
            raise SandboxError("Disabled hook directory must be empty and unlinked")
        top = self._git("rev-parse", "--show-toplevel").stdout.strip()
        if Path(top).resolve() != self.repository:
            raise SandboxError("Configured repository must be its Git top-level directory")
        filters = self._git("config", "--get-regexp", r"^filter\.", allow_missing=True)
        if filters.returncode == 0:
            raise SandboxError("Repositories with configured checkout filters require separate review")

    def _git(self, *arguments: str, allow_missing: bool = False) -> subprocess.CompletedProcess[str]:
        command = [str(self.git), "-c", f"core.hooksPath={self.hooks}", "-c", "core.fsmonitor=false",
                   "-c", "protocol.file.allow=never", "-C", str(self.repository), *arguments]
        result = subprocess.run(command, env=sanitized_environment(), shell=False,
                                capture_output=True, text=True, timeout=30,
                                stdin=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode and not (allow_missing and result.returncode == 1):
            raise SandboxError("Scoped Git operation failed; inspect the configured repository locally")
        return result

    def create(self, name: str, commit_sha: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", name):
            raise ValueError("Worktree name must be a bounded lowercase slug")
        if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit_sha):
            raise ValueError("Worktree revision must be an immutable full commit SHA")
        target = scoped_path(self.root, name)
        if target.exists():
            raise SandboxError("Worktree destination already exists; preserve it for review")
        if self._git("cat-file", "-t", commit_sha).stdout.strip() != "commit":
            raise SandboxError("Revision does not identify a commit")
        self._git("worktree", "add", "--detach", str(target), commit_sha)
        if not target.resolve().is_relative_to(self.root):
            raise SandboxError("Created worktree escaped its configured root")
        return target


RECIPES = {
    "label_tests": ("node", "--experimental-strip-types", "--test", "tests/planner.test.ts"),
    "python_tests": ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"),
    "python_unittest": ("python", "-I", "-m", "unittest", "discover", "-s", "tests"),
}


@dataclass(frozen=True)
class SandboxResult:
    returncode: int
    output: str
    output_truncated: bool
    recipe: str
    network: str = "none"


class DockerSandbox:
    def __init__(self, worktree_root: Path, image: str) -> None:
        self.root = worktree_root.resolve()
        if not re.fullmatch(r"[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}", image):
            raise ValueError("Use an operator-reviewed image pinned to a SHA256 digest")
        self.image = image

    def command(self, worktree: Path, recipe: str) -> list[str]:
        path = worktree.resolve(strict=True)
        if path == self.root or not path.is_dir() or not path.is_relative_to(self.root):
            raise ValueError("Container mount must be a scoped job worktree")
        # Docker's CSV-style mount grammar cannot safely represent these path delimiters here.
        if any(character in str(path) for character in [",", "\n", "\r"]):
            raise ValueError("Unsupported mount path delimiter")
        if recipe not in RECIPES:
            raise ValueError("Only fixed, reviewed test recipes are permitted")
        return ["docker", "run", "--rm", "--name=siteforge-" + uuid4().hex,
                "--pull=never", "--network=none", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--read-only", "--memory=512m", "--memory-swap=512m",
                "--cpus=1", "--pids-limit=128", "--user=65534:65534",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=64m", "--env=HOME=/tmp",
                "--env=PYTHONDONTWRITEBYTECODE=1", "--mount",
                f"type=bind,source={path},target=/workspace,readonly", "--workdir=/workspace",
                self.image, *RECIPES[recipe]]

    def run(self, worktree: Path, recipe: str, *, timeout_seconds: int = 120) -> SandboxResult:
        if not 1 <= timeout_seconds <= 300:
            raise ValueError("Sandbox timeout must be bounded to 1–300 seconds")
        command = self.command(worktree, recipe)
        executable = shutil.which("docker")
        if not executable:
            raise SandboxError("Docker unavailable; host execution fallback is prohibited")
        if os.name == "nt" and Path(executable).suffix.lower() != ".exe":
            raise SandboxError("Use the native Docker executable, not a shell wrapper")
        command[0] = executable
        # Drain excess output without retaining it in memory or filling a host log file.
        process = subprocess.Popen(command, shell=False, env=sanitized_environment(), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        output = bytearray()
        truncated = threading.Event()
        stream = process.stdout
        assert stream is not None
        def drain() -> None:
            for block in iter(lambda: stream.read(8192), b""):
                remaining = max(0, 65_536 - len(output))
                output.extend(block[:remaining])
                if len(block) > remaining:
                    truncated.set()
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            name = next(item.split("=", 1)[1] for item in command if item.startswith("--name="))
            try:
                subprocess.run([executable, "container", "rm", "--force", name],
                    shell=False, env=sanitized_environment(), stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            finally:
                process.kill()
                process.wait(timeout=10)
            raise SandboxError(f"Sandbox timed out; reconcile Docker container {name}") from error
        finally:
            reader.join(timeout=3)
        return SandboxResult(returncode, output.decode("utf-8", errors="replace"), truncated.is_set(), recipe)
