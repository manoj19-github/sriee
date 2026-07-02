# Coding Log — 120014 Call Local Model v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120014` |
| Status | Complete |

## Delivered behavior

1. Added immutable Ollama settings with environment/dotenv loading and safe diagnostics.
2. Restricts the provider URL to loopback HTTP with an explicit port and rejects
   remote, HTTPS, credential-bearing, path/query/fragment and portless endpoints.
3. Added bounded system/user/assistant messages, combined prompt limit and optional
   JSON-compatible object response schema.
4. Added lifecycle-managed HTTPX client creation, version/model health checks and
   deterministic cleanup.
5. Sends non-streaming requests with bounded context, output tokens, temperature,
   keep-alive and separate thinking output disabled.
6. Validates model identity, assistant role, completion state, non-empty/size-bounded
   content and JSON-object syntax for structured responses.
7. Returns typed content-free token/duration metadata alongside final content.
8. Converts timeouts, HTTP failures, missing models and malformed responses to fixed
   safe codes without reflecting provider bodies or exception text.
9. Added secret-free `.env.example` fields and a local Ollama operating guide.

## Local installation

Ollama `0.31.1` was already installed and healthy on the development machine.
`qwen3:4b-instruct` was pulled explicitly; Ollama verified the SHA-256 manifest.
The installed model is Qwen3 4.0B, Q4_K_M, local ID `0edcdef34593`.

The existing `qwen2.5:7b` model was preserved as a comparison/fallback and no model
was deleted or replaced.

## Security and privacy

There is no cloud fallback, provider credential, arbitrary URL, automatic model
download, tool execution or raw prompt/response logging. Model output remains
untrusted and must be validated by its owning graph node before policy or execution.

## Package impact

No package change. The implementation uses existing exact `httpx==0.28.1`,
Pydantic and Pydantic Settings pins. OpenCV is intentionally not installed yet because
no vision Global ID is being implemented in this change.
