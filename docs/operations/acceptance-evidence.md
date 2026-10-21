# Acceptance evidence and limits

Reviewed 2026-10-21 for commit `6ef15a0cf86cebd7eeb50d0801389825bb490fca`.
[Status](status.md) tracks acceptance; [runbook](runbook.md) describes procedures, not execution
proof. **Full MVP, production launch and 72-hour acceptance remain PENDING.** Public JSON evidence
is a captured observation, not live telemetry.

## Verification and CI

The whole local baseline passed **525 tests, 5 skipped** before the final stale-write release fence.
Afterward **64 affected release/provider/client tests** passed in **48.02 seconds**; Ruff and
Windows/Linux mypy across 28 application files passed. These scopes do not imply a new whole-suite count.

Current [CI run 39672699385](https://github.com/DankDude1028/Site-forge-/actions/runs/39672699385)
for `6ef15a0c` is **green: all three jobs passed**. [CI evidence](evidence/ci.json), artifact
`12380033711`, records 23 selected JUnit cases and these results:

| Scope | Observed result |
| --- | --- |
| Python/controls | **526 passed, 6 skipped, 1 warning in 63.40 seconds**; 28-file mypy, lint, locked audits, secret scan and SBOM checks passed. Skips are not passes. |
| PostgreSQL | Actual concurrent leasing/audit **1.057 seconds**; encrypted backup/restore **1.082 seconds**; application restore **1.175 seconds**. |
| Linux Docker | Actual digest-pinned sandbox boundary: **1 passed in 1.18 seconds**. Windows Docker/resource stress remains separate. |
| Dashboard | **2 Node/3 Playwright** tests and build/accessibility checks passed. |
| Utility build | **8 Node/4 Playwright**, both actual Astro build modes, type/build/axe and audit checks passed. Separate local production/preview runs had passed **4 Playwright tests each**. |

The preceding [run 39672220415](https://github.com/DankDude1028/Site-forge-/actions/runs/39672220415)
at `992735c` passed Python (526/6/1 in 81.40 seconds), Docker and dashboard but failed web on an
`EXDEV` temporary-output rename in the new Astro test. Commit `6ef15a0c` moved that test's temporary
output onto the same filesystem; the current hosted run confirms the fix. [Older green evidence](evidence/ci-4970d4f.json)
also remains source-bound history. The encrypted PostgreSQL drill authenticates the dump before creating an isolated
target, compares all application tables and resumes checkpoint/lease work. The application restore
drill also checks receipt replay, migration `0001` and audit/approval guards. These fixture drills
do not establish production schedules, off-host custody, key recovery or measured RPO/RTO.
Scans/tests do not constitute a full security audit.

## Implemented controls and release scope

- UTC-aware persistence preserves deadline instants; file-SQLite HTTP leasing and worker completion
  cover UTC/non-UTC deadlines. Naive incoming deadlines are rejected; migration DDL is unchanged.
- Typed transient errors, deadline precedence, pre-lease inference backpressure and checkpoint
  revalidation prevent blocked/native results from bypassing policy/source/receipt checks.
- Atomic replacement handles bounded Windows sharing failures; authenticated pagination has
  aggregate totals. Weekly drafts and persistent 50/80/100% budget notices include reserved costs
  and do not send external messages.
- [Encrypted backups](backups.md) use streamed AES-GCM authentication, scoped retention and new
  disposable restore targets. Credentials remain out of arguments/logs; inherited libpq redirection
  is rejected and admin/client phases are bounded.
- [Bundle transfer](bundles.md) seals bounded static bytes with authenticated uploader, site, commit
  and tree claims. A separate indexable production candidate links the exact ready private normal
  preview, site/commit and source tree. Promotion rejects ordinary noindex preview bytes. Provenance
  is **authenticated uploader claims, not independent GitHub OIDC/build attestation**; owners review hashes.
- [Releases](releases.md) bind exact owner approval, known cost, bytes and durable provider receipts.
  Reconciliation is externally read-only; same-hash upload recovery is bounded. Automatic rollback
  supports only a preapproved, previously healthy SiteForge target with known **zero incremental
  cost**, actor/approval/expiry/scope checks and a durable at-most-once claim. The kill-switch exception
  permits only that bound emergency target.

Two rollback concurrency defects were fixed before this freeze: a losing guard could mistake a
peer's completed restore for foreign drift; a stale health observation could overwrite active
rollback status and weaken the next-release fence. Regressions force both interleavings. Ordinary
writes now preserve claim state; both claim sites independently fence unresolved recovery until
exact provider/index health proof exists. Organization-first locking aligns storage/audit and claim
paths for PostgreSQL. Fault tests cover lost acknowledgments, death before/after effects, foreign
publishers and no blind redispatch. These provider transports are controlled fixtures, not live proof.

Netlify requires reauthentication and a protected target is absent. Releases default disabled.
No cloud resource, live Netlify mutation, external message or realized revenue was produced by these
operations. Hosted protection/health, authorized costs and production acceptance remain gates.

## Actual process and native-agent evidence

The [process-recovery snapshot](evidence/process-recovery.json), run
`0553d540-0470-4b1e-a662-d7f837d8c40d`, passed in **22.437 seconds**. It killed actual owned
supervisor/worker processes, observed an HTTP outage, restarted the same SQLite state, recovered
the checkpoint after real lease expiry and completed research/developer/QA fixture tasks. Stale
completion received HTTP 409. It made zero model/provider calls and predates the final release
implementation. [Runtime-drill scope](runtime-drill.md); local report
`runtime/actual-process-drill-final/report.json`. This is not PostgreSQL or 72-hour proof.

The [final native recheck](evidence/native-agent-final.json), task
`26ab3ce7-07bd-4fe2-8b79-e3df3044f156`, completed at **2026-10-21 20:40:00.550558 UTC** through
actual authenticated HTTP, WindowsWorker and measured E4B Q4_K_M 8K native tools. Scoring,
workflow proposal and finish produced **66.00** from supplied inputs, a proposed research/developer/
quality workflow with **`scheduled: false`**, and **9 SHA256-verified artifacts**. Source and loaded
model settings were unchanged during execution. Source was `992735c`, physical implementation
SHA-256 `308b1a56e12e4436d43a4bcbd416c518dfb698b5def7a25949b6921183f2eddd`;
the follow-up `6ef15a0c` difference is the Node build-test file only.

[Original native evidence](evidence/native-agent.json) retains the first failure before inference
from SQLite deadline timezone loss, the second Windows path/prerequisite-order failure, and the
earlier successful retry. These were application SDK defects, not benchmark model grades. The
final proof has no external/paid effects and proves one bounded portfolio proposal, not verified
demand, scheduled execution or unattended seven-role autonomy.

## Local model qualification and export integrity

Target inventory: Windows, RTX 4070 Ti with 12,282 MiB VRAM, NVIDIA driver 617.42 and approximately
16.98 GB RAM. Initial free RAM was about 330,860 KiB, not a per-run claim. LM Studio stays on
loopback; inference is serialized.

Fixture **v1.3.0**, exact UTF-8 SHA-256
`ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`,
was independently reviewed across 100 tasks: 25 tool/20 research/20 coding/15 content/15 workflow/
5 efficiency. Explicit canonical/type/content/native-provenance contracts were checked against
80 compliant noncoding references and 20 independent coding solutions without model calls.

Completed actual suites use **one trial/task, 1,024 maximum output tokens and verified parallelism 1**:

| Candidate | Quantization/context | Raw strict passes |
| --- | --- | ---: |
| Google Gemma E4B | Q4_K_M / 4K | 81/100 |
| Google Gemma E4B | Q4_K_M / 8K | 81/100 |
| Qwen3.5-9B | Q4_K_M / 4K | 53/100 |
| Google Gemma 12B QAT | Q4_0 / 4K | 64/100 |
| GPT-OSS-20B | MXFP4 / 4K | 87/100 |

[Routes](../../benchmarks/results/routing.json): **E4B 8K primary/worker**; **GPT-OSS 4K coding/
research/content**; QA unqualified; cloud disabled at $0. Every role needs complete v1.3 evidence,
each relevant category's sample/success floor and matching already-loaded source/quant/context/
parallel settings. No winner is auto-loaded. E4B 16K/32K each passed **5/5 short efficiency tasks**,
partial suites rather than long-context retrieval/quality proof. Larger models and unavailable
quantizations remain unmeasured. [Report](../../benchmarks/results/report.md),
[raw records](../../benchmarks/results/results.json), [filtered chart](../../benchmarks/results/model_comparison.html).

Timing remains conditional; GPU-only energy estimates exclude whole-PC/hosting overhead. Scores
do not prove unrestricted development, demand or originality. Content needs editorial human review;
coding uses a bounded interpreter and research uses supplied synthetic sources. Versions 1.0–1.2
remain unchanged **unqualified exploratory evidence** because of material contract defects; they
cannot route production work.

Public exports redact 111 incidental metadata fields, retaining private originals. Read-only review
verified **12 original/export files**, worktree/Git hashes and **1,188 rows across 16 runs** with
unchanged protected prompts/responses/native arguments/grades and verified prompt/response hashes.
All 14 tracked export blobs had zero actual profile/hostname matches and zero credential-pattern
hits in the stated scan. The [redaction manifest](../../benchmarks/results/redaction-manifest.json)
documents that boundary; a pattern scan does not guarantee every possible secret form is absent.

## Endurance and remaining acceptance

The [start snapshot](evidence/endurance-start.json) records run
`30d00b7f-dc31-4571-b54f-5a0d2c432a26`, started **2026-10-21 20:43:11.997084 UTC**, on commit
`6ef15a0c`, implementation SHA-256
`5c5e92decd949cce6f959f60fcedeb7f35b8c65d6abcdad9404351b8c85dae82`.
At capture it was **running**, with **3 tasks, no failures and 35.610 active seconds**. This is a
SQLite fixture pipeline with injected failures, not service/provider fault injection. Local report:
`runtime/endurance-final-source/report.json`. **Actual 72-hour result: PENDING.**

[Separate smoke](evidence/smoke.json), run `14213299-86be-4f82-8122-7e0f5006cb29`, passed **9 tasks
in 10.813 seconds**. [History](evidence/endurance-history.json) preserves interrupted runs including
`89f64a27` (169.172 seconds), `e2638a4c` (75.719 seconds) and `53eac094` (441.375 seconds).
**No smoke, interrupted time or tasks carry forward.** No notification promise or scheduled
follow-up task has been installed.

Fixture acceptance needs **259,200 observed active seconds and at least 900 tasks**, zero unauthorized/
duplicate/lost effects, all injected faults recovered, RSS growth at most 256 MiB, queue latency at
most 30 seconds and heartbeat gaps at most 15 seconds against unchanged sources. Sleep/offline
gaps do not count. Production-like acceptance separately needs PostgreSQL/service/provider faults,
six-hour disconnection and real network/OS outage recovery.

Remaining gates: protected hosted staging; authorized costs; TLS/roles/secrets/egress/monitoring;
applied protections; scheduled encrypted off-host backups/key recovery/measured RPO/RTO; and live
reconciled metrics. Independent OIDC/build attestation, broad arbitrary feature development/source
discovery and live provider fetchers are not implemented by the bounded executor. Separate production
SEO/linkage, authenticated bundle transfer and preapproved bounded automatic rollback are implemented
and tested; live operation remains unproven. Full MVP and production acceptance remain **PENDING**.
