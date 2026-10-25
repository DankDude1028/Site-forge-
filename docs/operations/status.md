# Implementation and acceptance status

Updated 2026-10-24 for commit `dbbff826c5d54c646ab30d28d1c2c29470d2ec55`. **The 72-hour SQLite
fixture soak PASSED. Full MVP acceptance, production-like endurance and production launch remain
PENDING.** See [acceptance evidence](acceptance-evidence.md)
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
| Larger-budget and Ministral runs | MEASURED locally; unpublished; routes unchanged | 2026-10-21, v1.3, 8K context, 4,096 output tokens, one trial, concurrent fixture soak. The 1,024-token runs cut off **36/47** Qwen3.5-9B and **32/36** Gemma 12B QAT failures mid-reasoning. Reruns: Qwen3.5-9B **75/100** (13 cut-offs), Gemma 12B QAT **72/100** (23 cut-offs; coding 2/20, all runaway reasoning). New verified Q4_K_M downloads: Ministral 3 14B Instruct **75/100**, 2,266 successes/hour; Ministral 3 8B Instruct **62/100**, 2,695/hour (research 4/20). Gemma E4B at **32K** context: **86/100** (coding 19/20, content 14/15, research 14/20, no cut-offs), 662/hour, 4,721 MiB VRAM peak; it meets the primary/worker/coding/content floors. An earlier E4B 8K run, `1f131dac`, is **invalid**: LM Studio stopped after warmup and all 100 requests failed transport. No run qualifies QA; E4B fails only research. Raw results in ignored `runtime/bench-longbudget/` pending redaction. |
| E4B context memory | MEASURED, load only | LM Studio 0.4.26, q8_0 KV, full GPU: VRAM **4,322 MiB at 8K; 4,643 at 32K; 5,075 at 64K; 5,939 at 128K**. Free RAM with model loaded stayed **3.7–3.9 GiB**. No long-context quality was measured. |
| LM Studio host memory | MEASURED limitation | With full GPU placement and default load settings, LM Studio private memory rose **3.95 GiB** for Gemma E4B and **6.32 GiB** for Qwen3.5-9B (6,640 MiB VRAM), leaving under 2 GB free RAM. After the owner set per-model "Keep Model in Memory" off on LM Studio 0.4.26, `llama-server` launched with `--load-mode mmap` and no lock. E4B's free-RAM drop on load fell from **4.9 GB to 3.1 GB**, but its process still held **4.05 GiB private**. GPT-OSS 20B (9,523 MiB VRAM) left **0.2 GB** free RAM. The setting removes locked pages, not llama.cpp's own host allocations. |
| Native HTTP/WindowsWorker proof | PASSED, one bounded role | [Final recheck](evidence/native-agent-final.json), task `26ab3ce7-07bd-4fe2-8b79-e3df3044f156`, completed at **20:40:00.550558 UTC** on source `992735c`: E4B 8K native scoring/proposal/finish, **66.00** from authored inputs, workflow proposed with `scheduled: false`, **9 artifact hashes verified**. Follow-up source difference: Node test only. [Earlier SDK failures](evidence/native-agent.json) remain preserved. Seven-role autonomy is not proven. |
| 72-hour SQLite fixture soak | PASSED, fixture scope | Run `0dc2d6a6-8587-4f14-b595-c1d4106128dc` ran under Task Scheduler (`pythonw.exe`) on the source hash below, from **2026-10-21 21:32:22 UTC** to **2026-10-24 21:41:04 UTC**, and reported `fixture_soak_passed`. Results: **72.000 observed hours** with 518 unobserved stall seconds excluded; **1,296 tasks over 432 cycles**; **2,654/2,654 injected faults recovered**; **0** failures, unauthorized effects, duplicate effects, lost tasks and external calls. Maximum queue latency was **8.571 s** (limit 30) and RSS growth **−22.3 MiB** (limit 256). [Final report](evidence/endurance-final.json). The scheduled task was removed afterwards. Prior run `30d00b7f` was **killed with its launching agent session** after **1,390.219 active seconds/9 tasks**, with no `finished_at` written; see [history](evidence/endurance-history.json). No interrupted time carries forward. |
| Production-like endurance | PENDING | PostgreSQL/service/provider faults, six-hour worker disconnection, real network outage and OS crash acceptance remain separate from SQLite fixtures/process drills. |
| Protected Netlify/live release | BLOCKED; defaults disabled | Netlify requires reauthentication and a protected target is absent. No live Netlify mutation or hosted protection/health/rollback proof occurred. [Releases](releases.md), [bundle transfer](bundles.md). |
| Production operations/economics | PENDING | Authorized costs, hosting/TLS/roles/secrets/egress/monitoring, applied protections, production backups, live metrics, demand and realized revenue remain unverified. |
| Opus 5.5 advisor | TWO LIVE REVIEWS MEASURED; not benchmark-qualified | Owner-approved per review, worst-case reservation against $3/day and $15/month owner caps, sent once, booked at measured cost. 12 advisor tests and 1 reconciliation test pass with no network. First live site review on 2026-10-22, approval `341bb922`: served by `claude-opus-5-5` with no fallback, `end_turn`, schema-valid JSON, **7,356 input / 3,435 output tokens, $0.098124 booked against a $0.833299 authorization**. A follow-up review of the revised template, approval `8e576e6d`, used 10,967 input and 3,266 output tokens and booked **$0.109188** against $0.887682. Month-to-date booked spend is **$0.207312** with zero reserved. Two reviews are not a quality benchmark. [Advisor](advisor.md). |
| E4B × Opus collaboration | MEASURED experiment; local harness, not a SiteForge feature | 2026-10-25: Gemma E4B (32K, local) drafted Rollwise edits as JSON find/replace operations limited to three files. Deterministic gates blocked new scripts, URLs, network or storage access, HTML injection, renamed contract text and loosened input limits. Every draft then had to pass TypeScript, unit tests with real builds, Edge desktop/mobile axe checks and the inspector before an owner-pre-approved Opus review. Unmediated runs produced no passing draft: E4B renamed the tested button, made 18 edits, and changed `min` to 0 when asked to *test* zero. With Director-resolved conflicts and line-level failure feedback, each round passed on the second attempt. Opus verdicts: needs_changes ($0.130868; the tests passed but the caption was never populated), needs_changes ($0.148592; a mobile overlap regression), ready ($0.116368). Total **$0.395828**. Opus's "ready" missed a desktop regression that pushed the calculator below the headline; the operator restored it while keeping E4B's caption, hint and reading key. |
| Rollwise template revision | PASSED locally; Opus re-review READY pending launch details; unpublished | Fixes the 2026-10-22 Opus review: an internal research note removed from the privacy page; host/contact details required for production builds, with preview placeholders; live recalculation with per-field errors, an "already have enough" state and a debounced screen-reader summary; 16px body and 15px secondary text; decorative glyphs removed; consistent "extra allowance" wording; a styled privacy page. Print-shop redesign with bundled OFL fonts and a roll-strip result. Checks: 10 Node tests including both real Astro build modes and a failing production build without details; TypeScript; 4 Playwright desktop/mobile checks on installed Edge (Chromium absent locally) with zero axe WCAG 2.1 AA violations and no outside requests; Python 526 passed, 6 skipped. The follow-up Opus review resolved every checkable prior finding and rated the design `distinct`. Remaining minor items: a caption for the partially spare last roll, the redundant Calculate button, and empty desktop space. This merge changes the soak's code fingerprint. |

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
or scheduled follow-up was installed; the soak runner's scheduled task was removed after the run. The
72-hour fixture soak **PASSED**. Full-MVP, production-like endurance and production acceptance remain **PENDING**.
