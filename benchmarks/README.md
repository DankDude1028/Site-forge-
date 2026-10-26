# Reproducible local model benchmark

This suite makes actual streaming requests to LM Studio on loopback. It never
downloads a model, calls a paid API, executes generated code on the host, or
performs a tool side effect. Native calls are recorded, schema checked, and
graded as proposals. Source packets are frozen synthetic fixtures, so this tests
source fidelity and evidence handling rather than live web knowledge.
Workflow benchmark tasks grade ordered recovery-plan proposals; actual durable
queue/worker recovery is exercised by integration/endurance tests separately.

Version 1.3.0 contains **100 distinct tasks**: 25 tool/JSON/policy (five native
OpenAI function calls), 20 source fidelity, 20 coding tasks with executable
fixture tests, 15 factual utility drafts, 15 workflow/recovery plans, and five
efficiency/context tasks. The prior v1.0.0 fixture remains immutable for the
initial measured run. The v1.1 revision replaced nested response placeholders
with JSON Schema and added actual native tool calling. v1.2 documents the
global policy action/reason vocabulary and numeric/boolean/string/null research
answer contract. v1.2 still had undocumented workflow codes, ambiguous research
status labels, and a content proxy that could accept incorrect units. Its raw
scores remain exploratory and cannot authorize routing. v1.3 publishes a sorted
global workflow API vocabulary with distractors, clarifies status/attempt/query
contracts, requires native-call provenance, and grades typed content fact slots
by meaning, numeric value and canonical unit. Earlier raw strict scores remain
unchanged; they cannot establish model quality or routing winners. Compare
models using the same fixture hash, system prompt, context, settings and task
coverage; do not mix versions into one headline score.

## Windows commands

From the repository in PowerShell, with LM Studio's local server running:

```powershell
$python = Join-Path $PWD '.venv\Scripts\python.exe'
lms ls
lms ps --json
lms unload --all
lms load 'google/gemma-4-e4b@q4_k_m' --identifier siteforge-benchmark --context-length 4096 --parallel 1 --gpu max --yes
& $python -m benchmarks.runners.run --model siteforge-benchmark --source-model 'google/gemma-4-e4b@q4_k_m' --quantization Q4_K_M --context 4096 --structured-json --max-tokens 1024
```

