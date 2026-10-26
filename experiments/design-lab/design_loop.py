"""Push Gemma E4B, running inside Claude Code, toward a 9/10 Rollwise design judged by Opus 5.5 from screenshots.

Arm A gets an open creative brief; arm B gets a full art direction and a technique cookbook. Each round, Claude Code
with E4B edits a disposable worktree (file tools only: no shell, no web, no secrets). Deterministic gates and the
full test suite run, then Opus scores screenshots and its fixes go back to the model. Each arm hill-climbs from its
best-scoring version. Opus spend is capped at the owner-approved $2.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cc_run import run_claude  # noqa: E402
from design_briefs import BRIEFS, CONSTRAINTS, SUBJECT  # noqa: E402

MAIN = HERE.parents[1]  # experiments/design-lab sits two levels below the repository root
WTS = {arm: MAIN / "runtime" / "worktrees" / f"rollwise-design-{arm}" for arm in "ab"}
REL = "packages/site-templates/label-roll-planner"
NODE = Path(os.environ["USERPROFILE"]) / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
PY = MAIN / ".venv" / "Scripts" / "python.exe"
SITE_ID = "a660ccb0-ab32-4140-80dd-ca64d2971dad"
MODEL_ID, TARGET = os.environ.get("DESIGN_MODEL", "siteforge-cc"), 9
# With a vision model, the designer sees screenshots of its page before editing and reviews its own result.
VISION = os.environ.get("DESIGN_VISION") == "1"
SHOTS, SHOT_NAMES = ".design-shots", ("desktop-fold.png", "mobile-fold.png", "desktop-full.png")
# Claude Code's default system prompt fills much of a 32K local context; a short one leaves room for files and images.
CC_SYSTEM = ("You are a web designer editing an Astro site with the Read, Write and Glob tools. Paths are relative to "
             "the current directory. Read each file once; you keep what you read. To change a file, call Write with "
             "file_path and the complete new content of that file, keeping every part you are not changing. Make the "
             "changes; do not only describe them.") if os.environ.get("DESIGN_SHORT_SYSTEM") == "1" else None
LOOK_FIRST = ("SEE THE PAGE FIRST: screenshots of the current version are in .design-shots/: desktop-fold.png (the "
              "first screen at 1280px wide), mobile-fold.png (the first screen on a 393px phone) and desktop-full.png "
              "(the whole desktop page). Read all three before you edit, so you know what the page really looks like.")
CRITIC = os.environ.get("DESIGN_CRITIC")  # a local vision model that reviews screenshots for a designer that cannot
LMS = str(Path(os.environ["USERPROFILE"]) / ".lmstudio" / "bin" / "lms.exe")
LOCAL_MODELS = {"siteforge-cc": ("google/gemma-4-e4b", 65536), "siteforge-vision": ("google/gemma-4-12b-qat", 32768)}
CRITIC_PROMPT = (
    "You are a demanding art director reviewing screenshots of a small website. The site: {subject}\n\nJudge only "
    "what is visible, and remember the first-screen images are crops of a longer page. List the 5 most important visual problems that keep it from looking polished and striking, most "
    "important first: broken, overlapping or clipped elements; cramped or empty areas; weak hierarchy; poor alignment "
    "or spacing; oversized or tiny elements; problems in the phone layout. For each, name the element as it appears "
    "on screen and say concretely how to fix it in CSS or markup. Number the list and add no introduction.")
CRITIC_FIX_PROMPT = (
    "Your edits pass every test. A local art director looked at screenshots of the rendered page and reported these "
    "visible problems:\n{critique}\n\nFix them now with focused edits, keeping your design and everything that already "
    "works. You cannot see the page, so be careful with layout and keep the phone layout to one column. End your reply "
    "with DONE.")
SELF_REVIEW_PROMPT = (
    "Your edits pass every test. Fresh screenshots of the result are now in .design-shots/: desktop-fold.png, "
    "mobile-fold.png and desktop-full.png. Read all three and judge them as a demanding art director would. If "
    "anything looks broken, overlapping, cramped, oversized, misaligned, empty, unbalanced or unfinished, especially "
    "on the phone, fix it now with focused edits and keep your design. If it already looks polished, change nothing. "
    "End your reply with DONE.")
BUDGET, PER_SCORE_GUARD = Decimal("2.00"), Decimal("0.20")
MAX_RUNS, MAX_SCORES, MAX_CONTINUES = 10, 5, 3
TOOLS = os.environ.get("DESIGN_TOOLS", "Read,Write,Edit,Glob,Grep,TodoWrite")
# Without Edit, the model changes a file by Writing all of it; that avoids misquoted or line-numbered old_string.
WRITE_ONLY_NOTE = ("" if "Edit" in TOOLS.split(",") else
                   "\n\nTOOLS: Edit is not available in this session. To change a file, Read it, then call Write with "
                   "file_path and the complete new content of the whole file, with no line numbers and no "
                   "placeholders such as '... unchanged ...'; keep every part you are not changing.")
CONTINUE_PROMPT = ("Continue carrying out the brief. Do the remaining steps now with your file tools; do not describe "
                   "plans, make the edits. When every part of the brief is built, reply with the single word DONE.")
PORTS = {"a": 4394, "b": 4395}
# Each paid batch needs the owner's exact approval in chat, quoted here; past approvals are spent.
APPROVAL_NOTE = os.environ.get("DESIGN_LAB_APPROVAL", "")
ALLOWED = re.compile(rf"^{re.escape(REL)}/src/(pages/(index|privacy)\.astro|styles/[\w.-]+\.css|"
                     rf"components/(?!Calculator\.astro$)[\w.-]+\.astro)$")
BASELINE_DIR = Path(os.environ["DESIGN_BASELINE_DIR"]) if os.environ.get("DESIGN_BASELINE_DIR") else None
PRIOR_SPEND = Decimal(os.environ.get("DESIGN_PRIOR_SPEND", "0"))
# DESIGN_RESUME_B="<check name>::<check-failure.txt>" keeps that arm's work in its worktree after a restart and
# hands it the failure feedback again, instead of starting the arm over.
INCREMENTAL = set(os.environ.get("DESIGN_INCREMENTAL", ""))  # arms that hill-climb instead of redesigning
RESUME = {arm: os.environ[f"DESIGN_RESUME_{arm.upper()}"].split("::", 1)
          for arm in "ab" if os.environ.get(f"DESIGN_RESUME_{arm.upper()}")}
IGNORED_PREFIXES = (f"{REL}/.claude/", f"{REL}/.design-shots/")
FORBIDDEN = {
    r"<script": "a new script tag", r"https?://(?!www\.w3\.org/)": "an external URL",
    r"\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource": "a network request",
    r"\beval\s*\(|new\s+Function|\bimport\s*\(": "dynamic code",
    r"localStorage|sessionStorage|indexedDB|document\.cookie": "browser storage",
    r"innerHTML|outerHTML|insertAdjacentHTML|document\.write": "HTML injection",
    # The optional quote sits inside the lookahead so backtracking cannot skip past it.
    r"@import": "a CSS @import", r"url\(\s*(?!['\"]?(?:data:|#|%23))": "a CSS url() that is not a data: URI",
    r"<iframe|<object|<embed|<link\b": "an embedded or linked resource",
    r"\son[a-z]+\s*=\s*[\"'{]": "an inline event handler",
}
# The calculator contract is locked in Calculator.astro; the page only has to render it and keep its own contract.
REQUIRED = [
    "No inputs leave your browser", 'name="robots" content={config.robots}', 'lang="en"', "<title>",
    "Label roll calculator", 'name="description"', "<Calculator />",
    "import Calculator from '../components/Calculator.astro';", 'rel="canonical" href={canonical}',
    "const canonical = new URL('/', Astro.site);", "import '../styles/site.css';",
]
# Exact original lines to quote when a model breaks them; it otherwise copies test expressions into the page.
KNOWN_FIXES = {
    'rel="canonical"': "The canonical link must be exactly as in the original files. In src/pages/index.astro the "
                       "frontmatter needs `const canonical = new URL('/', Astro.site);` and the <head> needs "
                       "`<link rel=\"canonical\" href={canonical} />`. In src/pages/privacy.astro the frontmatter "
                       "needs `const canonical = new URL('/privacy/', Astro.site);` and the same <link> line. Do not "
                       "copy expressions from the test such as ${origin} or ${route}; they do not exist in the page.",
    "local_only_calculator": "The visible page body of index.astro must include the sentence 'No inputs leave your "
                             "browser.' (for example next to the calculator). It must not sit inside the <head>.",
    "strict mode violation":"An id that must be unique appears more than once on the page, so the tests cannot tell "
                             "the copies apart. <Calculator /> must appear exactly once in index.astro, and no other "
                             "markup may reuse the calculator's ids.",
    "origin is not defined": "",  # filled in below: the model copied ${origin} from the canonical test
    "is not defined": "A variable used in a page is not defined. Look at the frontmatter (between the --- lines) of "
                      "the page and define it there, or restore the original line that used it.",
}
KNOWN_FIXES["origin is not defined"] = KNOWN_FIXES['rel="canonical"']

os.chdir(MAIN)
sys.path.insert(0, str(MAIN))
from siteforge.cli import load_environment  # noqa: E402

load_environment()
from siteforge.advisor import (advisor_settings, build_request, ensure_budgets, request_approval,  # noqa: E402
                               run_review, save_request)
from siteforge.db import Database  # noqa: E402
from siteforge.policy import PolicyService  # noqa: E402

CLEAN_ENV = {key: value for key, value in os.environ.items() if not key.startswith(("SITEFORGE_", "ANTHROPIC_"))}
CLEAN_ENV["PATH"] = str(NODE.parent) + os.pathsep + CLEAN_ENV.get("PATH", "")


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def git(wt: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(wt), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def changed(wt: Path) -> list[str]:
    paths = []
    for line in git(wt, "status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ")[-1]
        paths.append(path)
    return paths


def head_text(wt: Path, path: str) -> str:
    done = subprocess.run(["git", "-C", str(wt), "show", f"HEAD:{path}"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.stdout if done.returncode == 0 else ""


def gate(wt: Path) -> list[str]:
    errors, paths = [], [path for path in changed(wt) if not path.startswith(IGNORED_PREFIXES)]
    tracked = set(git(wt, "ls-files").splitlines())
    for path in [path for path in paths if not ALLOWED.match(path) and path not in tracked]:
        # Stray helper files the model created are never used; remove them instead of discarding the design.
        (wt / path).unlink(missing_ok=True)
        log(f"    removed stray file {path}")
        paths.remove(path)
    if not [path for path in paths if ALLOWED.match(path)]:
        return ["You changed no site files. Edit the allowed files to carry out the brief."]
    for path in paths:
        if not ALLOWED.match(path):
            errors.append(f"{path}: you may not edit this file"
                          + (" (the calculator is locked; style it from CSS instead)." if "Calculator" in path else "."))
            continue
        file = wt / path
        new = file.read_text(encoding="utf-8", errors="replace") if file.exists() else ""
        old = head_text(wt, path)
        for pattern, label in FORBIDDEN.items():
            if len(re.findall(pattern, new)) > len(re.findall(pattern, old)):
                errors.append(f"{path}: adds {label}, which is not allowed.")
    index = (wt / REL / "src/pages/index.astro").read_text(encoding="utf-8", errors="replace")
    errors += [f"src/pages/index.astro: missing required text {item!r}." for item in REQUIRED if item not in index]
    body = index.split("</head>", 1)[-1]  # visitors never see the <head>, and the harness restores it anyway
    errors += [f"src/pages/index.astro: missing required text {item!r} in the visible page body (it must come "
               "after </head>, not inside it)." for item in ("No inputs leave your browser", "<Calculator />")
               if item in index and item not in body]
    if (copies := index.count("<Calculator />")) > 1:
        # Each copy repeats the calculator's ids, which breaks the script and every test that finds them.
        errors.append(f"src/pages/index.astro: missing required text: <Calculator /> must appear exactly once, "
                      f"but it appears {copies} times. Keep one and delete the others.")
    return errors


def snapshot(wt: Path) -> dict[str, str | None]:
    return {path: ((wt / path).read_text(encoding="utf-8") if (wt / path).exists() else None)
            for path in changed(wt) if ALLOWED.match(path)}


def restore(wt: Path, snap: dict[str, str | None]) -> None:
    git(wt, "checkout", "HEAD", "--", ".")
    git(wt, "clean", "-fdq")
    for path, text in snap.items():
        target = wt / path
        if text is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")


def run(command: list[str], cwd: Path, timeout: int = 300) -> tuple[bool, str]:
    try:
        done = subprocess.run(command, cwd=cwd, env=CLEAN_ENV, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
        return done.returncode == 0, (done.stdout + done.stderr)[-20000:]
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"


def css_problems(wt: Path) -> list[str]:
    """Unbalanced braces make the browser drop every later rule; the tests only show that as odd symptoms."""
    problems: list[str] = []
    for path in sorted((wt / REL / "src" / "styles").glob("*.css")):
        rel = path.relative_to(wt / REL).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        # Blank out comments and strings but keep line breaks, so line numbers stay true.
        text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.S)
        rows, opened = text.splitlines(), []
        for number, row in enumerate(rows, 1):
            for char in re.sub(r"(['\"]).*?\1", "", row):
                if char == "{":
                    opened.append(number)
                elif char == "}":
                    if opened:
                        opened.pop()
                    else:
                        problems.append(f"{rel} line {number} has a }} with no matching {{. Remove it.")
        lines = source.splitlines()
        for number in opened:
            problems.append(f"{rel} line {number} opens a {{ block that is never closed, so the browser ignores "
                            f"every rule after it. The line is:\n  {number} | {lines[number - 1].strip()[:200]}\n"
                            "Add the missing } at the end of that rule.")
    sheets = [p.relative_to(wt / REL).as_posix() for p in sorted((wt / REL / "src" / "styles").glob("*.css"))]
    if not problems and sheets:
        ok, output = run([str(NODE), str(HERE / "css_check.cjs"), str(wt / REL), *sheets], HERE, timeout=120)
        try:
            parsed = json.loads(output.strip().splitlines()[-1]) if ok else []
        except (ValueError, IndexError):
            parsed = []
        for item in parsed:
            rows = (wt / REL / item["file"]).read_text(encoding="utf-8", errors="replace").splitlines()
            near = "\n".join(f"  {n} | {rows[n - 1][:160]}" for n in range(max(1, item["line"] - 2),
                                                                       min(len(rows), item["line"] + 1) + 1))
            problems.append(f"{item['file']} line {item['line']}: {item['message']}. The lines are:\n{near}")
    return problems + placeholder_problems(wt)


PLACEHOLDER = re.compile(r"\.\.\.\s*(lines?\s*[\d\s,-]*)?(unchanged|remain|omitted|same)|rest of (the )?(file|styles|code)"
                         r"|existing (styles|code|rules) (here|unchanged)", re.I)


def placeholder_problems(wt: Path) -> list[str]:
    """A model that writes '... lines 90-98 unchanged ...' instead of the real lines silently deletes them."""
    problems = []
    for path in [*sorted((wt / REL / "src/styles").glob("*.css")), *sorted((wt / REL / "src/pages").glob("*.astro")),
                 *sorted((wt / REL / "src/components").glob("*.astro"))]:
        if path.name in ("Calculator.astro", "base.css"):
            continue
        for number, row in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if PLACEHOLDER.search(row):
                problems.append(f"{path.relative_to(wt / REL).as_posix()} line {number} is a placeholder, not real "
                                f"code: {row.strip()[:120]}. The lines it stands for were deleted. Replace it with "
                                "the real rules or markup; never abbreviate a file you Write.")
    return problems


def unclosed_final_block(text: str) -> int:
    """Line of a single unclosed block that runs to the end of the file with every later line indented, which is
    unambiguous to close at the end (a model often drops the last }); 0 when that is not the case."""
    rows = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S).splitlines()
    opened: list[int] = []
    for number, row in enumerate(rows, 1):
        for char in re.sub(r"(['\"]).*?\1", "", row):
            if char == "{":
                opened.append(number)
            elif char == "}" and opened:
                opened.pop()
    if len(opened) != 1:
        return 0
    return opened[0] if all(not row.strip() or row[0] in " \t" for row in rows[opened[0]:]) else 0


def source_autofix(wt: Path) -> list[str]:
    """Strip pasted line-number prefixes and drop an exact duplicate of a component's --- frontmatter block (the copy
    otherwise renders as page text). Also restore each page's <head>: it holds only the title, description, robots
    and canonical tags that the tests and launch rules require, so a design has no reason to change it."""
    applied = []
    for name in ("index.astro", "privacy.astro"):
        path = wt / REL / "src/pages" / name
        if not path.exists():  # a deleted page is the gate's to reject
            continue
        original = git(wt, "show", f"HEAD:{REL}/src/pages/{name}")
        want, have = (re.search(r"<head>.*?</head>", text, flags=re.S) for text in (original, path.read_text(
            encoding="utf-8", errors="replace")))
        if want and have and want.group(0) != have.group(0):
            text = path.read_text(encoding="utf-8", errors="replace")
            path.write_text(text[:have.start()] + want.group(0) + text[have.end():], encoding="utf-8", newline="\n")
            applied.append(f"restored the original <head> of {name}")
    index = wt / REL / "src/pages/index.astro"
    text = index.read_text(encoding="utf-8", errors="replace") if index.exists() else ""
    head_end = text.find("</head>") + len("</head>") if "</head>" in text else 0
    body = text[head_end:]
    if "No inputs leave your browser" not in body and body.count("<Calculator />") == 1:
        # The model keeps hiding this required promise in the <head>; place it where the live site has it.
        at = head_end + body.index("<Calculator />")
        line_start = text.rfind("\n", 0, at) + 1
        indent = text[line_start:at] if not text[line_start:at].strip() else ""
        line = f'{indent}<p class="trust">No inputs leave your browser. No account, no ads, no tracking.</p>\n'
        index.write_text(text[:line_start] + line + text[line_start:], encoding="utf-8", newline="\n")
        applied.append("put the required privacy line back in the visible page, next to the calculator")
    for path in [*sorted((wt / REL / "src/pages").glob("*.astro")), *sorted((wt / REL / "src/components").glob("*.astro")),
                 *sorted((wt / REL / "src/styles").glob("*.css"))]:
        if path.name in ("Calculator.astro", "base.css"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # Line-number prefixes copied from Read output ("92<TAB>.roll {") break the file; real code never has them.
        stripped = re.sub(r"(?m)^ *\d+\t", "", text)
        if stripped != text:
            path.write_text(stripped, encoding="utf-8", newline="\n")
            applied.append(f"removed line-number prefixes pasted into {path.name}")
            text = stripped
        if path.suffix == ".css" and (end := unclosed_final_block(text)):
            text = text.rstrip("\n") + "\n}\n"
            path.write_text(text, encoding="utf-8", newline="\n")
            applied.append(f"closed the final block opened on line {end} of {path.name}")
        # An identical top-level declaration repeated in the frontmatter is a "already declared" build error.
        front = re.match(r"(---\r?\n)(.*?)(\r?\n---\r?\n)", text, flags=re.S)
        if front:
            seen, kept = set(), []
            for row in front.group(2).split("\n"):
                key = row.strip()
                if re.match(r"(const|let|import)\s", key) and key in seen:
                    continue
                seen.add(key)
                kept.append(row)
            if len(kept) != front.group(2).count("\n") + 1:
                text = front.group(1) + "\n".join(kept) + front.group(3) + text[front.end():]
                path.write_text(text, encoding="utf-8", newline="\n")
                applied.append(f"removed a repeated frontmatter declaration from {path.name}")
        match = re.match(r"(---\r?\n.*?\r?\n---\r?\n)(\s*\1)+", text, flags=re.S)
        if match:
            path.write_text(match.group(1) + text[match.end():], encoding="utf-8", newline="\n")
            applied.append(f"removed a duplicated frontmatter block from {path.name}")
    return applied


def checks_with_fixes(wt: Path, port: int, entry: dict, label: str) -> tuple[bool, dict[str, str]]:
    """Run the checks, applying the harness's mechanical fixes between rounds."""
    if source_fixes := source_autofix(wt):
        entry.setdefault("auto_fixes", []).extend(source_fixes)
        log(f"{label}: harness {'; '.join(source_fixes)}")
    ok, results = run_checks(wt)
    # A test stops at the first page with violations, so later pages surface only after a fix round.
    for _ in range(3):
        if ok or results.get("browser and accessibility", "passed") == "passed":
            break
        fixes = auto_fix(wt, results["browser and accessibility"], port)
        if not fixes:
            break
        entry.setdefault("auto_fixes", []).extend(fixes)
        log(f"{label}: harness applied {len(fixes)} mechanical fixes ({'; '.join(fixes)[:200]}); re-checking")
        ok, results = run_checks(wt)
    return ok, results


