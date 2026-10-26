"""Gemma E4B drafts Rollwise edits; deterministic gates and the test suite check them; Opus 5.5 reviews.

Local experiment harness. Model output is untrusted data: it may only replace unique snippets in three
template files, may not add scripts, URLs, network or storage access, or HTML injection, and must keep the
contract strings the inspector and tests rely on. Model text is never executed as a command, and build and
test subprocesses run without SiteForge or Anthropic secrets in their environment.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MAIN = Path(__file__).resolve().parents[2]  # the repository root
WT = MAIN / "runtime" / "worktrees" / "rollwise-collab"
TPL = WT / "packages" / "site-templates" / "label-roll-planner"
HERE = Path(__file__).resolve().parent
NODE = Path(os.environ["USERPROFILE"]) / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
PY = MAIN / ".venv" / "Scripts" / "python.exe"
SITE_ID = "a660ccb0-ab32-4140-80dd-ca64d2971dad"
PRIOR_REVIEW = MAIN / "runtime" / "advisor" / "89ecacdb7bc8603041c3d64d9710f1b7.result.json"
MODEL_KEY, MODEL_ID = "google/gemma-4-e4b", "siteforge-collab"
MAX_ROUNDS, MAX_ATTEMPTS, MAX_EDITS = 3, 3, 12
# Each paid batch needs the owner's exact approval in chat, quoted here; past approvals are spent.
APPROVAL_NOTE = os.environ.get("DESIGN_LAB_APPROVAL", "")
FILES = ["src/pages/index.astro", "src/styles/site.css", "src/scripts/calculator.ts"]
FORBIDDEN = {
    r"<script": "a new script tag", r"https?://": "an external URL", r"\bfetch\s*\(": "a network request",
    r"XMLHttpRequest|sendBeacon|WebSocket|EventSource": "a network request",
    r"\beval\s*\(|new\s+Function": "dynamic code", r"\bimport\s*\(": "a dynamic import",
    r"localStorage|sessionStorage|indexedDB|document\.cookie": "browser storage",
    r"innerHTML|outerHTML|insertAdjacentHTML|document\.write": "HTML injection",
    r"@import|url\s*\(": "an external CSS resource", r"<iframe|<object|<embed|<link\b": "an embedded or linked resource",
    r"\son[a-z]+\s*=": "an inline event handler",
}
REQUIRED = {
    "src/pages/index.astro": [
        "No inputs leave your browser", 'name="robots" content={config.robots}', '<label for="quantity"',
        'aria-live="polite"', 'lang="en"', "<title>", 'name="description"', 'id="planner"', "novalidate",
        'id="result"', 'id="result-kind"', 'id="order"', 'id="order-label"', 'id="enough"', 'id="strip"',
        'id="needed"', 'id="required"', 'id="left"', 'id="announce"', 'id="error"', "Calculate my rolls",
        "Items in this batch", "Labels per item", "Labels on each roll", "Full rolls you already have",
        "Extra allowance (%)", '<script src="../scripts/calculator.ts"></script>',
        # Input limits are part of the validation contract; drafts may not loosen them.
        'name="quantity" type="number" min="1" max="1000000" step="1"',
        'name="labels" type="number" min="1" max="100" step="1"',
        'name="perRoll" type="number" min="1" max="1000000" step="1"',
        'name="onHand" type="number" min="0" max="1000000" step="1"',
        'name="waste" type="number" min="0" max="100" step="0.1"'],
    "src/styles/site.css": [":focus-visible", "--accent"],
    "src/scripts/calculator.ts": ["planLabels", "#planner", "drawStrip", "announce("],
}

SYSTEM = f"""You are the Developer agent for SiteForge. You edit Rollwise, a small Astro site with a label roll
calculator for small-batch makers. A senior reviewer's findings are below; make small, focused edits that
address them well.

You may change only these files: {", ".join(FILES)}. Answer with JSON only, matching the schema. Each edit
replaces one exact snippet ("find") of the CURRENT file with new text ("replace"). Copy "find" character for
character from the file, include enough surrounding text to be unique, and keep it short. At most {MAX_EDITS} edits.

Hard rules (edits that break them are rejected):
- Keep every element id, label text, the "Calculate my rolls" button text, the phrase "No inputs leave your
  browser", the robots meta tag, aria-live="polite" and the existing script tag. Tests depend on them.
