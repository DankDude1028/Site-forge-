"""Check, render and score a lead's files that a stopped run left unscored. Usage: score_pending.py <arm> <files.json>"""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lead_loop as ll  # noqa: E402

import design_loop as dl  # noqa: E402

arm, files = sys.argv[1], Path(sys.argv[2])
wt, port = dl.WTS[ll.ARMS[arm]["wt"]], dl.PORTS[ll.ARMS[arm]["wt"]]
dl.restore(wt, json.loads(files.read_text(encoding="utf-8")))
print("harness:", dl.source_autofix(wt))
problems = ll.build_time_problems(wt) + dl.gate(wt)
if problems:
    raise SystemExit(f"gate: {problems}")
entry: dict = {}
ok, results = dl.checks_with_fixes(wt, port, entry, f"[{arm}] pending")
if not ok:
    raise SystemExit(f"checks failed: {[name for name, value in results.items() if value != 'passed']}")
render = files.parent / f"render-{files.stem.split('-')[-1]}"
shots = dl.capture(wt, port, render)
lint = json.loads((render / "lint.json").read_text(encoding="utf-8"))
if lint:
    raise SystemExit(f"visual lint: {lint}")
judge = dl.Judge()
scored = judge.score(shots, render)
(render / "scored-files.json").write_text(json.dumps(dl.snapshot(wt), indent=1), encoding="utf-8")
review = scored.get("review") or {}
print(f"scored {ll.rank(review)} for ${Decimal(scored['measured_cost'])}: {review.get('summary', '')}")
judge.db.dispose()
