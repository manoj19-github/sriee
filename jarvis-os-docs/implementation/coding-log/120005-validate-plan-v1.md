# Coding Log — 120005 Validate Plan v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120005` |
| Status | Complete |

## Delivered behavior

1. Added asynchronous `validatePlan` as an independent checkpoint-defense node.
2. Revalidates the complete serialized `PlanDraft` and rejects unknown schema
   versions or extra/malformed fields.
3. Re-resolves the authorized planning bundle and verifies capability-reference,
   actor and device binding before trusting capability or resource definitions.
4. Enforces registered capability IDs and exact versions, required/unique parameters,
   scalar constraints, capability timeout limits and typed opaque-resource binding.
5. Validates all dependency references, rejects self-dependencies and detects cycles
   using a deterministic topological traversal independent of action ordering.
6. Rejects duplicate action IDs, criterion IDs and semantically duplicate actions.
7. Requires unique, capability-declared verification definitions covering every
   action.
8. Enforces trusted limits for actions, criteria, arguments, dependency edges, total
   timeout and critical-path timeout.
9. Exposes only content-free `PlanValidationError` codes and propagates cancellation.

## Security and failure behavior

The validator never invokes a model, tool or operating-system action. Resolver
timeouts and exceptions collapse to a safe availability code. Unknown capabilities,
resources, dependencies and verification definitions fail closed. Raw exception
text, resource labels, plan argument values and resolver details are not copied into
diagnostics.

## Package impact

No package was added or changed. The implementation uses the standard library,
Pydantic and existing LangGraph planning contracts. Root `requirements.txt` remains
the authoritative set of 75 exact package pins.
