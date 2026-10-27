# Isolated HTTP/process recovery drill

Run from the repository with its installed Python dependencies:

```powershell
.\.venv\Scripts\python.exe -m siteforge.runtime_drill --root runtime/runtime-drill-001
```

The directory must be new or empty. The drill creates its own SQLite database,
tenant, one-hour random credentials and artifact workspace. It never loads the
user's `.env`, inherits provider credentials, starts LM Studio or calls providers.
All HTTP targets are the owned API on `127.0.0.1`; no cloud service is required.

Actual subprocesses run Uvicorn and `WindowsWorker`. The first worker writes a
real research result checkpoint and is abruptly killed before completion. The
owned API is also killed, an HTTP connection failure is observed, and a new API
process reads the preserved checkpoint. After the actual 15-second lease expires,
a new worker recovers research and completes the dependent trusted template build
and static QA. A stale completion token must be rejected. The fixture API uses
zero retry backoff for this bounded drill; ordinary application backoff is unchanged.

`report.json` records actual process IDs, UTC event times, elapsed time, task
attempts, checkpoint/artifact hashes and cleanup status. Tokens are only passed
through process environment, never command arguments or evidence. Owned processes
are stopped on success/failure; retained files are not deleted or overwritten.
An interrupted parent may require the operator to reconcile the recorded PIDs.

This proves a bounded SQLite HTTP/process recovery path. It is **not** a 72-hour
test, PostgreSQL recovery, physical network outage, complete PC reboot/offline
test, browser/build acceptance, or hosted provider reconciliation. Those gates
remain separate. Dependencies are Python, the repository packages, a permitted
loopback listener and permission to create/stop owned child processes.
