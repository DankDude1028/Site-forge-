# SiteForge

An approval-gated supervisor and outbound Windows worker for a small portfolio of useful sites.
Built from the supplied [master prompt](SiteForge_Blueprint.md). This was an empty repository at
inspection on October 21, 2026. The implementation includes a working local pipeline and measured,
bounded local model execution. Protected staging and the complete 72-hour acceptance test remain
pending; production publication remains disabled.

## Run on Windows

Python 3.12+, Node 22.23.4+ (or the bundled Node 24 runtime), Git and LM Studio are needed. Setup can discover the bundled Codex Python
when the Windows Store `python` alias is not an installed interpreter.

```powershell
.\scripts\Setup.ps1
Push-Location apps/dashboard
..\..\scripts\Invoke-Npm.ps1 ci
..\..\scripts\Invoke-Npm.ps1 run build
Pop-Location
.\.venv\Scripts\python.exe -m siteforge.cli init
.\scripts\Start-Local.ps1
.\.venv\Scripts\python.exe -m siteforge.cli demo
```

Open **http://127.0.0.1:8080**. Use `SITEFORGE_OWNER_TOKEN` from the ignored local `.env` file to enter
the dashboard. The token stays in browser memory. Initialization creates separate random owner and
worker credentials, binds the worker UUID, gives it an eight-hour expiry, provisions a local SQLite
tenant and sets external spend to zero. Do not commit, upload or share `.env`.

The demo sends real authenticated HTTP requests to the supervisor, queues seven dependent agent
tasks, and runs the Windows worker through registration, leases, checkpoints and completion. Its
research, source, Astro project, QA, content, growth and revenue artifacts are under
`runtime/artifacts/label-roll-planner/`. Synthetic market evidence is explicitly labeled. The useful
sample site calculates label roll length, waste, spare allowance and roll counts; it does not claim
real demand or revenue. Build it independently (on this PC use `scripts/Invoke-Npm.ps1` in place of the older default npm runtime):

```powershell
Push-Location packages/site-templates/label-roll-planner
..\..\..\scripts\Invoke-Npm.ps1 ci
..\..\..\scripts\Invoke-Npm.ps1 test
..\..\..\scripts\Invoke-Npm.ps1 run typecheck
..\..\..\scripts\Invoke-Npm.ps1 run build
..\..\..\scripts\Invoke-Npm.ps1 run e2e
..\..\..\scripts\Invoke-Npm.ps1 run dev
Pop-Location
```

Use `python -m siteforge.worker` for the continuously polling outbound worker after loading its
environment (see `apps/windows-worker`). Worker tokens expire; use a trusted operator process to
rotate them. No long-lived refresh credential or public LM Studio endpoint is introduced.

## Local model benchmarks

The harness contains 100 versioned tasks: 25 tools/policy/JSON, 20 source-fidelity, 20 coding tasks
with executable restricted-interpreter tests, 15 content constraints, 15 workflow/recovery, and five
efficiency tasks. It streams responses from actual LM Studio, samples hardware counters, records
exact models/quantization/context, and produces raw JSON, CSV, Markdown and an offline HTML chart.
It never executes model-generated host code or calls paid APIs.

```powershell
lms server start --bind 127.0.0.1 --port 1234
.\.venv\Scripts\python.exe -m benchmarks.runners.run --model siteforge-benchmark --source-model google/gemma-4-e4b --quantization Q4_K_M --context 4096 --load --structured-json --max-tokens 1024
.\.venv\Scripts\python.exe -m siteforge.cli import-benchmarks
```

See [benchmark instructions](benchmarks/README.md), [official model research](docs/research/model-candidates.md),
and [measured report](benchmarks/results/report.md). Open `benchmarks/results/model_comparison.html`
for charts. Compare matching fixture versions and settings. Versions 1.0–1.2 retain exploratory
outcomes with documented contract and grading defects; they cannot select routing winners.
Version 1.3 defines workflow symbols, research types and typed content facts with values, meanings
and units. A fenced answer or short smoke test cannot qualify a strict native tool response.
Editorial quality, originality and free-prose factuality still require review.

Unavailable quantizations, the requested 35B-A3B model when not installed, unrun contexts and genuine
long-context retrieval tests remain pending. Published file sizes and KV estimates are labeled
separately from measured GPU use. The router fails closed without sufficient complete measured role
coverage and never enables paid cloud escalation.

## Durable supervisor

PostgreSQL 16 is the production queue authority. [The decision record](docs/decisions/001-queue.md)
compares Temporal and the simpler PostgreSQL queue. SQLite is a local test backend. Configure
`SITEFORGE_DATABASE_URL`, apply [Alembic migrations](infrastructure/migrations/README.md), then
provision the organization with `Database.provision_org`. Schema creation is deliberately absent
from API startup. Docker Compose config is in `infrastructure/docker/compose.yml`; a Docker runtime
is required to validate that stack.

```powershell
.\.venv\Scripts\python.exe -m alembic -c infrastructure/migrations/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m siteforge.scheduler --once
```

