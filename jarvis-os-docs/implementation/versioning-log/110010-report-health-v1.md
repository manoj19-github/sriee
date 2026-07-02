# Versioning Log — 110010 Report Health v1

| Field | Value |
|---|---|
| Date | 2026-07-02 |
| Global ID | `110010` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `GET /health/live` returns minimal process liveness.
- `GET /health/ready` returns 200 when ready and 503 when dependency readiness is degraded.
- Readiness dependencies use fixed names with `ready` and safe `code` fields.
- Internal counters record probe/failure totals without request, task or dependency payloads.

## Compatibility

This is an additive API. No existing REST, WebSocket, database, graph, prompt or package version changed.

## Rollback

Remove the health router/reporter integration and dynamic runtime re-probe method. Existing startup readiness remains available internally.
