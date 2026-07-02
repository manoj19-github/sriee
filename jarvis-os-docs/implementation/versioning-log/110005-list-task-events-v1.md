# Versioning Log — 110005 List Task Events v1

| Field | Value |
|---|---|
| Record | VERSION-110005-v1 |
| Date | 2026-07-02 |
| Function version | v1 |
| Lifecycle | current |
| Compatibility | first implementation |

## Added

- `GET /api/v1/tasks/{task_id}/events`.
- Stable exclusive-cursor event pagination.
- Bounded page size and lookahead-based `has_more`.
- Authorized task-event repository/service contracts.
- Durable WebSocket recovery response envelope.

## Package changes

None. All imports use the existing 75 exact root requirement pins.

No database migration, WebSocket stream, graph, prompt or policy version changed.
