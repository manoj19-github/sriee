# Coding Log — 120008 Resume Approval v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120008` |
| Status | Complete |

## Delivered behavior

1. Added asynchronous `resumeApproval` with immutable checkpoint, request,
   resolution and bounded result contracts.
2. Revalidates the exact `120007` pending record and strict resume candidate,
   forbidding additional checkpoint fields.
3. Checks preview/request action, digest, risk and policy cross-bindings.
4. Requires valid task/thread/actor/device state identities to match the persisted
   approval and separately requires the active runtime LangGraph thread to match.
5. Compares identity and digest values with constant-time comparison.
6. Rejects candidate approval-ID or action-digest mismatch before store access.
7. Sends an identity-complete request to an injected atomic resolver that must
   authenticate and claim the decision once.
8. Validates the returned request exactly and enforces decision/outcome/expiry time
   consistency.
9. Replaces pending transport with a minimal versioned result, routing approved to
   `executing`, denied to `denied`, and late decisions to `expired`.
10. Sanitizes resolver failures, distinguishes already-consumed decisions and
    preserves cancellation. It never dispatches an action.

## Atomicity and replay boundary

The resolver contract owns the compare-and-claim transaction. Concurrent attempts
for the same approval permit exactly one resolution; later attempts report consumed.
Expiry is authoritative inside that atomic operation, avoiding a graph/store
time-of-check/time-of-use gap. The graph validates the returned record but cannot
turn a late decision into an approval.

## Package impact

No package changed. The implementation uses pinned Pydantic and standard-library
modules already represented by the 75 exact, duplicate-free root requirement pins.
