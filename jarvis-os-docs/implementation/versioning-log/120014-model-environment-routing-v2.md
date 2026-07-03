# Versioning Log — 120014 Model Environment Routing v2

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120014` |
| Version | `v2` |
| Lifecycle | `current` |

## Added contract

- `JARVIS_ENV` selects development/test or production policy.
- `OLLAMA_CHAT_URL` may select the exact allowlisted development endpoint.
- `OLLAMA_API_KEY` optionally supplies a secret Bearer credential.
- Development/test remote payloads omit local-only keep-alive and runtime options.
- Production remains loopback-only and rejects provider credentials.
- Safe diagnostics expose routing category and egress state, never URL or credential.

## Compatibility

The public request/response models and `callLocalModel` entry point are unchanged.
Existing production-local configuration works without `OLLAMA_CHAT_URL`. The version
is advanced to v2 because environment routing and optional authentication extend the
provider configuration contract.

No database, API, WebSocket, graph-state, prompt or package version changed.

## Rollback

Remove `OLLAMA_CHAT_URL` and `OLLAMA_API_KEY`, restore the v1 loopback-only settings
validator and set the function-map lifecycle back to `complete/current/v1`.
