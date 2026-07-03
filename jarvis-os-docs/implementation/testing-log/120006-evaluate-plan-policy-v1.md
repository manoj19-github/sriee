# Testing Log — 120006 Evaluate Plan Policy v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120006` |
| Environment | Windows, Python 3.14, exact root requirement pins |
| Result | **PASS — 383 passed in 4.98 seconds** |

## Focused verification

```text
python -m pytest backend/tests/unit/graph/test_policy.py -q -p no:cacheprovider
```

Result: **23 passed in 1.03 seconds**.

Covered scenarios:

1. Stable one-per-action decisions and existing graph-router compatibility.
2. All-allow, approval-required and whole-plan denial routing.
3. R2 scoped grants and unknown-action deny-by-default behavior.
4. Related-capability and repeated-capability anti-splitting elevation.
5. Action-specific and plan-wide security tightening.
6. Weaker security-model recommendation suppression.
7. Security risk elevation cannot create an ungranted R2 allow.
8. Invalid state, identity, policy references and plan schema.
9. Snapshot ownership/type validation and deny-by-default model constraints.
10. Resolver/advisor exceptions, timeouts, malformed assessments and unknown action IDs.
11. Cancellation propagation and incompatible-settings rejection.

## Full regression

```text
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Result: **383 passed in 4.98 seconds**.

The ignored temporary dependency target was populated from the exact root
`requirements.txt`. Test cache and bytecode generation were disabled.
