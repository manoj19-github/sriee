# Testing Log — 110003 Create Task v1

| Field | Value |
|---|---|
| Record | TEST-20260702-110003 |
| Date | 2026-07-02 |
| Global ID | 110003 |
| Environment | Windows, Python 3.14.4, exact pinned temporary dependencies |
| Suite | complete `backend/tests/unit` suite |
| Final result | **PASS — 50 passed in 0.99 seconds, 0 warnings** |

## Create-task coverage

1. Valid authenticated request returns 202.
2. Task, sequence-1 event and outbox intent are created together.
3. Initial event does not duplicate private task content.
4. Matching idempotent replay returns the original task with `created=false`.
5. Replay creates no duplicate event, outbox or dispatcher notification.
6. Changed content or input type with the same scoped key returns 409.
7. Idempotency scope separates actors/devices.
8. Ten concurrent identical creates produce exactly one transaction and one notification.
9. Dispatcher notification failure preserves accepted task and outbox intent.
10. Blank, oversized, unknown-type and extra-field payloads return 422 without writes.
11. Invalid idempotency/correlation identifiers return stable 422.
12. Transcript input is accepted and stored with correct type.
13. Missing authentication or task service fails before writes.
14. Settings, lifecycle and desktop-authentication regression suites remain green.

Decision: function 110003 may be marked `complete/current/v1`.
