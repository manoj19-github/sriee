# Versioning Log — 120009 Dispatch Action v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120009` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `dispatchAction(state, service=..., runtime_thread_id=...)` accepts only an
  executing v1 graph state with a validated plan and complete policy coverage.
- `PriorActionResult` is the minimal dependency-readiness input contract.
- `ActionDispatchRequest` is the bounded canonical outbox/WebSocket envelope.
- `ActionPolicyProof` and `ActionApprovalProof` carry minimal authorization evidence.
- `ActionDispatchLimits` defines atomic global/per-resource concurrency ceilings.
- `ActionDispatchStore.create_or_get_dispatch` atomically reserves capacity and
  creates or replays action state, event, outbox and lease.
- `ActionDispatchRecord` is the exact persisted replay result.

## Identity and compatibility

`dsp_<24 hex>` is stable for task/action identity. The 64-character idempotency key
hashes the full canonical request, so a material mutation conflicts rather than
silently replaying. Request and prior-result schema versions are `1.0`.

The existing graph topology and `JarvisState` fields do not change. Dispatch does
not append a fake result; 120010 remains responsible for correlating executor
receipts, releasing/reconciling leases and appending immutable collected results.
No REST, database migration or package version changes are included.

## Security boundary

This graph node is defense in depth. The desktop executor remains responsible for
current capability availability, resource canonicalization, final local policy,
approval signature/expiry and side-effect idempotency under 130003–130006 and the
executor functions.

## Rollback

Remove the dispatch module exports and restore 120009 to planned. Never replace the
atomic store/outbox boundary with a direct executor call or remove resource limits,
dependency readiness, approval-digest matching or replay identity.
