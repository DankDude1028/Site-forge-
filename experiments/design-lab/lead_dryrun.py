"""Offline checks of lead_loop: request sizes and worst-case costs, the build-time gate and file writing. No API calls."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lead_loop as ll  # noqa: E402

import design_loop as dl  # noqa: E402
from siteforge.advisor import build_request  # noqa: E402
from sqlalchemy import text  # noqa: E402

base = __import__("json").loads((ll.BASELINE / "opus-score.json").read_text(encoding="utf-8"))["review"]
state = {"best_review": base, "note": None, "concept": None}
wt = dl.WTS["a"]
dl.restore(wt, {})
brief = ll.brief_for("redesign", state, wt)
for arm, cfg in ll.ARMS.items():
    doc = build_request("design_lead", dl.SITE_ID, brief, documents=ll.documents(wt),
                        screenshots=[(s.name, s.read_bytes()) for s in ll.shots_of(ll.BASELINE)],
                        effort="high", max_tokens=32_000, model=cfg["model"])
    print(arm, "input bound", doc["input_token_bound"], "worst case $", doc["max_cost"], "fallbacks", doc["fallbacks"])
print("brief chars", len(brief), "docs", [name for name, _ in ll.documents(wt)])

# Build-time gate: unsafe imports and code are refused, safe font and component imports pass.
index = wt / dl.REL / "src/pages/index.astro"
original = index.read_text(encoding="utf-8")
index.write_text(original.replace("import '../styles/site.css';", "import '../styles/site.css';\n"
                                  "import '@fontsource/bricolage-grotesque/latin-800.css';\n"
                                  "import Hero from '../components/Hero.astro';\nimport fs from 'node:fs';\n"
                                  "import x from 'some-package';\nconst k = process.env.KEY;"), encoding="utf-8")
print("build-time problems:", ll.build_time_problems(wt))
dl.restore(wt, {})
written, refused = ll.apply_files(wt, [{"path": "src/styles/site.css", "content": "a{}"},
                                       {"path": "./src/components/Calculator.astro", "content": "x"},
                                       {"path": "src/styles/base.css", "content": "x"},
                                       {"path": "../../../etc/x.astro", "content": "x"},
                                       {"path": "packages/site-templates/label-roll-planner/src/components/Hero.astro",
                                        "content": "<div class='hero'></div>"}])
print("written", written, "refused", refused, "changed", dl.changed(wt))
dl.restore(wt, {})
print("clean after restore:", dl.changed(wt) == [])
judge = dl.Judge()
with judge.db.transaction() as session:
    rows = session.execute(text("select period, limit_amount, used_amount, reserved_amount from budgets "
                                "order by period")).all()
print("budgets:", rows)
judge.db.dispose()