The scheduler recovers deadlines/leases and stale workers. Daily fixture scheduling is opt-in;
`SITEFORGE_SCHEDULE_WEEKLY_REVIEWS=true` adds durable internal reviews from recorded economics,
preserving missing observations. Budget commitments produce internal 50/80/100% notices.
its database idempotency keys survive restarts. Model and external research jobs wait when the
Windows PC is offline. Seven typed roles have fixed tools, bounded retry rules, audited artifacts
and owner escalation. `local_model` mode writes structured proposals. `bounded_agent` mode runs
native tool calls for sourced evidence, drafts, trusted template previews, independent static QA,
opportunity scores, experiments and ledger reconciliation. It requires a qualified measured model
already loaded with matching quantization, context and parallelism. The loop has fixed role tools,
strict argument schemas, deadline/context/call limits, durable internal receipts and audit artifacts.
Executable tests require an operator-configured Docker image pinned by digest. Model-generated
host code, provider mutations, publishing and paid fallback are unavailable to this tool loop.

The API provides `/healthz`, `/readyz`, organization-scoped `/v1` catalogs, worker operations,
task cancellation, candidate scoring, workflows, approvals, budget configuration, action intents,
kill switch and ledger summaries. Owner/observer/worker/release scopes are distinct. Hashed token config
(`SITEFORGE_AUTH_TOKENS`) supports explicit capabilities and expiry. Authenticated `/metrics` is for
monitoring. Money uses Decimal; missing revenue imports remain unknown rather than zero.

## Gates and integrations

Spending, domains, production release, outreach, affiliate agreements, contracts, destructive
production operations and sensitive privilege changes require an immutable approval bound to
site, action, payload, amount, currency, operator and expiry. Daily/monthly/per-task reservations
are atomic. Replayed authorizations return the original intent; provider outcomes must be reconciled.
Audit mutation is rejected by database triggers. The kill switch stops dispatch and external effects.

The trusted Astro template is copied inside a scoped artifact workspace. General generated code
requires the Docker sandbox; there is no generic host-command endpoint. Provider adapters are
configured explicitly, use bounded calls and allowlists, and never receive credentials from models.
Connected analytics/financial accounts, provider-specific ingestion credentials, secret-manager/TLS
infrastructure, protected Netlify site identity, branch protection and a production release decision
must be supplied before enabling live operations. No provider success is fabricated.

GitHub Actions runs Python lint/type checks/tests, real PostgreSQL migration/concurrent leasing
checks, package vulnerability scans, a secret pattern scan, SBOM generation, dashboard browser/axe
tests and Astro build/tests. Manually enabled preview and promotion workflows call the supervisor's
exact approval, budget and durable provider-receipt pipeline. Releases default to disabled; unknown
costs, unresolved effects, unverified protection and mismatched artifact trees block advancement.
The separate [bundle workflow](.github/workflows/bundle.yml) builds without release credentials,
then transfers bounded, hashed static bytes through a scoped API for owner review. Normal previews
remain noindex. A separate indexable production variant links to the exact reviewed preview,
commit and source tree; promotion binds its own protected draft and manifest. Authenticated build
claims are labeled and do not establish independent GitHub attestation.
Default-disabled automatic rollback supports an exactly preapproved, previously healthy SiteForge
release with server-attested zero incremental cost. Durable claims prevent repeating an uncertain
restore. Unknown history, drift or cost blocks recovery. Hosted release acceptance remains pending.
See [release operations](docs/operations/releases.md) for scoped credentials, read reconciliation,
bounded upload recovery and limitations, and [bundle operations](docs/operations/bundles.md) for
transfer/SEO checks. `.netlify` is ignored. No live deployment was performed.

[Encrypted backups](docs/operations/backups.md) stream PostgreSQL dumps into authenticated AES-GCM
archives, retain verified local history and restore only into new disposable databases. Production
scheduling, protected off-host storage and key custody remain operator acceptance work.

## Endurance and acceptance

```powershell
# Fast smoke evidence (not 72-hour acceptance)
.\.venv\Scripts\python.exe -m siteforge.endurance --root runtime/smoke --hours 0.02 --cycles 3 --interval 0
# Actual wall-clock fixture run in a hidden background process
.\scripts\Start-Endurance.ps1 -RunDirectory runtime/endurance-final-source
# Optional current-user logon recovery, no administrator rights
.\scripts\Install-EnduranceTask.ps1 -RunDirectory runtime/endurance-final-source
```

The runner counts observed active time, persists progress, prevents parallel ownership with an OS
file lock, and exercises hundreds of dependent tasks over 72 real hours. It injects fixture model,
network, malformed-output, lease and database reconnect faults, verifies checkpoint/fence recovery,
checks blocked approvals, zero budgets and receipt replays, and measures latency/memory. Short runs
are labeled smoke. Even a 72-hour fixture soak cannot certify untested PostgreSQL/service/OS/network
faults or a hosted staging deployment. See [status](docs/operations/status.md) and the
[operations runbook](docs/operations/runbook.md) for exact remaining acceptance gates.

An additional [actual process recovery drill](docs/operations/runtime-drill.md) hard-stops only its
isolated API/worker subprocesses, observes a real loopback outage and lease expiry, then recovers
the checkpoint and research/build/QA chain. Run it with a new evidence directory:

```powershell
.\.venv\Scripts\python.exe -m siteforge.runtime_drill --root runtime/process-drill
```

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check siteforge benchmarks tests scripts
.\.venv\Scripts\python.exe -m mypy siteforge --ignore-missing-imports
```
