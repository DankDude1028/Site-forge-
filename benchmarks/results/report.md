# SiteForge local model benchmark

Only successful requests to the actual local LM Studio endpoint are measured. No fabricated hardware values or paid API calls are used.

Partial suites cannot establish role winners. Source fidelity uses versioned synthetic source packets, and content scoring is an objective constraint proxy requiring editorial review. Coding tests use a bounded AST interpreter; model code never executes on the host.

**Exploratory baselines:** v1.0/v1.1/v1.2 raw strict fixed-budget outcomes are preserved unchanged. v1.2 still had undocumented workflow codes, ambiguous research status labels, and a content proxy that could accept incorrect units. These runs cannot establish model quality or authorize automatic routing. Only v1.3 has the revised contracts; compare matching fixture/settings/context/quant runs. Typed content facts are measured; editorial quality, originality and free-prose factuality remain human-review requirements.

| Model / context | Fixture / JSON mode | Status | Tasks | Pass | Success/hour | TTFT s | Tokens/s | Peak GPU MiB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| google/gemma-4-e4b / 4096 | 1.0.0 / plain | complete | 100 | 0 | 0.000 | 0.185 | 95.466 | 4828 |
| google/gemma-4-e4b / 4096 | 1.1.0 / structured | complete | 100 | 56 | 382.610 | 0.903 | 84.976 | 5178 |
| google/gemma-4-12b-qat / 4096 | 1.2.0 / structured | setup_failed | 0 | 0 | PENDING | PENDING | PENDING | PENDING |
| google/gemma-4-12b-qat / 4096 | 1.2.0 / structured | complete | 100 | 46 | 153.639 | 0.664 | 55.166 | 10248 |
| qwen/qwen3.5-9b / 4096 | 1.2.0 / structured | complete | 100 | 41 | 192.670 | 0.231 | 72.054 | 6971 |
| google/gemma-4-e4b / 4096 | 1.2.0 / structured | complete | 100 | 71 | 597.215 | 0.167 | 96.446 | 4839 |
| openai/gpt-oss-20b / 4096 | 1.2.0 / structured | complete | 100 | 71 | 660.908 | 0.821 | 32.745 | 10021 |
| google/gemma-4-e4b / 8192 | 1.2.0 / structured | interrupted | 46 | 35 | 887.191 | 0.172 | 97.914 | 4832 |
| google/gemma-4-e4b / 4096 | 1.3.0 / structured | complete | 100 | 81 | 641.062 | 0.177 | 96.346 | 4824 |
| google/gemma-4-e4b / 8192 | 1.3.0 / structured | complete | 100 | 81 | 636.376 | 0.196 | 96.271 | 4875 |
| openai/gpt-oss-20b / 4096 | 1.3.0 / structured | interrupted | 17 | 11 | 928.623 | 0.854 | 35.491 | 9970 |
| qwen/qwen3.5-9b / 4096 | 1.3.0 / structured | complete | 100 | 53 | 244.665 | 0.286 | 72.112 | 6885 |
| google/gemma-4-12b-qat / 4096 | 1.3.0 / structured | complete | 100 | 64 | 200.050 | 1.330 | 55.068 | 9513 |
| openai/gpt-oss-20b / 4096 | 1.3.0 / structured | complete | 100 | 87 | 811.844 | 0.984 | 32.619 | 9979 |
| google/gemma-4-e4b / 16384 | 1.3.0 / structured | partial | 5 | 5 | 1781.409 | 0.247 | 99.279 | 4915 |
| google/gemma-4-e4b / 32768 | 1.3.0 / structured | partial | 5 | 5 | 1793.289 | 0.239 | 100.226 | 5131 |

## Run `32ef97aa-2d45-4d48-b057-c795e7c9aea6`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.0.0`, SHA256 `a4c6e207245a6679c99f9653fbf9bbcf18474b417bc2bd5ea8e131a7075244da`.

Model load seconds: 12.870 (operator supplied actual measurement; see external command evidence). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 512, "retries": 1, "seed": 17, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 0/25; research 0/20; coding 0/20; content 0/15; workflow 0/15; efficiency 0/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 0/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.016161 kWh; estimated electricity: $0.002424. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 351.036 s; warmups 1.293 s; model load 12.870 s; observed runner segment time PENDING s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is PENDING/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: UNKNOWN; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `2beecc0f-2036-46eb-93e2-4bd58b077da4`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.1.0`, SHA256 `e37657af9fa6be80aaef7c203b571d9dd509160404188fd96917fc5be8328d24`.

Model load seconds: 12.870 (operator supplied actual measurement; see external command evidence). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 13/25; research 7/20; coding 15/20; content 15/15; workflow 1/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 56/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.021849 kWh; estimated electricity: $0.003277. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 526.907 s; warmups 1.160 s; model load 12.870 s; observed runner segment time PENDING s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is PENDING/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `5e57cf65-9f2c-4e3f-9dbc-30a36f5d8958`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_0`; fixture version `1.2.0`, SHA256 `b471484e20b0c1a6afef6bcc20242e6240a23b4c53a39dd68791a3d03b108d1d`.

