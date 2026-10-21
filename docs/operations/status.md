# Implementation and acceptance status

Updated 2026-10-21, with evidence inspected at 18:37 UTC. A working local fixture pipeline and
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
| Hosted implementation checks | PASSED at `a71c7e8` | [CI run 39653684353](https://github.com/DankDude1028/Site-forge-/actions/runs/39653684353): Python 266 passed, 3 skipped; lint, type checks, dependency audits, builds and browser checks passed. Changes after this commit, including fixture v1.3 qualification, need their own final run. |
| PostgreSQL concurrent leasing and audit guard | PASSED, bounded integration | PostgreSQL 16.15: 8 concurrent workers completed 20 unique tasks without duplicate claims; audit truncation was rejected. This is not long-duration PostgreSQL recovery evidence. |
| Real Docker sandbox boundary | PASSED on hosted Linux | Actual digest-pinned Python container denied network and writes, ran as non-root with no effective capabilities, and received no fixture host credential; 1 integration test passed. Windows Docker and resource-exhaustion tests remain pending. |
| Migration and application security controls | PASSED, tested scope | Alembic/schema checks, tenant/identity fences, capability checks, immutable audit guards, approval binding, budget reservations and receipt replay tests passed. This is not a full security audit. |
| Actual GPU comparison and role routing | PENDING corrected v1.3 runs | [Generated benchmark report](../../benchmarks/results/report.md) and raw records preserve actual measurements. Fixture v1.2 had prompt/grader contract defects, including hidden exact workflow action labels; every previous strict aggregate is exploratory and cannot establish final quality ranks or automatic qualified routes. Planned corrected suites: E4B 8K, GPT-OSS 4K, Qwen3.5-9B 4K and Gemma 12B QAT 4K, each verified parallelism 1. Final counts and qualification remain pending. |
| 72-hour SQLite fixture soak | PENDING, source freeze required | Historical runs `4c1ec950-2bc9-4ec9-9ffa-708465746539` and `d5dadf17-189c-4a1b-8df7-a3d2d77de910` were interrupted for source updates. Neither is accepted or contributes elapsed time to a replacement. Start a fresh root/report against frozen final sources; required: 259,200 active seconds, at least 900 tasks, matching source hash and all thresholds. |
| Full production-like endurance | PENDING | A fixture soak cannot close real PostgreSQL/service/OS/network outage, long worker-disconnect, hosted-preview or provider reconciliation acceptance. Run and preserve these separately. |
| Protected Netlify preview | BLOCKED | Netlify connection needs reauthentication and no protected target site is configured. No protected deployment receipt, verified access control or hosted health result exists. Local noindex/build checks do not satisfy this gate. |
| Cloud hosting and authorized budget | PENDING | No cloud infrastructure was provisioned. TLS, secrets, least-privilege roles, quotas, monitoring and an owner-authorized operating budget require actual configuration and verification. |
| Isolated PostgreSQL fixture dump/restore | PASSED, bounded integration | Latest hosted JUnit confirms real custom-format `pg_dump`/`pg_restore`, row equality, checkpoint/authorization replay, resumed completion, migration version and restored audit/approval guards. No provider was contacted. |
| Production backups and restore | PENDING | Scheduled encrypted backups, protected storage/keys, retention, observed backup success and a production restore drill with measured RPO/RTO remain pending. The isolated CI fixture test does not close this gate. |
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

Benchmark and endurance reports change during execution. Preserve run IDs, fixture/source hashes,
settings, raw records and timestamps when accepting them. Old v1.2 outputs, including content,
research and coding outcomes, remain diagnostic evidence; do not silently rescore them or relabel
them v1.3. Automatic routes stay unqualified until corrected v1.3 evidence passes the new checks.
Do not combine smoke/interrupted runs or infer missing measurements. Record final CI and a new
source-stable endurance run before closing another gate.
