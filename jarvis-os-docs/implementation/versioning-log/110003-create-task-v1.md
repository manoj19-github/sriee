# Versioning Log — 110003 Create Task v1

| Field | Value |
|---|---|
| Record | VERSION-110003-v1 |
| Date | 2026-07-02 |
| Function version | v1 |
| Lifecycle | current |
| Compatibility | first implementation |

## Added

- `POST /api/v1/tasks`.
- Text/transcript task-input contract.
- Immutable task, initial-event and outbox records.
- Atomic repository and outbox-notifier interfaces.
- Actor/device-scoped idempotency and request hashing.
- Stable replay, conflict, validation and unavailable-service behavior.

## API v1

Required headers: authenticated desktop-session headers, `Idempotency-Key`, and `X-Correlation-Id`.

Successful creation and matching replay both return 202; `created` distinguishes a new task from replay. Mismatched idempotency reuse returns 409.

## Package changes

None. All imports use packages already pinned in root `requirements.txt`, which remains at 75 exact pins.

No database migration, event-bus transport, graph, prompt or policy version changed.
