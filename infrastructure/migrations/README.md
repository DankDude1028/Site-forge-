# Schema administration

Run from the repository root after installing Python dependencies:

```powershell
$env:SITEFORGE_DATABASE_URL = 'postgresql+psycopg://siteforge_migrator:YOUR_PASSWORD@localhost:5432/siteforge'
python -m alembic -c infrastructure/migrations/alembic.ini upgrade head
python -m alembic -c infrastructure/migrations/alembic.ini check
```

`SITEFORGE_DATABASE_URL` takes precedence over `DATABASE_URL`. An unconfigured migration uses the local SQLite simulation database. PostgreSQL 16 is the production queue authority; Redis and Temporal do not separately dispatch these tasks. The initial migration freezes all 29 entity tables, UUID identifiers, JSONB provider data, NUMERIC(18,6) money, foreign keys, state/check/uniqueness constraints, queue indexes, immutable audit triggers, and immutable approval bindings. SQLite uses compatible local types and database triggers for deterministic tests.

Use a separate database owner for migrations. The API/worker database role needs only `SELECT, INSERT, UPDATE` on its business tables and `SELECT, INSERT` on `audit_events`; it must not own the schema, disable triggers, truncate tables, or receive DDL rights. A database administrator can override database protections and is outside the application credential boundary. Provision organization UUIDs through `Database.provision_org` during trusted initialization. Schema creation is never automatic in the API. `Database.create_schema` is exclusively for local fixtures.

Back up before schema changes. The initial migration deliberately refuses downgrade because deleting tables would destroy retained audit history. Rollback requires a verified backup restore into a clean database and an application version compatible with that backup.

SQLite migration and schema drift tests run in the ordinary suite. To run actual PostgreSQL migration/concurrent lease tests against a dedicated test database:

```powershell
$env:SITEFORGE_TEST_POSTGRES_URL = 'postgresql+psycopg://siteforge_test:YOUR_PASSWORD@localhost:5432/siteforge_test'
python -m pytest tests/integration/test_api.py -k postgres -v
```

The PostgreSQL test migrates the test database, claims and completes 20 tasks using eight competing workers, checks every task was claimed exactly once, and verifies that `TRUNCATE audit_events` is rejected by the database trigger. It is marked skipped when a PostgreSQL service is unavailable; SQLite concurrency results do not establish PostgreSQL behavior.
