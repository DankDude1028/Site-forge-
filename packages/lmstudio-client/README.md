# LM Studio adapter

The Python implementation is `siteforge/lmstudio.py`; keeping one importable
implementation prevents dashboard, worker and benchmark clients from diverging.
`LMStudioClient.complete(messages, model, max_tokens=512, temperature=0, tools=None, response_schema=None)`
returns an immutable `Completion` including text, reasoning text, latency, TTFT,
server token usage, tokens/sec, finish reason and chunks. `acomplete` uses an
async thread wrapper; `generate(prompt, model)` returns text for simple workers.

Only loopback HTTP is permitted. Redirects and environment proxies are disabled.
Requests do not load/download models or fall back to paid APIs. Transport and
malformed/incomplete SSE failures raise `LMStudioError`; callers apply explicit
bounded retry policy. The benchmark retains raw evidence and native tool calls;
the adapter itself never executes those calls.
`response_schema` sends a strict OpenAI-compatible JSON Schema to local LM
Studio; validation remains the caller's responsibility and invalid output fails
closed. There is no automatic repair or cloud fallback.
