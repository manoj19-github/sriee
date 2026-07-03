# Coding Log — 120010 Collect Action Result v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120010` |
| Status | Complete |

## Delivered behavior

1. Added asynchronous `collectActionResult` with immutable executor candidate,
   collection request/record, service/settings and atomic store contracts.
2. Requires executing state, valid task/thread/actor/device identity and exact active
   runtime thread.
3. Revalidates the v1 plan and unique known action/dispatch/receipt result state.
4. Accepts only JSON-safe bounded result transport; raw output and extra fields are
   structurally impossible.
5. Correlates dispatch, full-request idempotency key, task, thread, action, attempt,
   receipt and executor-device identity.
6. Limits retained payload to safe error code plus unique opaque artifact references.
7. Requires timezone-aware ordered execution/collection timestamps.
8. Uses one atomic store operation to match the queued dispatch, persist one
   immutable result/event and release the resource lease.
9. Downgrades lease-expired or timeout-overrun receipts to `uncertain` even when the
   executor reports success.
10. Revalidates the complete returned dispatch/result/request record before graph
    state changes.
11. Recovers a store-committed result into a stale graph checkpoint, while returning
    an empty append delta when that exact receipt is already checkpointed.
12. Rejects a different result for an already-collected action and sanitizes
    not-found, correlation, receipt-conflict and availability failures.
13. Preserves cancellation and transitions only to `verifying`; collection never
    declares task success.

## Atomicity and duplicate boundary

The persistence adapter owns pending-action lookup, receipt uniqueness, immutable
result/event creation and lease release in one transaction. An identical duplicate
returns the same record without repeating any write or release. Checkpoint
idempotency is handled separately so a crash between database commit and graph
checkpoint neither loses nor duplicates the result projection.

## Package impact

No package changed. The implementation uses pinned Pydantic and standard-library
modules already represented by the 75 exact, duplicate-free root requirement pins.
