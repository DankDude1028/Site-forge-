# SiteForge

An approval-gated supervisor and outbound Windows worker for a small portfolio of useful sites.
Built from the supplied [master prompt](SiteForge_Blueprint.md). This was an empty repository at
inspection on October 21, 2026. The implementation includes a working local fixture pipeline;
production publication remains disabled.

## Run on Windows

Python 3.12+, Node 22.23.4+ (or the bundled Node 24 runtime), Git and LM Studio are needed. Setup can discover the bundled Codex Python
when the Windows Store `python` alias is not an installed interpreter.

```powershell
.\scripts\Setup.ps1
Push-Location apps/dashboard
npm ci
npm run build
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
for charts. Use the same fixture version/settings for comparisons. Early 1.0/1.1 exploratory runs
retain strict failures and document contract ambiguities; those versions cannot select production
routing winners. A fenced answer or a short smoke test is never silently counted as a valid strict
tool response. Content grading is a constraint proxy; editorial quality still requires review.

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
its database idempotency keys survive restarts. Model and external research jobs wait when the
Windows PC is offline. Seven typed roles have fixed tools, bounded retry rules, audited artifacts
and owner escalation. Live-model mode produces structured proposals; it cannot execute arbitrary
generated code, publish, or expand permissions.

The API provides `/healthz`, `/readyz`, organization-scoped `/v1` catalogs, worker operations,
task cancellation, candidate scoring, workflows, approvals, budget configuration, action intents,
kill switch and ledger summaries. Owner/observer/worker scopes are distinct. Hashed token config
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
tests and Astro build/tests. The manually enabled preview workflow requires a configured protected
Netlify site and protection verification. `.netlify` is ignored. The production workflow fails
closed until exact approval consumption, provider reconciliation, health checks and a tested
fix-forward release are connected. No live launch or deployment is implied by a local build.

## Endurance and acceptance

```powershell
# Fast smoke evidence (not 72-hour acceptance)
.\.venv\Scripts\python.exe -m siteforge.endurance --root runtime/smoke --hours 0.02 --cycles 3 --interval 0
# Actual wall-clock fixture run in a hidden background process
.\scripts\Start-Endurance.ps1
# Optional current-user logon recovery, no administrator rights
.\scripts\Install-EnduranceTask.ps1
```

The runner counts observed active time, persists progress, prevents parallel ownership with an OS
file lock, and exercises hundreds of dependent tasks over 72 real hours. It injects fixture model,
network, malformed-output, lease and database reconnect faults, verifies checkpoint/fence recovery,
checks blocked approvals, zero budgets and receipt replays, and measures latency/memory. Short runs
are labeled smoke. Even a 72-hour fixture soak cannot certify untested PostgreSQL/service/OS/network
faults or a hosted staging deployment. See [status](docs/operations/status.md) and the
[operations runbook](docs/operations/runbook.md) for exact remaining acceptance gates.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check siteforge benchmarks tests scripts
.\.venv\Scripts\python.exe -m mypy siteforge --ignore-missing-imports
```
