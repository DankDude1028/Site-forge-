# Operations and recovery

## Start and inspect

Use README.md for local setup. API logs are under ignored `runtime/`. Check `/healthz` for process
health and `/readyz` for database/schema readiness. The dashboard uses only authenticated API data.
Read the latest task attempt, fencing token owner, deadline and checkpoint before retrying work.
Worker credentials are UUID-bound and expire within 24 hours; rotate through a trusted operator
process before expiry. Keep owner, worker and observer identities separate.

## Worker disconnect or supervisor restart

The Windows worker reconnects outbound, renews leases while active and fences itself if renewal
is uncertain. The supervisor reclaims expired leases with bounded retry/backoff. A stale attempt
cannot complete a new claim. If an effect has an unknown provider outcome, reconcile against the
provider's idempotency key before another request. An authorization receipt records intent and
never proves a Netlify deployment, payment or message was sent.

## Kill switch and exhausted work

POST `/v1/kill-switch` with `{"enabled":true}` using an owner token. Read-only inspection remains
available. Preserve failed attempts/audit evidence; do not delete durable jobs to make the queue
look clean. Investigate dead-lettered jobs, fix the root cause and enqueue a new semantic task key.
The switch does not reverse actions already performed by external providers.

## Budget reconciliation

External spend defaults to zero. Configure current UTC daily and monthly ceilings only after
explicit authorization. A reservation consumes both ceilings and the task cap. An unknown outcome
keeps funds reserved; a verified failure releases them; a verified success records spend once.
Do not add the daily and monthly accounting projections together as two separate expenses.
Missing provider coverage is unknown. Forecasts, estimates, unsettled items and realized revenue
remain separately labeled.

## Backup and restore targets

Targets: daily encrypted backups (RPO <=24h), tested recovery within eight hours, audit retention
>=90 days subject to privacy requirements. Configure real backup storage before cloud launch.
Use `pg_dump --format=custom` under a dedicated backup identity; secrets belong in a protected
credential mechanism, not command arguments or Git. Restore into a new isolated database with
`pg_restore`, apply/verify migrations, run integrity/tenancy/queue tests, compare retained receipts
and audit totals, then switch the service URL. A documented target is not evidence of a restore
drill; that acceptance gate is pending until performed.

## Preview and release

No Netlify site is created automatically. Configure a protected preview site and a scoped token;
verify access control and `noindex` before enabling `.github/workflows/staging.yml`. Preview URLs
alone do not provide privacy. First production publication requires an owner decision for the
exact reviewed commit/site and all acceptance gates. For a bad published revision, prepare a
reviewed fix-forward/revert release with exact approval. A failed deploy that never published
does not replace the live revision. Preserve the prior provider deploy/commit reference.

## Endurance evidence

The current run directory is recorded in [status](status.md); its `report.json` is updated every five observed active seconds. Inspect `pid`,
heartbeat freshness, completed durable tasks, injected/recovered fault counts, memory growth and
failures. Restarts resume the report and do not count offline time. Do not combine separate runs
or accelerate the clock to satisfy 259,200 seconds. The optional Windows task uses the current
user at logon; pass the same `-RunDirectory` to the startup and task-install scripts. Sleep/shutdown delays completion. If implementation bytes change, preserve the interrupted run and start a fresh directory. The initial fixture simulation does not claim
real provider outages, supervisor OS process death or PostgreSQL endurance. Preserve those limits
when reporting results. No cloud spending or public launch occurs in the runner.

## Remaining deployment operations

Configure least-privilege database roles, TLS ingress, secret manager/rotation, restricted egress,
rate-limited external adapters, GitHub branch protection and Netlify preview protection. Validate
Docker image builds and sandbox escape/resource controls on a host with Docker. Add provider
credentials through secure configuration, reconcile imported source IDs, and run a real backup
restore drill. Telegram delivery remains opt-in; absent opt-in, daily digest drafts stay local.