- No new script tags, external URLs, network requests, browser storage, innerHTML or inline event handlers,
  and no CSS url() or @import.
- Body text stays at least 16px and secondary text at least 15px. Keep the palette: ink #1b2a2f, kraft
  #b98b5e, panel #eef1ec, accent #d9482b only for the result number and focus rings.
- Do not change the calculation itself. planLabels in src/lib/planner.ts is correct and not editable.
- Never rename the button and never change an input's min, max, step or required attributes, even if a
  finding suggests it. These rules always win over the findings.
- If a finding needs no change, or only asks for evidence, leave it alone and say so in the summary."""

# The Director's job: settle conflicts between reviewer findings and the contract before the drafter sees them.
MEDIATION = """Notes from the Director (these override the reviewer where they conflict):
- Keep the button text "Calculate my rolls". If the button seems redundant, make its role clearer with nearby
  text instead. On phones it already scrolls to the result.
- Input limits stay as they are. Requests to test zero, blank or negative inputs are evidence requests, and this
  round's screenshots show the error state and focus ring, so they need no code change.
- Prefer a few well-chosen edits over many small ones.
- In calculator.ts, only add what the new text needs (for example a few lines that set the caption). Do not
  rewrite, reorder or "clean up" existing code. Every brace and parenthesis you open must close."""

ROUND_ONE_TASKS = """Tasks for this round, from the reviewer's last pass:
1. Roll strip clarity: the last roll is half hatched, so "5 to order" can read as "4 to order plus spare". Add a
   short visible caption under the strip, for example "5 rolls to order · 450 spare labels on the last roll",
   written by drawStrip or calculate in calculator.ts into a new element in index.astro, styled in site.css.
2. Empty desktop space: on desktop the left column is empty below the intro while the calculator card is tall.
   Use it well, for example with a short "How to read the result" key next to the card, or by making the intro
   sticky. Keep it small and on-brand; on mobile it must still read naturally.
3. Calculate button: keep the label, but make clear that results update live and the button shows the result
   (for example a short line of helper text)."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["summary", "edits"], "properties": {
    "summary": {"type": "string"},
    "edits": {"type": "array", "items": {"type": "object", "additionalProperties": False,
              "required": ["file", "find", "replace", "reason"],
              "properties": {"file": {"type": "string", "enum": FILES}, "find": {"type": "string"},
                             "replace": {"type": "string"}, "reason": {"type": "string"}}}}}}

sys.path.insert(0, str(MAIN))
os.chdir(MAIN)
from siteforge.cli import load_environment  # noqa: E402

load_environment()
from siteforge.advisor import (advisor_settings, build_request, ensure_budgets, request_approval,  # noqa: E402
                               run_review, save_request)
from siteforge.db import Database  # noqa: E402
from siteforge.lmstudio import LMStudioClient  # noqa: E402
from siteforge.policy import PolicyService  # noqa: E402

CLEAN_ENV = {key: value for key, value in os.environ.items()
             if not key.startswith(("SITEFORGE_", "ANTHROPIC_"))}
CLEAN_ENV["PATH"] = str(NODE.parent) + os.pathsep + CLEAN_ENV.get("PATH", "")


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def read_files() -> dict[str, str]:
    return {name: (TPL / name).read_text(encoding="utf-8") for name in FILES}


def write_files(files: dict[str, str]) -> None:
    for name, text in files.items():
        (TPL / name).write_text(text, encoding="utf-8", newline="\n")


def locate(text: str, find: str) -> tuple[int, int]:
    if not find.strip():
        raise ValueError("an empty find")
    count = text.count(find)
    if count == 1:
        start = text.index(find)
        return start, start + len(find)
    if count > 1:
        raise ValueError(f"find text that matches {count} places; include more surrounding text")
    pattern = r"\s+".join(re.escape(token) for token in find.split())
    matches = list(re.finditer(pattern, text))
    if len(matches) == 1:
        return matches[0].span()
    raise ValueError("find text that is not in the current file" if not matches
                     else f"find text that matches {len(matches)} places")


def apply_edits(files: dict[str, str], edits: list[dict[str, str]]) -> tuple[dict[str, str], list[str]]:
    new, errors = dict(files), []
    if len(edits) > MAX_EDITS:
        return new, [f"{len(edits)} edits exceeds the limit of {MAX_EDITS}"]
    for number, edit in enumerate(edits, 1):
        try:
            start, end = locate(new[edit["file"]], edit["find"])
        except ValueError as error:
            errors.append(f"Edit {number} ({edit['file']}): {error}.")
            continue
        new[edit["file"]] = new[edit["file"]][:start] + edit["replace"] + new[edit["file"]][end:]
    return new, errors


