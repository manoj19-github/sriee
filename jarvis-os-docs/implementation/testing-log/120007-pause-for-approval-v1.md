# Testing Log — 120007 Pause For Approval v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120007` |
| Environment | Windows, Python 3.14, exact root requirement pins |
| Result | **PASS — 399 passed in 5.72 seconds** |

## Focused verification

```text
python -m pytest backend/tests/unit/graph/test_approval.py -q -p no:cacheprovider
```

Result: **16 passed in 0.99 seconds**.

Covered scenarios:

1. Persistence occurs before interrupt with exact typed preview/resource scope.
2. Replay reuses one approval and one event, then carries strict resume data.
3. Canonical argument ordering and digest change on material action mutation.
4. First-ask selection prevents blanket approval.
5. Invalid state, identities, plan or decision coverage.
6. Deny/no-ask paths cannot enter the approval node.
7. Store unavailability, invalid record and idempotency conflict sanitization.
8. Cancellation propagation and incompatible settings.
9. Non-JSON, extra-field and oversized resume payload rejection.
10. Real LangGraph `MemorySaver` interrupt plus `Command(resume=...)` replay.

## Full regression

```text
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Result: **399 passed in 5.72 seconds**.

The exact pinned environment was installed only under ignored `.tmp`; bytecode and
pytest cache generation were disabled.
