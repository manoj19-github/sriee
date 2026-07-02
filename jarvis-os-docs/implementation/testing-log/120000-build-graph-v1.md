# Testing Log — 120000 Build Graph v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120000` |
| Environment | Windows, repository Python environment |
| Result | **PASS — 142 passed in 3.16 seconds** |

## Focused verification

Command:

```text
python -m pytest backend/tests/unit/graph/test_builder.py -q
```

Result: **23 passed in 0.71 seconds**.

Coverage includes:

1. Fixed topology registration without invoking any registered node.
2. Compiled graph name and injected checkpointer identity.
3. Allow flow through dispatch, collection, verification and response.
4. Ask flow through pause/resume before dispatch.
5. Deny flow directly to response without dispatch.
6. Recoverable verification through exactly one test revision loop.
7. Append reducer preservation across separate action-result updates.
8. Every valid policy/approval/verification branch.
9. Fail-closed behavior for unknown routing statuses.
10. Missing/extra node rejection.
11. Node contract-version mismatch rejection before invocation.
12. Non-durable and version-mismatched checkpointer rejection.
13. Incompatible reducer and graph-setting rejection.

The focused runtime scenarios use LangGraph's in-memory saver behind a test-only
durability binding. This verifies builder/checkpoint integration without claiming
PostgreSQL persistence; production persistence remains Global ID `140004`.

## Full regression and static verification

```text
python -m pytest backend/tests -q
python -m compileall -q backend/src backend/tests
git diff --check
```

Results:

- Backend: **142 passed in 3.16 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Git emitted only the expected Windows line-ending checkout warning.

No external database, Redis service, model provider, network call or OS adapter was
used by these tests.
