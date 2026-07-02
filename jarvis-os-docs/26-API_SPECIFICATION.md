# API Specification

Base: `/api/v1`. JSON uses UTC RFC 3339 timestamps and stable string IDs.

| Method | Path | Purpose |
|---|---|---|
| POST | `/tasks` | Create task from text/transcript |
| GET | `/tasks/{id}` | Task snapshot |
| GET | `/tasks/{id}/events` | Paginated durable events |
| POST | `/tasks/{id}/cancel` | Request cancellation |
| POST | `/approvals/{id}/decision` | Approve/deny exact pending action |
| GET/POST | `/projects` | List/register projects |
| PATCH | `/projects/{id}` | Update project config |
| GET | `/capabilities` | Device capability manifest |
| GET/DELETE | `/grants/{id}` | Inspect/revoke grant |
| GET/DELETE | `/memories/{id}` | Inspect/forget memory |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Dependency readiness |

## Mutation headers

`Authorization`, `X-Device-Id`, `X-Contract-Version`, `Idempotency-Key`, and `X-Correlation-Id`.

## Error shape

```json
{
  "error": {
    "code": "approval_expired",
    "message": "Approval expired before execution.",
    "correlation_id": "cor_...",
    "retryable": false,
    "details": {}
  }
}
```

Use 409 for state/idempotency conflict, 422 for contract validation, 428 when approval is required, 429 for quota, and 503 for unavailable dependency. OpenAPI and generated clients are authoritative; CI rejects breaking diffs without a version plan.

## Create task v1

`POST /api/v1/tasks` requires authenticated desktop headers plus:

- `Idempotency-Key`: 16–128 safe identifier characters.
- `X-Correlation-Id`: 16–128 safe identifier characters.

Request:

```json
{
  "input": {
    "type": "text",
    "content": "Continue my JARVIS backend work."
  }
}
```

`input.type` is `text` or `transcript`; content is non-blank and at most 16,000 characters. Unknown fields are rejected.

Accepted response (`202`):

```json
{
  "task_id": "tsk_...",
  "status": "created",
  "created": true,
  "event_sequence": 1,
  "accepted_at": "2026-07-02T12:00:00Z"
}
```

An identical idempotent replay returns the original task with `created=false`. Reusing the same actor/device/key scope for a different input type, content, or negotiated contract returns `409 idempotency_key_conflict`.
