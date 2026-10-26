# Design lab

Experiments that tried to push the Rollwise template from a correct page to a visually striking
one, run 2026-10-24 to 2026-10-26. This is not a SiteForge feature: nothing in the supervisor or
worker calls it, CI does not check it, and its paths fit one PC. Results, costs and limits are in
[status](../../docs/operations/status.md), in the rows "E4B × Opus collaboration", "Local-model
design loop" and "API design lead".

| Experiment | Script | Result |
| --- | --- | --- |
| Gemma E4B drafts edits, Opus reviews | `collab.py` | Each round passed the checks on the second try, after a director resolved conflicts and gave line-level feedback |
| Local models design, Opus scores 1–10 | `design_loop.py` | 20 designs; none above the 6/10 baseline; $1.35 of scoring |
| Opus 5.5 or Haiku 5.5 leads, Opus scores | `lead_loop.py` | Opus reached 7/10; Haiku held 6–7; $2.89 in total |

## Files

- `design_loop.py`: the local-model loop. It also holds the shared parts that the other scripts import:
  - the gates and the full checks;
  - the mechanical auto-fixes;
  - screenshot capture;
  - the Opus judge (`Judge`).
- `design_briefs.py`: the briefs and constraints for its two arms.
- `cc_run.py`: runs the bundled Claude Code CLI against LM Studio for the local model. It uses file tools only, an environment with no secrets, and a config folder under `runtime/cc-config/`.
- `collab.py` and `collab_capture.cjs`: the E4B × Opus collaboration rounds.
- `lead_loop.py`: Opus vs Haiku as lead designer, through the advisor's `design_lead` kind.
- `lead_dryrun.py`: offline checks of `lead_loop.py`. It makes no API call and stops at the approval guard.
- `score_pending.py`: checks, renders and scores a lead's files that a stopped run left unscored.
- `review_checks.py`: runs the full checks on worktree b with no auto-fixes.
- `design_capture.cjs`, `design_overflow.cjs`, `css_check.cjs`: the screenshots and visual lint, the finder for elements that stick out past the screen, and the CSS syntax check.
- `logs/`: the run logs, with the Windows profile path replaced by `%USERPROFILE%`.

Each run writes its records, screenshots, scores and best files to an ignored `runtime/` folder
(`design-*`, `collab-*`, `lead-*`). Each advisor request and result is kept in `runtime/advisor/`.

## Safety model

- **Model output is untrusted.** A local model edits only a disposable git worktree under `runtime/worktrees/`. It has file tools and nothing else: no shell, no web access and no secrets.
- **Deterministic gates run before anything else.** Every change must pass:
  - allowed paths only; the locked `Calculator.astro` and `base.css` are refused;
  - forbidden patterns: scripts, external URLs, network calls, browser storage, HTML injection and event handlers;
  - a build-time import rule.
- **The checks come next:** TypeScript, unit tests, the Astro build, Edge Playwright with axe on desktop and phone, and the site-factory inspector.
- **Claude calls go through `siteforge.advisor`:**
  - each one is approved by its exact request hash;
  - its worst case is reserved against the $3/day and $15/month caps;
  - it is sent once and booked at its measured cost.

## Paid runs need a fresh owner approval

`design_loop.py`, `collab.py` and `lead_loop.py` refuse to call Claude unless `DESIGN_LAB_APPROVAL` holds
the owner's exact approval for that batch, quoted from chat. The advisor must also be enabled, with
`ANTHROPIC_API_KEY`, in the ignored `.env`. The approvals that past runs used are spent:

| Batch | Owner approval in chat | Spent |
| --- | --- | --- |
| Collaboration rounds | "Up to 3 rounds (Recommended)" | recorded in status |
| Local design loop scoring | "Up to $2 (Recommended)" | $1.352696 |
| Opus vs Haiku design lead | "Both head-to-head, up to $3 (Recommended)" | $2.887029 |

## Known defects and limits

- **The contrast auto-fix trusts a single axe frame.** It greyed the 7/10 design's hero button because axe measured the button mid fade-in. The template test now waits for animations on `review/rollwise-opus-design`, but `auto_fix` itself is unchanged.
- **Paths are tied to one PC.** Node lives under `%USERPROFILE%\.cache\codex-runtimes\`, LM Studio is driven by the `lms` CLI, and the model keys, worktree names, ports 4393–4395, `SITE_ID` (from the local database) and the baseline folder in `runtime/` are all fixed.
- **It needs worktrees** at `runtime/worktrees/rollwise-design-a` and `-b`, with `node_modules` installed, on a branch that has the locked calculator component.
- **The results are thin.** Each comes from one subject and single trials, and the score variance is unmeasured. The scores come from one model judging screenshots.

Offline check, from the repository root:

```powershell
.\.venv\Scripts\python.exe experiments\design-lab\lead_dryrun.py
```
