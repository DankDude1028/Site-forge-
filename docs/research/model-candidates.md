# Local model candidates and benchmark decisions

Research date: **2026-10-21**. Target: Windows 11, RTX 4070 Ti with 12 GB VRAM, i5-12400F, 16 GB system RAM, LM Studio. This research informs test order; only recorded runs on the owner's computer may establish routing winners.

## Evidence labels

- **Verified upstream** means an official author model card or first-party runtime document was opened on the research date.
- **Published artifact size** means a publisher's downloadable file size. It is neither measured VRAM nor a throughput measurement.
- **Local inventory** means the local inspection performed during this implementation session. Preserve the raw environment and model inventory with benchmark output; inventory alone is not a benchmark.
- **Estimate** means an explicit planning calculation. **Pending** means the corresponding experiment has not completed.

## Names, licenses, and compatibility

Every candidate explicitly requested in the handoff exists in an official model repository as of the research date. In particular, Qwen3.6-35B-A3B and Qwen3.8-27B are verified; the word "purported" in the handoff is not a reason to reject them. Instruction-tuned Gemma variants carry the `-it` suffix and should be used for agent evaluations.

| Requested candidate | Verified upstream identity and architecture | License stated on card | Context advertised upstream | LM Studio test interpretation |
| --- | --- | --- | --- | --- |
| Gemma 4 E4B | [`google/gemma-4-E4B-it`](https://huggingface.co/google/gemma-4-E4B-it), 4.5B effective, about 8B including embeddings | Apache 2.0 | 128K | Native function calling and reasoning; effective parameter count must not be used as storage count. |
| Gemma 4 12B | [`google/gemma-4-12B-it`](https://huggingface.co/google/gemma-4-12B-it), 11.95B, unified multimodal dense architecture | Apache 2.0 | 256K | Compare ordinary PTQ with the separately identified QAT artifact. |
| Qwen3.5-9B | [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B), dense, hybrid linear/full attention, vision encoder | Apache 2.0 | 262,144 native | Useful baseline for all seven roles; smaller storage than 27B/35B candidates. |
| Qwen3.6-35B-A3B | [`Qwen/Qwen3.6-35B-A3B`](https://huggingface.co/Qwen/Qwen3.6-35B-A3B), 35B total, 3B active, MoE | Apache 2.0 | 262,144 native | Active parameters describe compute, not the resident expert weights. |
| Qwen3.8-27B | [`Qwen/Qwen3.8-27B`](https://huggingface.co/Qwen/Qwen3.8-27B), dense, hybrid attention | Apache 2.0 | 262,144 native | Stronger upstream coding/agent candidate, but materially exceeds 12 GB at normal Q4. |
| gpt-oss-20b | [`gpt-oss-20b` official OpenAI documentation](https://developers.openai.com/api/docs/models/gpt-oss-20b), 21B total, 3.6B active | Apache 2.0 | 131K in LM Studio model metadata | Native tools, structured output, configurable reasoning. Evaluate the supplied MXFP4 artifact, not a fictitious ordinary Q4 equivalent. |

These are model licenses, not licenses for retrieved web content, third-party datasets, or generated sites. Preserve model notices and identify exact derivative/artifact revisions. This review did not assess every fine-tune's licensing or authorize paid hosted inference.

The [LM Studio Gemma catalog](https://lmstudio.ai/models/gemma-4) and dedicated [Qwen3.6](https://lmstudio.ai/models/qwen/qwen3.6-35b-a3b), [Qwen3.8](https://lmstudio.ai/models/qwen/qwen3.8-27b), and [gpt-oss](https://lmstudio.ai/models/openai/gpt-oss-20b) entries establish available GGUF integrations. On this NVIDIA/Windows machine use the llama.cpp GGUF backend; MLX downloads are not Windows CUDA artifacts. Runtime compatibility and tool parsing must still pass a local smoke test for each exact installed runtime revision.

## Published artifacts and real hardware fit

The following numbers were read from the LM Studio Community publisher's file listings. All sizes in this table are decimal GB; do not compare them numerically to GiB without converting. Text-only tests should record whether a multimodal projector was also loaded.

| Artifact family | Q4_K_M file | Q6_K file | Additional projector file | First-party artifact listing |
| --- | ---: | ---: | ---: | --- |
| Gemma 4 E4B-it | 5.34 GB | 6.22 GB | 0.992 GB BF16 | [Published files](https://huggingface.co/lmstudio-community/gemma-4-E4B-it-GGUF/tree/main) |
| Gemma 4 12B-it | 7.38 GB | 9.79 GB | 0.175 GB BF16 | [Published files](https://huggingface.co/lmstudio-community/gemma-4-12B-it-GGUF/tree/main) |
| Qwen3.5-9B | 5.63 GB | 7.36 GB | 0.922 GB BF16 | [Published files](https://huggingface.co/lmstudio-community/Qwen3.5-9B-GGUF/tree/main) |
| Qwen3.6-35B-A3B | 21.2 GB | 28.5 GB | 0.903 GB BF16 | [Published files](https://huggingface.co/lmstudio-community/Qwen3.6-35B-A3B-GGUF/tree/main) |
| Qwen3.8-27B | 16.8 GB | 22.4 GB | 0.931 GB BF16 | [Published files](https://huggingface.co/lmstudio-community/Qwen3.8-27B-GGUF/tree/main) |
| gpt-oss-20b | 12.1 GB **MXFP4**, not Q4_K_M | Not supplied in this listing | Text model | [Published files](https://huggingface.co/lmstudio-community/gpt-oss-20b-GGUF/tree/main) |

**Local inventory communicated by the environment inspection on 2026-10-21:** RTX 4070 Ti, 12 GB VRAM, driver 617.42; 16 GB RAM with approximately 330 MB free at inspection. Downloaded models included Qwen3.8-27B around 17.74 GB Q4, Qwen3.6-27B around 17.48 GB Q4, gpt-oss-20b around 12.11 GB MXFP4, Gemma 4 E4B around 5.34 GB Q4, Gemma 4 12B QAT around 7.15 GB Q4_0, and Qwen3.5-9B around 5.63 GB Q4. Those inventory sizes can differ from the publisher table because the exact quantizer, revision, included tensors, and file accounting differ. The locally installed **Qwen3.6-27B is not Qwen3.6-35B-A3B**; never label a run with the other model's name.

No tokens/sec, task success, TTFT, peak inference memory, or completed load duration is asserted here. Those values belong in measured benchmark records. Very low available system memory is a current feasibility constraint. Keep supervisor/database/browser workloads light during model tests, avoid parallel models, and retain failed/OOM/timeout runs as evidence. Do not silently report only successful runs.

**Inference from storage and hardware, not a measurement:** E4B and Qwen3.5-9B Q4/Q6 have the best initial chance of full GPU placement with useful context. Gemma 12B Q4/QAT is a plausible larger candidate. Its Q6 has less room for context and runtime allocations. gpt-oss MXFP4 is marginal for full 12 GB placement; partial CPU placement may be necessary. Qwen 27B Q4 and 35B Q4 cannot fit their weights entirely in 12 GB and need substantial CPU offload or a separately evaluated lower-bit artifact. Sixteen GB total RAM is also restrictive for these larger models. SSD capacity does not substitute for RAM bandwidth or GPU memory.

OpenAI's [Transformers execution guide](https://developers.openai.com/cookbook/articles/gpt-oss/run-transformers) quotes about 16 GB VRAM for gpt-oss-20b MXFP4 and notes different hardware support for its native MXFP4 kernels. That is a Transformers runtime statement, not proof of the exact LM Studio GGUF memory footprint on Ada. The GGUF artifact and LM Studio engine must be measured separately; do not assume native Blackwell/Hopper FP4 acceleration on the RTX 4070 Ti.

## Q4, Q5, Q6, and lower-bit experiments

[llama.cpp's tensor encoding reference](https://github.com/ggml-org/llama.cpp/wiki/Tensor-Encoding-Schemes) gives block storage rates of 4.5 bits/weight for Q4_K, 5.5 for Q5_K, and 6.5625 for Q6_K. A mixed `Q4_K_M` model is not a uniform four-bit array. Metadata, embeddings, tensor choices, vision encoders, runtime buffers, KV cache, and alignment alter file and memory totals. The [quantizer source](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/quantize.cpp) contains model-specific size/perplexity examples; they are not SiteForge quality measurements.

For **planning only**, a uniform encoding calculation `parameters * block_bits_per_weight / 8 / 1e9` yields the following storage estimates. These are not expected measured VRAM and are deliberately separate from published files.

| Nominal stored parameters | Q4_K estimate | Q5_K estimate | Q6_K estimate |
| --- | ---: | ---: | ---: |
| 8B | 4.50 GB | 5.50 GB | 6.56 GB |
| 9B | 5.06 GB | 6.19 GB | 7.38 GB |
| 12B | 6.75 GB | 8.25 GB | 9.84 GB |
| 27B | 15.19 GB | 18.56 GB | 22.15 GB |
| 35B | 19.69 GB | 24.06 GB | 28.71 GB |

Compare Q4_K_M and Q6_K first for installed small models. Add Q5_K_M when a traceable exact artifact is available; the LM Studio Community listings above do not provide a Q5 entry. Record a missing quantization as unavailable rather than relabeling Q6 as Q5. Raising precision can preserve quality but consume more memory and alter speed; the direction and size of the throughput effect depend on kernels and offload.

The verified [Google 12B QAT GGUF](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf) and [E4B QAT GGUF](https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf) are additional candidates. [Google's overview](https://ai.google.dev/gemma/docs/core) documents their quantization-aware training and local GGUF format. Treat QAT as a separate trained artifact; its claims do not establish local parity or justify comparing it under the ordinary PTQ artifact ID. QAT 12B is already present locally and deserves an early run.

IQ3/IQ2 or Q2_K variants of 27B/35B are optional research arms only. They may reduce storage enough to change placement, but compression can damage tools, retrieval, code, and calibration. Test the full task suite and fail dangerous actions even when other answers are fluent. Never copy the full-precision model's published quality scores to a two-bit quant. Do not reduce MoE expert counts as an invisible fit workaround: that changes the tested inference configuration and can change behavior.

## Context and cache accounting

Benchmark 4,096, 8,192, 16,384, and 32,768 token configured contexts only when the model loads safely. The advertised 128K/256K window is a model capability ceiling, not a promise that it fits this PC. A larger configured window can allocate additional cache even for a short prompt. Weight precision and KV precision are separate settings.

For ordinary full attention, an FP16 K/V planning formula is `tokens * full_attention_layers * 2(K,V) * kv_heads * head_dimension * 2 bytes`. For the hybrid Qwen architectures in the cards, applying it **only to their full-attention layers** estimates the following. Recurrent/linear-attention states, batching, alignment, and backend policy add overhead, so these totals are incomplete estimates.

| Model | Full-attention assumptions from card | 4K | 8K | 16K | 32K |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen3.5-9B | 8 layers, 4 KV heads, dimension 256 | 128 MiB | 256 MiB | 512 MiB | 1,024 MiB |
| Qwen3.6-35B-A3B | 10 layers, 2 KV heads, dimension 256 | 80 MiB | 160 MiB | 320 MiB | 640 MiB |
| Qwen3.8-27B | 16 layers, 4 KV heads, dimension 256 | 256 MiB | 512 MiB | 1,024 MiB | 2,048 MiB |

Gemma uses sliding windows and additional architecture features; do not substitute a naive all-layers full-attention estimate. Run [`lms load --estimate-only <model-key> --context-length 4096`](https://lmstudio.ai/docs/cli/local-models/load) for each context/placement setting, store the estimate, and then separately store the measured load/inference peaks. The CLI estimator accounts for context and other load features; it remains an estimate. CPU offload can free VRAM but moves pressure to already constrained RAM and can increase latency. Run one GPU job at a time.

## Agent quality evidence and evaluation boundaries

Official cards provide useful screening evidence, with different harnesses and settings. Examples: Qwen3.5-9B reports BFCL-V4 66.1, TAU2 79.1, and LiveCodeBench v6 65.6. Qwen3.6-35B-A3B reports SWE-bench Verified 73.4 and Terminal-Bench 2.0 51.5. Qwen3.8-27B reports SWE-bench Pro 61.7 and Terminal Bench 2.1 73.0. Google's instruction-tuned card reports LiveCodeBench v6 52.0 for E4B and 72.0 for 12B, with Tau2 42.2 and 69.0 respectively. These are **publisher-reported upstream scores**, not results on this computer or its quantized files. See the [9B](https://huggingface.co/Qwen/Qwen3.5-9B), [35B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B), [27B](https://huggingface.co/Qwen/Qwen3.8-27B), and [Gemma instruction-tuned](https://huggingface.co/google/gemma-4-12B-it) cards for settings.

Benchmark versions, tools, prompt templates, context, sampling, and reasoning budgets differ. Scores are not directly interchangeable and do not establish a safe autonomous agent. SiteForge must evaluate schema validity independently from factual correctness and permitted actions. Constrained JSON can produce well-formed incorrect decisions. A content score cannot compensate for an unauthorized purchase or fabricated citation.

## LM Studio API implementation contract

Use localhost only, preferably `http://127.0.0.1:1234`; never expose inference publicly. SiteForge's outbound worker, not the supervisor, brokers inference. [LM Studio authentication](https://lmstudio.ai/docs/developer/core/authentication) requires 0.4.0+ and must be explicitly enabled in server settings; it is off by default. Supply a local scoped API token through environment/secret storage and redact it from logs.

The [native API overview](https://lmstudio.ai/docs/developer/rest) recommends `/api/v1/*` for 0.4.0+. Use these concrete contracts:

| Operation | Endpoint and required data | Evidence to retain |
| --- | --- | --- |
| Inventory | [`GET /api/v1/models`](https://lmstudio.ai/docs/developer/rest/list) | `models[].key`, quantization object, `size_bytes`, format, capabilities, loaded instance IDs/configs |
| Load | [`POST /api/v1/models/load`](https://lmstudio.ai/docs/developer/rest/load), `model`, `context_length`, `echo_load_config: true` | Returned `instance_id`, `load_time_seconds`, actual `load_config` |
| Unload | [`POST /api/v1/models/unload`](https://lmstudio.ai/docs/developer/rest/unload), **`instance_id`** | Unload acknowledgment; do not pass a model key under the wrong field |
| Controlled application tools | [`POST /v1/chat/completions`](https://lmstudio.ai/docs/developer/openai-compat/tools), OpenAI-style function definitions | Parsed `tool_calls`, original arguments, deterministic policy decision, tool result |
| Schema-constrained answer | [`POST /v1/chat/completions`](https://lmstudio.ai/docs/developer/openai-compat/structured-output), `response_format` JSON schema | Raw response, schema validation result, objective task grade |

The native chat endpoint supports MCP integrations but its feature table does not support arbitrary custom tool definitions; keep SiteForge's controlled tool dispatcher on chat completions. LM Studio can return malformed/unparsed model tool text as ordinary content; a model card's tool capability does not guarantee tool-call reliability. Never execute such text as shell code or infer permission from it.

Configured context belongs in the load call for chat completions. Capture effective load settings rather than assuming a `context_length` key in a completions request changed the model. For latency record request start, first streamed generated token, finish time, token counts, and whether reasoning or final text produced that token. Server-native statistics and wall-clock measurements have different scopes and should be named separately.

## Initial test order and routing decision

1. Verify the installed versions, inventory, GPU baseline, system memory, and one-model constraint.
2. Run Gemma E4B Q4 and Qwen3.5-9B Q4 at 4K, then 8K. Run Gemma 12B QAT Q4_0 independently. Preserve warmup and cold-load evidence.
3. Expand to 16K/32K and Q5/Q6 only when estimated and measured headroom permits. Record blocked contexts without synthetic performance values.
4. Run gpt-oss-20b with explicitly recorded partial offload if required. Qwen3.8-27B and Qwen3.6-35B-A3B are optional offload/lower-bit comparisons; verify that the latter is actually downloaded before requesting it.
5. Add [Qwen3.5-4B](https://lmstudio.ai/models/qwen/qwen3.5-4b) as a lightweight efficiency control if needed. Larger Qwen3-Coder-Next/180B-class models are not plausible ordinary full-GPU candidates for this hardware; size and active-parameter claims do not bypass storage limits.

For primary agent, lightweight worker, coding, research, content, and QA, the routing status remains **PENDING until measured role-specific success/hour exists**. Calculate successful tasks divided by total elapsed hours, including retries, recovery, and amortized model switches; report confidence/sample counts. Enforce safety/schema/source-fidelity minimums before ranking efficiency. A role may have no qualifying local model. Keep a human review path. Optional paid cloud escalation remains disabled at a $0 budget until explicitly approved.

Electricity cost requires measured energy or an explicitly labeled estimate and an operator-provided tariff. GPU utilization or TDP alone does not establish energy consumption. No cloud API price or realized revenue has been inferred from these local experiments.
