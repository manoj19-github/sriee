# Testing Log — 120014 Model Environment Routing v2

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120014` |
| Environment | Windows, Python 3.14, exact root requirement pins |
| Result | **PASS — 360 passed in 4.69 seconds** |

## Focused verification

```text
python -m pytest backend/tests/unit/providers/test_ollama.py -q -p no:cacheprovider
```

Result: **31 passed in 0.42 seconds**.

Coverage includes local production configuration, exact development/test allowlisting,
production remote rejection, URL-injection rejection, minimal remote payloads, local
bounded options, structured output, local and remote health, secret Bearer injection,
secret redaction, transport failures and malformed/mismatched responses.

## Full regression

```text
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Result: **360 passed in 4.69 seconds**.

## Live smoke

The exact supplied endpoint and non-sensitive `"hii"` payload were attempted without
a credential. Network connectivity succeeded, and the provider returned
`{"error":"unauthorized"}`. This is recorded as an external authentication
prerequisite, not a successful model completion. No response text beyond the fixed
error code and no secret was logged.

After a provider-issued Bearer token was supplied through ignored `.env`, the same
bounded request passed. Sanitized evidence: model identity matched `qwen3.6:27b`,
`done=true`, role was `assistant`, and response content was non-empty (32 characters).
Neither the credential nor response text was printed or committed.
