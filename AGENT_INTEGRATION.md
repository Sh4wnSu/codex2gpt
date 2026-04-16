# Agent Integration Guide

This document is for agents and agent-like clients that need to call the local `codex2gpt` service correctly.

## Base URLs

Default local base:

```text
http://127.0.0.1:18100
```

Default inference base:

```text
http://127.0.0.1:18100/v1
```

Health check:

```text
http://127.0.0.1:18100/health
```

These are defaults from `run.sh`. The actual host and port come from `LITE_HOST` and `LITE_PORT`.

## Which Endpoint To Use

Choose the endpoint that matches your client protocol:

- native clients: `POST /v1/responses`
- OpenAI Chat clients: `POST /v1/chat/completions`
- Anthropic clients: `POST /v1/messages`
- Anthropic token estimate: `POST /v1/messages/count_tokens`
- Gemini clients: `POST /v1beta/models/{model}:generateContent`
- Gemini streaming clients: `POST /v1beta/models/{model}:streamGenerateContent`

If you are building a new internal agent, `POST /v1/responses` is usually the cleanest default.

## Stable Identity Rules

The most important rule is:

Use stable identity for the same logical workflow.

The proxy preserves routing and improves cache reuse with fields such as:

- `session_id`
- `conversation_id`
- `prompt_cache_key`
- `client_id`
- `business_key`

Recommended pattern:

```text
session_key = client_id + ":" + business_key
```

Practical guidance:

- keep `client_id` stable per caller
- keep `business_key` stable per workflow
- do not generate a new random key on every retry
- do not mix unrelated workflows under the same key

Good `business_key` examples:

- `summary`
- `translate`
- `repo-review`
- `ticket-4821`

Bad examples:

- UUID per request
- current timestamp
- incrementing request counter

## Concurrency Behavior

The service is designed around logical-flow serialization:

- same `client_id + business_key`: serialized
- different `client_id + business_key`: can run concurrently

This helps preserve upstream cache behavior without blocking unrelated work.

## Authentication

If `LITE_API_KEY` is configured, use:

```text
Authorization: Bearer YOUR_LOCAL_API_KEY
```

Gemini-style clients can also use:

```text
x-goog-api-key: YOUR_LOCAL_API_KEY
```

If `LITE_API_KEY` is unset, local inference traffic can work without bearer auth.

## Model Guidance

Common safe defaults:

- `gpt-5.4`
- `gpt-5.3-codex`

Anthropic compatibility currently accepts these aliases:

- `claude-opus-4-6` -> `gpt-5.4-1m` -> upstream `gpt-5.4`
- `claude-sonnet-4-6` -> `gpt-5.4` -> upstream `gpt-5.4`
- `claude-haiku-4-5` -> `gpt-5.3-codex` -> upstream `gpt-5.3-codex`
- Direct GPT model IDs such as `gpt-5.4`, `gpt-5.4-1m`, and `gpt-5.3-codex` are also accepted for Claude Code `/model gpt-*` flows

Unsupported Anthropic aliases are rejected.

Fast mode behavior:

- `speed: "fast"` still requires `anthropic-beta: fast-mode-*`
- When fast mode is active, the proxy prefers the non-1M sibling route and falls back to `low` reasoning effort only when the request did not already specify effort or thinking
- Anthropic-compatible responses echo `usage.speed = "fast"` so Claude Code can reflect the active fast-mode state correctly

## Minimal Examples

### Native Responses API

```bash
curl http://127.0.0.1:18100/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "client_id": "agent-runner-01",
    "business_key": "summary",
    "input": "Summarize the latest build logs.",
    "stream": false
  }'
```

### OpenAI Chat Completions

```bash
curl http://127.0.0.1:18100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "client_id": "agent-runner-01",
    "business_key": "summary",
    "messages": [
      { "role": "user", "content": "Summarize the latest build logs." }
    ],
    "stream": false
  }'
```

### Anthropic Messages

Anthropic-compatible requests must include:

- `anthropic-version: 2023-06-01`

Current first-pass Anthropic compatibility also supports:

- `thinking` with `budget_tokens` and `type: "adaptive"`
- `output_config.format`
- `output_config.effort`
- user `image` blocks
- user `document` blocks that can map to Responses `input_file`
- `POST /v1/messages/count_tokens` with tool/schema/image-aware estimation
- empty `signature_delta` compatibility frames for streamed thinking blocks

Current accept-and-ignore behavior:

- `metadata`

Current beta-gated behavior:

