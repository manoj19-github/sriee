# Versioning Log — 110011 Map Domain Errors v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `110011` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- API failures use `{error: {code, message, correlation_id, retryable, details}}`.
- API responses repeat the safe identifier through `X-Correlation-Id`.
- WebSocket `error` frames use the same five public payload fields.
- Validation details contain no more than 20 location/type projections.
- Unknown server exceptions map to a static, non-retryable `internal_error`.

## Compatibility

Successful REST responses and non-error WebSocket frames are unchanged. Existing
FastAPI `detail.code` failures are now wrapped in the documented stable envelope in
applications created by the production factory. WebSocket error payloads retain
`payload.code` and add compatible fields.

No database, graph, prompt, policy, migration or package version changed.

## Rollback

Remove the production handler installation and restore the previous minimal WebSocket
error payloads. Domain services and their typed exceptions remain unchanged.
