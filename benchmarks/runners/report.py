"""Write honest machine-readable results and offline HTML comparison charts."""
from __future__ import annotations

import csv
import argparse
import io
import json
from pathlib import Path
from statistics import mean
from typing import Any


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def summarize(run: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in run.get("results", []) if not row.get("warmup")]
    successes = sum(bool(row.get("passed")) for row in rows)
    seconds = sum(row.get("wall_seconds", 0) for row in rows)
    warmup_seconds = sum(row.get("wall_seconds", 0) for row in run.get("results", []) if row.get("warmup"))
    def average(key):
        values = [row.get("completion", {}).get(key) for row in rows]
        values = [v for v in values if v is not None]
        return mean(values) if values else None
    categories = {category: {"tasks": len(values), "passed": sum(bool(row.get("passed")) for row in values),
                              "success_rate": mean(bool(row.get("passed")) for row in values)}
                  for category in ("tool", "research", "coding", "content", "workflow", "efficiency")
                  if (values := [row for row in rows if row["category"] == category])}
    watts = [sample.get("gpu_power_watts") for sample in run.get("telemetry_samples", []) if sample.get("gpu_power_watts") is not None]
    # Energy/cost deliberately remain estimates even when a power sample is measured.
    energy_estimate = mean(watts) * seconds / 3_600_000 if watts else None
    errors = sum(len(row.get("errors", [])) for row in rows)
    attempts = sum(row.get("request_attempts", len(row.get("errors", [])) + int("completion" in row)) for row in rows)
    diagnostic = sum(bool(row.get("passed")) or bool(row.get("diagnostic_fence_stripped", {}).get("passed")) for row in rows)
    return {"tasks": len(rows), "passed": successes, "success_rate": successes / len(rows) if rows else None,
            "schema_validity": mean(bool(row.get("schema_valid")) for row in rows) if rows else None,
            "request_error_rate": errors / attempts if attempts else None,
            "diagnostic_semantic_passed": diagnostic,
            "diagnostic_semantic_rate": diagnostic / len(rows) if rows else None,
            "success_per_hour": successes * 3600 / seconds if seconds else None,
            "mean_latency_seconds": average("latency_seconds"),
            "mean_ttft_seconds": average("time_to_first_token_seconds"),
            "mean_tokens_per_second": average("tokens_per_second"), "wall_seconds": seconds,
            "task_request_and_grade_seconds": seconds, "warmup_seconds": warmup_seconds,
            "model_load_seconds": run.get("load_seconds"),
            "runner_wall_seconds": run.get("runner_wall_seconds"),
            "successful_tasks_per_runner_hour": successes * 3600 / run["runner_wall_seconds"] if run.get("runner_wall_seconds") else None,
            "categories": categories,
            "estimated_gpu_energy_kwh": energy_estimate,
            "estimated_gpu_electricity_usd": energy_estimate * run["settings"].get("electricity_usd_kwh", 0.15) if energy_estimate is not None else None,
            "api_cost_usd_measured": 0, "estimation_limits": "GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization."}


