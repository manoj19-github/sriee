# Coding Log — 120003 Classify Intent v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120003` |
| Status | Complete |

## Delivered behavior

1. Added fixed intent, target and ambiguity enums plus strict model-output, scope and
   graph-projection contracts.
2. Validates planning state, normalized request, task/actor/device identity, unique
   reference bounds and the required policy/capability reference pair.
3. Resolves every authorized opaque reference through an injected actor/device-aware
   ephemeral summary resolver under fixed per-summary, aggregate and timeout bounds.
4. Sends the normalized request and clearly labelled untrusted summaries only to the
   injected local structured-model gateway.
5. Validates model JSON against the strict schema and rejects duplicate or invented
   context references.
6. Gives schema-invalid, unstructured or unauthorized output exactly one repair
   attempt without echoing the rejected response.
7. Computes consequential status and clarification routing in application code.
8. Requires clarification for low-confidence consequential intent, unknown intent,
   incompatible consequential target, missing project scope or model-declared fixed
   ambiguity.
9. Returns only a typed checkpoint-safe intent projection and preserves input state.
10. Preserves cancellation while mapping resolver/provider/runtime failures to fixed
    content-free error codes.

## Security and privacy

The model cannot return commands, paths, policy decisions, risk levels, free-form
reasoning or ambiguity text through the accepted schema. Context summaries exist only
for the model call and are excluded from graph output, exception messages and test
diagnostics. Selected scope is always a subset of the opaque references already
authorized by `120002`.

## Package impact

No package change. The implementation uses the existing exact `pydantic`, `anyio` and
local Ollama/HTTPX contracts already pinned in `requirements.txt`.
