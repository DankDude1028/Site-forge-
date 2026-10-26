"""Run the bundled Claude Code CLI against the local LM Studio model with an isolated, secret-free environment."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

def _find_claude() -> Path:
    """The desktop app updates and moves its bundled Claude Code; use the newest copy installed, or CC_BINARY."""
    if os.environ.get("CC_BINARY"):
        return Path(os.environ["CC_BINARY"])
    roots = [Path(os.environ["APPDATA"]) / "Claude/claude-code",
             *Path(os.environ["LOCALAPPDATA"], "Claude-Data").glob("*/claude-code")]
    found = [exe for root in roots for exe in root.glob("*/*/claude.exe")]
    if not found:
        raise FileNotFoundError("no bundled Claude Code binary found; set CC_BINARY")
    version = lambda exe: tuple(int(part) for part in exe.parent.parent.name.split(".") if part.isdigit())
    return max(found, key=lambda exe: (version(exe), exe.stat().st_mtime))


CC = _find_claude()
HERE = Path(__file__).resolve().parent
KEEP = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "PROGRAMDATA", "PROGRAMFILES",
        "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS", "PATH",
        "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA", "USERNAME", "COMPUTERNAME")


def run_claude(prompt: str, cwd: Path, model: str, *, tools: str, max_turns: int, timeout: int,
               resume: str | None = None, system_prompt: str | None = None) -> dict:
    """system_prompt replaces Claude Code's long default prompt (and --bare skips CLAUDE.md and other context), which
    leaves room for files and screenshots in a small local context window."""
    env = {key: value for key, value in os.environ.items() if key.upper() in KEEP}
    env.update({"ANTHROPIC_BASE_URL": "http://127.0.0.1:1234", "ANTHROPIC_AUTH_TOKEN": "lmstudio",
                "ANTHROPIC_MODEL": model, "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": model, "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
                "CLAUDE_CONFIG_DIR": str(HERE.parents[1] / "runtime" / "cc-config"), "DISABLE_AUTOUPDATER": "1",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1",
                "DISABLE_ERROR_REPORTING": "1", "API_TIMEOUT_MS": "900000"})
    if os.environ.get("CC_NO_THINKING") == "1":
        env["MAX_THINKING_TOKENS"] = "0"  # a local reasoning model otherwise thinks ~16K tokens before each step
    # --allowedTools only pre-approves; a tool is unavailable only when it is disallowed.
    blocked = ["Bash", "BashOutput", "KillShell", "WebFetch", "WebSearch", "Task", "NotebookEdit",
               *[name for name in ("Edit", "MultiEdit", "Write", "Glob", "Grep", "TodoWrite")
                 if name not in tools.split(",")]]
    command = [str(CC), "-p", prompt, "--model", model, "--allowedTools", tools,
               "--disallowedTools", ",".join(blocked),
               "--permission-mode", "acceptEdits", "--max-turns", str(max_turns), "--output-format", "json",
               "--strict-mcp-config"]
    if resume:
        command += ["--resume", resume]
    if system_prompt:
        command += ["--system-prompt", system_prompt, "--bare"]
        env["ANTHROPIC_API_KEY"] = "lmstudio"  # --bare reads only this variable; LM Studio ignores the value
    started = time.perf_counter()
    try:
        done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
        output, code = done.stdout, done.returncode
        stderr = done.stderr[-2000:]
    except subprocess.TimeoutExpired as error:
        output, code, stderr = (error.stdout or ""), -1, "timeout"
    seconds = round(time.perf_counter() - started, 1)
    try:
        result = json.loads(output.strip().splitlines()[-1]) if output.strip() else {}
    except ValueError:
        result = {"raw": output[-2000:]}
    return {"exit": code, "seconds": seconds, "stderr": stderr, "result": result}


if __name__ == "__main__":
    report = run_claude(sys.argv[1], Path(sys.argv[2]), sys.argv[3], tools=sys.argv[4], max_turns=int(sys.argv[5]),
                        timeout=int(sys.argv[6]))
    print(json.dumps({k: (v if k != "result" else {x: report["result"].get(x) for x in
                      ("result", "num_turns", "is_error", "subtype", "duration_ms", "raw")}) for k, v in report.items()}, indent=2))
