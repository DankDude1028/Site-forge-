"""Opus 5.5 and Haiku 5.5 as lead designer for Rollwise, head to head, judged by Opus 5.5 from screenshots.

Each arm's model receives the current files, screenshots, the art director's latest review and the build rules, and
answers with whole files through the capped advisor. The harness writes only allowed files, gates them, runs the full
checks and the visual lint, then Opus scores the screenshots with the same calibrated rubric as the 6/10 baseline.
Failures go back to the same model as a fix round; each arm hill-climbs from its best scored version.
Owner approved up to $3 in chat: 'Both head-to-head, up to $3 (Recommended)'.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_loop as dl  # noqa: E402  (also loads .env and chdirs to the main checkout)
from design_briefs import SUBJECT  # noqa: E402
from siteforge.advisor import (ADVISOR_MODEL, HAIKU_MODEL, build_request, ensure_budgets,  # noqa: E402
                               request_approval, run_review, save_request)
from siteforge.queue import DomainError  # noqa: E402

_build_request = dl.build_request
# A score answers in about 1,300 tokens; a smaller cap keeps the worst case the ledger reserves near $0.25.
dl.build_request = lambda *args, **kwargs: _build_request(*args, **{"max_tokens": int(os.environ.get("LEAD_SCORE_MAX_TOKENS", "8000")), **kwargs})
TOTAL_CAP = Decimal("3.00")
ARMS = {"opus": {"wt": "b", "model": ADVISOR_MODEL, "cap": Decimal(os.environ.get("LEAD_CAP_OPUS", "2.05")),
                 "lead": Decimal("0.60"),
                 "fixes": 2, "attempts": int(os.environ.get("LEAD_ATTEMPTS_OPUS", "5")), "effort": "medium"},  # at high effort it thought through all 32K
        "haiku": {"wt": "a", "model": HAIKU_MODEL, "cap": Decimal(os.environ.get("LEAD_CAP_HAIKU", "0.95")),
                  "lead": Decimal("0.04"),
                  "fixes": 3, "attempts": int(os.environ.get("LEAD_ATTEMPTS_HAIKU", "12")), "effort": "medium"}}  # high truncated at 32K too
SCORE_GUARD = Decimal("0.10")
SCHEDULE = ["opus", "haiku", "haiku", "haiku"]  # Opus attempts cost about fifteen Haiku attempts
BASELINE = dl.MAIN / "runtime" / "design-20261025T220540Z" / "baseline"
TPL_ALLOWED = re.compile(r"^src/(pages/(index|privacy)\.astro|styles/(?!base\.css$)[\w.-]+\.css|"
                         r"components/(?!Calculator\.astro$)[\w.-]+\.astro)$")
EDITABLE = ["src/pages/index.astro", "src/pages/privacy.astro", "src/components/SiteHeader.astro",
            "src/components/SiteFooter.astro", "src/styles/site.css"]
LOCKED = ["src/components/Calculator.astro", "src/scripts/calculator.ts", "src/styles/base.css"]
# Build-time code is the one place model output could run on this PC; allow only style and markup imports.
IMPORT = re.compile(r"""^\s*import\s+(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]""", re.M)
SAFE_IMPORT = re.compile(r"^(?:(?:\.{1,2}/)+[\w./-]+\.(?:astro|css)|@fontsource/[\w-]+/[\w-]+\.css)$")
BUILD_TIME = {r"\bprocess\b": "process", r"\brequire\s*\(": "require()", r"\bnode:": "a node: module",
              r"import\.meta": "import.meta", r"set:html": "set:html", r"Astro\.glob": "Astro.glob"}

BOLD = """- one bold concept from the world of label printing and small-batch making, carried through everything;
- a signature hero visual you draw yourself as inline SVG and CSS (for example an oversized label roll unspooling a
  strip of labels, a press sheet with registration marks and colour bars, die-cut label shapes); the art director
  rates imagery low when the only visual is the small roll strip;
- a confident layout: full-bleed bands, an asymmetric grid, a dramatic type scale (display sizes around
  clamp(3rem, 8vw, 7rem)) and deliberate whitespace, with no empty dead zones beside the calculator;
