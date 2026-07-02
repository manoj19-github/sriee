# Coding Log — 110004 Get Task v1

| Field | Value |
|---|---|
| Record | CODE-20260702-110004 |
| Date | 2026-07-02 |
| Global ID | 110004 |
| Canonical name | `python-fastapi-get-task-mandatory-p0-complete-current-v1` |
| Status transition | `planned → complete` after complete backend test gate |
| Source | `backend/src/jarvis/tasks/`, `backend/src/jarvis/main.py` |
| Tests | `backend/tests/unit/tasks/test_get_task.py` plus all backend unit suites |

## Implementation steps

1. Expanded task lifecycle statuses and terminal outcomes.
2. Added immutable task-projection, plan, pending-approval and result records.
3. Added privacy-safe API response models.
4. Added opaque artifact references that always require separate authorization.
5. Extended task creation to seed its initial projection atomically.
6. Added a query-repository contract and concurrency-safe in-memory implementation.
7. Added projection replacement for development/tests with immutable owner/device/creation identity.
8. Added `TaskQueryService` with strict task-ID validation.
9. Required both actor and device ownership using timing-safe comparisons.
10. Collapsed malformed, missing and unauthorized tasks into `task_not_found`.
11. Added authenticated `GET /api/v1/tasks/{task_id}` and application-factory integration.
12. Documented the complete v1 response and privacy exclusions.

## Privacy boundary

The response never contains original input content, actor/device IDs, request hashes, idempotency keys, event/outbox data, artifact content, paths, URLs or download tokens. Result artifacts are reference IDs only.

PostgreSQL projection materialization remains tracked under the data-layer Global IDs; it is not claimed complete by this API/application implementation.
