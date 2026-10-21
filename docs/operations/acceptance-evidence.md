# Acceptance evidence and limits

Evidence reviewed 2026-10-21 at 18:37 UTC. This document distinguishes executed checks from
implemented controls and unperformed operations. The current [status](status.md) is the acceptance
checklist. The [runbook](runbook.md) describes recovery procedures, not proof they were all exercised.

## Hosted baseline

[GitHub Actions run 39653684353](https://github.com/DankDude1028/Site-forge-/actions/runs/39653684353)
completed successfully at 18:34:28 UTC on 2026-10-21 for commit
`a71c7e83cafc155a49ac9c95ae57ca111c0266c1`. The three jobs succeeded. This evidence covers that
commit; a subsequent working-tree change requires subsequent checks.

| Job | Observed result |
| --- | --- |
| [Python](https://github.com/DankDude1028/Site-forge-/actions/runs/39653684353/job/119408258954) | Ruff passed; mypy found no issues in 21 source files; pytest **266 passed, 3 skipped, 1 warning** in 15.51 seconds. `pip-audit` reported no known vulnerabilities in the locked Python requirements. A CycloneDX SBOM and pytest XML were uploaded as `python-evidence`. |
| [Web](https://github.com/DankDude1028/Site-forge-/actions/runs/39653684353/job/119408259198) | Node v24.21.0. Dashboard TypeScript/build, 2 Node tests and 2 Playwright tests passed. Utility: 5 Node tests, TypeScript check, static Astro build and 4 Playwright tests passed. Clean installs and final npm audits reported **0 vulnerabilities** for both projects. |
| [Container](https://github.com/DankDude1028/Site-forge-/actions/runs/39653684353/job/119408258639) | Supervisor image built. A separate actual Docker sandbox integration test passed: **1 passed** in 0.59 seconds. |

The Python skips were the Docker test requiring an explicit engine/image, Windows executable
VERSIONINFO, and Windows junction behavior. The first was executed separately in the container job.
The other two are platform-specific and are not counted as Linux passes. Earlier local Windows
checks are separate from this hosted run. The one warning did not fail the suite; this document does
not suppress or reinterpret warnings.

## PostgreSQL, migrations and application controls

The Python job started a real `postgres:16-alpine` service; its server log reports PostgreSQL 16.15.
The [integration test at the reviewed commit](https://github.com/DankDude1028/Site-forge-/blob/a71c7e83cafc155a49ac9c95ae57ca111c0266c1/tests/integration/test_api.py)
applied Alembic migrations to that PostgreSQL database, registered eight workers, enqueued twenty
tasks, then used eight concurrent consumers to lease, start and complete them. It asserted exactly
twenty distinct task IDs, matching the original set, with all tasks completed. PostgreSQL rejected
`TRUNCATE audit_events` through the immutable audit guard. This is actual bounded concurrent lease
evidence for the single PostgreSQL queue authority, not a 72-hour durability or failover test.

The migration test separately upgraded a fresh SQLite database, checked migration consistency and
observed thirty tables: twenty-nine application entities plus Alembic's version table. It also
verified the audit deletion guard. Production startup requires an existing migrated schema; it does
not silently create one. A successful migration does not establish a safe future downgrade, upgrade
of a large live database, or recovery of a damaged production database.

The same run also executed the [actual PostgreSQL fixture dump/restore test](https://github.com/DankDude1028/Site-forge-/blob/a71c7e83cafc155a49ac9c95ae57ca111c0266c1/tests/integration/test_postgres_restore.py).
JUnit in `python-evidence`, artifact ID `12370393988`, records
`test_actual_postgres_dump_restore_preserves_queue_receipts_and_guards` as passed in 1.285 seconds,
with no skip or failure element. The test created two fresh isolated loopback databases, migrated
the source, populated a running task/checkpoint and approved authorization intent, performed actual
custom-format `pg_dump` and `pg_restore`, then compared every application table's rows. It verified
the same authorization receipt was replayed, the checkpoint was retained, the restored running task
could complete, the migration version remained `0001`, and audit truncation and approval tampering
were still rejected. The test did not contact a provider; its reserved intent is not a deployment.

This establishes bounded fixture recovery on the hosted PostgreSQL service. It does not establish
scheduled backups, encryption, remote storage, key custody, retention, backup monitoring, production
database privileges, cross-version restoration, or measured production RPO/RTO. Those gates remain
pending. The test cleans up only the two UUID-named disposable databases it created.

The executed [API tests](https://github.com/DankDude1028/Site-forge-/blob/a71c7e83cafc155a49ac9c95ae57ca111c0266c1/tests/integration/test_api.py),
[security tests](https://github.com/DankDude1028/Site-forge-/blob/a71c7e83cafc155a49ac9c95ae57ca111c0266c1/tests/security/test_security.py)
and [policy tests](https://github.com/DankDude1028/Site-forge-/blob/a71c7e83cafc155a49ac9c95ae57ca111c0266c1/tests/unit/test_policy.py)
cover tenant visibility, owner/observer/worker separation, worker identity and lease fencing,
capability enforcement, hostile source text that cannot expand permissions, audit update/deletion
guards, exact approval binding and replay, zero default external spend, atomic reservations,
unknown-outcome retention and one-time reconciliation. Provider responses in these policy tests are
fixtures or mocks; they do not prove live provider idempotency or production financial settlement.

The committed-file secret pattern scan passed with its own stated limitation: it is not a full
secret detector. Dependency audits report known advisories in the scanned dependency sets at scan
time. Neither result is a full repository security review or proof of absence of vulnerabilities.

## Docker execution actually exercised

The container job resolved and ran:

```text
python:3.12-slim@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2
```

The [real integration test](https://github.com/DankDude1028/Site-forge-/blob/a71c7e83cafc155a49ac9c95ae57ca111c0266c1/tests/integration/test_docker_sandbox.py)
executed the fixed `python_unittest` recipe through `DockerSandbox`, using the locally pulled image's
RepoDigest. Inside the container it verified UID 65534, zero effective Linux capabilities, absence
of a fixture host secret, failed writes to the job bind and container root, absence of an arbitrary
host file, and failed outbound socket access. The caller checked successful exit, no host escape
file, no output truncation and reported network mode `none`.

The implementation also constructs fixed CPU/RAM/swap/PID limits, `no-new-privileges`, a read-only
root/job mount, bounded output and timeout cleanup. This run did not stress every resource limit or
prove immunity to all engine/kernel escapes. It ran on a hosted Linux Docker engine; the actual
Windows worker's Docker engine, account permissions and resource enforcement still require a
separate installation and validation. Missing Docker fails closed. It never falls back to executing
untrusted generated code on the host.

The earlier [provider/sandbox implementation note](provider-sandbox.md) predates this hosted run;
its statement that Docker execution is pending is superseded for this specific Linux integration
scope only. Live provider connection and Windows Docker acceptance remain pending.

## Browser, accessibility and build scope

The utility template's desktop and mobile Playwright checks exercise calculator changes and invalid
input, detect horizontal overflow, check privacy/noindex/robots/sitemap output and use axe on the
home and privacy pages with WCAG 2 A/AA and 2.1 AA tags. They also reject unexpected external browser
requests. The dashboard browser checks exercise the authenticated UI against fixture API data and
include axe. These are automated browser checks, not a manual accessibility audit or a production
load, authentication penetration or cross-browser test.

The utility lockfile uses patched Astro 7.4.2, Vite 8.3.5 and Sharp 0.35.5. Both npm audit results
were zero at the reviewed commit. The earlier vulnerable Astro 6 dependency baseline is not the
accepted build. Node must satisfy the repository's declared engine, at least 22.23.4; hosted web CI
used Node 24.21.0. The static build generated two pages and `/sitemap.xml`. A successful local/static
build and noindex metadata establish neither hosting privacy nor deployment success.

## Live measurements still in progress

Use [benchmark report](../../benchmarks/results/report.md),
[JSON records](../../benchmarks/results/results.json),
[CSV records](../../benchmarks/results/results.csv),
[diagnostic records](../../benchmarks/results/diagnostic_results.json) and
[comparison charts](../../benchmarks/results/model_comparison.html) together. These are generated
from actual local LM Studio requests and may still change during an active run. The report preserves
load/setup failures, raw scores, fixture versions, model/quant/context identities, sampling limits
and loaded parallelism.

An independent contract review found that fixture v1.2 workflow prompts did not fully disclose the
exact serialized action labels the grader required. Reasonable recovery plans could therefore fail
for vocabulary/serialization differences rather than unsafe behavior. Research/type/lexical and
other category contracts are also being reviewed against their prompts, response schemas and
expected values. Earlier v1.0/v1.1 had already documented contract ambiguities. **All previous strict
aggregates are exploratory diagnostics, not final model quality ranks or routing qualifications.**

Raw responses, strict failures, timing, memory, source metadata and earlier content/research/coding
outcomes remain preserved. For example, recorded v1.2 4K runs include E4B 71/100 and Qwen3.5-9B
41/100 with parallelism one, and Gemma 12B QAT 46/100 with parallelism four. These are historical
grader outcomes only. Previous statements that v1.2 category thresholds qualified a route are
withdrawn; no automatic qualified route may be derived from them. Do not silently normalize old
answers into passes or relabel an old run as the corrected fixture.

Fixture v1.3 will make the canonical contract explicit and must pass independent prompt/schema/
grader review before actual reruns. Planned runs are E4B at 8K and GPT-OSS, Qwen3.5-9B and Gemma 12B
QAT at 4K, each with verified loaded parallelism one. Record their new fixture hash, exact model/
quant/context, settings, raw outputs, complete coverage and qualification version. Corrected final
counts, matching-setting comparisons and role qualification remain pending. Different contexts
still make hardware/throughput comparisons conditional. Unavailable quantizations and unrun context
experiments remain pending.

Content scores are constraint proxies, research packets are synthetic benchmark inputs, and coding
answers are checked by a bounded interpreter. These are useful repeatable measurements, not proof
of editorial originality, real market demand or arbitrary application correctness. Reported GPU
energy/cost is a sampled GPU-only estimate with an assumed tariff, excluding whole-PC power and
overhead. Task-time success/hour is distinct from whole-run throughput including loads and reports.

## Endurance and release gates still open

The historical fixture reports are under ignored `runtime/endurance/` and `runtime/endurance-final/`.
Run `4c1ec950-2bc9-4ec9-9ffa-708465746539` started at 17:50:40.036688 UTC on 2026-10-21 and was
interrupted for a source update at 18:27:59 UTC, after 2,234.110 active seconds and twelve tasks.
Replacement `d5dadf17-189c-4a1b-8df7-a3d2d77de910` started at 18:30:48.210469 UTC, recorded source
hash `49d8bb14f6c552f2886d82390cde7e8b8ae3db7ae5b00c3989f6bd90516ccdab`, and was interrupted
again at 18:36:06.042724 UTC after 300.672 active seconds and three tasks. Its report explicitly
states `interrupted_for_source_update` and acceptance `PENDING` because the routing fixture version
is changing. Neither is accepted, and no elapsed time or tasks carry into the next run.

These short historical reports recorded no failures, unauthorized effects, duplicate effects or
lost tasks, with injected/recovered fixture counts matching at their snapshots. They exercised
selected approvals, budgets, receipts, kill switch, model/network error, database reconnect, lease
and malformed-output paths. These are deliberate fixture faults, not claims that real providers
or OS services failed. Preserve the raw reports and their scope rather than extending their claims.

Passing requires at least 259,200 active seconds and 900 tasks, zero unauthorized/duplicate/lost
effects, all injected faults recovered, RSS growth no more than 256 MiB and queue latency no more
than thirty seconds, with source hash and heartbeat continuity checks. The reports have not met
duration/task thresholds. Once implementation and qualification code freeze, create a fresh runtime
root with its own run ID and implementation hash. Sleep/offline time does not count; separate smoke
or interrupted runs must not be added together. Even a completed fixture run does not close
actual PostgreSQL/service restart, six-hour worker disconnect, OS crash, real network outage or
protected hosted-site acceptance.

| Remaining operational gate | Evidence required to close it |
| --- | --- |
| Protected preview, currently blocked | Reauthenticate Netlify, configure an existing protected target and scoped token, verify unauthenticated access is denied, preserve draft deploy receipt, exact commit, health and protection checks. No such preview was deployed here. |
| Cloud setup and budget | Owner-authorized provider/budget, actual TLS/secret/role/egress/rate-limit/monitoring setup, verified recurring-cost coverage. Infrastructure templates alone do not satisfy this. |
| Branch protection | Owner-reviewed configuration actually applied, required check/review behavior verified, deployment environment access verified. Prepared JSON is not an applied setting. |
| Production backup/restore | The isolated fixture dump/restore passed in the hosted baseline above. Production still requires encrypted scheduled backups, protected keys/storage, retention, observed backup success, a production restore drill and measured RPO/RTO. Current runbook values are targets. |
| Live analytics/economics | Authorized provider connections, reconciled source identities, freshness/coverage, realized revenue and complete cost provenance. Missing coverage remains unknown. |
| End-to-end provider effects | Supervisor policy and exact approval consumption connected to provider mutation, durable effect receipt, unknown-outcome reconciliation and health checks, then tested together. Adapter mocks and authorization intents are insufficient. |
| Production publication | All applicable gates accepted, exact owner-approved release/site/amount, protected staging and tested fix-forward release. The current production workflow intentionally exits unsuccessfully before publication. |

No cloud service, protected preview, paid resource, public launch, external message or production
revenue is evidenced by these checks. Record the next final CI run, corrected v1.3 measurements and
source-stable endurance run with their own immutable identities; do not silently extend this
baseline's scope.
