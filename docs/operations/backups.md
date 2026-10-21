# Encrypted PostgreSQL backup and disposable restore

`siteforge.backups` and the PowerShell wrappers implement local encrypted backups, authenticated
manifests, bounded retention and restore into a **new disposable database**. They never overwrite
or drop an existing database, promote a target, switch an application URL, provision storage or
contact a provider. Scheduling, protected off-host storage, key custody and production RPO/RTO
acceptance remain operator work.

Install the locked Python requirements and PostgreSQL client tools matching the server major
version. The PowerShell scripts require PowerShell 7. Use an owner-controlled absolute backup
directory on a filesystem supporting atomic hard links. Each backup gets a random UUID filename;
its manifest is published last as the commit marker. A failed write may leave an uncommitted
encrypted archive; retention preserves unverified/orphan files for inspection.

## Configure secrets without command-line values

Use a trusted secret manager or the process environment to set:

- `SITEFORGE_BACKUP_KEY`: base64 encoding of **32 cryptographically random bytes**. Generate and
  store it through the trusted secret mechanism; do not print it into transcripts or Git.
- `SITEFORGE_BACKUP_DATABASE_URL`: explicit PostgreSQL URI including its dedicated backup identity
  and password. Only `sslmode` and `sslrootcert` URI options are accepted. Non-loopback hosts require
  `sslmode=verify-full`; configure the correct CA certificate. Local fixture connections may disable TLS.
- `SITEFORGE_RESTORE_DATABASE_URL`: explicit target URI with a fresh database name in the exact form
  `siteforge_restore_<32 lowercase UUID hex digits>`.
- `SITEFORGE_RESTORE_ADMIN_URL`: same host, port, identity, credentials and TLS settings, with database
  `postgres`. Its role needs permission to create the disposable database.

The public `-KeyId` identifies the key version and is authenticated; it is not the secret key.
Keep historical keys until every required backup encrypted with them has expired or been replaced.
Never reuse one key ID for different key material. Passwords are supplied to PostgreSQL clients in
their environment; URIs, keys and provider error bodies are excluded from arguments and CLI logs.
Unrelated inherited provider secrets/libpq service options are excluded from the child environment.
The direct restore admin connection refuses any inherited `PG*` variables (including `PGHOSTADDR`,
`PGSERVICE` and `PGPASSWORD`); clear them and configure the dedicated URI variables instead.

## Back up and retain locally

Run from the repository with the environment already populated:

```powershell
.\scripts\Backup-Postgres.ps1 -Directory C:\SiteForgeBackups -KeyId primary-2026-10 `
  -Python .\.venv\Scripts\python.exe -PgBin 'C:\Program Files\PostgreSQL\16\bin'
```

The wrapper creates one encrypted custom-format dump, then applies retention (default 30 days,
at least seven verified backups **per source identity**). `-RetainDays` and `-Keep` change these
local values. Retention only deletes canonical UUID-named archive/manifest pairs whose AES-GCM
authentication and hashes verify with the supplied key and whose age exceeds the limit. Other key
versions, malformed files, links and unknown names are preserved. Inspection is capped at 1,000
candidates and 60 seconds; it fails before deletion if inspection exceeds the deadline.

Dump bytes are encrypted as they stream from `pg_dump`, without a plaintext dump file. Envelopes use
AES-256-GCM with fresh 96-bit nonces and authenticate version, UUID, UTC creation time, source identity
and key ID. Manifests include encrypted archive and dump hashes/sizes; checksums alone are never
treated as authentication. Defaults cap dump size at 512 MiB and a client operation at 600 seconds;
explicit limits cannot exceed 8 GiB or 3,600 seconds. Subprocess failures and limit breaches do not
produce a committed backup. The manifest contains public source host/database metadata; protect
directory access even though dump contents are encrypted.

## Restore into a disposable database

Use an isolated PostgreSQL test/recovery service and a dedicated limited restore role. A PostgreSQL
dump contains database objects and SQL, so do not restore an untrusted source as a production
superuser. This command creates a database; it does not isolate an entire PostgreSQL server.

```powershell
.\scripts\Restore-Postgres.ps1 -Directory C:\SiteForgeBackups `
  -Archive C:\SiteForgeBackups\siteforge-backup-<backup-uuid-hex>.sfb `
  -KeyId primary-2026-10 -Disposable -Python .\.venv\Scripts\python.exe `
  -PgBin 'C:\Program Files\PostgreSQL\16\bin'
```

Before any database connection, the full envelope and manifest are verified into a quarantined
delete-on-close file. The temporary directory is mode 0700 on POSIX; Windows ACLs explicitly grant
only the current user and SYSTEM. Authentication must finish before `CREATE DATABASE` or
`pg_restore` can run. Restore uses `--single-transaction --exit-on-error`, without `--clean` or
`--create`. The admin connection has explicit connect, statement and lock timeouts; inherited
libpq options cannot override them. An existing target fails at creation. A restore failure leaves its newly created
disposable database for inspection; cleanup is an explicit operator action. The authenticated source
database name cannot equal the target. Credentials never appear in the receipt.

Python equivalents are `python -m siteforge.backups backup|retain|restore --help`. Alternate environment
variable **names**, client paths and limits can be supplied through that CLI; secret values cannot.

## Evidence and acceptance

Unit tests exercise real AES-GCM round trips, metadata/ciphertext/tag/key corruption, manifests,
size bounds, retention isolation and database-operation ordering using fixture subprocesses.
`tests/integration/test_encrypted_backup_restore.py` additionally uses actual PostgreSQL clients on
fresh UUID databases when `SITEFORGE_TEST_POSTGRES_URL` points to an explicit loopback fixture
service. It compares every application table and resumes the retained checkpoint/lease. A skipped
test is not a successful restore drill. Neither unit tests nor the disposable CI drill establish
scheduled production backups, off-site retention, key recovery, cross-version compatibility or
measured production RPO/RTO.

Encryption dependency: [PyCA cryptography 50.0.2 on PyPI](https://pypi.org/project/cryptography/50.0.2/),
with the [documented GCM authentication boundary](https://cryptography.io/en/stable/hazmat/primitives/symmetric-encryption/#cryptography.hazmat.primitives.ciphers.modes.GCM).
The version and its transitive dependencies are pinned in `requirements.lock`; preserve the matching
dependency audit and CI results with an accepted release.
