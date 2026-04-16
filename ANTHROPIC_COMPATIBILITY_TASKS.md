# Anthropic Compatibility Execution Tasks

## Purpose

This checklist translates the compatibility plan into an execution order that
matches practical development flow. The list is intentionally ordered by what
should be implemented first to reduce rework and keep test feedback tight.

## Execution Order

- [x] Create stable request fixtures copied from real `free-code` request
      shapes.
  Include at least:
  - simple text chat
  - tool use + tool result
  - adaptive thinking
  - `output_config.format`
  - `output_config.effort`
  - image input
  - ignored compatibility fields (`metadata`, `context_management`, `speed`)
  - unsupported blocks (`document`, `tool_reference`)

- [x] Add failing tests for Anthropic top-level field handling before changing
      implementation.
  Cover:
  - acceptance of `metadata`
  - acceptance of `context_management`
  - acceptance of `speed`
  - acceptance of `anthropic-beta`
  - support for `output_config.format`
  - support for `output_config.effort`

- [x] Add failing tests for content block handling before changing
      implementation.
  Cover:
  - `image` block success
  - explicit `document` rejection
  - explicit `tool_reference` rejection
  - existing `thinking` / `redacted_thinking` history skip behavior still
    works

- [x] Refactor the Anthropic request path so it no longer depends on the
      generic unsupported top-level field stripping.
  Goal:
  - Anthropic requests must be normalized through an Anthropic-specific path
  first
  - OpenAI and Gemini paths must remain unchanged

- [x] Introduce an internal Anthropic normalization layer in `app.py`.
  This layer should produce a clear internal structure for:
  - normalized model
  - normalized system prompt
  - normalized content blocks
  - normalized output config
  - normalized compatibility-only ignored fields

- [x] Implement translation for `output_config.effort`.
  Expected behavior:
  - accepted on the Anthropic path
  - mapped into the Responses reasoning configuration when compatible
  - tested independently from thinking

- [x] Implement translation for `output_config.format`.
  Expected behavior:
  - accepted on the Anthropic path
  - mapped into the same structured-output path already used elsewhere in the
    proxy
  - validated with both object and schema-style output fixtures if applicable

- [x] Upgrade thinking handling to support both budget-based and
      adaptive-style requests.
  Expected behavior:
  - `thinking.type = adaptive` does not fail
  - budget-based requests still map to reasoning effort bands
  - existing tests for simpler thinking requests continue to pass

- [x] Implement `image` content block translation.
  Expected behavior:
  - user image blocks map into Responses image input
  - malformed image blocks return Anthropic-style `invalid_request_error`

- [x] Add explicit rejections for unsupported semantic blocks in the first pass.
  Required first-pass explicit rejections:
  - `document`
  - `tool_reference`
  Do not silently drop them.
  Note: these explicit rejections were used in the first pass and later
  promoted to compatibility handling during the second pass.

- [x] Expand tool schema normalization to accept Claude-Code-style extra tool
      fields without failing.
  Accept and ignore in first pass:
  - `cache_control`
  - `defer_loading`
  - `eager_input_streaming`

- [x] Upgrade `/v1/messages/count_tokens` to use an Anthropic-aware estimator.
  Include overhead for:
  - system prompt
  - message text
  - tool call arguments
  - tool result text
  - tool schemas
  - image blocks
  - structured output schema

- [x] Add tests for the improved token estimator.
  Cover:
  - tools increase token estimate
  - images increase token estimate
  - structured output config increases token estimate

- [x] Verify the non-streaming Anthropic response path still returns valid
      message envelopes after the new request normalization is added.
  Re-check:
  - text output blocks
  - tool use output blocks
  - usage mapping
  - stop reason mapping

- [x] Re-verify the streaming Anthropic response path after the normalization
      changes.
  Required checks:
  - text streams as `text_delta`
  - tool arguments stream as `input_json_delta`
  - thinking streams as `thinking_delta`
  - stream closes with `message_delta` and `message_stop`

- [x] Re-verify the buffered SSE compatibility path used for Bearer-auth or
      Claude-Code-like clients.
  Required checks:
  - buffered stream still contains named events
  - buffered stream still includes final stop events
  - existing compatibility behavior is not regressed

- [x] Run the full existing `codex2gpt` test suite and fix regressions before
      attempting any second-pass features.
  At minimum:
  - `tests/test_app.py`
  - `tests/test_runtime_features.py`
  - `tests/test_relay_protocol.py`
  - `tests/test_gemini_protocol.py`

- [x] Update user-facing or agent-facing docs only after the implementation is
      stable.
  Suggested follow-up docs:
  - `README.md`
  - `README_EN.md`
  - `AGENT_INTEGRATION.md`

- [x] Run live smoke tests with the real Anthropic-compatible client config.
  Completed with `/home/sh4wnsu/free-code/cli-dev` using
  `/home/sh4wnsu/.claude/settings.json`.
  Verified:
  - simple chat
  - structured output via `--json-schema`
  - tool use by reading a local file
  - no new server-side errors after restarting the proxy with the current code

- [x] Harden streaming request handling against client disconnects.
  Completed by treating `BrokenPipeError` / reset-style disconnects as silent
  client aborts instead of trying to emit a second error response.

## Stop Line For First Pass

Stop the first implementation pass when all of the following are true:

- normal `free-code`-style Anthropic chat works
- tool use works
- adaptive thinking no longer fails
- structured output config no longer fails
- image input works
- token estimation is materially better
- unsupported semantic blocks fail explicitly
- OpenAI and Gemini compatibility remain intact

Do **not** continue into second-pass features until this first-pass stop line is
green.

Current status: first-pass stop line is green.

## Second-Pass Candidates

These are intentionally postponed and should not block the first pass:

- [x] document block support
- [x] `tool_reference` compatibility flattening
- [x] full beta header semantics
- [x] server-side tool history compatibility (`server_tool_use` /
      `connector_text` downgraded to text instead of full semantics)
- [x] connector-text-specific streaming behavior
- [x] signature streaming for thinking blocks
