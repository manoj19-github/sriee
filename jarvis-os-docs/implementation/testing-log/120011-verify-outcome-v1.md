# Testing Log — 120011 Verify Outcome v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120011` |
| Environment | Windows, repository Python environment |
| Result | **PASS — 518 passed in 5.68 seconds** |

## Focused verification

```text
$env:PYTHONPATH='backend/src'
python -m pytest backend/tests/unit/graph/test_verification.py -q -p no:cacheprovider
```

Final focused result: **56 passed in 1.44 seconds**.

Coverage includes:

1. All-pass, all-fail, confirmed partial and uncertain aggregate classification.
2. Executor success with failed postcondition and executor failure with verified
   postcondition success.
3. Retryable revision routing, permanent issue handling and exhausted uncertainty.
4. Missing action receipt, missing probe, probe timeout and probe runtime outage.
5. Exact task/thread/actor/device/action/receipt/resource/argument probe request.
6. Capability/version/code/read-only descriptor validation.
7. Probe result identity, timestamp, evidence and type mismatch rejection.
8. Stable immutable store persistence and stale-checkpoint recovery without probes.
9. Exact checkpoint replay with empty reducer output and no I/O.
10. Partial checkpoint evidence rejection.
11. Semantically forged stored/checkpoint outcomes, receipts and observation IDs.
12. State, identity, runtime-thread, revision, plan/result and settings validation.
13. Registry/store error sanitization and cancellation propagation.
14. Definite-verdict evidence and aggregate-count contract validation.

## Integration boundary

Tests use asynchronous in-memory read-only probes, registry and immutable store fakes
with the real production contracts and orchestration. No model is involved in
120011, so an Ollama smoke test is not applicable. No OS action, filesystem read,
database, Redis, desktop adapter or network endpoint was invoked.

## Full regression and static verification

```text
$env:PYTHONPATH='backend/src'
python -m pytest backend/tests/unit/graph -q -p no:cacheprovider
python -m pytest backend/tests -q -p no:cacheprovider
python -m compileall -q backend/src backend/tests
git diff --check
```

Pre-documentation results:

- Graph suite: **365 passed in 3.18 seconds**.
- Full backend suite: **518 passed in 7.16 seconds**.

Final post-documentation evidence:

- Focused verification suite: **56 passed in 1.44 seconds**.
- Graph suite: **365 passed in 2.71 seconds**.
- Full backend suite: **518 passed in 5.68 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Function-map derivation: **199 total / 173 planned / 0 in progress / 26 complete**.
- Git emitted only expected Windows line-ending checkout warnings.
