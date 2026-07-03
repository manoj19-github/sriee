# Testing Log — 120004 Create Plan Draft v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120004` |
| Environment | Windows, repository Python environment, local Ollama |
| Result | **PASS — 330 passed in 6.49 seconds** |

## Focused verification

```text
$env:PYTHONPATH='backend/src'
python -m pytest backend/tests/unit/graph/test_plan.py -q
```

Final focused result: **65 passed in 1.89 seconds**.

Coverage includes:

1. Stable semantic action/criterion IDs independent of model step labels and correct
   dependency projection.
2. Checkpoint exclusion of summaries, capability descriptions and resource labels.
3. Strict structured prompt and untrusted-data labelling.
4. Unknown capability/version/parameter and missing/duplicate argument rejection.
5. Boolean, enum, numeric range, restricted identifier and opaque-resource validation.
6. Raw path, arbitrary prose string and unregistered resource rejection.
7. Self/forward/unknown/duplicate dependencies and duplicate semantic-action rejection.
8. Declared, unique success criteria with coverage for every action.
9. One content-free repair and safe failure after two invalid outputs.
10. State, intent, clarification, ownership, reference, bound and settings validation.
11. Resolver/provider sanitization and cancellation propagation.
12. Capability parameter contract and absence of command/risk/rationale schema fields.

## Live local-model smoke test

The real loopback `OllamaModelGateway` called installed model
`qwen3:4b-instruct` using synthetic summaries, one registered read-only
`project.inspect` capability and one opaque project resource.

An initial stochastic response attempted a self-dependency and was rejected safely.
The final independent run returned a valid one-action plan with the exact registered
capability/version, opaque resource binding, no dependencies and declared
`inspection_recorded` criterion. The checkpoint projection contained only stable
derived IDs and typed values.

No cloud, tool execution, filesystem mutation, database, Redis or desktop action was
invoked.

## Full regression and static verification

```text
$env:PYTHONPATH='backend/src'
python -m pytest backend/tests -q
python -m compileall -q backend/src backend/tests
git diff --check
```

Final post-documentation results:

- Focused planner suite: **65 passed in 1.89 seconds**.
- Full backend regression: **330 passed in 6.49 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Function-map derivation: **174 total / 155 planned / 0 in progress / 19 complete**.
- Git emitted only expected Windows line-ending checkout warnings.
