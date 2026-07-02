# Testing Log — 110011 Map Domain Errors v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `110011` |
| Environment | Windows, repository Python environment |
| Result | **PASS — 119 passed in 2.56 seconds** |

## Focused verification

Command:

```text
python -m pytest backend/tests/unit/test_errors.py backend/tests/unit/websocket/test_session.py -q
```

Result: **22 passed in 0.51 seconds**.

The focused suite covers:

1. All eight existing typed task/approval domain failures map to fixed status/code pairs.
2. Service-unavailable errors carry explicit retryability and safe correlation headers.
3. Bearer authentication challenges survive the safe envelope boundary.
4. Validation errors expose only bounded locations/types and omit rejected values.
5. Unexpected exception text and malformed correlation identifiers are not reflected.
6. WebSocket errors use the shared fields and do not reflect unknown error codes.
7. Existing authenticated session, replay, subscription, rate and overflow behavior
   remains green.

## Full regression and static verification

```text
python -m pytest backend/tests -q
python -m compileall -q backend/src backend/tests
git diff --check
```

Results:

- Backend: **119 passed in 2.56 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Git emitted only the expected Windows line-ending checkout warnings.

## Initial failed run

The initial focused run was **19 passed, 2 failed**. Both failures were in newly added
test/mapping integration: unsupported filtering arguments on FastAPI's validation
wrapper and a correlation fixture that met the safe grammar. The correction is
described in the coding record; the final focused and full suites passed.
