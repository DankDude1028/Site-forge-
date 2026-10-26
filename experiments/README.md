# Experiments

Local experiments, kept so their code and logs are not lost. **None of this is part of SiteForge:**
the supervisor and worker never run it, CI does not lint, type-check or test it, and it was written
for one Windows PC. The results that count, with their costs and limits, are recorded in
[status](../docs/operations/status.md).

- [design-lab/](design-lab/README.md): design-quality experiments on the Rollwise template,
  2026-10-24 to 2026-10-26. Local models and Claude as designers, Opus as judge.
- `analysis/`: helpers for the benchmark and soak evidence.
  - `compare.py` compares complete v1.3 benchmark runs by category, with cut-offs and successes per hour.
  - `bench_peek.py` shows the progress of a benchmark results file.
  - `context_sweep.py` loads one model at several context sizes and records VRAM and RAM. It runs no inference.
  - `record_soak.py` was a one-off that recorded an interrupted soak run in the endurance history.

Run them from the repository root with `.\.venv\Scripts\python.exe`.
