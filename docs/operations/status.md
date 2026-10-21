# Implementation and acceptance status

Updated 2026-10-21, with evidence inspected at 18:28 UTC. A working local fixture pipeline and
passing hosted checks are available. Full MVP acceptance and production launch are **not complete**.
See [acceptance evidence](acceptance-evidence.md) for exact scopes and limitations, and the
[runbook](runbook.md) for operator recovery procedures.

## Verified baseline

- The [repository](https://github.com/DankDude1028/Site-forge-) was empty when cloned for this work.
- The accessible target PC is Windows with an RTX 4070 Ti, 12,282 MiB VRAM and NVIDIA driver 617.42.
  Installed RAM is 16,984,162,304 bytes; initial free RAM was approximately 330,860 KiB. This is a
  starting snapshot, not a claim about available memory during every benchmark.
- LM Studio CLI commit was `69d945a`. Its local service was started on port 1234. Inventory showed
  six installed LLM candidates and one embedding model, totaling 65.53 GB reported by LM Studio.
- Gemma E4B's initial 4K/full-GPU load preflight took 12.87 seconds and reported 4.97 GiB.
  Loading a model does not establish its task quality or a routing winner.

## Acceptance gates

PASSED below means the stated bounded check passed. It does not imply production acceptance.

| Gate | Status | Evidence and remaining work |
| --- | --- | --- |
| Hosted implementation checks | PASSED at `a206bb2` | [CI run 39650123014](https://github.com/DankDude1028/Site-forge-/actions/runs/39650123014): Python 196 passed, 3 skipped; lint, type checks, dependency audits, builds and browser checks passed. Changes after this commit need their own final run. |
| PostgreSQL concurrent leasing and audit guard | PASSED, bounded integration | PostgreSQL 16.15: 8 concurrent workers completed 20 unique tasks without duplicate claims; audit truncation was rejected. This is not long-duration PostgreSQL recovery evidence. |
| Real Docker sandbox boundary | PASSED on hosted Linux | Actual digest-pinned Python container denied network and writes, ran as non-root with no effective capabilities, and received no fixture host credential; 1 integration test passed. Windows Docker and resource-exhaustion tests remain pending. |
| Migration and application security controls | PASSED, tested scope | Alembic/schema checks, tenant/identity fences, capability checks, immutable audit guards, approval binding, budget reservations and receipt replay tests passed. This is not a full security audit. |
| Actual GPU comparison and role routing | IN PROGRESS | [Generated benchmark report](../../benchmarks/results/report.md) and raw records are authoritative. Completed fixture v1.2 4K suites so far: Gemma E4B 71/100 (parallelism 1), Qwen3.5-9B 41/100 (parallelism 1), Gemma 12B QAT 46/100 (parallelism 4, ineligible for automatic routing). GPT-OSS was still running; these scores are a dated snapshot, not the final model/routing table. |
| 72-hour SQLite fixture soak | PENDING, INTERRUPTED | Historical `runtime/endurance/report.json`, run `4c1ec950-2bc9-4ec9-9ffa-708465746539`: interrupted for a source update at 18:27:59 UTC, after 2,234.110 active seconds, 4 cycles and 12 completed tasks. It is not an accepted run. Start a new run against final sources; required: 259,200 active seconds, at least 900 tasks, and all thresholds. |
| Full production-like endurance | PENDING | A fixture soak cannot close real PostgreSQL/service/OS/network outage, long worker-disconnect, hosted-preview or provider reconciliation acceptance. Run and preserve these separately. |
| Protected Netlify preview | BLOCKED | Netlify connection needs reauthentication and no protected target site is configured. No protected deployment receipt, verified access control or hosted health result exists. Local noindex/build checks do not satisfy this gate. |
| Cloud hosting and authorized budget | PENDING | No cloud infrastructure was provisioned. TLS, secrets, least-privilege roles, quotas, monitoring and an owner-authorized operating budget require actual configuration and verification. |
| Backups and restore | PENDING | RPO/RTO and restore procedures are documented targets. A planned isolated PostgreSQL fixture dump/restore drill requires its own final CI evidence; scheduled encrypted production backups, retention, key management and a production restore drill remain pending even if that test passes. |
| Branch protection and deployment access | PENDING | A branch-protection configuration is prepared, not applied. Verify required reviews/checks and protected deployment environments with the owner. |
| Live provider metrics and economics | PENDING | Imported/fixture ledger and reconciliation logic do not establish connected production analytics, realized revenue, complete provider costs or business demand. |
| Production launch | NOT ENABLED | The production workflow deliberately fails closed. Exact owner approval, provider effect reconciliation, protected staging, health checks and a tested fix-forward release must be connected and accepted before publication. |

## Implemented controls versus operational acceptance

The API, durable queue, outbound Windows worker, seven typed agent roles, local utility template,
dashboard, policy/budget engine, migrations and bounded provider/sandbox adapters have executable
implementations. Fixture mode produces research, site and quality artifacts. Local model proposal
mode and bounded internal tool execution are separate modes; the latter requires qualified measured
routing and an already-loaded matching model. Their presence does not prove a successful unattended
real-model portfolio run or permit production/provider effects.

External actions remain disconnected from the autonomous agent loop. Secure provider configuration,
approval consumption, durable provider receipts, unknown-outcome reconciliation and health verification
must be exercised together before claiming an end-to-end live workflow. No paid resource, public site,
outreach, revenue or production deployment is implied by the local artifacts or CI checks.

Benchmark and endurance reports change during execution. Preserve the run IDs, settings, raw records
and timestamps when accepting them; do not combine smoke runs or infer missing measurements. The
latest final CI and any isolated restore-drill evidence must be recorded before closing another gate.
