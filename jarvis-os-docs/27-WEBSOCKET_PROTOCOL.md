# WebSocket Protocol

Endpoint: `/api/v1/ws`; authenticated during handshake with device/session binding. REST remains the durable fallback.

## Frame

```json
{
  "type": "task.subscribe",
  "version": "1.0",
  "message_id": "msg_...",
  "sent_at": "2026-07-02T12:00:00Z",
  "payload": {"task_id": "tsk_...", "after_sequence": 12}
}
```

Client messages: `hello`, `task.subscribe`, `task.unsubscribe`, `task.cancel`, `approval.decision`, `action.result`, `ping`.

Server messages: `welcome`, `task.event`, `action.request`, `resync.required`, `error`, `pong`.

## Delivery

On reconnect, client sends last durable sequence and fetches gaps. Messages may duplicate; IDs and action idempotency make consumers safe. Acknowledgement means receipt, not execution. Action results include attempt/receipt IDs. Heartbeats detect stale connections; exponential backoff has jitter and a cap.

Unknown major versions close with a protocol error. Invalid, oversized, unauthorized, or rate-limited frames are rejected and audited. Approval frames repeat the action digest and are processed through the same REST use case.

`action.result` v1 contains only dispatch and request idempotency IDs, task/thread/
action/attempt/receipt IDs, executor device ID, terminal outcome, timezone-aware
start/completion times, optional safe error code and opaque artifact references.
It forbids raw stdout, file content, screenshots, exception text and extra fields.
The backend acknowledges transport receipt only after atomic correlation/persistence;
this acknowledgement is not outcome verification.

## Implemented desktop session v1

Endpoint: `/api/v1/ws`.

Handshake headers: desktop authentication headers plus `X-Protocol-Version: 1.0`. Authentication occurs before acceptance. Welcome includes connection ID, negotiated contract, subscription limit and frame-size limit.

Implemented client frames: `ping`, `task.subscribe`, `task.unsubscribe`.

Implemented server frames: `welcome`, `pong`, `task.event`, `task.subscribed`, `task.unsubscribed`, `resync.required`, `error`.

Subscriptions first replay durable pages from the exclusive cursor, then receive bounded live events. Duplicate live sequences are ignored. A gap or queue overflow removes the affected subscription and emits `resync.required`; the client resumes through `GET /api/v1/tasks/{task_id}/events`.

Implemented `error` payloads contain the stable fields `code`, `message`,
`correlation_id`, `retryable`, and `details`. Codes and messages are allowlisted;
raw frame content and exception text are never reflected.