def publish_shots(wt: Path, source: Path | None) -> bool:
    """Put screenshots where a vision model can Read them; the gate and snapshots ignore this folder."""
    target = wt / REL / SHOTS
    shutil.rmtree(target, ignore_errors=True)
    if source is None or not (source / "desktop-fold.png").exists():
        return False
    target.mkdir(parents=True)
    for name in SHOT_NAMES:
        if (source / name).exists():
            shutil.copy2(source / name, target / name)
    return True


BROWSER_FLAKE = re.compile(r"Unable to capture screenshot|Target page, context or browser has been closed|"
                           r"browserType\.launch|Protocol error \(Target|net::ERR_CONNECTION_REFUSED|"
                           r"webServer.*(timed out|exited)")


def run_checks(wt: Path) -> tuple[bool, dict[str, str]]:
    problems = css_problems(wt)
    if problems:
        return False, {"CSS syntax": "\n".join(problems)}
    tpl = wt / REL
    config = tpl / "test-results" / "edge.config.mjs"
    config.parent.mkdir(exist_ok=True)
    config.write_text("import base from '../playwright.config.mjs';\nexport default { ...base, testDir: '../e2e', "
                      "outputDir: './edge-run', webServer: { ...base.webServer, cwd: '..' }, projects: base.projects"
                      ".map(p => ({ ...p, use: { ...p.use, channel: 'msedge' } })) };\n", encoding="utf-8")
    checks = {
        "typecheck": ([str(NODE), "node_modules/typescript/bin/tsc", "--noEmit"], tpl),
        "unit tests": ([str(NODE), "--experimental-strip-types", "--test", "--test-reporter=tap", "tests/planner.test.ts",
                        "tests/site-config.test.mjs", "tests/launch-details.test.mjs", "tests/build-modes.test.mjs"], tpl),
        "build": ([str(NODE), "node_modules/astro/bin/astro.mjs", "build"], tpl),
        "browser and accessibility": ([str(NODE), "node_modules/@playwright/test/cli.js", "test", "-c",
                                       "test-results/edge.config.mjs", "--reporter=line"], tpl),
        "site factory inspector": ([str(PY), "-m", "pytest", "tests/unit/test_site_factory.py", "-q", "-p",
                                    "no:cacheprovider"], wt),
    }
    results = {}
    for name, (command, cwd) in checks.items():
        ok, output = run(command, cwd)
        if not ok and name == "browser and accessibility" and BROWSER_FLAKE.search(output):
            # A browser-infrastructure glitch says nothing about the design; retry once before blaming the model.
            log(f"    browser glitch ({BROWSER_FLAKE.search(output).group(0)}); retrying the browser check once")
            ok, output = run(command, cwd)
        if not ok and name == "site factory inspector":
            # The tests only assert static_passed; name the failing inspector rules so the model can act on them.
            _, named = run([str(PY), "-c", "import sys, tempfile; from pathlib import Path; "
                            "from siteforge.site_factory import create_preview, inspect_preview; "
                            "root = Path(tempfile.mkdtemp()); create_preview(root, 'label-planner'); "
                            "print('Inspector failures:', inspect_preview(root, 'label-planner')['failures'])"], wt)
            output += "\n" + named.strip()[-400:]
        results[name] = "passed" if ok else output
        if not ok:
            return False, results
    return True, results


