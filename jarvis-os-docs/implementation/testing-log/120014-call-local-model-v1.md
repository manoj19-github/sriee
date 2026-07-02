# Testing Log — 120014 Call Local Model v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120014` |
| Environment | Windows; Ollama 0.31.1; RTX 3050 Laptop GPU 4 GB; RAM 15.7 GB |
| Result | **PASS — 186 passed in 3.40 seconds plus live smoke PASS** |

## Focused deterministic verification

Command:

```text
python -m pytest backend/tests/unit/providers/test_ollama.py -q
```

Result: **19 passed in 0.42 seconds**.

Coverage includes:

1. Valid loopback settings and content-free diagnostics.
2. Rejection of remote, HTTPS, credential-bearing, path-bearing and portless URLs.
3. Message, combined prompt and JSON-schema bounds.
4. Not-started, ready and configured-model-missing health states.
5. Lifecycle cleanup of the managed HTTP client.
6. Exact bounded chat payload including context/output/temperature and no streaming
   or separate thinking output.
7. Typed token and duration metadata.
8. JSON Schema forwarding and JSON-object response enforcement.
9. Canonical `callLocalModel` delegation.
10. Sanitized timeout, connection, HTTP, missing-model, invalid-JSON and model-mismatch
    failures.

## Full regression and static verification

```text
python -m pytest backend/tests -q
python -m compileall -q backend/src backend/tests
git diff --check
```

Results:

- Backend: **186 passed in 3.40 seconds**.
- Python bytecode compilation: **PASS**.
- Diff whitespace validation: **PASS**.
- Git emitted only expected Windows line-ending checkout warnings.

## Live local verification

1. `ollama --version`: `0.31.1`.
2. `ollama pull qwen3:4b-instruct`: **PASS**, manifest digest verified.
3. `ollama list`: installed model ID `0edcdef34593`, storage size 2.5 GB.
4. Gateway health through `/api/version` and `/api/tags`: `ready`.
5. Structured gateway chat: **PASS** with keys `provider` and `status`.
6. Model identity: `qwen3:4b-instruct`.
7. Prompt/output tokens: 40 / 21.
8. Cold request duration: 14,700.2 ms.
9. Runtime placement: 42% CPU / 58% GPU, context 8192.

The first live harness invocation failed before gateway execution because legacy
PowerShell stripped quotes from `python -c`. The unchanged smoke program was rerun
through Python standard input and passed. No product code changed for this harness
correction.
