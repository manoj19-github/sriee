# Versioning Log — 120014 Call Local Model v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120014` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- Provider: loopback Ollama HTTP API.
- Default model: `qwen3:4b-instruct`.
- Tested local runtime: Ollama `0.31.1`.
- Tested model ID: `0edcdef34593`; Qwen3 4.0B Q4_K_M.
- Default context: 8192 tokens.
- Default maximum output: 1024 tokens.
- Default temperature: 0.2.
- Default timeout/connect timeout: 120 / 5 seconds.
- Default keep-alive: 5 minutes.
- Streaming and separate provider thinking output: disabled.
- Optional response format: JSON object schema up to 32,768 serialized bytes.
- Safe readiness and provider failure codes.

## Compatibility

This adds Global ID `120014` within the existing LangGraph allocation and extends the
Stage 02 range from `120000–120013` to `120000–120014`. Existing graph topology,
REST, WebSocket, task, database, policy and prompt contracts remain compatible.

No Python dependency changed. The external Ollama runtime/model is independently
installed and is not committed to the repository.

## Rollback

Remove the provider package, safe example settings and local-provider documentation.
Optionally remove the local model with `ollama rm qwen3:4b-instruct`; this does not
affect source, database state or the preserved `qwen2.5:7b` model.
