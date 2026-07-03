# API Specification

Base: `/api/v1`. JSON uses UTC RFC 3339 timestamps and stable string IDs.

Health probes are process-level endpoints under `/health`, outside the versioned task API base.

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

Implemented error mapping v1 uses an allowlisted code-to-status/message/retryability
registry for API and WebSocket failures. API failures return the envelope above and
repeat the safe correlation identifier in `X-Correlation-Id`. WebSocket `error`
frames use the same five fields as their payload. Validation details contain at most
20 issue locations and types; rejected input, validator messages and contexts are
not returned. Unknown exceptions become non-retryable `internal_error` responses
without exception text or stack traces. Framework-generated routing failures pass
through the same envelope. An HTTP exception without an allowlisted domain code
retains its valid 4xx/5xx status while its arbitrary detail is replaced by a static
message.

## Health probes v1

`GET /health/live` reports only whether the HTTP process can return a bounded response. It does not probe dependencies and returns 200 even when readiness is degraded:

```json
{
  "status": "live",
  "state": "ready"
}
```

`GET /health/ready` performs bounded health checks for telemetry, database, checkpointer, graph, providers and workers. A fully ready response is 200:

```json
{
  "status": "ready",
  "state": "ready",
  "accepting_work": true,
  "dependencies": {
    "database": {
      "ready": true,
      "code": "ready"
    }
  },
  "failure_code": null
}
```

A dependency outage, exception or timeout returns 503 with `status=not_ready`, marks the runtime as not accepting work and uses only validated safe identifiers such as `providers_unavailable` or `database_health_check_failed`. The process remains live and later probes can restore readiness after recovery.

Health responses never include connection strings, hosts, credentials, exception text, settings fingerprints or personal/task content. Internal metrics count liveness probes, readiness probes, degraded probes and dependency failures without payloads.

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

## Get task v1

`GET /api/v1/tasks/{task_id}` requires the authenticated actor and device that own the task. Malformed IDs, unknown tasks and ownership mismatch all return the same `404 task_not_found` response.

Response:

```json
{
  "task_id": "tsk_...",
  "status": "awaiting_approval",
  "plan": {
    "revision": 3,
    "status": "validated"
  },
  "pending_approval": {
    "approval_id": "apr_...",
    "action_id": "act_...",
    "risk_tier": "R2",
    "expires_at": "2026-07-02T12:02:00Z"
  },
  "result": null,
  "created_at": "2026-07-02T12:00:00Z",
  "updated_at": "2026-07-02T12:00:05Z"
}
```

Result snapshots may contain an outcome, bounded summary and opaque artifact references. Artifact content, path, URL and download access are never embedded:

```json
{
  "reference_id": "art_...",
  "requires_separate_authorization": true
}
```

The response omits task input, actor/device identity, idempotency keys, request hashes and internal event/outbox data.

## List task events v1

`GET /api/v1/tasks/{task_id}/events` requires task ownership by the authenticated actor and device.

Query parameters:

- `after_sequence`: exclusive cursor, integer ≥ 0, default `0`.
- `limit`: page size from 1 through 100, default `50`.

Response:

```json
{
  "task_id": "tsk_...",
  "events": [
    {
      "event_id": "evt_...",
      "task_id": "tsk_...",
      "sequence": 1,
      "type": "task.created",
      "schema_version": "1.0",
      "occurred_at": "2026-07-02T12:00:00Z",
      "correlation_id": "corr_...",
      "data": {
        "input_type": "text",
        "contract_version": "1.2.0"
      }
    }
  ],
  "next_cursor": 1,
  "has_more": false
}
```

Events are strictly ascending and include only sequences greater than `after_sequence`. `next_cursor` is the last returned sequence, or the supplied cursor when no events remain. Clients reconnecting after WebSocket loss repeatedly request pages until `has_more=false`.

Malformed IDs, unknown tasks and ownership mismatch return the same `404 task_not_found`. Invalid cursor/limit values return 422. Reads never mutate task, event or outbox state.

## Cancel task v1

`POST /api/v1/tasks/{task_id}/cancel` requires task ownership and `X-Correlation-Id`. It returns 202 after durable cancellation intent is recorded. `status=cancellation_requested` is not a claim that execution has stopped. Replays return `created=false`; terminal tasks remain terminal without a new event/outbox.

## Decide approval v1

`POST /api/v1/approvals/{approval_id}/decision` requires ownership, `X-Correlation-Id`, `decision` (`approve` or `deny`) and the exact lowercase 64-character action digest. Unknown/unauthorized approvals return 404. Expired, consumed or mismatched approvals return distinct 409 codes. The action payload is never accepted or returned by this endpoint.
