# System architecture

SiteForge is a hybrid supervisor for a bounded portfolio of useful websites. This repository was
cloned from https://github.com/DankDude1028/Site-forge- on 2026-10-21 and was empty.
The original handoff is preserved in SiteForge_Blueprint.md.

## Trust and execution

The cloud API stores durable business state and a single PostgreSQL task queue. Agents propose
work through typed contracts; deterministic policy checks capabilities, exact approvals and money.
A Windows worker polls outbound, registers its identity, renews fenced leases, checkpoints, and
submits artifacts. LM Studio binds to 127.0.0.1. No inbound worker service is needed.

The initial operational mode is fixture research, isolated template generation, and independent
local checks. No arbitrary command or browser automation endpoint is exposed. Model-generated
Python is evaluated through the restricted benchmark evaluator rather than executed on the host.
General generated application code needs a hardened container/VM executor before enablement.

PostgreSQL is the production queue authority. SQLite is supported for reproducible local smoke
tests only. Production multi-process leasing must be tested against PostgreSQL, not inferred
from SQLite results. See ../decisions/001-queue.md for the Temporal comparison.

## Data boundaries

Every task, worker, evidence record, budget and approval belongs to an organization. Access tokens
are hashed, scoped, identity-bound and kept out of prompts and artifacts. The owner provisions
worker credentials with an expiry. API write operations use semantic idempotency keys; leases
carry fencing tokens. An expired attempt cannot complete work after another worker acquires it.

Money uses Decimal with an ISO currency. Realized revenue requires a verified imported provider
record; forecast revenue remains separate. API spend starts at zero. There is no automatic paid
cloud escalation. Provider credentials remain server/adapter configuration, never model input.

## Threat boundaries and mitigations

| Threat | Enforced boundary | Remaining deployment work |
| --- | --- | --- |
| Prompt injection | Source data cannot grant tools; deterministic allowlists | Test each new external adapter |
| Unauthorized spend or launch | Exact action, site, amount, hash and expiry approval | Real provider reconciliation before enablement |
| Duplicate effect after crash | Fenced tasks and durable unique effect receipts | Provider-specific idempotency and reconciliation |
| Worker theft | Hashed scoped identity and expiry | Secret store, rotation, TLS ingress |
| Cross-tenant reads | org filters and owner/worker role checks | Deploy DB row-level policy if opening multi-user access |
| Code escape or exfiltration | No generic host execution; scoped artifact output | Hardened VM/container sandbox with egress quotas |
| Durable task loss | DB transactions, retries, checkpoints, dead letters | Backups and real restore drill |
| Audit alteration | Append-only database audit constraints/triggers | Least-privilege DB role and external log retention |

## Milestone evidence

The final operational status lives in ../operations/status.md. Hardware benchmarks retain raw
outputs and observed metrics. Full context sweeps and endurance are separate acceptance gates.
No production launch is implied by local tests, a preview build, or a successful API request.
