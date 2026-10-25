# Implementation and acceptance status

Updated 2026-10-21 for commit `6ef15a0cf86cebd7eeb50d0801389825bb490fca`. **Full MVP, 72-hour
acceptance and production launch remain PENDING.** See [acceptance evidence](acceptance-evidence.md)
and [runbook](runbook.md). Public JSON files are point-in-time snapshots, not live monitoring.

## Current evidence

| Gate | Status | Evidence and remaining work |
| --- | --- | --- |
| Local checks | PASSED, stated scopes | Whole local baseline: **525 passed, 5 skipped**, before the final stale-write fence. After that fix, **64 affected release/provider/client tests** passed in **48.02 seconds**. Ruff and Windows/Linux mypy across 28 files passed. These are separate runs, not an inferred whole-suite count. |
| Current hosted CI | PASSED at `6ef15a0c` | [Run 39672699385](https://github.com/DankDude1028/Site-forge-/actions/runs/39672699385): all three jobs passed; Python **526 passed, 6 skipped, 1 warning in 63.40 seconds**, 28-file mypy; Docker **1 test in 1.18 seconds**; dashboard **2 Node/3 Playwright**; utility **8 Node/4 Playwright**, both actual Astro build modes, type/build/axe/audit/secret/SBOM checks. [CI evidence](evidence/ci.json), artifact `12380033711`, contains 23 selected JUnit cases. |
| Preceding hosted CI | PARTIAL; web failure fixed | At `992735c`, [run 39672220415](https://github.com/DankDude1028/Site-forge-/actions/runs/39672220415) passed Python **526 tests, 6 skipped, 1 warning** in **81.40 seconds**, 28-file mypy, audits/secret/SBOM checks, Docker **1 test in 1.29 seconds**, and dashboard **2 Node/3 Playwright**. Web failed on an `EXDEV` temporary-output rename. Commit `6ef15a0c` fixes that Astro test's filesystem choice; **8 Node tests** and both actual builds passed locally, with production/preview **4 Playwright tests each** already passed. The earlier run is not wholly green. |
| PostgreSQL/restore | PASSED, bounded CI drills | Actual fixtures cover concurrent leasing, application dump/restore and authenticated encrypted backup/restore with resumed checkpoint work. Production schedules, off-host storage, key recovery and measured RPO/RTO remain pending. [Backups](backups.md). |
| Actual process recovery | PASSED, 22.437-second SQLite drill | Run `0553d540-0470-4b1e-a662-d7f837d8c40d` killed owned worker/supervisor processes and recovered lease/checkpoint work. [Evidence](evidence/process-recovery.json), [scope](runtime-drill.md). No PostgreSQL/model/provider calls; not a 72-hour test. |
| Local GPU comparison/routes | PASSED, conditional measured scope | Complete v1.3 strict passes: GPT-OSS MXFP4 4K **87/100**; E4B Q4_K_M 4K/8K **81/100 each**; Gemma 12B QAT Q4_0 4K **64/100**; Qwen3.5-9B Q4_K_M 4K **53/100**. One trial, 1,024 output tokens, parallelism 1. [Routes](../../benchmarks/results/routing.json): primary/worker E4B 8K; coding/research/content GPT-OSS 4K; QA unqualified; cloud disabled at $0. |
| Native HTTP/WindowsWorker proof | PASSED, one bounded role | [Final recheck](evidence/native-agent-final.json), task `26ab3ce7-07bd-4fe2-8b79-e3df3044f156`, completed at **20:40:00.550558 UTC** on source `992735c`: E4B 8K native scoring/proposal/finish, **66.00** from authored inputs, workflow proposed with `scheduled: false`, **9 artifact hashes verified**. Follow-up source difference: Node test only. [Earlier SDK failures](evidence/native-agent.json) remain preserved. Seven-role autonomy is not proven. |
| 72-hour SQLite fixture soak | RUNNING at snapshot; acceptance PENDING | Run `30d00b7f-dc31-4571-b54f-5a0d2c432a26` started **20:43:11.997084 UTC** on the source hash below. [Start snapshot](evidence/endurance-start.json): 3 tasks, no failures, threshold not met. No interrupted time carries forward. |
| Production-like endurance | PENDING | PostgreSQL/service/provider faults, six-hour worker disconnection, real network outage and OS crash acceptance remain separate from SQLite fixtures/process drills. |
| Protected Netlify/live release | BLOCKED; defaults disabled | Netlify requires reauthentication and a protected target is absent. No live Netlify mutation or hosted protection/health/rollback proof occurred. [Releases](releases.md), [bundle transfer](bundles.md). |
| Production operations/economics | PENDING | Authorized costs, hosting/TLS/roles/secrets/egress/monitoring, applied protections, production backups, live metrics, demand and realized revenue remain unverified. |
| Rollwise template revision | PASSED locally; not reviewed again; unpublished | Fixes the 2026-10-22 Opus review: an internal research note removed from the privacy page; host/contact details required for production builds, with preview placeholders; live recalculation with per-field errors, an "already have enough" state and a debounced screen-reader summary; 16px body and 15px secondary text; decorative glyphs removed; consistent "extra allowance" wording; a styled privacy page. Print-shop redesign with bundled OFL fonts and a roll-strip result. Checks: 10 Node tests including both real Astro build modes and a failing production build without details; TypeScript; 4 Playwright desktop/mobile checks on installed Edge (Chromium absent locally) with zero axe WCAG 2.1 AA violations and no outside requests; Python 526 passed, 6 skipped. The soak's template fingerprint changes when this merges. |

## Implemented scope and limits

Implemented and tested: tenant-scoped API/queue; outbound Windows worker; seven bounded internal
agent roles; utility template/dashboard; approvals/budgets/receipts; UTC deadlines; typed transient
retries; cache/source revalidation; inference backpressure; atomic Windows persistence; pagination
and aggregate totals; weekly internal reviews; persistent 50/80/100% budget notices. Notices create
internal records without sending external messages.

The [release path](releases.md) now supports sealed authenticated bundle transfer and a separate
indexable production candidate linked to the exact ready private normal preview and commit/tree.
Owner approval binds site, cost and bytes. Automatic health rollback supports only a preapproved,
previously healthy SiteForge target with known **zero incremental cost**. Durable claims prevent
repeat dispatch; reconciliation performs external reads only. The kill-switch exception permits
only that exact emergency target. Concurrency fixes preserve claims across stale observations and
independently fence later releases; organization-first locking covers the reviewed PostgreSQL paths.
Provider tests use controlled transports.

Bundle provenance is **authenticated uploader claims**, with owner review of exact hashes;
independent GitHub OIDC/build attestation is not implemented. Broad arbitrary feature development,
autonomous source discovery and live provider fetchers remain outside the bounded executor, which
uses supplied evidence, fixed tools/templates and approved sandbox recipes.

## Evidence identities and history

Fixture v1.3.0 SHA-256:
`ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.
All 100 contracts were independently reviewed: 25 tool/20 research/20 coding/15 content/15 workflow/
5 efficiency. Versions 1.0–1.2 remain unqualified exploratory evidence. Routing requires complete
v1.3 runs, each relevant category's success/sample floor and matching already-loaded settings;
it never auto-loads. E4B 16K/32K passed five short efficiency tasks each, **partial suites only**.
Long-context retrieval, unavailable quantizations and larger configurations remain unmeasured;
timing is conditional and content scores require human editorial review.

Benchmark exports are frozen and byte-verified against worktree, Git blobs and the
[redaction manifest](../../benchmarks/results/redaction-manifest.json); private originals and exact
task-response hashes are retained. Earlier native UTC/path/prompt defects, the losing-guard stale
health race, the stale-observation release-fence race and hosted `EXDEV` build-test failure remain
in evidence/tests/history. Fixes do not erase those failures.

Current soak implementation SHA-256:
`5c5e92decd949cce6f959f60fcedeb7f35b8c65d6abcdad9404351b8c85dae82`.
Local report: `runtime/endurance-final-source/report.json`. [Separate smoke](evidence/smoke.json)
passed **9 tasks in 10.813 seconds** and adds no soak time. [History](evidence/endurance-history.json)
retains interrupted runs including `89f64a27` (**169.172 seconds**), `e2638a4c` (**75.719 seconds**)
and `53eac094` (**441.375 seconds**). **No historical time/tasks carry forward.** No notification
or scheduled follow-up was installed. Actual 72-hour/full-MVP/production acceptance remains **PENDING**.
