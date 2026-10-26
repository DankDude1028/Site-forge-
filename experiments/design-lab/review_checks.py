"""Run the full Rollwise checks on worktree b with no automatic fixes and print each result."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_loop as dl  # noqa: E402

ok, results = dl.run_checks(dl.WTS["b"])
for name, value in results.items():
    if value == "passed":
        print(f"{name}: passed")
    else:
        text = re.sub(r"\x1b\[[0-9;]*m", "", value)
        print(f"{name}: FAILED\n{text[-6000:]}")
print("ALL PASSED" if ok else "FAILED")
