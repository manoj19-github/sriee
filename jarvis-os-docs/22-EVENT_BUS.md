# Event Bus

The task event stream is the integration spine. PostgreSQL/outbox is authoritative; Redis may accelerate live delivery.

## Envelope

```json
{
  "event_id": "evt_...",
  "type": "action.completed",
  "schema_version": "1.0",
  "occurred_at": "2026-07-02T12:00:00Z",
  "task_id": "tsk_...",
  "correlation_id": "cor_...",
  "producer": "desktop-executor",
  "sequence": 17,
  "data": {}
}
```

Events are immutable, ordered per task, idempotently consumed, and retained by class. Producers write domain change and outbox record atomically. Consumers track event IDs and tolerate duplicates/gaps. Breaking payload changes create a new event type/version.

Core events include task, plan, approval, action, verification, model, connection, and audit lifecycle events. Payloads reference large artifacts and never contain secrets.

Action dispatch commits queued action state, one immutable event, one outbox record
and one bounded resource lease atomically. The outbox payload is a strict
`action.request` with a stable dispatch ID and full-request idempotency hash.
Redelivery is expected; consumers and the store reconcile by dispatch identity
rather than creating another action or lease.

Executor `action.result` delivery carries one attempt/receipt plus exact dispatch,
idempotency, task, thread, action and executor-device identity. The atomic collector
matches the queued action, appends one immutable result event and releases the
resource lease in one transaction. Identical redelivery returns the stored
collection; a different receipt or payload for the same dispatch is a conflict.
Payload bodies remain in separately authorized artifacts, never the event frame.
