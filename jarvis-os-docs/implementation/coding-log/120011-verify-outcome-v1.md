# Coding Log — 120011 Verify Outcome v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120011` |
| Status | Complete |

## Delivered behavior

1. Added strict read-only probe descriptor, request and result contracts bound to
   exact capability/version/verification code.
2. Probe requests carry task/thread/actor/device, criterion/action/receipt identity,
   typed action arguments and opaque resource IDs only.
3. Runs every declared criterion through bounded concurrent probes; a collected
   executor success never satisfies a criterion by itself.
4. Requires definite pass/fail verdicts to cite unique opaque evidence references;
   uncertainty carries a fixed reason code.
5. Converts missing action receipts, missing probes, probe timeout and probe runtime
   outage into explicit retryable uncertainty.
6. Rejects malformed, non-read-only, stale, mis-correlated or capability-mismatched
   probe evidence instead of weakening it to uncertainty.
7. Classifies all-pass as succeeded, confirmed pass/fail as partially succeeded,
   all-fail as failed and any unresolved criterion as uncertain.
8. Routes only when every unresolved criterion is retryable and the revision budget
   remains; permanent issues terminate under the deterministic task-status mapping.
9. Persists criterion evidence and one aggregate outcome through an injected
   immutable load-or-record store.
10. Uses stable plan/revision-derived verification and criterion observation IDs.
11. Recovers a stored verification into a stale checkpoint and suppresses all I/O
    and reducer output when the exact checkpoint evidence already exists.
12. Recomputes outcome, counts, recovery, criterion/action/receipt relationships,
    evidence timing and stable IDs for database and checkpoint replay.
13. Preserves cancellation, validates the active runtime thread and sanitizes
    registry/store failures.

## Status mapping

- Verified `succeeded` → task `succeeded`.
- Non-recoverable `partially_succeeded` → task `partially_succeeded`.
- Non-recoverable `failed` → task `failed`.
- Recoverable failed/partial/uncertain → `planning` for the existing bounded revision
  route.
- Exhausted/non-recoverable `uncertain` remains explicit in the aggregate evidence
  and maps to task `failed`, because the canonical task state has no terminal
  uncertain status.

## Security and privacy

The checkpoint contains fixed codes, correlations, timestamps and opaque `evd_`
references only. Probe output cannot embed raw filesystem, command, screen, process,
artifact or exception content. Probe declarations are read-only contracts; concrete
adapters remain responsible for enforcing that property.

## Package impact

No package changed. The implementation uses pinned Pydantic and standard-library
async/concurrency/hash/JSON modules already represented by the exact root pins.