def write_reports(output: Path, payload: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for run in payload.get("runs", []):
        run["summary"] = summarize(run)
    atomic_write(output / "results.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    stream = io.StringIO(newline="")
    fields = ["run_id", "model", "source_model", "quantization", "context", "run_status", "task_id", "category", "trial", "passed", "schema_valid", "score", "wall_seconds", "latency_seconds", "time_to_first_token_seconds", "output_tokens", "tokens_per_second", "prompt_sha256", "response_sha256", "errors"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for run in payload.get("runs", []):
        for row in run.get("results", []):
            if row.get("warmup"):
                continue
            flat = {key: run.get(key) for key in ("run_id", "model", "source_model", "quantization", "context")}
            flat["run_status"] = run["status"]
            flat.update({key: row.get(key) for key in fields if key in row})
            flat.update({key: row.get("completion", {}).get(key) for key in fields if key in row.get("completion", {})})
            flat["errors"] = json.dumps(row.get("errors", []))
            writer.writerow(flat)
    atomic_write(output / "results.csv", stream.getvalue())
    def fmt(value, digits=3):
        return "PENDING" if value is None else f"{value:.{digits}f}"
    lines = ["# SiteForge local model benchmark", "", "Only successful requests to the actual local LM Studio endpoint are measured. No fabricated hardware values or paid API calls are used.", "", "Partial suites cannot establish role winners. Source fidelity uses versioned synthetic source packets, and content scoring is an objective constraint proxy requiring editorial review. Coding tests use a bounded AST interpreter; model code never executes on the host.", "", "**Baseline limitations:** fixture v1.0/v1.1 left policy reason vocabulary and some numerical response types ambiguous. Their raw strict scores are preserved as diagnostics and must not establish general model quality or production winners. Fixture v1.2 documents these contracts. Compare only matching fixture/settings/context/quant runs.", "", "| Model / context | Fixture / JSON mode | Status | Tasks | Pass | Success/hour | TTFT s | Tokens/s | Peak GPU MiB |", "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for run in payload.get("runs", []):
        summary = run["summary"]
        lines.append(f"| {run['source_model']} / {run['context']} | {run['dataset_version']} / {'structured' if run['settings'].get('structured_json') else 'plain'} | {run['status']} | {summary['tasks']} | {summary['passed']} | {fmt(summary['success_per_hour'])} | {fmt(summary['mean_ttft_seconds'])} | {fmt(summary['mean_tokens_per_second'])} | {fmt(run.get('telemetry', {}).get('peak_gpu_used_mib'), 0)} |")
    for run in payload.get("runs", []):
        summary = run["summary"]
        lines.extend(["", f"## Run `{run['run_id']}`", "", f"Exact inference ID: `{run['model']}`; quantization: `{run['quantization']}`; fixture version `{run['dataset_version']}`, SHA256 `{run['dataset_sha256']}`.", "", f"Model load seconds: {fmt(run.get('load_seconds'))} ({run.get('load_measurement', 'not measured')}). Context requested: {run['context']}; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.", "", f"Settings: `{json.dumps(run['settings'], sort_keys=True)}`", "", "Category outcomes: " + "; ".join(f"{k} {v['passed']}/{v['tasks']}" for k, v in summary["categories"].items()), "", f"Secondary diagnostic allowing only removal of a complete markdown JSON fence: {summary['diagnostic_semantic_passed']}/{summary['tasks']}. This never changes primary strict success.", "", "Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.", "", f"Estimated GPU energy: {fmt(summary['estimated_gpu_energy_kwh'], 6)} kWh; estimated electricity: ${fmt(summary['estimated_gpu_electricity_usd'], 6)}. {summary['estimation_limits']}"])
        lines.extend(["", f"Timing separated: task requests/grading {fmt(summary['task_request_and_grade_seconds'])} s; warmups {fmt(summary['warmup_seconds'])} s; model load {fmt(summary['model_load_seconds'])} s; observed runner segment time {fmt(summary['runner_wall_seconds'])} s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is {fmt(summary['successful_tasks_per_runner_hour'])}/hour. Externally supplied load measurements are listed separately rather than silently included."])
        actual_parallel = run.get("actual_parallel", run.get("loaded_model_metadata", {}).get("parallel"))
        requested_parallel = run["settings"].get("parallel", 1)
        lines.extend(["", f"Loaded prediction parallelism: {actual_parallel if actual_parallel is not None else 'UNKNOWN'}; requested/default comparison condition: {requested_parallel}. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing."])
        if run.get("condition_warnings"):
            lines.extend(["", "Conditions: " + "; ".join(run["condition_warnings"])])
    if not payload.get("runs"):
        lines.extend(["", "Hardware benchmark results: **PENDING**. Run the documented harness on local LM Studio."])
    candidate_path = Path(__file__).parents[1] / "candidates.json"
    if candidate_path.exists():
        plan = json.loads(candidate_path.read_text(encoding="utf-8"))
        lines.extend(["", "## Candidate/context coverage", "", "Downloaded local inventory is recorded in `benchmarks/candidates.json`. Artifact bytes are disk sizes, not VRAM. Only complete v1.2 runs count as MEASURED below; context/quantization variants are never inferred.", "", "| Downloaded candidate | Quant | 4K | 8K | 16K | 32K |", "|---|---|---|---|---|---|"])
        for candidate in plan["candidates"]:
            coverage = []
            for context in plan["contexts"]:
                matched = [run for run in payload.get("runs", []) if run.get("source_model", "").split("@", 1)[0] == candidate["source_model"] and run.get("quantization") == candidate["quantization"] and run.get("context") == context and run.get("dataset_version") == plan["qualified_dataset_version"]]
                coverage.append("MEASURED" if any(run["status"] == "complete" for run in matched) else matched[-1]["status"] if matched else "PENDING")
            lines.append(f"| {candidate['source_model']} | {candidate['quantization']} | " + " | ".join(coverage) + " |")
        lines.extend(["", "Requested Qwen3.6-35B-A3B: absent under that exact name in local inventory; identity/license verification remains PENDING. Installed Qwen3.6-27B is a separate replacement candidate. Q5, Q6 and justified lower-bit variant sweeps remain PENDING because those artifacts are not in the captured inventory. Large models require actual RAM/VRAM/offload headroom before loading; absence of a result is not a quality failure."])
    lines.extend(["", "## Acceptance and routing", "", "Quality, tool/schema reliability, coding tests, speed, memory, sampled efficiency, and estimated electricity appear separately in the HTML charts. Role routing uses complete measured runs only, minimum 5 role samples and >=80% success; among qualifying models it chooses measured successful tasks/hour. A full 100-task run is necessary but does not establish production reliability. No cloud fallback is authorized.", "", "4K/8K/16K/32K context and Q4/Q5/Q6 sweeps are separate runs; unavailable variants stay PENDING. No quality extrapolation across quantizations. High RAM pressure may prevent large-model tests.", ""])
    atomic_write(output / "report.md", "\n".join(lines))
    chart_runs = [{"label": f"{run['source_model']} {run['quantization']} {run['context']} fixture{run['dataset_version']} {'structured' if run['settings'].get('structured_json') else 'plain'}", "status": run["status"],
                   **run["summary"], "gpu_mib": run.get("telemetry", {}).get("peak_gpu_used_mib")} for run in payload.get("runs", [])]
    data = json.dumps(chart_runs).replace("<", "\\u003c")
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>SiteForge measured model comparison</title>
<style>body{font:16px system-ui;background:#0e1724;color:#e5edf6;margin:32px;max-width:1200px}h1{font-size:30px}select{padding:9px}section{background:#182638;padding:20px;margin:18px 0;border-radius:10px}.row{margin:14px 0}.label{display:block;font-size:13px}.bar{background:#4cc9ba;height:22px;min-width:2px}.value{font-family:monospace}p{line-height:1.6}.pending{color:#e5bd6a}</style>
<h1>SiteForge local model comparison</h1><p>Actual local requests; unknown values remain PENDING. Partial runs are exploratory. v1.0/v1.1 strict scores have ambiguous response-contract limitations and cannot establish model quality or routing winners. v1.2 fixes those contracts; compare matching settings/fixtures.</p>
<label>Metric <select id="metric"><option value="success_rate">Quality: success fraction (measured)</option><option value="tool">Tool reliability (measured)</option><option value="coding">Coding pass fraction (measured)</option><option value="mean_tokens_per_second">Generation tokens/sec (measured)</option><option value="mean_ttft_seconds">First token seconds (measured, lower is better)</option><option value="gpu_mib">Peak total GPU memory MiB (sampled)</option><option value="success_per_hour">Successful tasks/hour (measured)</option><option value="estimated_gpu_energy_kwh">GPU energy kWh (estimate)</option><option value="estimated_gpu_electricity_usd">GPU electricity USD (estimate)</option></select></label><section id="chart"></section>
<p>CPU/RAM/raw outputs, request errors, per-task graders, model load time, exact model/quant/context, driver and LM Studio inventory are in results.json. Electricity excludes CPU/RAM/idle baseline and uses the configured rate. No API spending occurred. Compare like context, quantization and task coverage.</p>
<script>const runs=DATA;function draw(){const key=document.querySelector('#metric').value;const values=runs.map(r=>['tool','coding'].includes(key)?r.categories[key]?.success_rate:r[key]);const maximum=Math.max(0.001,...values.filter(v=>v!==null&&v!==undefined));const chart=document.querySelector('#chart');chart.replaceChildren();if(!runs.length){chart.textContent='PENDING: no hardware runs recorded';return}runs.forEach((r,i)=>{const row=document.createElement('div');row.className='row';const label=document.createElement('span');label.className='label';label.textContent=r.label+' · '+r.status;row.append(label);const value=values[i];const bar=document.createElement('div');bar.className='bar';bar.style.width=(value==null?0:90*value/maximum)+'%';row.append(bar);const number=document.createElement('span');number.className='value';number.textContent=value==null?'PENDING':Number(value).toFixed(4);row.append(number);chart.append(row)})}document.querySelector('#metric').onchange=draw;draw()</script></html>'''.replace("DATA", data)
    atomic_write(output / "model_comparison.html", document)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate reports after all benchmark runs finish")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results"))
    args = parser.parse_args()
    if (args.output / ".run.lock").exists():
        raise RuntimeError("A benchmark is active; regenerate reports after it completes")
    payload = json.loads((args.output / "results.json").read_text(encoding="utf-8"))
    write_reports(args.output, payload)


if __name__ == "__main__":
    main()