The exact inference ID is `--model`; `--source-model` records the downloaded
model/variant. Quantization must be supplied from `lms ps --json`, not guessed.
`--structured-json` uses LM Studio's documented `response_format: json_schema`
grammar constraint on non-native tasks. Schemas contain property names/types,
never expected answer constants or enumerations. Its value is recorded in run
settings. The unconstrained baseline remains a distinct experiment. See the
[official structured output documentation](https://lmstudio.ai/docs/developer/openai-compat/structured-output).
If `--load` is supplied, the runner unloads all models then loads the requested
existing local variant and measures CLI wall-clock load duration. It never
downloads. Without `--load`, load duration remains PENDING unless an actual
external measurement is supplied with `--load-seconds`.

```powershell
& $python -m benchmarks.runners.run --model siteforge-benchmark --source-model 'qwen/qwen3.5-9b@q4_k_m' --quantization Q4_K_M --context 4096 --load
& $python -m benchmarks.runners.run --model siteforge-benchmark --source-model 'qwen/qwen3.5-9b@q4_k_m' --quantization Q4_K_M --context 8192 --load
& $python -m benchmarks.runners.run --model siteforge-benchmark --source-model 'qwen/qwen3.5-9b@q4_k_m' --quantization Q4_K_M --context 16384 --load
& $python -m benchmarks.runners.run --model siteforge-benchmark --source-model 'qwen/qwen3.5-9b@q4_k_m' --quantization Q4_K_M --context 32768 --load
```

Use `--trials 3` for repeated trials and `--warmups 2` after loading. Default
settings are one warmup, one trial, temperature 0, seed 17, max 512 generated
tokens and one bounded retry on a transport error. Reasoning-heavy models can
hit the output limit; keep that failure visible, and run a separately labeled
larger-token experiment. `finish_reason` is retained for every completion.
Invalid JSON/answers are task failures, not automatic repair opportunities.

`--limit 5` and `--category coding` run subsets and are marked **partial**.
`--resume` skips saved task/trial pairs from a run with exactly matching model,
quant/context, task selection, fixture hash and inference settings. A lock
prevents concurrent benchmark processes sharing one output directory. Inspect
the PID recorded in `.run.lock` before removing a stale lock after a hard kill.
Only one loaded LLM is allowed. The actual context is verified from `lms ps`;
if the CLI is unavailable, it stays unverified and cannot authorize routing.
Prediction parallelism defaults to one and is passed to `lms load`; an already
loaded model with extra slots remains a measured conditional observation and
cannot authorize routing. Extra cache slots change memory even for serial calls.

## Results and measurement limits

Every task is saved immediately into `results/results.json`; rerunning the
reports also creates `results.csv`, `report.md`, and a standalone offline
`model_comparison.html` containing interactive metric charts. Raw prompts,
answers, reasoning text, prompt/response SHA256, fixture SHA256, all transport
errors, output usage, finish reason, exact model metadata, native API inventory,
CLI/runtime version, running Windows app VERSIONINFO, driver, settings and context are retained. No task output
is trusted as an instruction.

After all runs finish, `python -m benchmarks.runners.report` regenerates reports
with the current report version; it refuses to overwrite an active run.

TTFT is wall-clock time until the first nonempty content/reasoning/tool chunk.
Tokens/sec uses server-reported completion tokens over time after that first
chunk. It is null when token counts are unavailable; chunk counts are never
substituted for tokens. Latency includes request and stream processing. Peak
GPU memory is total device memory, not model-exclusive memory. RAM/CPU include
separate whole-system and recognized LM Studio processes. Samples every second
can miss brief peaks. Unsupported counters are null, not zero. Sampled GPU
power integrated over task time yields an explicitly **estimated** GPU-only
energy/cost value at a configurable electricity rate, excluding CPU/RAM/idle
baseline and hardware amortization. Actual metered API spend is zero.

Strict JSON/schema/task success is the primary result. A fenced answer is a
strict failure; a separate `diagnostic_fence_stripped` field records whether its
contents would satisfy the task. Diagnostics never overwrite the primary score.
To diagnose an older baseline that predates that field, run
`python -m benchmarks.runners.diagnose`; it writes `diagnostic_results.json`
separately and leaves all original scores and raw responses untouched.
Content grading compares unordered typed fact slots `{key,value,unit}`, citations,
title/advice bounds and an explicitly required literal advice keyword. Numbers
are compared numerically, but booleans cannot substitute for numbers. Fabricated
units, swapped meanings and duplicate slots fail. Claim-related phrases produce
review warnings instead of primary failures; a correct negated claim is not
failed by substring matching. This is
not a claim that an objective grader can establish originality or editorial
quality or free-prose factuality; these require human review. The coding interpreter supports a bounded
documented Python subset and executes tests against AST nodes, never `exec` or
`eval`; no imports, I/O, reflection, recursion or arbitrary attributes.

Q4/Q5/Q6 and lower-bit variants require their own downloaded artifact and
complete run; no quality extrapolation is performed. The 4K/8K/16K/32K request
matrix is supported, but tasks exercise at most several thousand input tokens:
larger context runs measure allocation and short-task behavior, not retrieval
accuracy across a filled 32K window. Large models that exceed actual RAM/VRAM
headroom must remain PENDING instead of forcing an unsafe allocation.

`siteforge.model_router.ModelRouter` selects complete, measured, verified-context
runs using qualified v1.3.0 contracts only. It requires at least five samples and >=80% success in the relevant
role categories, then maximizes successful tasks/hour. Missing evidence raises
`NoMeasuredModel`. Paid escalation has no implicit route.

## Validation

```powershell
& $python -m pytest tests/unit/test_benchmark.py tests/unit/test_lmstudio.py -q
& $python -m ruff check benchmarks siteforge/lmstudio.py siteforge/model_router.py
& $python -m mypy benchmarks siteforge/lmstudio.py siteforge/model_router.py
```

Fixture generation is deterministic: `python -m benchmarks.datasets.build`
rebuilds v1.3.0 only. Changing a fixture requires a version/hash change. Runner
refuses a file whose SHA256 disagrees with its versioned manifest.
