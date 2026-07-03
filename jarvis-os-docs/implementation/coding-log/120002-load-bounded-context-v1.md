# Coding Log — 120002 Load Bounded Context v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120002` |
| Status | Complete |

## Delivered behavior

1. Added immutable context kind/classification/reference/query contracts.
2. Reference objects contain only opaque ID, kind, actor/device ownership,
   classification and version; extra source content is forbidden.
3. Added injected protocols for project, capability, policy and memory sources.
4. Executes all four reads concurrently under independent bounded deadlines.
5. Applies fixed per-source and aggregate reference limits.
6. Requires exactly one policy and one capability reference, each bound to the
   authenticated actor and device.
7. Allows actor-wide project/memory references while rejecting any mismatched declared
   device.
8. Validates kind-specific ID prefixes, source kind, ownership and duplicate IDs before
   writing state.
9. Degrades optional project/memory source failure to fixed retryable state errors;
   required policy/capability source failure stops the node.
10. Preserves cancellation and returns only ordered reference IDs plus optional safe
    errors without mutating the input state.

## Security and privacy

The ephemeral source query carries normalized request content only to project/memory
selectors; capability and policy sources receive no request text. The field is hidden
from query representation. Checkpoint output
contains no project path/content, capability payload, policy body, memory text,
exception message or arbitrary source metadata.

Concrete PostgreSQL, policy, desktop-manifest and memory retrieval adapters remain
separate planned functions; this change defines and verifies their authorization-safe
orchestration boundary.

## Package impact

No package change. The implementation uses existing exact Pydantic pins and Python
standard-library concurrency/types.
