# Acceptance evidence and limits

Evidence reviewed 2026-10-21. This document distinguishes executed checks from
implemented controls and unperformed operations. The current [status](status.md) is the acceptance
checklist. The [runbook](runbook.md) describes recovery procedures, not proof they were all exercised.

## Hosted baseline

[GitHub Actions run 39655980576](https://github.com/DankDude1028/Site-forge-/actions/runs/39655980576)
succeeded for commit `d64e46954ee10998185febf7a418758bf407d357`; its final update was
18:49:29 UTC on 2026-10-21. All three jobs succeeded. This is the latest verified hosted baseline,
not acceptance of the subsequent application and persistence fixes in the working tree.

| Job | Observed result |
| --- | --- |
| [Python](https://github.com/DankDude1028/Site-forge-/actions/runs/39655980576/job/119416225555) | Ruff passed; mypy found no issues in 21 source files; pytest **289 passed, 3 skipped, 1 warning** in 16.90 seconds. Locked dependency audits reported no known vulnerabilities; pytest XML and a CycloneDX SBOM were uploaded. |
| [Web](https://github.com/DankDude1028/Site-forge-/actions/runs/39655980576/job/119416225322) | Dashboard TypeScript/build, 2 Node tests and 2 Playwright tests passed. Utility: 5 Node tests, TypeScript check, static Astro build and 4 Playwright tests passed. Final npm audits reported **0 vulnerabilities** for both projects. |
| [Container](https://github.com/DankDude1028/Site-forge-/actions/runs/39655980576/job/119416225652) | Supervisor image built. The actual Docker sandbox integration test passed: **1 passed** in 1.08 seconds. |

The Python skips were the Docker test requiring an explicit engine/image, Windows executable
VERSIONINFO, and Windows junction behavior. The first was executed separately in the container job.
The other two are platform-specific and are not counted as Linux passes. Earlier local Windows
checks are separate from this hosted run. The one warning did not fail the suite; this document does
not suppress or reinterpret warnings.

## PostgreSQL, migrations and application controls

The Python job started a real `postgres:16-alpine` service; its server log reports PostgreSQL 16.15.
The [integration test at the hosted baseline](https://github.com/DankDude1028/Site-forge-/blob/d64e46954ee10998185febf7a418758bf407d357/tests/integration/test_api.py)
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

The earlier accepted [run 39653684353](https://github.com/DankDude1028/Site-forge-/actions/runs/39653684353)
also supplied individually inspected JUnit for the
[actual PostgreSQL fixture dump/restore test](https://github.com/DankDude1028/Site-forge-/blob/a71c7e83cafc155a49ac9c95ae57ca111c0266c1/tests/integration/test_postgres_restore.py).
That run's `python-evidence`, artifact ID `12370393988`, records
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

The executed [API tests](https://github.com/DankDude1028/Site-forge-/blob/d64e46954ee10998185febf7a418758bf407d357/tests/integration/test_api.py),
[security tests](https://github.com/DankDude1028/Site-forge-/blob/d64e46954ee10998185febf7a418758bf407d357/tests/security/test_security.py)
and [policy tests](https://github.com/DankDude1028/Site-forge-/blob/d64e46954ee10998185febf7a418758bf407d357/tests/unit/test_policy.py)
cover tenant visibility, owner/observer/worker separation, worker identity and lease fencing,
capability enforcement, hostile source text that cannot expand permissions, audit update/deletion
guards, exact approval binding and replay, zero default external spend, atomic reservations,
unknown-outcome retention and one-time reconciliation. Provider responses in these policy tests are
fixtures or mocks; they do not prove live provider idempotency or production financial settlement.

The committed-file secret pattern scan passed with its own stated limitation: it is not a full
secret detector. Dependency audits report known advisories in the scanned dependency sets at scan
time. Neither result is a full repository security review or proof of absence of vulnerabilities.

## Application corrections after the hosted baseline

The pre-atomic-persistence local Windows baseline was **342 passed, 4 skipped**, with Ruff and
mypy passing for all 21 application files. The skips require PostgreSQL, Docker, or unavailable
Windows symbolic-link permission. This count covers the UTC and agent retry/cache regressions;
the final suite including the newer atomic persistence changes is **PENDING**.

- `UTCDateTime` requires aware timestamps on writes, normalizes them to UTC, and restores UTC to
  SQLite's timezone-free stored values. Eight tests cover every mapped timestamp type, UTC and
  non-UTC deadlines through file SQLite and HTTP leasing, actual fixture-worker completion,
  naive-input rejection, and an unchanged Alembic schema check. PostgreSQL dialect conversion is
  tested locally; the final hosted PostgreSQL rerun remains pending.
- Agent outcomes use a strict boolean `retryable` and bounded `error_code`. Only transport/native
  availability, inference contention and model readiness can authorize bounded retries. Malformed
  responses, policy/deadline/context limits and observed model identity changes require review.
  Deadline expiry takes precedence over a transport timeout. Worker backpressure checks the shared
  inference lock before leasing; retries revalidate internal receipts and sources rather than reuse
  blocked/failed or bounded-agent completion checkpoints. Fixture developer and QA work is rerun.
- The dashboard pages tasks and pending approvals in batches of 100, shows aggregate totals from
  the authenticated summary endpoint, and rejects stale refresh/session responses. Audit display
  identifies its bounded recent window instead of presenting it as complete history.
- Atomic file persistence prepares and fsyncs a temporary file, then retries only Windows
  access/sharing/lock denials for at most two seconds. It retains the previous valid target if
  replacement fails and propagates unrelated errors. Benchmark reports, endurance state and local
  artifacts use the helper. Reader-contention and permanent-denial regressions were added; final
  verification is pending. These bounded retries do not establish power-loss durability.

The first actual authenticated native-agent demonstration, task
`0ee01e99-5085-4b2a-822f-54fff1887240` at 19:04:25 UTC, **failed before model inference**: SQLite
returned its future 19:09:25 UTC deadline without a timezone, which the agent rejected as expired.
The original `runtime/native-agent-evidence.json` and task failure are preserved. The helper's exit
code zero is not successful agent completion. The UTC correction is regression-tested; a new
end-to-end native-agent proof under a new idempotency key is **PENDING**.

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

Independent review found fixture v1.2 workflow prompts did not disclose exact serialized action
labels required by the grader; research/type and content constraints also needed correction.
Earlier v1.0/v1.1 had documented contract ambiguities. **All v1.0–v1.2 strict aggregates are preserved
exploratory diagnostics, not final model quality ranks or automatic routing qualifications.**

Raw responses, strict failures, timing, memory, source metadata and earlier content/research/coding
outcomes remain preserved. For example, recorded v1.2 4K runs include E4B 71/100 and Qwen3.5-9B
41/100 with parallelism one, and Gemma 12B QAT 46/100 with parallelism four. These are historical
grader outcomes only. Previous statements that v1.2 category thresholds qualified a route are
withdrawn; no automatic qualified route may be derived from them. Do not silently normalize old
answers into passes or relabel an old run as the corrected fixture.

Fixture **v1.3.0 is frozen and independently reviewed across all 100 tasks**, with exact UTF-8 SHA-256
`ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.
Its categories remain 25 tool, 20 research, 20 coding, 15 content, 15 workflow and 5 efficiency.
Canonical action vocabulary, numeric/status contracts and the restricted coding subset are explicit.
Content uses order-independent typed meaning/value/unit slots; editorial originality and free-prose
accuracy still need human review. Native reliability requires actual tool-call provenance, not
assistant text that prints tool-shaped JSON. Review verified 80 compliant noncoding references and
20 independently authored coding references without live model calls or rescoring old results.

Actual corrected qualification runs are in progress: E4B at 4K and 8K, plus GPT-OSS, Qwen3.5-9B and
Gemma 12B QAT at 4K, with verified loaded parallelism one. Final per-model counts and measured
role routes: **PENDING**. Preserve any command/load/write failures as well as completed runs; a
phase exit status alone is not a quality score. Automatic routing accepts only complete v1.3 evidence,
requires the configured sample/success floor in **each** relevant category, and verifies the loaded
source, quantization, context and single-slot settings. No winner is auto-loaded. The HTML quality
chart defaults to complete v1.3 4K runs and separates other fixtures/contexts through selectors.
Different contexts and concurrent development make throughput comparisons conditional; unavailable
quantizations and unrun context experiments remain pending.

Content scores measure the declared typed/literal constraints, research packets are synthetic benchmark inputs, and coding
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
states `interrupted_for_source_update` and acceptance `PENDING`. These and subsequent roots,
including `runtime/endurance-final-v13/`, were interrupted for source changes. **All previous runs
are unaccepted; accepted active seconds are zero.** No elapsed time or tasks carry into a replacement.

The two enumerated early reports recorded no failures, unauthorized effects, duplicate effects or
lost tasks, with injected/recovered fixture counts matching at their snapshots. They exercised
selected approvals, budgets, receipts, kill switch, model/network error, database reconnect, lease
and malformed-output paths. These are deliberate fixture faults, not claims that real providers
or OS services failed. Preserve the raw reports and their scope rather than extending their claims.

Passing requires at least 259,200 active seconds and 900 tasks, zero unauthorized/duplicate/lost
effects, all injected faults recovered, RSS growth no more than 256 MiB and queue latency no more
than thirty seconds, with source hash and at most fifteen seconds between observed heartbeats. The reports have not met
duration/task thresholds. Once implementation and qualification code freeze, create a fresh runtime
root with its own run ID and implementation hash. Sleep/offline time does not count; separate smoke
or interrupted runs must not be added together. Even a completed fixture run does not close
actual PostgreSQL/service restart, six-hour worker disconnect, OS crash, real network outage or
protected hosted-site acceptance.

Final application CI run/commit: **PENDING**. Fresh source-stable endurance run ID, implementation
hash and start time: **PENDING**. These placeholders must be filled from new immutable evidence,
not inherited from the hosted baseline or an interrupted root.

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
