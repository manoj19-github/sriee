# Testing Log — 120001 Normalize Request v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120001` |
| Environment | Windows, repository Python environment |
| Result | **PASS — 167 passed in 3.28 seconds** |

## Focused verification

Command:

```text
python -m pytest backend/tests/unit/graph/test_normalize.py backend/tests/unit/graph/test_builder.py -q
```

Result: **48 passed in 1.06 seconds**: 25 normalization cases plus 23 graph-builder
regressions.

Normalization coverage includes:

1. Exact text preservation across Unicode, leading/trailing whitespace and CRLF.
2. Transcript type/content preservation.
3. No input-state mutation.
4. Existing task/thread ID preservation without generator invocation.
5. Missing task ID assignment and stable task-derived thread ID.
6. Idempotent output after the first delta is merged into state.
7. Invalid actor, device, task and thread identifiers.
8. Missing, malformed and unsupported contract versions.
9. Missing, blank, NUL, unknown-type, extra-field and overlong payloads.
10. Configured serialized-byte bound.
11. Invalid normalization settings and starting status.
12. Invalid generated ID suppression without value reflection.

## Full regression and static verification

```text
python -m pytest backend/tests -q
python -m compileall -q backend/src backend/tests
git diff --check
```

Results:

- Backend: **167 passed in 3.28 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Git emitted only expected Windows line-ending checkout warnings.

No external service, model, network, database, Redis or OS adapter was used.
