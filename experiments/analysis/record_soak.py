import json
import sys
from datetime import datetime, timezone
from pathlib import Path
root = Path(sys.argv[1])
ev = root / 'docs/operations/evidence'
dead = json.loads((root / 'runtime/endurance-final-source/report.json').read_text(encoding='utf-8'))
history = json.loads((ev / 'endurance-history.json').read_text(encoding='utf-8'))
entry = {
    'local_report': 'runtime/endurance-final-source/report.json',
    'run_id': dead['run_id'], 'kind': dead['kind'],
    # The report still says "running": the process was hard-killed, so its finally block never ran.
    'status': 'killed_with_launching_session',
    'started_at': dead['started_at'], 'last_heartbeat_at': dead['heartbeat_at'],
    'implementation_sha256': dead['implementation_sha256'],
    'active_seconds': dead['active_seconds'], 'completed_tasks': dead['completed_tasks'],
    'failure_count': len(dead['failures']),
    'note': 'Launched by Start-Endurance.ps1 as a child of an agent session; no runner process remained at 2026-10-21T21:08:39Z and no finished_at was written.',
}
history["runs"] = [entry if r["run_id"] == entry["run_id"] else r for r in history["runs"]]
if False:
    history['runs'].insert(0, entry)
history['captured_at'] = datetime.now(timezone.utc).isoformat()
(ev / 'endurance-history.json').write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
live = json.loads((root / 'runtime/endurance-dbbff82/report.json').read_text(encoding='utf-8'))
start = {'source_commit': sys.argv[2], 'snapshot_captured_at': datetime.now(timezone.utc).isoformat(),
         'acceptance_status': 'PENDING',
         'scope_note': 'Point-in-time fixture snapshot, not live telemetry or 72-hour acceptance',
         'launcher': 'Task Scheduler (scripts/Install-EnduranceTask.ps1, pythonw.exe)', **live}
(ev / 'endurance-start.json').write_text(json.dumps(start, indent=2) + '\n', encoding='utf-8')
print(entry['status'], entry['active_seconds'], '| new run', live['run_id'], live['active_seconds'], live['completed_tasks'])
