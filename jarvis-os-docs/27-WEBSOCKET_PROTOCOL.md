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