def _rgb(color: str) -> list[int]:
    color = color.lstrip("#")
    color = "".join(c * 2 for c in color) if len(color) == 3 else color[:6]
    return [int(color[i:i + 2], 16) for i in (0, 2, 4)]


def _luminance(rgb: list[int]) -> float:
    linear = [c / 3294.6 if c <= 10.31 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(a: list[int], b: list[int]) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def passing_color(fg: str, bg: str, need: float) -> str:
    """Blend the text colour toward black or white, whichever has room, until it passes; keeps the design's hue."""
    text, ground = _rgb(fg), _rgb(bg)
    target = [0, 0, 0] if _luminance(ground) > 0.18 else [255, 255, 255]
    for step in range(1, 21):
        mixed = [round(c + (t - c) * step / 20) for c, t in zip(text, target)]
        if _ratio(mixed, ground) >= need + 0.15:
            return "#" + "".join(f"{c:02x}" for c in mixed)
    return "#000000" if target[0] == 0 else "#ffffff"


def compile_error_context(output: str) -> str:
    """Point at the exact source of an Astro compile error; the model cannot run the compiler to find it."""
    location = re.search(r"Location:\s+(\S+?\.astro):(\d+):(\d+)", output)
    if not location:
        return ""
    path, line = Path(location.group(1)), int(location.group(2))
    try:
        source = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    name = path.relative_to(path.parents[2]).as_posix() if len(path.parents) > 2 else path.name
    start = max(1, line - 12)
    shown = "\n".join(f"{n:4d} | {source[n - 1][:160]}" for n in range(start, min(len(source), line + 2) + 1))
    text = f"The compiler stopped at {name} line {line}. Those lines are:\n{shown}"
    stray = re.search(r"Closing tag '</([\w:-]+)>' has no matching opening tag", output)
    if stray and line <= len(source):
        text += (f"\nLine {line} has a </{stray.group(1)}> that closes nothing. Every element opened on that line must "
                 f"be closed by its own tag (a <div> by </div>); replace the stray </{stray.group(1)}>.")
    tag = re.search(r"closing tag for '([\w:-]+)'", output)
    if tag:
        opened: list[int] = []
        for number, row in enumerate(source, 1):
            for match in re.finditer(rf"<(/?){re.escape(tag.group(1))}\b[^>]*?(/?)>", row):
                if match.group(1):
                    if opened:
                        opened.pop()
                elif not match.group(2):
                    opened.append(number)
        if opened:
            text += (f"\nThe <{tag.group(1)}> tag opened on line(s) {', '.join(map(str, opened))} is never closed. "
                     f"Add </{tag.group(1)}> where that group ends, or remove the opening tag.")
    return text


AXE_HINTS = {
    "dlitem": "Inside a <dl>, a <div> that wraps a <dt>/<dd> pair must have no role attribute; remove role=... from "
              "those wrappers and keep every <dt>/<dd> directly in the <dl> or in a plain <div> inside it.",
    "definition-list": "A <dl> may only contain <dt>, <dd> and plain <div> wrappers around them.",
    "list": "A <ul> or <ol> may only contain <li> elements directly.",
    "listitem": "An <li> must sit directly inside a <ul> or <ol>.",
    "heading-order": "Headings must not skip levels: an <h2> is followed by <h3>, not <h4>.",
    "region": "All visible content must sit inside a landmark such as <header>, <main>, <footer> or <section "
              "aria-labelledby=...>.",
    "landmark-unique": "Two landmarks of the same kind need different accessible names.",
    "landmark-no-duplicate-banner": "Use only one top-level <header>.",
    "landmark-no-duplicate-contentinfo": "Use only one top-level <footer>.",
    "aria-allowed-role": "Remove role attributes that the element does not allow.",
    "link-name": "Every link needs visible text or an aria-label.",
    "svg-img-alt": "An <svg role=\"img\"> needs a <title> or aria-label; decorative SVGs should be aria-hidden=\"true\".",
    "nested-interactive": "Do not put links or buttons inside other links or buttons.",
}


def axe_summary(lines: list[str]) -> list[str]:
    """Name each failing axe rule other than colour contrast, the elements it flags and the usual fix."""
    found: dict[str, dict] = {}
    current = None
    for index, line in enumerate(lines):
        rule = re.search(r'"id": "([\w-]+)"', line)
        if rule and index and '"helpUrl"' in lines[index - 1]:
            current = rule.group(1)
            help_line = re.search(r'"help": "(.*)",?$', lines[index - 2]) if index > 1 else None
            found.setdefault(current, {"help": help_line.group(1) if help_line else current, "html": []})
        elif current and current != "color-contrast" and (html := re.search(r'"html": "(.*)",?$', line)) \
                and any('"failureSummary"' in lines[k] for k in range(max(0, index - 4), index)):
            snippet = html.group(1).replace('\\"', '"')[:110]
            if snippet not in found[current]["html"]:
                found[current]["html"].append(snippet)
    return [f"- {rule} ({info['help']}): {'; '.join(info['html'][:4]) or 'see the raw output'}. "
            + AXE_HINTS.get(rule, "") for rule, info in found.items() if rule != "color-contrast"][:6]


def overflow_scan(wt: Path, port: int) -> list[dict]:
    """Find the elements that stick out past the screen in the built site; the model cannot see the page."""
    server = subprocess.Popen([str(PY), "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory",
                               str(wt / REL / "dist")], env=CLEAN_ENV, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    try:
        time.sleep(2)
        ok, output = run([str(NODE), str(HERE / "design_overflow.cjs"), str(wt / REL), f"http://127.0.0.1:{port}"],
                         HERE, timeout=180)
    finally:
        server.terminate()
    try:
        return json.loads(output.strip().splitlines()[-1]) if ok else []
    except (ValueError, IndexError):
        return []


def overflow_report(wt: Path, port: int) -> str:
    hits = overflow_scan(wt, port)
    if not hits:
        return ""
    return ("These elements stick out past the screen edge and cause the sideways scrolling:\n- "
            + "\n- ".join(f"{h['label']}, page {h['path']}: {h['element']} spans {h['left']}px to {h['right']}px but "
                          f"the screen is {h['width']}px wide" for h in hits)
            + "\nConstrain them (max-width: 100%, no fixed widths wider than the screen, no 100vw plus padding, no "
            "negative margins or translateX that push them out) or clip their section with overflow-x: clip.")


def contrast_fixes(output: str) -> dict[str, str]:
    """Map each axe colour-contrast target selector to a passing colour of the same hue."""
    lines, fixes = output.splitlines(), {}
    for index, line in enumerate(lines):
        if '"failureSummary"' in line and index + 1 < len(lines) and "contrast of" in lines[index + 1]:
            m = re.search(r"foreground color: (#\w+), background color: (#\w+).*?Expected contrast ratio of ([\d.]+)",
                          lines[index + 1])
            target = next((lines[j + 1].strip().lstrip("+").strip().strip(",")[1:-1].replace('\\"', '"')
                           for j in range(index + 2, min(index + 12, len(lines) - 1)) if '"target"' in lines[j]), "")
            if m and target and "{" not in target and "}" not in target:
                fixes[target] = passing_color(m.group(1), m.group(2), float(m.group(3)))
    return fixes


def auto_fix(wt: Path, output: str, port: int) -> list[str]:
    """Apply deterministic fixes for mechanical accessibility failures, as a linter's --fix would. The design itself
    stays the model's; every fix is logged and reported."""
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    tpl, applied, css = wt / REL, [], []
    if '"id": "dlitem"' in output:
        for path in [tpl / "src/pages/index.astro", tpl / "src/pages/privacy.astro",
                     *sorted((tpl / "src/components").glob("*.astro"))]:
            if path.name == "Calculator.astro" or not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            fixed = re.sub(r'<div\s+role="[^"]*"(\s*>\s*<dt)', r"<div\1", text)
            if fixed != text:
                path.write_text(fixed, encoding="utf-8", newline="\n")
                applied.append(f"removed role attributes from the <dt>/<dd> wrappers in {path.name}")
    for selector, color in contrast_fixes(output).items():
        css.append(f"{selector} {{ color: {color} !important; }}")
        applied.append(f"set {selector} text to {color} for WCAG AA contrast")
    if "scrollWidth <= innerWidth" in output:
        for hit in overflow_scan(wt, port):
            # Clip only a small decorative overhang; a layout that runs far off the screen must be fixed, not hidden.
            overshoot = max(hit["right"] - hit["width"], -hit["left"])
            if hit.get("clip") and overshoot <= 40:
                rule = f"{hit['clip']} {{ overflow-x: clip; }}"
                if rule not in css:
                    css.append(rule)
                    applied.append(f"clipped {hit['clip']} so {hit['element']} no longer sticks out past the screen")
    if css:
        sheet = tpl / "src/styles/site.css"
        if not sheet.exists():  # never the locked base.css
            sheet = next((p for p in sorted((tpl / "src/styles").glob("*.css")) if p.name != "base.css"), sheet)
        with sheet.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n/* Mechanical accessibility fixes applied by the design harness. */\n" + "\n".join(css) + "\n")
    return applied


def failure_feedback(check: str, output: str) -> str:
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    lines = output.splitlines()
    parts: list[str] = [context] if (context := compile_error_context(output)) else []
    # Pull out the facts the model can act on (failed tests, what covers a control, which text fails contrast)
    # before the raw excerpt, because axe's JSON diff alone fills the excerpt budget.
    failed = list(dict.fromkeys(m.group(1).strip() for line in lines
                                if (m := re.match(r"\s*\d+\) (\[\w+\] .*)$", line))))
    if failed:
        parts.append("Failed tests:\n" + "\n".join(f"- {name}" for name in failed[:6]))
    blockers = list(dict.fromkeys(m.group(1).strip() for line in lines
                                  if (m := re.search(r"- (<.+?) intercepts pointer events", line))))
    if blockers:
        target = re.search(r"locator resolved to (<\w+[^>]*>[^<]{0,60})", output)
        parts.append(f"A click on {target.group(1) + '…' if target else 'a calculator control'} timed out because "
                     "other elements sit on top of it:\n- " + "\n- ".join(blockers[:6])
                     + "\nFix the layout so nothing overlaps the form at that width "
                     "(check grid placement, negative margins, absolute or fixed positioning and fixed heights) "
                     "and give purely decorative layers pointer-events: none.")
    contrast: list[str] = []
    for index, line in enumerate(lines):
        if '"failureSummary"' in line and index + 1 < len(lines) and "contrast of" in lines[index + 1]:
            m = re.search(r"contrast of ([\d.]+) \(foreground color: (#\w+), background color: (#\w+).*?"
                          r"Expected contrast ratio of ([\d.:]+)", lines[index + 1])
            html = next((re.sub(r'\\"', '"', h.group(1)) for later in lines[index + 2:index + 5]
                         if (h := re.search(r'"html": "(.*)",?$', later))), "")
            target = next((lines[j + 1].strip().lstrip("+").strip().strip('",') for j in range(index + 2, min(index + 12, len(lines) - 1))
                           if '"target"' in lines[j]), "")
            if m:
                need = float(m.group(4).split(":")[0])
                fix = passing_color(m.group(2), m.group(3), need)
                contrast.append(f"- {target or html[:80]}: text {m.group(2)} on {m.group(3)} is {m.group(1)}:1, "
                                f"needs {m.group(4)}. Fix: add a rule `{target or 'that element'} {{ color: {fix}; }}` "
                                f"or change its background. ({html[:70]})")
    other = axe_summary(lines)
    if other:
        parts.append("Other accessibility rules that fail:\n" + "\n".join(other))
    if "scrollWidth <= innerWidth" in output:
        parts.append("The page is wider than the screen, so it scrolls sideways (a test checks that it does not).")
    if contrast:
        parts.append("Text that fails WCAG AA contrast. Each line gives a colour that passes; the rule must win over "
                     "your other rules for that element, so put it at the end of your stylesheet:\n"
                     + "\n".join(dict.fromkeys(contrast[:10])))
    keep: list[str] = []
    for index, line in enumerate(lines):
        if re.search(r"not ok|error|Error|AssertionError|expected|Expected|Received|violation|failed|Failed", line):
            keep.extend(lines[index:index + 4])
    parts += [hint for key, hint in KNOWN_FIXES.items() if key in output]
    budget = 1200 if parts else 2500
    excerpt = "\n".join(dict.fromkeys(keep))[:budget] or output[-1500:]
    parts.append("Raw output excerpt:\n" + excerpt)
    return (f"Your current files failed the {check} check. They are still in place: read them, fix the cause "
            "with small edits and keep your design.\n\n" + "\n\n".join(parts))


def capture(wt: Path, port: int, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen([str(PY), "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory",
                               str(wt / REL / "dist")], env=CLEAN_ENV, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    try:
        time.sleep(2)
        ok, output = run([str(NODE), str(HERE / "design_capture.cjs"), str(wt / REL), str(out),
                          f"http://127.0.0.1:{port}"], HERE, timeout=240)
        if not ok:
            raise RuntimeError("screenshot capture failed: " + output[-400:])
    finally:
        server.terminate()
    return [out / name for name in ("desktop-fold.png", "desktop-full.png", "mobile-full.png")]


class Judge:
    def __init__(self) -> None:
        import anthropic
        self.settings = advisor_settings()
        if self.settings["enabled"] != "true" or not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("Advisor is not enabled or the API key is missing")
        if not APPROVAL_NOTE.strip():
            raise SystemExit("Set DESIGN_LAB_APPROVAL to the owner's exact chat approval for this batch")
        self.db = Database(os.environ["SITEFORGE_DATABASE_URL"])
        self.policy, self.org = PolicyService(self.db), os.environ["SITEFORGE_ORG_ID"]
        self.client, self.spent = anthropic.Anthropic(), Decimal("0")

    def can_afford(self) -> bool:
        return self.spent + PER_SCORE_GUARD <= BUDGET

    def score(self, shots: list[Path], out: Path) -> dict:
        brief = (f"Score this website design. {SUBJECT} This is a private preview, so a proof stamp and host and "
                 "contact placeholders are expected. Screenshots: the desktop first screen, the full desktop page "
                 "and the full phone page.")
        text = (out / "page-text.txt").read_text(encoding="utf-8")[:20000]
        document = build_request("design_score", SITE_ID, brief, documents=[("page-text.txt", text)],
                                 screenshots=[(shot.name, shot.read_bytes()) for shot in shots])
        path = save_request(document, MAIN / "runtime" / "advisor")
        approval = request_approval(self.policy, self.org, document, "design-loop")
        self.policy.decide(self.org, approval["id"], "owner", True, APPROVAL_NOTE)
        ensure_budgets(self.policy, self.org, monthly=self.settings["monthly"], daily=self.settings["daily"])
        result = run_review(self.policy, self.org, approval["id"], path, self.client,
                            results_root=MAIN / "runtime" / "advisor")
        self.spent += Decimal(result["measured_cost"])
        (out / "opus-score.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result


def new_edit_failures(session_id: str, seen: set[str]) -> list[str]:
    """Failed Edit/Write calls in a session transcript; the model often reports success after every edit failed."""
    base = "\\\\?\\" + str((MAIN / "runtime" / "cc-config" / "projects").resolve())  # transcript paths exceed MAX_PATH
    failures: list[str] = []
    for folder in os.listdir(base):
        path = os.path.join(base, folder, f"{session_id}.jsonl")
        if not os.path.exists(path):
            continue
        names: dict[str, str] = {}
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    content = (json.loads(line).get("message") or {}).get("content")
                except ValueError:
                    continue
                for item in content if isinstance(content, list) else []:
                    if item.get("type") == "tool_use":
                        target = str((item.get("input") or {}).get("file_path", ""))
                        names[item.get("id", "")] = f"{item.get('name')} {target}".strip()
                    elif item.get("type") == "tool_result" and item.get("is_error"):
                        call = names.get(item.get("tool_use_id", ""), "")
                        if item.get("tool_use_id") in seen or not call.startswith(("Edit", "Write", "MultiEdit")):
                            continue
                        seen.add(item.get("tool_use_id"))
                        text = item.get("content")
                        text = text if isinstance(text, str) else json.dumps(text)
                        failures.append(f"{call}: {re.sub(r'</?tool_use_error>', '', text).strip()[:240]}")
    return failures


def edit_failure_prompt(failures: list[str]) -> str:
    return ("These tool calls FAILED and saved nothing, so the files do not contain those changes yet:\n- "
            + "\n- ".join(dict.fromkeys(failures[:8]))
            + "\nEdit takes exactly these parameters: file_path, old_string, new_string, and optionally replace_all. "
            "Write takes exactly file_path and content. Never add any other parameter, such as reason. For "
            "old_string, copy the text exactly as Read shows it, without the line-number prefix; for a large change, "
            "Write the whole file instead. Redo every failed change now, then end your reply with DONE." + WRITE_ONLY_NOTE)


def describe(review: dict) -> str:
    scores = review.get("scores", {})
    fixes = [f"- [{f['severity']}] {f['area']}: {f['recommendation']}" for f in review.get("findings", [])[:8]]
    return (f"overall {scores.get('overall')}/10 (" + ", ".join(f"{k} {v}" for k, v in scores.items() if k != "overall")
            + ")\nTheir summary: " + review.get("summary", "") + "\nTheir highest-impact fixes:\n" + "\n".join(fixes))


def markup_classes(wt: Path) -> list[str]:
    names: set[str] = set()
    for file in [wt / REL / "src/pages/index.astro", *sorted((wt / REL / "src/components").glob("*.astro"))]:
        for value in re.findall(r'class="([^"{}]+)"', file.read_text(encoding="utf-8", errors="replace")):
            names.update(value.split())
    return sorted(names)


def incremental_prompt(state: dict, wt: Path) -> str:
    """Hill-climb the best version: one or two of the art director's fixes per session, never a full redesign.
    A small model makes targeted edits well and loses what already works when it redesigns from scratch."""
    review = state["best_review"]
    order = {"critical": 0, "major": 1, "minor": 2}
    findings = sorted(review.get("findings", []), key=lambda f: order.get(f.get("severity"), 3))
    if not findings:
        return BRIEFS["b"]
    start = state.get("offset", 0) % len(findings)
    chosen = (findings + findings)[start:start + min(2, len(findings))]
    steps = "\n".join(f"{n}. [{f.get('area')}] {f.get('recommendation')}" for n, f in enumerate(chosen, 1))
    prompt = (f"You are improving an existing website. Do not redesign it. The site: {SUBJECT}\n\nThe current files "
              f"are the best version so far: an art director scored it {review.get('scores', {}).get('overall')}/10 "
              f"and said: {review.get('summary', '')}\n\nCarry out exactly these improvements in this session, fully "
              f"and with care, and change nothing else:\n{steps}\n\nYou cannot change scripts, so anything that moves "
              "with the results (the roll strip, the numbers) must be done with CSS on the existing classes and ids, "
              "and any part of an improvement that would need JavaScript or a change to Calculator.astro must be "
              "skipped (do the rest of it); "
              "for example the .roll spans can become rings with border-radius, borders and a conic-gradient that "
              "uses var(--used). Keep the existing layout, palette, fonts, copy and every element you are not "
              "improving. Read the files first, then make focused edits. CSS must match the "
              "markup; these classes exist in the page right now: "
              + " ".join(f".{name}" for name in markup_classes(wt))
              + ". If you add a new class in CSS, add the element that uses it in the same session.\n\n" + CONSTRAINTS)
    if state["note"]:
        prompt += "\n\n" + state["note"]
    if state["feedback"]:
        prompt += "\n\n" + state["feedback"]
    return prompt


def prompt_for(arm: str, state: dict, wt: Path, fixing: bool = False) -> str:
    text = _prompt_body(arm, state, wt, fixing) + WRITE_ONLY_NOTE
    return LOOK_FIRST + "\n\n" + text if state.get("shots_published") else text


def use_model(identifier: str) -> None:
    """Keep exactly one large local model loaded (AGENTS.md) and swap in the one this step needs."""
    listed = subprocess.run([LMS, "ps", "--json"], env=CLEAN_ENV, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    loaded = [m.get("identifier") for m in json.loads(listed.stdout or "[]")]
    if loaded == [identifier]:
        return
    for other in loaded:
        subprocess.run([LMS, "unload", other], env=CLEAN_ENV, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    key, context = LOCAL_MODELS[identifier]
    subprocess.run([LMS, "load", key, "--identifier", identifier, "--context-length", str(context), "--gpu", "max",
                    "-y"], env=CLEAN_ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                   check=True)


def critic_review(run_dir: Path) -> str:
    """Ask the local vision model, as an art director with no tools, what is visibly wrong with the screenshots."""
    import base64
    import urllib.request
    content: list[dict] = []
    for name, caption in (("desktop-fold.png", "Desktop, first screen only (1280px wide; the page continues below this crop):"),
                          ("mobile-fold.png", "Phone, first screen only (393px wide; the page continues below this crop, so content cut at the bottom edge is not clipped):"),
                          ("desktop-full.png", "Desktop, the whole page:")):
        if (run_dir / name).exists():
            content += [{"type": "text", "text": caption},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                     "data": base64.b64encode((run_dir / name).read_bytes()).decode()}}]
    content.append({"type": "text", "text": CRITIC_PROMPT.format(subject=SUBJECT)})
    body = {"model": CRITIC, "max_tokens": 6000, "thinking": {"type": "enabled", "budget_tokens": 3000},
            "messages": [{"role": "user", "content": content}]}
    request = urllib.request.Request("http://127.0.0.1:1234/v1/messages", data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json", "x-api-key": "lmstudio",
                                              "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(request, timeout=900) as response:
        data = json.load(response)
    return "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text").strip()


def self_review(wt: Path, arm: str, number: int, run_dir: Path, sid: str, passes: list,
                entry: dict) -> tuple[list[Path], list[str]]:
    """Have the rendered page reviewed visually and let the designer fix what is seen: either a vision designer reads
    its own screenshots, or a separate local vision critic lists problems for the designer. The change is kept only if
    it still passes the gate, every check and the visual lint; otherwise the tested version and its shots come back."""
    names = ("desktop-fold.png", "desktop-full.png", "mobile-full.png")
    good, label = snapshot(wt), f"[{arm}] run {number}"
    before = run_dir / "before-self-review"
    before.mkdir(exist_ok=True)
    for name in (*SHOT_NAMES, "mobile-full.png", "lint.json", "page-text.txt"):
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, before / name)
    if CRITIC:
        log(f"{label}: swapping in {CRITIC} as a local art director")
        use_model(CRITIC)
        try:
            critique = critic_review(run_dir)
        finally:
            use_model(MODEL_ID)
        (run_dir / "local-critique.txt").write_text(critique, encoding="utf-8")
        entry["local_critique"] = critique[:2000]
        log(f"{label}: local art director listed problems; the designer is fixing them")
        prompt = CRITIC_FIX_PROMPT.format(critique=critique) + WRITE_ONLY_NOTE
    else:
        publish_shots(wt, run_dir)
        log(f"{label}: the model is reviewing screenshots of its own page")
        prompt = SELF_REVIEW_PROMPT
    seen: set[str] = set()
    new_edit_failures(sid, seen)  # mark the session's earlier failures so only this review's count
    review = run_claude(prompt, wt / REL, MODEL_ID, tools=TOOLS, max_turns=25, timeout=1500, resume=sid,
                        system_prompt=CC_SYSTEM)
    passes.append(review)
    for _ in range(2):  # the model reports the fixes done even when every edit failed
        review_sid = (review.get("result") or {}).get("session_id")
        failures = new_edit_failures(review_sid, seen) if review_sid else []
        if not failures:
            break
        log(f"{label}: {len(failures)} review edits failed; asking the model to redo them")
        review = run_claude(edit_failure_prompt(failures), wt / REL, MODEL_ID, tools=TOOLS, max_turns=20,
                            timeout=1200, resume=review_sid, system_prompt=CC_SYSTEM)
        passes.append(review)
    (run_dir / "claude-code.json").write_text(json.dumps(passes, indent=2), encoding="utf-8")
    entry["self_review_seconds"] = review["seconds"]
    if snapshot(wt) == good:
        entry["self_review"] = "no changes"
        log(f"{label}: self-review made no changes")
        return [run_dir / n for n in names], []
    if not gate(wt) and checks_with_fixes(wt, PORTS[arm], entry, label)[0]:
        shots = capture(wt, PORTS[arm], run_dir)
        if not json.loads((run_dir / "lint.json").read_text(encoding="utf-8")):
            entry["self_review"] = "changes kept"
            log(f"{label}: self-review changes pass every check; keeping them")
            return shots, []
    restore(wt, good)
    for path in before.iterdir():
        shutil.copy2(path, run_dir / path.name)
    entry["self_review"] = "changes reverted"
    log(f"{label}: self-review changes broke a check; reverted to the tested version")
    return [run_dir / n for n in names], []


def _prompt_body(arm: str, state: dict, wt: Path, fixing: bool = False) -> str:
    if fixing and state["feedback"]:
        # A small model follows a short, single-purpose prompt; under the full brief it redesigns instead of fixing.
        return ("FIX ROUND. Your design is already in the files. A check is failing, and your only job in this "
                "session is to fix that failure with small, focused changes. Do not redesign, "
                "and do not change anything the failure does not mention.\n\n" + state["feedback"]
                + "\n\nAfter editing, Read the lines you changed to confirm the fix is really in the file, then end "
                "your reply with DONE.\n\nThe rules you must keep following:\n" + CONSTRAINTS)
    if arm in INCREMENTAL and state["best_review"]:
        return incremental_prompt(state, wt)
    prompt = BRIEFS[arm] + (
        "\n\nCSS MUST MATCH THE MARKUP. These classes exist in the page right now: "
        + " ".join(f".{name}" for name in markup_classes(wt))
        + ". If your CSS styles a new class, add elements with that class to index.astro or a component in this "
        "same session. Keep every CSS custom property you use defined, including the font tokens --display and "
        "--body that the font rules depend on.")
    if state["best_review"] is not None and state["improved_once"]:
        prompt += ("\n\nTHIS IS A REVISION ROUND. The current files are your best version so far. The art director "
                   f"scored it {describe(state['best_review'])}\nCarry out these fixes to raise the score toward 9/10. "
                   "Keep what already works.")
    if state["note"]:
        prompt += "\n\n" + state["note"]
    if state["feedback"]:
        prompt += "\n\n" + state["feedback"]
    return prompt


def main() -> None:
    out = MAIN / "runtime" / f"design-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out.mkdir(parents=True)
    log(f"output: {out}")
    judge = Judge()
    judge.spent = PRIOR_SPEND
    if CRITIC:
        use_model(MODEL_ID)  # the designer works first; the critic is swapped in only to review screenshots
    for arm, wt in WTS.items():
        if arm not in RESUME:
            restore(wt, {})
    if BASELINE_DIR is not None:
        # Rendering is unchanged since that score, so reuse it instead of paying again.
        shutil.copytree(BASELINE_DIR / "baseline", out / "baseline")
        baseline = json.loads((out / "baseline" / "opus-score.json").read_text(encoding="utf-8"))
    else:
        ok, results = run_checks(WTS["a"])
        if not ok:
            raise SystemExit("baseline checks failed: " + json.dumps(results)[:500])
        baseline_shots = capture(WTS["a"], PORTS["a"], out / "baseline")
        baseline = judge.score(baseline_shots, out / "baseline")
    base_review = baseline.get("review") or {}
    base_score = base_review.get("scores", {}).get("overall", 0)
    log(f"baseline: current Rollwise scored {base_score}/10 (${baseline['measured_cost']})")
    states = {arm: {"best_score": base_score, "best_snapshot": {}, "best_review": base_review, "improved_once": False,
                    "feedback": None, "note": None, "working": None, "runs": 0, "scores": 0, "done": False,
                    "history": []}
              for arm in "ab"}
    for arm in "ab":  # an incremental arm's place in the art director's fix list survives a restart
        states[arm]["offset"] = int(os.environ.get(f"DESIGN_OFFSET_{arm.upper()}", "0"))
    fresh = next((arm for arm in "ab" if arm not in RESUME), None)
    if VISION and fresh:
        # The scored baseline has no phone first-screen shot; render the unchanged site once so the model can see it.
        built, output = run([str(NODE), "node_modules/astro/bin/astro.mjs", "build"], WTS[fresh] / REL)
        if built:
            capture(WTS[fresh], PORTS[fresh], out / "baseline-shots")
            for state in states.values():
                state["best_shots"] = out / "baseline-shots"
        log(f"baseline screenshots for the vision model: {'ready' if built else 'build failed: ' + output[-200:]}")
    for arm, (check, failure) in RESUME.items():
        states[arm]["working"] = snapshot(WTS[arm])
        if check == "recheck":
            states[arm]["skip_model"] = True
            log(f"[{arm}] resuming {len(states[arm]['working'])} changed files straight into the checks")
            continue
        failure_text = Path(failure).read_text(encoding="utf-8")
        states[arm]["feedback"] = failure_text if check == "gate" else failure_feedback(check, failure_text)
        if "scrollWidth <= innerWidth" in failure_text and (wide := overflow_report(WTS[arm], PORTS[arm])):
            states[arm]["feedback"] += "\n\n" + wide
        log(f"[{arm}] resuming {len(states[arm]['working'])} changed files that failed {check}")
    summary ={"baseline": {"score": base_score, "cost": baseline["measured_cost"], "scores": base_review.get("scores")},
               "arms": states, "output": str(out)}
    try:
        while not all(state["done"] for state in states.values()):
            for arm in ("b", "a"):
                state = states[arm]
                if state["done"]:
                    continue
                wt, number = WTS[arm], state["runs"] + 1
                run_dir = out / f"arm-{arm}" / f"run-{number}"
                run_dir.mkdir(parents=True)
                # Build, test and lint failures keep the work in place so the model can fix it; gate rejections
                # and lower scores fall back to the best scored version.
                restore(wt, state["working"] if state["working"] is not None else state["best_snapshot"])
                fixing = state["working"] is not None
                shots_source = state.get("working_shots") if fixing else state.get("best_shots")
                state["shots_published"] = VISION and publish_shots(wt, shots_source)
                state["working"] = state["working_shots"] = None
                prompt = prompt_for(arm, state, wt, fixing)
                (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
                if state.pop("skip_model", False):
                    # Resumed files that were fixed outside the loop go straight to the checks.
                    log(f"[{arm}] run {number}: re-checking the resumed files without a model session")
                    session = {"seconds": 0.0, "result": {}}
                else:
                    log(f"[{arm}] run {number}: Claude Code + {MODEL_ID} working")
                    session = run_claude(prompt, wt / REL, MODEL_ID, tools=TOOLS, max_turns=40, timeout=1800,
                                         system_prompt=CC_SYSTEM)
                passes, total_seconds = [session], session["seconds"]
                seen_failures: set[str] = set()
                failures: list[str] = []
                # Small models often announce the next step and stop, or report success after their edits failed;
                # resume the same session until DONE with no failed edits.
                for _ in range(MAX_CONTINUES):
                    last = passes[-1].get("result") or {}
                    session_id, text = last.get("session_id"), str(last.get("result", ""))
                    if not session_id:
                        break
                    failures = new_edit_failures(session_id, seen_failures)
                    if failures:
                        follow = edit_failure_prompt(failures)
                        log(f"[{arm}] run {number}: {len(failures)} edit calls failed; asking the model to redo them")
                    elif "DONE" in text:
                        break
                    else:
                        follow = CONTINUE_PROMPT
                        log(f"[{arm}] run {number}: continuing the session")
                    before = json.dumps(snapshot(wt), sort_keys=True)
                    passes.append(run_claude(follow, wt / REL, MODEL_ID, tools=TOOLS, max_turns=30,
                                             timeout=1500, resume=session_id, system_prompt=CC_SYSTEM))
                    total_seconds += passes[-1]["seconds"]
                    if json.dumps(snapshot(wt), sort_keys=True) == before:
                        break
                session = {**passes[-1], "seconds": round(total_seconds, 1), "passes": len(passes)}
                state["runs"] += 1
                result = session.get("result") or {}
                entry = {"run": number, "seconds": session["seconds"], "passes": len(passes),
                         "turns": sum((p.get("result") or {}).get("num_turns") or 0 for p in passes),
                         "cc_outcome": result.get("subtype") or session.get("stderr", "")[-200:],
                         "model_summary": str(result.get("result", ""))[:1500]}
                (run_dir / "claude-code.json").write_text(json.dumps(passes, indent=2), encoding="utf-8")
                state["note"] = None
                # Repair setup tags and the privacy line before the gate, so a design is not discarded for them.
                if pre_fixes := source_autofix(wt):
                    entry.setdefault("auto_fixes", []).extend(pre_fixes)
                    log(f"[{arm}] run {number}: harness {'; '.join(pre_fixes)}")
                errors = gate(wt)
                if errors:
                    entry["outcome"] = "gate rejected"
                    entry["problems"] = errors[:12]
                    if len(errors) <= 2 and all("missing required text" in error for error in errors):
                        # Dropped wording is easy to restore, so keep the design instead of discarding it.
                        state["working"] = snapshot(wt)
                        state["feedback"] = ("Your files are still in place, but they are missing text the page must "
                                             "keep:\n" + "\n".join(errors[:12]) + "\nAdd each missing text back "
                                             "exactly as written, in a sensible place, and change nothing else.")
                    else:
                        state["feedback"] = ("Your last version was rejected by the safety gate and discarded:\n"
                                             + "\n".join(errors[:12]))
                        state["offset"] = state.get("offset", 0) + 2  # an incremental arm stops retrying those fixes
                    if failures:
                        state["feedback"] += "\n\n" + edit_failure_prompt(failures)
                    log(f"[{arm}] run {number}: gate rejected ({errors[0]}) after {session['seconds']}s")
                else:
                    (run_dir / "changes.json").write_text(json.dumps(sorted(snapshot(wt)), indent=2), encoding="utf-8")
                    # Keep every attempt's files so a broken render can be diagnosed after the worktree moves on.
                    (run_dir / "files.json").write_text(json.dumps(snapshot(wt), indent=1), encoding="utf-8")
                    ok, results = checks_with_fixes(wt, PORTS[arm], entry, f"[{arm}] run {number}")
                    if not ok:
                        failed = next(name for name, value in results.items() if value != "passed")
                        entry["outcome"] = f"{failed} failed"
                        state["feedback"] = failure_feedback(failed, results[failed])
                        if "scrollWidth <= innerWidth" in results[failed] and (wide := overflow_report(wt, PORTS[arm])):
                            state["feedback"] += "\n\n" + wide
                        state["working"] = snapshot(wt)
                        (run_dir / "check-failure.txt").write_text(results[failed], encoding="utf-8")
                        log(f"[{arm}] run {number}: {failed} failed after {session['seconds']}s")
                    elif not judge.can_afford():
                        entry["outcome"] = "passed checks; not scored, budget reached"
                        state["done"] = True
                        log(f"[{arm}] run {number}: passed checks but the scoring budget is used up")
                    else:
                        state["feedback"] = None
                        log(f"[{arm}] run {number}: all checks passed in {session['seconds']}s; capturing")
                        shots = capture(wt, PORTS[arm], run_dir)
                        lint = json.loads((run_dir / "lint.json").read_text(encoding="utf-8"))
                        sid = (passes[-1].get("result") or {}).get("session_id")
                        if (VISION or CRITIC) and not lint and sid:
                            shots, lint = self_review(wt, arm, number, run_dir, sid, passes, entry)
                        if lint:
                            entry.update({"outcome": "visual lint failed", "problems": lint[:10]})
                            state["feedback"] = ("Your current files build, but the page renders broken. They are still "
                                                 "in place; fix these problems:\n- " + "\n- ".join(lint[:10]))
                            state["working"], state["working_shots"] = snapshot(wt), run_dir
                            state["history"].append(entry)
                            log(f"[{arm}] run {number}: visual lint failed ({lint[0][:120]})")
                            if state["runs"] >= MAX_RUNS:
                                state["done"] = True
                            continue
                        log(f"[{arm}] run {number}: visual lint clean; scoring")
                        scored = judge.score(shots, run_dir)
                        state["scores"] += 1
                        review = scored.get("review") or {}
                        score = review.get("scores", {}).get("overall", 0)
                        entry.update({"outcome": "scored", "score": score, "scores": review.get("scores"),
                                      "cost": scored["measured_cost"]})
                        if score > state["best_score"]:
                            state.update({"best_score": score, "best_snapshot": snapshot(wt), "best_review": review,
                                          "improved_once": True, "best_run": number, "offset": 0,
                                          "best_shots": run_dir})
                            log(f"[{arm}] run {number}: NEW BEST {score}/10 (${scored['measured_cost']}, "
                                f"total ${judge.spent})")
                        else:
                            state["offset"] = state.get("offset", 0) + 2  # incremental arms move to the next fixes
                            state["note"] = (f"Your last attempt scored {score}/10, not better than your best "
                                             f"{state['best_score']}/10, so it was discarded. Try a stronger approach.")
                            log(f"[{arm}] run {number}: scored {score}/10, below best {state['best_score']} "
                                f"(${scored['measured_cost']}, total ${judge.spent})")
                        if score >= TARGET:
                            state["done"] = True
                state["history"].append(entry)
                if state["runs"] >= MAX_RUNS or state["scores"] >= MAX_SCORES or not judge.can_afford():
                    state["done"] = True
                (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    finally:
        for arm, state in states.items():
            if state["working"] is not None:
                # Unfinished fix-in-place work stays in the worktree (and on disk) so a restart can resume it.
                (out / f"arm-{arm}").mkdir(parents=True, exist_ok=True)
                (out / f"arm-{arm}" / "working.json").write_text(json.dumps(state["working"], indent=1),
                                                                 encoding="utf-8")
                restore(WTS[arm], state["working"])
            else:
                restore(WTS[arm], state["best_snapshot"])
            if state["best_snapshot"]:
                best = out / f"arm-{arm}" / "best"
                best.mkdir(parents=True, exist_ok=True)
                for path, text in state["best_snapshot"].items():
                    if text is not None:
                        (best / Path(path).name).write_text(text, encoding="utf-8")
        summary["opus_spent"] = str(judge.spent)
        (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        judge.db.dispose()
        log(f"done: spent ${judge.spent}; best A {states['a']['best_score']}, best B {states['b']['best_score']}, "
            f"baseline {base_score}")


if __name__ == "__main__":
    main()
