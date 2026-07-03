# Versioning Log — 120005 Validate Plan v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120005` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `validatePlan(state, service=...)` accepts a planning-state checkpoint containing
  one v1 `PlanDraft`.
- `PlanValidationService` supplies the authorized context resolver and immutable
  validation settings.
- Successful validation returns the canonical JSON-compatible plan projection.
- Failures raise `PlanValidationError` with a stable content-free code.
- Aggregate budgets cover action/criterion counts, arguments, dependency edges,
  total timeout and critical-path timeout.

## Compatibility

The contract is additive. Existing plan-draft generation is unchanged, and a valid
120004 projection passes without shape changes. The new node performs no persistence,
policy decision, approval or side effect.

No database, API, WebSocket, prompt or package version changed.

## Rollback

Remove the validation module exports and restore 120005 to planned. The earlier
planning functions remain independently usable, but graph composition must not route
an unvalidated plan into policy evaluation.