- `output_config.format` requires `anthropic-beta: structured-outputs-*`
- `output_config.effort` requires `anthropic-beta: effort-*`
- `output_config.task_budget` requires `anthropic-beta: task-budgets-*`
- `context_management` requires `anthropic-beta: context-management-*`
- `speed: "fast"` requires `anthropic-beta: fast-mode-*`
- streaming `connector_text` compatibility requires `anthropic-beta: summarize-connector-text-*`
- `tool_reference` plus tool-schema `defer_loading` / `eager_input_streaming` require `anthropic-beta: advanced-tool-use-*` or `tool-search-tool-*`

When the matching beta is present:

- `context_management` and `speed` are still consumed and ignored by the compatibility layer instead of being forwarded upstream
- streamed text blocks switch to `connector_text` / `connector_text_delta` event shapes and include an empty `signature_delta` before close

Current compatibility handling for `tool_reference`:

- accepted inside `tool_result` content
- flattened into text hints that preserve discovered tool names
- intended as a compatibility approximation, not full Anthropic expansion semantics

Current history-compatibility downgrades:

- assistant-history `server_tool_use` blocks are flattened into text
- `connector_text` blocks are treated as ordinary text
- `image` / `document` items nested inside `tool_result` content are downgraded into placeholders

Current explicit rejections:

- `document.source.type = "content"` and other document shapes that do not map cleanly to `input_file`
- deeper Anthropic server-side tool semantics that still do not map safely

```bash
curl http://127.0.0.1:18100/v1/messages \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "client_id": "agent-runner-01",
    "business_key": "summary",
    "messages": [
      { "role": "user", "content": "Summarize the latest build logs." }
    ],
    "stream": false
  }'
```

Use `POST /v1/messages/count_tokens` when you need a token estimate before the real request.

### Gemini-Compatible Request

```bash
curl http://127.0.0.1:18100/v1beta/models/gpt-5.4:generateContent \
  -H 'Content-Type: application/json' \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [{ "text": "Summarize the latest build logs." }]
      }
    ]
  }'
```

Gemini JSON-mode requests can use:

- `generationConfig.responseMimeType = "application/json"`
- `generationConfig.responseSchema`

## Structured Outputs And Tools

Supported structured-output patterns include:

- OpenAI `response_format.type = json_object`
- OpenAI `response_format.type = json_schema`
- Gemini `responseMimeType = application/json`
- Gemini `responseSchema`

Tool and function calling are supported across the translated protocol paths used by the current code.

## Streaming Notes

Streaming is supported on:

- `/v1/responses`
- `/v1/chat/completions`
- `/v1/messages`
- Gemini streaming endpoint

Operational notes:

- `/v1/responses` can use HTTP SSE or WebSocket-backed upstream transport
- `/v1/messages` may use a buffered compatibility path for Bearer-auth Anthropic-style clients such as Claude Code

## Observability Headers

Completed non-stream responses can include:

- `X-Codex2gpt-Account`
- `X-Codex2gpt-Prompt-Tokens`
- `X-Codex2gpt-Cached-Tokens`
- `X-Codex2gpt-Cache-Hit-Rate`

These headers help agents record:

- which account actually served the request
- whether the upstream cache was hit
- prompt-size trends across runs

## Python Example

```python
import json
import urllib.request

BASE_URL = "http://127.0.0.1:18100/v1"

payload = {
    "model": "gpt-5.4",
    "client_id": "agent-runner-01",
    "business_key": "summary",
    "input": "Summarize the latest build logs.",
    "stream": False,
}

req = urllib.request.Request(
    f"{BASE_URL}/responses",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=180) as resp:
    body = json.loads(resp.read().decode("utf-8"))
    print(body)
```

## JavaScript Example

```js
const resp = await fetch("http://127.0.0.1:18100/v1/responses", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "gpt-5.4",
    client_id: "agent-runner-01",
    business_key: "summary",
    input: "Summarize the latest build logs.",
    stream: false,
  }),
});

const data = await resp.json();
console.log(data);
```

## When to Send `prompt_cache_key`

Usually you do not need to.

Prefer stable:

- `client_id`
- `business_key`

Only send `prompt_cache_key` explicitly when you intentionally want multiple client processes to share the same upstream cache identity.

## Diagnostics

Useful operator endpoints:

- `GET /health`
- `GET /auth/status`
- `GET /admin/recent-requests`
- `POST /admin/test-connection`

If cache hit behavior looks wrong, check:

1. whether `client_id` is stable
2. whether `business_key` is stable
3. whether the same model is reused
4. whether the prompt prefix changed substantially
5. whether retries keep generating new session identity