def gate(before: dict[str, str], after: dict[str, str]) -> list[str]:
    errors = []
    for name in FILES:
        for pattern, label in FORBIDDEN.items():
            if len(re.findall(pattern, after[name])) > len(re.findall(pattern, before[name])):
                errors.append(f"{name}: adds {label}, which is not allowed.")
        for required in REQUIRED[name]:
            if required in before[name] and required not in after[name]:
                errors.append(f"{name}: removes required text {required!r}.")
        if len(after[name]) > 3 * len(before[name]) + 4000:
            errors.append(f"{name}: grows far beyond a focused edit.")
    return errors


def run(command: list[str], cwd: Path, timeout: int = 300) -> tuple[bool, str]:
    try:
        done = subprocess.run(command, cwd=cwd, env=CLEAN_ENV, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        return done.returncode == 0, (done.stdout + done.stderr)[-20000:]
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"


def run_checks() -> tuple[bool, dict[str, str]]:
    config = TPL / "test-results" / "edge.config.mjs"
    config.parent.mkdir(exist_ok=True)
    config.write_text("import base from '../playwright.config.mjs';\nexport default { ...base, testDir: '../e2e', "
                      "outputDir: './edge-run', webServer: { ...base.webServer, cwd: '..' }, projects: base.projects"
                      ".map(p => ({ ...p, use: { ...p.use, channel: 'msedge' } })) };\n", encoding="utf-8")
    # Fastest and most precise first: TypeScript names the exact file, line and error.
    checks = {
        "typecheck": ([str(NODE), "node_modules/typescript/bin/tsc", "--noEmit"], TPL),
        "unit tests": ([str(NODE), "--experimental-strip-types", "--test", "--test-reporter=tap", "tests/planner.test.ts",
                        "tests/site-config.test.mjs", "tests/launch-details.test.mjs", "tests/build-modes.test.mjs"], TPL),
        "build": ([str(NODE), "node_modules/astro/bin/astro.mjs", "build"], TPL),
        "browser and accessibility": ([str(NODE), "node_modules/@playwright/test/cli.js", "test", "-c",
                                       "test-results/edge.config.mjs", "--reporter=line"], TPL),
        "site factory inspector": ([str(PY), "-m", "pytest", "tests/unit/test_site_factory.py", "-q", "-p",
                                    "no:cacheprovider"], WT),
    }
    results = {}
    for name, (command, cwd) in checks.items():
        ok, output = run(command, cwd)
        results[name] = "passed" if ok else "FAILED:\n" + output
        if not ok:
            return False, results
    return True, results


def failure_feedback(check: str, output: str, files: dict[str, str]) -> str:
    """The failing lines and the drafted code they point at, not the tail of a long log."""
    lines = output.splitlines()
    keep: list[str] = []
    for index, line in enumerate(lines):
        if re.search(r"not ok|error|Error|AssertionError|expected|✘|failed|Failed", line):
            keep.extend(lines[index:index + 4])
    excerpt = "\n".join(dict.fromkeys(keep))[:1800] or output[-1200:]
    context = []
    for name, number in dict.fromkeys(re.findall(r"(src/[\w/.\-]+)\((\d+),\d+\)", output)):
        if name in files:
            source, line = files[name].splitlines(), int(number)
            span = range(max(1, line - 4), min(len(source), line + 4) + 1)
            context.append(f"{name} around line {line} (your edited version):\n" +
                           "\n".join(f"{n:4} | {source[n - 1]}" for n in span))
    return (f"Your edits applied, but the {check} check failed. The files were restored to their original "
            f"state; send corrected edits against the original files.\n{excerpt}\n\n" + "\n\n".join(context[:3]))


def ask_e4b(client: LMStudioClient, findings: str, files: dict[str, str], feedback: str) -> tuple[dict | None, dict]:
    body = "\n\n".join(f'<file path="{name}">\n{text}\n</file>' for name, text in files.items())
    user = f"Reviewer findings to address:\n<findings>\n{findings}\n</findings>\n\nCurrent files:\n{body}"
    if feedback:
        user += f"\n\nYour previous attempt was rejected. Fix these problems and answer again:\n{feedback}"
    completion = client.complete([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                                 MODEL_ID, max_tokens=8192, response_schema=SCHEMA)
    meta = {"latency_seconds": round(completion.latency_seconds, 1), "output_tokens": completion.output_tokens,
            "tokens_per_second": round(completion.tokens_per_second or 0, 1), "finish_reason": completion.finish_reason}
    if completion.finish_reason == "length":
        return None, {**meta, "error": "Your answer was cut off before it finished. Make fewer, shorter edits."}
    try:
        proposal = json.loads(completion.text)
        assert isinstance(proposal.get("edits"), list) and isinstance(proposal.get("summary"), str)
    except (ValueError, AssertionError):
        return None, {**meta, "error": "Your answer was not valid JSON matching the schema."}
    return proposal, meta


def capture(round_dir: Path) -> list[Path]:
    server = subprocess.Popen([str(PY), "-m", "http.server", "4393", "--bind", "127.0.0.1", "--directory",
                               str(TPL / "dist")], env=CLEAN_ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(2)
        ok, output = run([str(NODE), str(HERE / "collab_capture.cjs"), str(TPL), str(round_dir),
                          "http://127.0.0.1:4393"], HERE, timeout=180)
        if not ok:
            raise RuntimeError("screenshot capture failed: " + output[-500:])
    finally:
        server.terminate()
    return [round_dir / name for name in ("desktop-custom.png", "mobile-custom.png", "desktop-error-focus.png",
                                          "desktop-enough.png")]


def actionable(review: dict) -> list[dict]:
    return [finding for finding in review.get("findings", [])
            if not finding["recommendation"].strip().lower().startswith(("no change", "none needed"))]


def format_findings(review: dict) -> str:
    lines = [f"- [{f['severity']}] {f['area']}: {f['evidence']} Recommended: {f['recommendation']}"
             for f in actionable(review)]
    design = review.get("design") or {}
    if design.get("direction"):
        lines.append(f"- Design direction: {design['direction']}")
    return "\n".join(lines)


def main() -> None:
    settings = advisor_settings()
    if settings["enabled"] != "true" or not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Advisor is not enabled or the API key is missing")
    if not APPROVAL_NOTE.strip():
        raise SystemExit("Set DESIGN_LAB_APPROVAL to the owner's exact chat approval for this batch")
    out = MAIN / "runtime" / f"collab-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out.mkdir(parents=True)
    log(f"output: {out}")
    subprocess.run(["lms", "unload", "--all"], capture_output=True, timeout=120)
    loaded = subprocess.run(["lms", "load", MODEL_KEY, "--identifier", MODEL_ID, "--context-length", "32768",
                             "--parallel", "1", "--yes"], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=300)
    if loaded.returncode != 0:
        raise SystemExit("could not load Gemma E4B")
    log("Gemma E4B loaded at 32K context")
    client = LMStudioClient(timeout=900)
    db = Database(os.environ["SITEFORGE_DATABASE_URL"])
    policy, org = PolicyService(db), os.environ["SITEFORGE_ORG_ID"]
    import anthropic
    findings, summary = ROUND_ONE_TASKS + "\n\n" + MEDIATION, {"rounds": [], "output": str(out)}
    try:
        for number in range(1, MAX_ROUNDS + 1):
            round_dir = out / f"round-{number}"
            round_dir.mkdir()
            start, feedback, record = read_files(), "", {"round": number, "findings_given": findings, "attempts": []}
            (round_dir / "findings-given.txt").write_text(findings, encoding="utf-8")
            passed, proposal = False, None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                log(f"round {number} attempt {attempt}: asking Gemma E4B")
                proposal, meta = ask_e4b(client, findings, start, feedback)
                entry = {"attempt": attempt, **meta}
                if proposal is None:
                    feedback = meta["error"]
                    record["attempts"].append({**entry, "outcome": "invalid answer"})
                    log(f"  rejected: {feedback}")
                    continue
                (round_dir / f"e4b-attempt-{attempt}.json").write_text(json.dumps(proposal, indent=2), encoding="utf-8")
                new, errors = apply_edits(start, proposal["edits"])
                errors += gate(start, new) if not errors else []
                if not proposal["edits"]:
                    errors = ["You made no edits. Address the findings that need a change."]
                if errors:
                    feedback = "\n".join(errors)
                    record["attempts"].append({**entry, "edits": len(proposal["edits"]), "outcome": "gate rejected",
                                               "problems": errors})
                    log(f"  gate rejected {len(errors)} problem(s): {errors[0]}")
                    continue
                write_files(new)
                log(f"  {len(proposal['edits'])} edit(s) applied; running checks")
                ok, results = run_checks()
                record["attempts"].append({**entry, "edits": len(proposal["edits"]),
                                           "outcome": "checks passed" if ok else "checks failed", "checks": results})
                if ok:
                    passed = True
                    log("  all checks passed")
                    break
                write_files(start)
                failed = next(name for name, result in results.items() if result != "passed")
                feedback = failure_feedback(failed, results[failed], new)
                (round_dir / f"feedback-attempt-{attempt}.txt").write_text(feedback, encoding="utf-8")
                log(f"  {failed} failed; reverted")
            if not passed:
                write_files(start)
                record["outcome"] = "no passing draft; round abandoned"
                summary["rounds"].append(record)
                log(f"round {number}: no passing draft after {MAX_ATTEMPTS} attempts")
                break
            diff = "".join("".join(difflib.unified_diff(start[name].splitlines(True), read_files()[name].splitlines(True),
                                                          f"a/{name}", f"b/{name}")) for name in FILES)
            (round_dir / "round-diff.txt").write_text(diff, encoding="utf-8")
            record["e4b_summary"] = proposal["summary"]
            record["edit_reasons"] = [edit["reason"] for edit in proposal["edits"]]
            log("  capturing screenshots")
            shots = capture(round_dir)
            brief = (f"Rollwise collaboration round {number}. A local model, Gemma 4 E4B, drafted these changes in "
                     "response to your previous findings. Deterministic safety gates and the full test suite passed "
                     "before this review (unit tests including real builds, TypeScript, desktop and mobile browser "
                     "tests with axe WCAG 2.1 AA checks, and the SiteForge inspector).\n\n"
                     f"Its summary of the change: {proposal['summary']}\n\n"
                     "Attached: the findings it was given, the code diff for this round, and page text. Screenshots: "
                     "a custom batch on desktop and mobile, an error state with keyboard focus after blanking 'Labels "
                     "on each roll', and the state where owned rolls exceed the need. This is still a private preview, "
                     "so host and contact placeholders are expected.\n\n"
                     "Say whether each given finding is resolved, flag any regression or new problem the change "
                     "introduced, and say whether the site is ready to publish once host and contact details are "
                     "supplied. Begin the recommendation of any finding that needs no change with 'No change needed'.")
            documents = [("findings-given.txt", findings), ("round-diff.txt", diff or "(no change)"),
                         ("page-text.txt", (round_dir / "page-text.txt").read_text(encoding="utf-8"))]
            document = build_request("site_review", SITE_ID, brief, documents=documents,
                                     screenshots=[(shot.name, shot.read_bytes()) for shot in shots])
            request_path = save_request(document, MAIN / "runtime" / "advisor")
            approval = request_approval(policy, org, document, "collab-harness")
            policy.decide(org, approval["id"], "owner", True, APPROVAL_NOTE)
            ensure_budgets(policy, org, monthly=settings["monthly"], daily=settings["daily"])
            log(f"  sending Opus review (worst case ${document['max_cost']})")
            result = run_review(policy, org, approval["id"], request_path, anthropic.Anthropic(),
                                results_root=MAIN / "runtime" / "advisor")
            (round_dir / "opus-review.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            review = result.get("review") or {}
            record.update({"opus_status": result["status"], "opus_cost": result["measured_cost"],
                           "verdict": review.get("verdict"), "opus_summary": review.get("summary"),
                           "actionable_findings": len(actionable(review)) if review else None,
                           "design": (review.get("design") or {}).get("distinctiveness")})
            summary["rounds"].append(record)
            log(f"  Opus: {result['status']}, verdict {review.get('verdict')}, cost ${result['measured_cost']}, "
                f"{record['actionable_findings']} actionable finding(s)")
            if result["status"] != "complete" or (review.get("verdict") == "ready" and not actionable(review)):
                break
            findings = format_findings(review) + "\n\n" + MEDIATION
    finally:
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        subprocess.run(["lms", "unload", MODEL_ID], capture_output=True, timeout=120)
        db.dispose()
        log("done")


if __name__ == "__main__":
    main()
