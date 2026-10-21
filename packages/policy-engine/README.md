# Policy engine

Implementation: `siteforge/policy.py` with typed `siteforge/contracts.py` and immutable database guards. Default deny, exact approvals, atomic UTC daily/monthly/task budgets, one-use authorization intents, reconciliation and kill switch. Tests: unit policy, API and security suites. Models cannot grant permissions.
