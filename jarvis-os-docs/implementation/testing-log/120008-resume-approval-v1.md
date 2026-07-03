# Testing Log — 120008 Resume Approval v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120008` |
| Environment | Windows, Python 3.14, exact root requirement pins |
| Result | **PASS — 414 passed in 4.74 seconds** |

## Focused verification

```text
python -m pytest backend/tests/unit/graph/test_approval_resume.py -q -p no:cacheprovider
```

Result: **15 passed in 0.90 seconds**.

Covered scenarios:

1. Approved, denied and expired authoritative routing.
2. Bounded approval-result projection with raw resume data removed.
3. Runtime thread mismatch rejected before store access.
4. Task/thread/actor/device checkpoint identity mismatch.
5. Resume approval-ID and action-digest mismatch.
6. Invalid workflow status, runtime thread and extra checkpoint fields.
7. Cross-field checkpoint binding tampering.
8. Concurrent atomic attempts produce one success and one consumed failure.
9. Sanitized resolver unavailability and cancellation propagation.
10. Invalid and request-conflicting resolver records.

## Full regression

```text
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Result: **414 passed in 4.74 seconds**.

The 75 exact requirement pins were installed only under ignored `.tmp`; bytecode and
pytest cache generation were disabled.
