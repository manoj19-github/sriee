# Testing Log — 120003 Classify Intent v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120003` |
| Environment | Windows, repository Python environment, local Ollama |
| Result | **PASS — 265 passed in 4.28 seconds** |

## Focused verification

Command:

```text
$env:PYTHONPATH='backend/src'
python -m pytest backend/tests/unit/graph/test_intent.py -q
```

Coverage includes:

1. All fixed intent/target projections and consequential classification.
2. Deterministic low-confidence, unknown, missing-project, inconsistent-target and
   fixed-ambiguity clarification routing.
3. Authorized reference subset enforcement and invented/duplicate reference rejection.
4. Exactly one content-free repair for malformed, invalid or unstructured output.
5. Bounded summary count, kind/prefix, per-item/aggregate size and resolver deadline.
6. Required policy/capability state references.
7. Provider/resolver error sanitization and cancellation propagation.
8. Strict response schema, untrusted-context labelling and prompt boundary.
9. Input immutability and exclusion of request/summary content from checkpoint output.
10. Invalid graph state, identity, request and settings rejection.

## Live local-model smoke test

The real loopback `OllamaModelGateway` called installed model
`qwen3:4b-instruct` with a benign information request and three synthetic bounded
context summaries. The model returned schema-valid `information_request` intent with
`general` target, empty reference scope, confidence `1.0` and no ambiguity. The node
returned a non-consequential projection with no clarification required.

No cloud, tool, filesystem, database, Redis or desktop action was invoked.

## Full regression and static verification

```text
$env:PYTHONPATH='backend/src'
python -m pytest backend/tests -q
python -m compileall -q backend/src backend/tests
git diff --check
```

Final post-documentation results:

- Focused classifier suite: **48 passed in 1.02 seconds**.
- Full backend regression: **265 passed in 4.28 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Git emitted only expected Windows line-ending checkout warnings.
