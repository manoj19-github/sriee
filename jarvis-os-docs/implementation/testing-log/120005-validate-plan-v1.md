# Testing Log — 120005 Validate Plan v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120005` |
| Environment | Windows, Python 3.14, exact root requirement pins |
| Result | **PASS — 348 passed in 5.11 seconds** |

## Focused verification

```text
python -m pytest backend/tests/unit/graph/test_validation.py -q -p no:cacheprovider
```

Result: **15 passed in 1.01 seconds**.

Covered scenarios:

1. Canonical deterministic validation and resolver identity binding.
2. Invalid workflow state, identity, context references and plan schema version.
3. Unknown capabilities, version mismatches and capability timeout contracts.
4. Invalid typed arguments and unknown opaque resources.
5. Duplicate action/criterion IDs and duplicate action semantics.
6. Unknown dependencies, self-dependencies and multi-action cycles.
7. Aggregate timeout and critical-path budget overflow.
8. Unknown, duplicate or missing verification definitions.
9. Mismatched context ownership, resolver exception and resolver timeout.
10. Cancellation propagation and incompatible trusted settings.

## Full regression

```text
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Result: **348 passed in 5.11 seconds**.

The suite used an ignored temporary dependency target populated from the exact root
`requirements.txt` pins. No test cache or bytecode was requested.
