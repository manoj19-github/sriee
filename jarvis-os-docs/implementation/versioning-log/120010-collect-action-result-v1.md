# Versioning Log — 120010 Collect Action Result v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120010` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `collectActionResult(state, candidate, service=..., runtime_thread_id=...)`
  accepts an executing graph state and strict JSON `action.result` candidate.
- `ExecutorActionResult` is the bounded desktop/backend transport contract.
- `ActionResultCollectionRequest` binds the authenticated actor to the candidate.
- `ActionResultStore.collect_or_get_action_result` atomically correlates, persists
  result/event and releases the dispatch lease.
- `ActionResultCollectionRecord` carries the authoritative dispatch and minimal
  graph projection with first-create/duplicate evidence.
- `ActionResultSettings` bounds transport bytes.

## Compatibility

The function appends the existing `PriorActionResult` v1 projection to the existing
`action_results` reducer and changes status from `executing` to `verifying`. No
`JarvisState` schema, graph topology, REST route, package version or database
migration changes.

The concrete persistence adapter remains tracked by data-layer functions. Transport
authentication and frame routing use existing FastAPI/WebSocket contracts. 120011
remains solely responsible for independent postcondition verification and final
task outcome.

## Security and reliability

Raw executor output cannot enter graph state. Late/overrun success is uncertain.
Identity mismatch, unknown pending action, changed duplicate receipt and tampered
store records fail closed. Database and graph idempotency are deliberately separate
to survive a crash between their commits.

## Rollback

Remove the collection module exports and restore 120010 to planned. Do not replace
atomic receipt/event/lease reconciliation with direct append, accept raw output, or
treat an executor-reported success as verified task success.