Model load seconds: PENDING (not measured). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes:

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 0/0. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: PENDING kWh; estimated electricity: $PENDING. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 0.000 s; warmups 0.000 s; model load PENDING s; observed runner segment time PENDING s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is PENDING/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: UNKNOWN; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `19f72170-4b42-4e27-8a21-0b9a2d5aa4f0`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_0`; fixture version `1.2.0`, SHA256 `b471484e20b0c1a6afef6bcc20242e6240a23b4c53a39dd68791a3d03b108d1d`.

Model load seconds: 116.768 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 22/25; research 16/20; coding 3/20; content 0/15; workflow 1/15; efficiency 4/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 46/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.055461 kWh; estimated electricity: $0.008319. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 1077.852 s; warmups 2.425 s; model load 116.768 s; observed runner segment time 1203.578 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 137.590/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 4; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `1dac7e10-a409-4cb5-a8da-025bf050250f`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.2.0`, SHA256 `b471484e20b0c1a6afef6bcc20242e6240a23b4c53a39dd68791a3d03b108d1d`.

Model load seconds: 22.522 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 18/25; research 14/20; coding 2/20; content 0/15; workflow 2/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 41/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.041581 kWh; estimated electricity: $0.006237. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 766.076 s; warmups 5.578 s; model load 22.522 s; observed runner segment time 805.028 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 183.348/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `151969f8-1a28-4358-bc4e-e02538ac75d1`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.2.0`, SHA256 `b471484e20b0c1a6afef6bcc20242e6240a23b4c53a39dd68791a3d03b108d1d`.

Model load seconds: 7.931 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 19/25; research 16/20; coding 15/20; content 15/15; workflow 1/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 71/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.019859 kWh; estimated electricity: $0.002979. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 427.986 s; warmups 0.976 s; model load 7.931 s; observed runner segment time 446.288 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 572.724/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `527d1970-83dc-4610-8ce9-50aebdd25689`

Exact inference ID: `siteforge-benchmark`; quantization: `MXFP4`; fixture version `1.2.0`, SHA256 `b471484e20b0c1a6afef6bcc20242e6240a23b4c53a39dd68791a3d03b108d1d`.

Model load seconds: 72.645 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 18/25; research 17/20; coding 17/20; content 13/15; workflow 1/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 71/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.005862 kWh; estimated electricity: $0.000879. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 386.740 s; warmups 2.149 s; model load 72.645 s; observed runner segment time 473.596 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 539.700/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `b7281fbf-cfac-4b4f-9d2c-b49cb9e4ea47`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.2.0`, SHA256 `b471484e20b0c1a6afef6bcc20242e6240a23b4c53a39dd68791a3d03b108d1d`.

Model load seconds: 7.762 (measured CLI wall time). Context requested: 8192; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 19/25; research 16/20; coding 0/1

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 35/46. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.006440 kWh; estimated electricity: $0.000966. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 142.021 s; warmups 0.985 s; model load 7.762 s; observed runner segment time PENDING s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is PENDING/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `f9f48526-61a0-449b-a75b-8982ce34d2b7`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 27.235 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 21/25; research 14/20; coding 17/20; content 11/15; workflow 13/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 81/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.020996 kWh; estimated electricity: $0.003149. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 454.870 s; warmups 5.995 s; model load 27.235 s; observed runner segment time 502.144 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 580.710/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `fff39baa-b9fa-40da-85c7-d62ba0c578c8`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 6.860 (measured CLI wall time). Context requested: 8192; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 21/25; research 14/20; coding 17/20; content 11/15; workflow 13/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 81/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.021219 kWh; estimated electricity: $0.003183. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 458.220 s; warmups 0.997 s; model load 6.860 s; observed runner segment time 480.086 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 607.392/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `8fa9c004-3e06-4308-944d-661ff09723ea`

