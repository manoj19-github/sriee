# Testing Log — 120009 Dispatch Action v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120009` |
| Environment | Windows, Python 3.14, exact root requirement pins |
| Result | **PASS — 432 passed in 5.14 seconds** |

## Focused verification

```text
python -m pytest backend/tests/unit/graph/test_dispatch.py -q -p no:cacheprovider
```

Result: **18 passed in 0.94 seconds**.

Covered scenarios:

1. Exact allow request, state/event/outbox/lease and configured limits.
2. Ask request with exact consumed approval proof and recomputed digest.
3. Replay reuses one request, event, outbox and lease.
4. Deterministic first dependency-ready unresolved selection.
5. Canonical argument ordering and material-change idempotency rekeying.
6. Global and per-resource capacity exhaustion.
7. Missing, wrong-action, denied and forged-digest approvals.
8. Deny, incomplete and duplicate policy coverage.
9. Unsatisfied dependencies and already-complete plan.
10. Unknown, duplicate and malformed prior results.
11. Invalid status, identity and runtime thread.
12. Unsafe string bindings and missing verification.
13. Oversized requests and incompatible settings.
14. Store unavailability, invalid/conflicting records, wrong lease and cancellation.

## Full regression

```text
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Result: **432 passed in 5.14 seconds**.

The 75 exact requirement pins were installed only under ignored `.tmp`; bytecode and
pytest cache generation were disabled.
