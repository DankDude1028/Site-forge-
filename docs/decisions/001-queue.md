# ADR 001: PostgreSQL is the single MVP queue authority

Date: 2026-10-21. Status: accepted for the MVP implementation; deployment/endurance acceptance remains conditional on actual tests.

## Context

SiteForge has one intermittently online Windows GPU worker, a lightweight cloud supervisor, a 90-day pilot, and no approved paid infrastructure budget. Jobs need durable state, atomic leases, retries, dependencies, checkpoints, audit events, approval gates, and exact-action receipts. The handoff explicitly requires evaluating Temporal against a simpler PostgreSQL queue. The earlier architecture's Temporal requirement is superseded by that explicit evaluation instruction.

## Options and evidence

| Concern | Temporal | PostgreSQL task table |
| --- | --- | --- |
| Recovery model | Durable workflow history and replay; timers and workflow primitives provided by the platform | Durable rows, explicit transitions, leases, checkpoint records, and recovery logic implemented by SiteForge |
| Operational footprint | Temporal Service and database, plus application workers, or a separately approved hosted service | Existing application PostgreSQL plus supervisor and worker |
| Policy and economics transaction | Business records remain in PostgreSQL; coordinated projection/outbox design needed | Budget reservations, approvals, task transitions, attempts, and audit writes can share one transaction |
| Development risk | Workflow determinism, SDK and replay/versioning constraints | More responsibility for lease fencing, scheduling, starvation, concurrency tests, retention and recovery |
| Future long workflows | Strong fit for complex, long-running workflows | Suitable while the explicit state machine and task volume remain bounded; revisit with measured evidence |

Temporal documents event-history-based recovery, a service plus database, and separately hosted application workers. Those are real advantages and dependencies; using Temporal does not itself make external actions idempotent. Sources: [Temporal platform](https://docs.temporal.io/temporal), [workflow execution and replay](https://docs.temporal.io/workflow-execution), and [activity idempotency](https://docs.temporal.io/activity-definition#idempotency).

PostgreSQL explicitly identifies `SKIP LOCKED` as useful for multiple consumers of queue-like tables, while warning that the view is inconsistent for general-purpose queries. Row locks operate inside transactions; the application still owns business invariants. Sources: [PostgreSQL 16 SELECT locking](https://www.postgresql.org/docs/16/sql-select.html#SQL-FOR-UPDATE-SHARE), [transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html), and [database constraints](https://www.postgresql.org/docs/16/ddl-constraints.html). Production targets PostgreSQL 16 as requested; using version-specific documentation avoids silently adopting an unreleased database feature.

## Decision

Use **one PostgreSQL-backed durable task state machine** as queue authority for the MVP. Do not install a parallel Redis, in-memory, or Temporal queue that can independently dispatch the same task. Redis may later cache observations but cannot own task durability. A local SQLite adapter may support developer tests only if clearly labeled; SQLite tests do not prove PostgreSQL concurrency or production readiness.

Workers request scoped work through the authenticated supervisor API, using outbound connections. The supervisor selects an eligible task with `FOR UPDATE SKIP LOCKED` in a short transaction, writes its lease/attempt and immutable audit event, and commits before returning work. Model inference and network actions run outside database transactions.

The following is the required semantic shape, not a substitute for schema-specific implementation and integration tests:

```sql
BEGIN;
SELECT id FROM tasks
WHERE status IN ('ready', 'retry_scheduled')
  AND available_at <= CURRENT_TIMESTAMP
  AND capability = :authorized_capability
ORDER BY available_at, created_at, id
FOR UPDATE SKIP LOCKED
LIMIT 1;
-- Recheck dependencies, budget, cancellation, deadline, and kill switch.
-- Atomically assign owner, fresh lease token/generation, and expiry;
-- increment attempt, then append transition/attempt/audit records.
COMMIT;
```

Eligibility also requires organization scope, supported capability, a ready dependency graph, remaining attempt allowance, and no unresolved approval. Tenant and worker authorization comes from authenticated identity, not model output or request-supplied organization claims. Unique idempotency keys bind organization, task intent, and canonical payload hash; conflicting reuse must fail instead of returning an unrelated operation.

## Required correctness contracts

- States are `pending`, `ready`, `leased`, `running`, `completed`, `blocked`, `waiting_approval`, `retry_scheduled`, `failed`, and `cancelled`. All transitions are checked and timestamped.
- Start with 30-second worker heartbeats and 120-second leases. Completion, checkpoint, and renewal require current owner **and** lease token/generation **and** unexpired lease. A re-leased task fences out its old worker.
- Reclaim expired leases transactionally. Retry only idempotent/reconciled actions, with bounded backoff and maximum three automatic attempts. Exhausted tasks are terminal failures/dead letters with retained evidence. Offline workers never cause durable jobs to disappear.
- Never promise exactly-once external execution from row locks. Durable delivery is at least once. Use a unique immutable effect key, provider idempotency where available, provider reconciliation after uncertain outcomes, and a durable receipt. Unknown external outcome blocks retries until reconciled.
- Approvals bind the exact payload hash, site, action, amount/currency, operator, and expiry. Payload changes invalidate approval. A task lease is not an approval. The kill switch prevents new protected effects at dispatch time as well as scheduling time.
- Reserve per-job/day/month budget in the same transaction that authorizes an effect, with conditional updates or row locks. Persist reservation release/reconciliation. Never check remaining money and later decrement it in an unrelated transaction.
- Store dependencies and checkpoints in PostgreSQL. Use monotonic checkpoint sequence/unique keys and artifact checksums. Ensure stale attempts cannot replace newer checkpoints.
- Task state, attempt, lease, cost records, and transition audit must commit together. Keep audit append-only under the application database role. Database backup/restore is part of acceptance, not implied by choosing PostgreSQL.

## Validation and consequences

Required PostgreSQL integration tests include competing claims, lease expiry/reclaim, stale-worker completion, duplicate creation, idempotency hash conflict, cancellation/claim race, concurrent budget reservation, transactional audit rollback, supervisor restart, disconnect/reconnect, and uncertain external outcomes. Kill-and-restart tests must use persistent storage and fresh process instances. Unit tests and a short simulation cannot replace the actual 72-hour run.

This decision reduces initial services and keeps the pilot's task/budget/audit changes transactional. It adds application maintenance burden and creates no unlimited scale claim. Review it when queue latency violates predeclared thresholds, database contention becomes material, workflows need extensive durable timers/signals, or the recovery implementation becomes harder to audit than Temporal replay.

If migrating, drain or explicitly transfer existing jobs, assign ownership by a versioned cutover, retain immutable task/effect identities, and disable the old claimant before the new authority runs. PostgreSQL can then remain business projection storage while Temporal owns execution. Never run two competing authorities during migration.

No paid service was provisioned and no production deployment was authorized by this ADR.
