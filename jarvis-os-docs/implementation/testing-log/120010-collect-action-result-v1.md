# Testing Log — 120010 Collect Action Result v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120010` |
| Environment | Windows, Python 3.14, exact root requirement pins |
| Result | **PASS — 462 passed in 5.36 seconds** |

## Focused verification

```text
python -m pytest backend/tests/unit/graph/test_action_result.py -q -p no:cacheprovider
```

Result: **30 passed in 1.11 seconds**.

Covered scenarios:

1. Exact success correlation, persistence, event, lease release and graph append.
2. Failed, cancelled and uncertain terminal outcome preservation.
3. Lease-late and timeout-overrun success downgraded to uncertain.
4. Store duplicate recovers a stale checkpoint without another durable write.
5. Exact checkpoint duplicate emits an empty reducer delta.
6. Conflicting checkpoint result fails closed.
7. Task, thread, action and executor-device mismatch.
8. Pending dispatch/idempotency mismatch.
9. Extra fields, non-JSON data, invalid outcome/error/time/artifact contracts.
10. Payload byte bound and settings validation before store access.
11. State/status/identity/runtime-thread and duplicate-result validation.
12. Sanitized not-found, correlation, receipt-conflict and unavailable failures.
13. Cancellation propagation.
14. Invalid, exact-request-conflicting and internally tampered store records.
15. Naive timestamp rejection.

## Full regression

```text
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Result: **462 passed in 5.36 seconds**.

The 75 exact requirement pins were installed only under ignored `.tmp`; bytecode and
pytest cache generation were disabled.