Exact inference ID: `siteforge-benchmark`; quantization: `MXFP4`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 20.496 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 11/17

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 11/17. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.000751 kWh; estimated electricity: $0.000113. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 42.644 s; warmups 2.551 s; model load 20.496 s; observed runner segment time PENDING s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is PENDING/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `01dd3203-2ceb-4670-bb74-5bd6e6f6a321`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 18.514 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 21/25; research 13/20; coding 1/20; content 0/15; workflow 13/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 53/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.041835 kWh; estimated electricity: $0.006275. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 779.843 s; warmups 5.623 s; model load 18.514 s; observed runner segment time 824.761 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 231.340/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `4130844c-9de0-48d9-911a-c1fb0bf13b5f`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_0`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 76.712 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 23/25; research 15/20; coding 2/20; content 6/15; workflow 14/15; efficiency 4/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 64/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.058716 kWh; estimated electricity: $0.008807. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 1151.713 s; warmups 2.849 s; model load 76.712 s; observed runner segment time 1268.400 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 181.646/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `8b02bd44-9095-4556-8ba4-641cdb9f7560`

Exact inference ID: `siteforge-benchmark`; quantization: `MXFP4`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 67.256 (measured CLI wall time). Context requested: 4096; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: tool 19/25; research 17/20; coding 17/20; content 15/15; workflow 14/15; efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 87/100. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.005863 kWh; estimated electricity: $0.000879. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 385.789 s; warmups 3.727 s; model load 67.256 s; observed runner segment time 488.723 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 640.854/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `0ead35db-dec6-469e-8e7c-2f4276faae5d`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 7.750 (measured CLI wall time). Context requested: 16384; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 5/5. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.000389 kWh; estimated electricity: $0.000058. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 10.104 s; warmups 1.023 s; model load 7.750 s; observed runner segment time 23.188 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 776.263/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Run `31022369-a3c7-4cae-ab5f-1c8c681c585a`

Exact inference ID: `siteforge-benchmark`; quantization: `Q4_K_M`; fixture version `1.3.0`, SHA256 `ac59d435468237015e8d16d778fa6e461c27c7f10a249af3c9bd388391f78369`.

Model load seconds: 4.482 (measured CLI wall time). Context requested: 32768; actual loaded context is recorded in native metadata and `lms ps` inventory; an unverified context must not be treated as measured.

Settings: `{"electricity_usd_kwh": 0.15, "max_tokens": 1024, "parallel": 1, "retries": 1, "seed": 17, "structured_json": true, "temperature": 0, "timeout_seconds": 120.0, "trials": 1, "warmups": 1}`

Category outcomes: efficiency 5/5

Secondary diagnostic allowing only removal of a complete markdown JSON fence: 5/5. This never changes primary strict success.

Measured telemetry includes total GPU memory across processes, system RAM/CPU, and recognized LM Studio process RAM/CPU. Sampling can miss brief peaks; process names and WDDM counters vary. Unknown counters remain null.

Estimated GPU energy: 0.000404 kWh; estimated electricity: $0.000061. GPU-only sampled power estimate excludes idle baseline, CPU, RAM, monitor, overhead and amortization.

Timing separated: task requests/grading 10.037 s; warmups 0.640 s; model load 4.482 s; observed runner segment time 19.545 s. Headline successful tasks/hour uses measured task time; runner throughput including metadata, report writes, warmups and in-run loading is 920.956/hour. Externally supplied load measurements are listed separately rather than silently included.

Loaded prediction parallelism: 1; requested/default comparison condition: 1. Sequential requests do not remove cache memory allocated to extra slots. Different/unknown parallelism makes memory and throughput rankings conditional and disqualifies automatic routing.

## Candidate/context coverage

Downloaded local inventory is recorded in `benchmarks/candidates.json`. Artifact bytes are disk sizes, not VRAM. Only complete v1.3 runs count as MEASURED below; context/quantization variants are never inferred.

| Downloaded candidate | Quant | 4K | 8K | 16K | 32K |
|---|---|---|---|---|---|
| google/gemma-4-e4b | Q4_K_M | MEASURED | MEASURED | partial | partial |
| google/gemma-4-12b-qat | Q4_0 | MEASURED | PENDING | PENDING | PENDING |
| qwen/qwen3.5-9b | Q4_K_M | MEASURED | PENDING | PENDING | PENDING |
| openai/gpt-oss-20b | MXFP4 | MEASURED | PENDING | PENDING | PENDING |
| qwen/qwen3.6-27b | Q4_K_M | PENDING | PENDING | PENDING | PENDING |
| qwen/qwen3.8-27b | Q4_K_M | PENDING | PENDING | PENDING | PENDING |

Requested Qwen3.6-35B-A3B: absent under that exact name in local inventory; upstream identity and license were verified in docs/research/model-candidates.md; local hardware benchmarking remains PENDING. Installed Qwen3.6-27B is a separate replacement candidate. Q5, Q6 and justified lower-bit variant sweeps remain PENDING because those artifacts are not in the captured inventory. Large models require actual RAM/VRAM/offload headroom before loading; absence of a result is not a quality failure.

## Acceptance and routing

Quality, tool/schema reliability, coding tests, speed, memory, sampled efficiency, and estimated electricity appear separately in the HTML charts. Role routing uses complete measured runs only, minimum 5 samples and >=80% success in every required role category; among qualifying models it chooses measured successful tasks/hour. A full 100-task run is necessary but does not establish production reliability. No cloud fallback is authorized.

4K/8K/16K/32K context and Q4/Q5/Q6 sweeps are separate runs; unavailable variants stay PENDING. No quality extrapolation across quantizations. High RAM pressure may prevent large-model tests.
