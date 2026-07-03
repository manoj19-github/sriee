# Coding Log — 120004 Create Plan Draft v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120004` |
| Status | Complete |

## Delivered behavior

1. Added strict capability manifest, parameter, planning summary and opaque resource
   contracts.
2. Capability manifests are actor/device-bound and tied to the single authorized
   `cap_` reference loaded by `120002`.
3. Supports only boolean, bounded integer/number, fixed enum, restricted identifier
   and registered opaque-resource parameter kinds.
4. Added a strict model plan with fixed objective, assumption/warning codes, bounded
   actions, earlier-step dependencies and declared verification codes.
5. Rejects unknown capability/version pairs, undeclared/missing/duplicate arguments,
   wrong scalar types/ranges, raw paths, unregistered resources and timeout overflow.
6. Rejects forward/self/duplicate dependencies, duplicate step IDs, duplicate
   semantic actions, undeclared/duplicate criteria and actions without verification.
7. Gives invalid or unstructured model output exactly one repair attempt without
   echoing rejected content.
8. Derives stable action and criterion IDs from canonical task/action semantics,
   independent of model step labels; the model cannot assign execution identifiers.
9. Rejects clarification-required or unauthorized intent before resolving context or
   invoking the model.
10. Returns only the typed plan delta, preserves input state and propagates
    cancellation while sanitizing provider/resolver failures.

## Security and privacy

The model-facing schema has no command, script, path, rationale, expected-effect,
risk or arbitrary metadata fields. Arbitrary nested values are impossible. String
bindings are accepted only as trusted-manifest enum values, restricted identifiers or
opaque registered resource IDs. Capability availability is explicitly not permission;
policy evaluation remains downstream.

Ephemeral summaries, resource labels and capability descriptions are labelled
untrusted in the prompt and excluded from checkpoint output, exceptions and logs.

## Package impact

No package change. The implementation uses existing exact Pydantic, AnyIO and local
Ollama/HTTPX contracts already pinned in `requirements.txt`.
