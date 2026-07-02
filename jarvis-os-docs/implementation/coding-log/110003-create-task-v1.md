# Coding Log — 110003 Create Task v1

| Field | Value |
|---|---|
| Record | CODE-20260702-110003 |
| Date | 2026-07-02 |
| Global ID | 110003 |
| Canonical name | `python-fastapi-create-task-mandatory-p0-complete-current-v1` |
| Status transition | `planned → complete` after complete backend test gate |
| Source | `backend/src/jarvis/tasks/`, `backend/src/jarvis/main.py` |
| Tests | `backend/tests/unit/tasks/test_create_task.py` plus all backend unit suites |

## Implementation steps

1. Added frozen text/transcript request models with strict unknown-field rejection, non-blank validation, NUL rejection and 16,000-character limit.
2. Added immutable task, initial event and outbox domain records.
3. Added an atomic `TaskRepository.create_or_get` contract.
4. Added a concurrency-safe in-memory adapter for deterministic application tests.
5. Scoped idempotency by actor, device and key.
6. Canonically hashed input type/content plus negotiated contract version.
7. Created one task, sequence-1 `task.created` event and `graph.task.requested` outbox intent in one repository operation.
8. Returned the original task for matching replay and 409 for mismatched reuse.
9. Added best-effort dispatcher wake-up only for newly created tasks; durable outbox remains authoritative if wake-up fails.
10. Added authenticated `POST /api/v1/tasks` and application-factory integration.
11. Added stable 422/409/503 API errors and documented the v1 request/response.

## Boundary

This function implements the API/application transaction contract. PostgreSQL migrations, repositories and outbox publisher remain independently tracked by Global IDs 140001–140005; they are not falsely marked complete here.

No task input content is copied into the initial event, outbox record, diagnostics or logs.
