# Testing Log — 120002 Load Bounded Context v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120002` |
| Environment | Windows, repository Python environment |
| Result | **PASS — 217 passed in 3.73 seconds** |

## Focused verification

Command:

```text
python -m pytest backend/tests/unit/graph/test_context.py backend/tests/unit/graph/test_normalize.py backend/tests/unit/graph/test_builder.py -q
```

Result: **79 passed in 1.44 seconds**: 31 context cases plus 48 normalization/graph
regressions.

Context coverage includes:

1. Fixed policy/capability/project/memory output ordering.
2. Opaque string-only checkpoint references with no request/source content.
3. Exact ephemeral query and per-source limit propagation, with request content
   supplied only to project/memory selectors.
4. Input-state immutability and request-content exclusion from query representation.
5. Required policy/capability failures and exact-one requirements.
6. Optional project/memory degradation with bounded safe errors.
7. Required and optional deadline behavior.
8. Wrong-source kind and kind/prefix rejection.
9. Actor/device ownership and required device binding.
10. Per-source/aggregate limit and duplicate-ID rejection.
11. Extra content rejection by the reference schema.
12. Invalid state, request and loader-setting rejection.
13. Cancellation propagation without conversion to an optional-source failure.

## Full regression and static verification

```text
python -m pytest backend/tests -q
python -m compileall -q backend/src backend/tests
git diff --check
```

Results:

- Backend: **217 passed in 3.73 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Git emitted only expected Windows line-ending checkout warnings.

All context sources were deterministic in-memory fakes. No database, desktop, model,
network, filesystem, Redis or OS adapter was accessed.