- a striking result card: a huge answer number, and the .roll spans restyled as real-looking rolls (concentric
  rings with radial and conic gradients, the partial roll filled by --used);
- detail: texture (data: URI SVG noise or halftone), crop and registration marks, perforations, a print-slug footer,
  and one orchestrated load animation inside @media (prefers-reduced-motion: no-preference);
- a phone layout as good as the desktop one.
Keep the answer efficient: return only the files you change, write CSS without comments, and stay under about
20,000 tokens in total."""
RUBRIC = ("The art director scores 1-10 against award-level web design: 1-3 broken or amateur; 4-5 competent but "
          "template-like; 6 tidy with some character; 7 distinctive and polished with a clear point of view; 8 "
          "memorable, with strong craft throughout; 9 award-level: a bold, cohesive concept executed with precision, "
          "a signature visual idea, refined typography and detail, excellent on mobile. Low contrast, tiny text, "
          "decoration that slows the task and broken phone layouts are penalized.")
RULES = """FILES: paths are relative to the site folder. You may return src/pages/index.astro, src/pages/privacy.astro,
src/styles/site.css (or new .css files in src/styles, imported from a page), and src/components/*.astro (new
components too) except Calculator.astro. Calculator.astro, calculator.ts and base.css are locked and shown for
reference only. Return each file you change whole; files you leave out stay as they are.

THE CALCULATOR IS LOCKED: its working markup (form, inputs, button, result, roll strip and live regions) lives in
Calculator.astro and index.astro renders it with <Calculator />. You may wrap <Calculator /> in your own elements
and place decoration around it, and restyle all of it from CSS using its classes and ids (see the file).
calculator.ts draws the roll strip as span elements with classes .roll, .roll.order, .roll.have and .roll.partial
(which sets the CSS variable --used, a percentage), plus .more; restyle them freely but keep them visible.

HARD RULES. Breaking any of them gets the files rejected automatically:
1. Keep in index.astro: <Calculator /> exactly once and its import line, the <title> text, the phrase "No inputs
   leave your browser" in the visible body (not the <head>), <meta name="robots" content={config.robots} />, the
   canonical link and its const, lang="en" and the meta description. Keep the <head> of index.astro and
   privacy.astro exactly as it is (the harness restores it).
2. No <script> tags, no inline event handlers, no external URLs, no remote fonts or images, no <link>, <iframe>,
   <object> or <embed>, and no CSS @import. CSS url() may only use data: URIs (inline SVG or noise is fine).
   Inline <svg> markup in .astro files is fine.
3. Frontmatter may import only local .astro and .css files (./ or ../ paths) and @fontsource CSS, keeping the
   existing imports. No other build-time code: no process, require, node: modules, import.meta, Astro.glob or
   set:html.
4. Fonts: the installed families are Bricolage Grotesque (weights 200-800, for example
   import '@fontsource/bricolage-grotesque/latin-800.css';) and Source Sans 3 (200-900). No other fonts exist.
5. Accessibility is tested: body text at least 16px with 4.5:1 contrast (large text 3:1), a visible focus style,
   motion only inside @media (prefers-reduced-motion: no-preference), and no sideways scrolling at 390px width. A
   section that changes its background must also set its own text colour. Nothing may sit on top of the
   calculator at any width: tests tap every field and the Calculate button on a 393px-wide phone, so decorative
   layers need pointer-events: none and must sit behind the content.
6. CSS must match the markup: every class you style must exist in a page or component you return or keep, and
   every custom property you use must be defined."""


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{now()}] {message}", flush=True)


def read(wt: Path, rel: str) -> str:
    path = wt / dl.REL / rel
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def documents(wt: Path) -> list[tuple[str, str]]:
    extra = sorted(str(p.relative_to(wt / dl.REL)).replace("\\", "/") for p in [
        *(wt / dl.REL / "src/components").glob("*.astro"), *(wt / dl.REL / "src/styles").glob("*.css")])
    editable = list(dict.fromkeys(EDITABLE + [p for p in extra if TPL_ALLOWED.match(p)]))
    return ([(f"{rel} (locked, reference only)", read(wt, rel)) for rel in LOCKED]
            + [(rel, read(wt, rel)) for rel in editable if (wt / dl.REL / rel).exists()])


def build_time_problems(wt: Path) -> list[str]:
    errors = []
    for path in dl.changed(wt):
        if not path.endswith(".astro") or not (wt / path).exists():
            continue
        new, old = (wt / path).read_text(encoding="utf-8", errors="replace"), dl.head_text(wt, path)
        match = re.match(r"---\r?\n(.*?)\r?\n---", new, flags=re.S)
        front = match.group(1) if match else ""
        old_imports = set(IMPORT.findall(old))
        for spec in IMPORT.findall(front):
            if spec not in old_imports and not SAFE_IMPORT.match(spec):
                errors.append(f"{path}: imports {spec!r}; only local .astro/.css files and @fontsource CSS may be "
                              "imported.")
        for pattern, label in BUILD_TIME.items():
            if len(re.findall(pattern, new)) > len(re.findall(pattern, old)):
                errors.append(f"{path}: adds {label}, which is not allowed.")
    return errors


def apply_files(wt: Path, files: list[dict]) -> tuple[list[str], list[str]]:
    written, refused = [], []
    for item in files:
        rel = str(item.get("path", "")).replace("\\", "/").strip().lstrip("./")
        rel = rel.removeprefix(dl.REL + "/")
        content = item.get("content")
        if not TPL_ALLOWED.match(rel) or not isinstance(content, str) or len(content) > 200_000:
            refused.append(rel or "(no path)")
            continue
        target = wt / dl.REL / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8", newline="\n")
        written.append(rel)
    return written, refused


def brief_for(mode: str, state: dict, wt: Path, feedback: str = "") -> str:
    classes = " ".join(f".{name}" for name in dl.markup_classes(wt))
    head = f"SITE: {SUBJECT}\n\nTHE TARGET: {RUBRIC}\n"
    if mode == "redesign":
        task = ("THE TASK: redesign this site so the art director scores it 9/10. The current design scored "
                f"{dl.describe(state['best_review'])}\nRefinements of this design keep scoring 6, so do not polish "
                "it: keep the copy, the calculator and the required content, and replace the visual design. A 7 or "
                "more needs a page that looks clearly different and memorable at first glance:\n" + BOLD
                + "\nThe screenshots show the current rendering, for reference only.")
    elif mode == "revise":
        task = ("THE TASK: the files below are your best version so far. The art director scored it "
                f"{dl.describe(state['best_review'])}\nRevise it to raise the score toward 9/10. Address the "
                "highest-impact findings fully and make bold changes where they call for them; keep what works. "
                f"Lift the lowest-scoring dimensions most: {weakest(state['best_review'])}. "
                "The screenshots show how it renders now. Return only the files you change, CSS without comments, "
                "under about 20,000 tokens.")
        if state.get("concept"):
            task += f"\nYour concept so far: {state['concept']}"
    else:
        task = ("FIX ROUND. Your design is in the files below and failed an automatic check. Return corrected "
                "versions of only the files that need to change, and keep the design.\n\n" + feedback)
        if state.get("concept"):
            task += f"\n\nYour concept: {state['concept']}"
    if state.get("note") and mode != "fix":
        task += "\n\n" + state["note"]
    return (head + "\n" + task + "\n\nCLASSES IN THE MARKUP RIGHT NOW: " + classes + "\n\n" + RULES
            + "\n\nAnswer with concept (one or two sentences), summary (what you changed) and files.")


class Lead:
    def __init__(self, judge: dl.Judge) -> None:
        self.judge = judge
        self.calls = 0

    def call(self, arm: str, brief: str, docs: list[tuple[str, str]], shots: list[Path], run_dir: Path,
             effort: str = "high") -> dict:
        self.calls += 1
        document = build_request("design_lead", dl.SITE_ID, brief, documents=docs,
                                 screenshots=[(shot.name, shot.read_bytes()) for shot in shots],
                                 effort=effort, model=ARMS[arm]["model"],
                                 max_tokens=int(os.environ.get(f"LEAD_MAX_TOKENS_{arm.upper()}", "32000")))
        path = save_request(document, dl.MAIN / "runtime" / "advisor")
        judge = self.judge
        approval = request_approval(judge.policy, judge.org, document, "design-lead-loop")
        judge.policy.decide(judge.org, approval["id"], "owner", True, dl.APPROVAL_NOTE)
        ensure_budgets(judge.policy, judge.org, monthly=judge.settings["monthly"], daily=judge.settings["daily"])
        result = run_review(judge.policy, judge.org, approval["id"], path, judge.client,
                            results_root=dl.MAIN / "runtime" / "advisor")
        judge.spent += Decimal(result["measured_cost"])
        (run_dir / f"lead-{self.calls}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (run_dir / f"brief-{self.calls}.txt").write_text(brief, encoding="utf-8")
        return result


def rank(review: dict) -> tuple[int, int]:
    """Overall score first; a tie goes to the design with the higher sum of the other dimensions, so a bolder
    design that ties the baseline overall becomes the base for revision instead of being thrown away."""
    scores = review.get("scores") or {}
    return scores.get("overall", 0), sum(value for name, value in scores.items() if name != "overall")


def weakest(review: dict) -> str:
    scores = {name: value for name, value in (review.get("scores") or {}).items() if name != "overall"}
    return ", ".join(f"{name} {value}/10" for name, value in sorted(scores.items(), key=lambda item: item[1])[:3])


def shots_of(folder: Path | None) -> list[Path]:
    names = ("desktop-fold.png", "mobile-fold.png", "desktop-full.png", "mobile-full.png")
    found = [folder / name for name in names if folder and (folder / name).exists()]
    return found[:3]


def attempt(arm: str, state: dict, lead: Lead, judge: dl.Judge, out: Path) -> None:
    cfg, wt = ARMS[arm], dl.WTS[ARMS[arm]["wt"]]
    port = dl.PORTS[cfg["wt"]]
    number = state["attempts"] = state["attempts"] + 1
    run_dir = out / f"arm-{arm}" / f"attempt-{number}"
    run_dir.mkdir(parents=True)
    label = f"[{arm}] attempt {number}"
    entry: dict = {"attempt": number, "calls": []}
    state["history"].append(entry)
    dl.restore(wt, state["best_snapshot"])
    mode = "revise" if state["best_snapshot"] else "redesign"
    brief, shots = brief_for(mode, state, wt), shots_of(state["best_shots"])
    effort = state.get("effort", cfg["effort"])
    for call in range(cfg["fixes"] + 1):
        if state["spent"] + cfg["lead"] + SCORE_GUARD > cfg["cap"] or judge.spent + cfg["lead"] + SCORE_GUARD > TOTAL_CAP:
            log(f"{label}: stopping; the next call would not fit the budget (arm ${state['spent']}, "
                f"total ${judge.spent})")
            state["done"] = True
            entry["outcome"] = "budget reached"
            return
        log(f"{label}: {'fix call' if call else mode} by {cfg['model']}")
        before = judge.spent
        try:
            result = lead.call(arm, brief, documents(wt), shots, run_dir, effort)
        except DomainError as error:
            log(f"{label}: advisor refused the call ({error}); stopping this arm")
            state["done"] = True
            entry["outcome"] = f"advisor refused: {error}"
            return
        except Exception as error:  # an API error may or may not have billed; never retry blindly
            log(f"{label}: API error {type(error).__name__}: {str(error)[:200]}; stopping this arm")
            state["done"] = True
            entry["outcome"] = f"api error: {type(error).__name__}"
            return
        cost = judge.spent - before
        state["spent"] += cost
        attempts = result.get("attempts") or [{}]
        entry["calls"].append({"status": result["status"], "cost": str(cost),
                               "output_tokens": attempts[0].get("output_tokens")})
        log(f"{label}: {result['status']} (${cost}, {attempts[0].get('output_tokens')} output tokens; arm "
            f"${state['spent']}, total ${judge.spent})")
        design = result.get("review")
        if result["status"] == "truncated":
            state["effort"] = effort = "medium"
            brief = brief_for("fix", state, wt, "Your previous answer ran out of output space and was cut off, "
                              "so nothing was saved. Return the same design more compactly: only the files you "
                              "change, without comments or repetition.")
            continue
        if result["status"] != "complete" or not design:
            entry["outcome"] = f"lead answer {result['status']}"
            return
        state["concept"] = design.get("concept") or state.get("concept")
        written, refused = apply_files(wt, design.get("files") or [])
        entry.setdefault("summaries", []).append(design.get("summary", "")[:600])
        log(f"{label}: wrote {', '.join(written) or 'nothing'}" + (f"; refused {', '.join(refused)}" if refused else ""))
        (run_dir / f"files-{call + 1}.json").write_text(json.dumps(dl.snapshot(wt), indent=1), encoding="utf-8")
        if pre := dl.source_autofix(wt):
            log(f"{label}: harness {'; '.join(pre)}")
        errors = build_time_problems(wt) + dl.gate(wt)
        if refused:
            errors.append("These paths are not allowed and were ignored: " + ", ".join(refused))
        if errors:
            log(f"{label}: gate rejected ({errors[0][:160]})")
            if any("you may not edit" in e or "adds" in e or "imports" in e for e in errors):
                dl.restore(wt, state["best_snapshot"])  # unsafe files never reach a build
                brief = brief_for("fix", state, wt, "Your files were rejected by the safety gate and discarded, so "
                                  "the files below are the previous version. Return your design again without these "
                                  "problems:\n" + "\n".join(errors[:12]))
            else:
                brief = brief_for("fix", state, wt, "Your files are missing required content:\n" + "\n".join(errors[:12]))
            shots = []
            continue
        ok, results = dl.checks_with_fixes(wt, port, entry, label)
        if not ok:
            failed = next(name for name, value in results.items() if value != "passed")
            (run_dir / f"check-failure-{call + 1}.txt").write_text(results[failed], encoding="utf-8")
            feedback = dl.failure_feedback(failed, results[failed])
            if "scrollWidth <= innerWidth" in results[failed] and (wide := dl.overflow_report(wt, port)):
                feedback += "\n\n" + wide
            log(f"{label}: {failed} failed")
            brief, shots = brief_for("fix", state, wt, feedback.replace("read them, fix the cause with small edits",
                                                                        "fix the cause")), []
            continue
        shots_dir = run_dir / f"render-{call + 1}"
        score_shots = dl.capture(wt, port, shots_dir)
        lint = json.loads((shots_dir / "lint.json").read_text(encoding="utf-8"))
        if lint:
            log(f"{label}: visual lint failed ({lint[0][:140]})")
            brief = brief_for("fix", state, wt, "Your files build and pass the tests, but the page renders broken "
                              "(the screenshots show the current render):\n- " + "\n- ".join(lint[:10]))
            shots = shots_of(shots_dir)
            continue
        if judge.spent + SCORE_GUARD > TOTAL_CAP:
            log(f"{label}: passed every check, but scoring would exceed the $3 cap")
            entry["outcome"] = "passed; not scored"
            state["done"] = True
            return
        scored = judge.score(score_shots, shots_dir)
        cost = Decimal(scored["measured_cost"])
        state["spent"] += cost
        review = scored.get("review") or {}
        score = review.get("scores", {}).get("overall", 0)
        entry.update({"outcome": "scored", "score": score, "scores": review.get("scores"), "fix_calls": call})
        (shots_dir / "scored-files.json").write_text(json.dumps(dl.snapshot(wt), indent=1), encoding="utf-8")
        if rank(review) > rank(state["best_review"]):
            state.update({"best_score": score, "best_snapshot": dl.snapshot(wt), "best_review": review,
                          "best_shots": shots_dir, "best_attempt": number, "note": None})
            log(f"{label}: NEW BEST {score}/10, dimensions {rank(review)[1]} (score ${cost}; arm "
                f"${state['spent']}, total ${judge.spent})")
        else:
            state["note"] = (f"Your last attempt scored {score}/10, not better than your best {state['best_score']}/10, "
                             "so it was discarded. Try a stronger approach to the findings.")
            log(f"{label}: scored {score}/10, dimensions {rank(review)[1]}, not above best {state['best_score']} "
                f"(dimensions {rank(state['best_review'])[1]}; arm ${state['spent']}, total ${judge.spent})")
        if score >= dl.TARGET:
            state["done"] = True
        return
    entry["outcome"] = "fix calls used up"
    log(f"{label}: still failing after {cfg['fixes']} fix calls; back to the best version")


def main() -> None:
    out = dl.MAIN / "runtime" / f"lead-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out.mkdir(parents=True)
    log(f"output: {out}")
    judge = dl.Judge()
    lead = Lead(judge)
    baseline = json.loads((BASELINE / "opus-score.json").read_text(encoding="utf-8"))
    base_review = baseline.get("review") or {}
    base_score = base_review.get("scores", {}).get("overall", 0)
    log(f"baseline: current Rollwise {base_score}/10, reused from yesterday's scoring (no new cost)")
    # A restart carries the spend so far, so the $3 cap covers the whole experiment.
    prior = {arm: Decimal(os.environ.get(f"LEAD_PRIOR_{arm.upper()}", "0")) for arm in ARMS}
    judge.spent = sum(prior.values(), Decimal("0"))
    states = {arm: {"best_score": base_score, "best_snapshot": {}, "best_review": base_review, "best_shots": BASELINE,
                    "spent": prior[arm], "attempts": 0, "done": False, "history": [], "note": None}
              for arm in ARMS}
    log(f"spend carried over from earlier runs: ${judge.spent}")
    for arm, state in states.items():
        # LEAD_SEED_OPUS=<render dir> restarts an arm from a design an earlier run scored, as its best version.
        if seed := os.environ.get(f"LEAD_SEED_{arm.upper()}"):
            render = Path(seed)
            review = json.loads((render / "opus-score.json").read_text(encoding="utf-8"))["review"]
            files = render / "scored-files.json"
            if not files.exists():  # runs before scored-files.json existed saved the files as the lead wrote them
                files = render.parent / f"files-{render.name.split('-')[-1]}.json"
            state.update({"best_score": review["scores"]["overall"], "best_review": review, "best_shots": render,
                          "best_snapshot": json.loads(files.read_text(encoding="utf-8"))})
            state["concept"] = next((json.loads(p.read_text(encoding="utf-8")).get("review") or {}).get("concept")
                                    for p in sorted(render.parent.glob("lead-*.json"), reverse=True))
            log(f"[{arm}] starts from {render} ({state['best_score']}/10, dimensions {rank(review)[1]})")
    for cfg in ARMS.values():
        dl.restore(dl.WTS[cfg["wt"]], {})
    summary = {"baseline": base_score, "arms": states, "output": str(out)}
    try:
        step = 0
        while not all(state["done"] or state["attempts"] >= ARMS[arm]["attempts"] for arm, state in states.items()):
            arm = SCHEDULE[step % len(SCHEDULE)]
            step += 1
            state = states[arm]
            if state["done"] or state["attempts"] >= ARMS[arm]["attempts"]:
                continue
            attempt(arm, state, lead, judge, out)
            (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    finally:
        for arm, state in states.items():
            dl.restore(dl.WTS[ARMS[arm]["wt"]], state["best_snapshot"])
            if state["best_snapshot"]:
                best = out / f"arm-{arm}" / "best"
                best.mkdir(parents=True, exist_ok=True)
                for path, text in state["best_snapshot"].items():
                    if text is not None:
                        (best / Path(path).name).write_text(text, encoding="utf-8")
        summary["spent"] = str(judge.spent)
        (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        judge.db.dispose()
        log(f"done: spent ${judge.spent}; best Opus {states['opus']['best_score']} "
            f"(${states['opus']['spent']}), best Haiku {states['haiku']['best_score']} "
            f"(${states['haiku']['spent']}), baseline {base_score}")


if __name__ == "__main__":
    main()
