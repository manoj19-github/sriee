# Versioning Log — 120006 Evaluate Plan Policy v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120006` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `evaluatePlanPolicy(state, service=...)` consumes one v1 validated plan.
- `PlanPolicyService` supplies a policy snapshot resolver, optional security advisor
  and bounded timeouts.
- `PolicySnapshot` is actor/device/reference bound and deny-by-default.
- `PolicyActionRule` supplies exact capability/version baseline decisions.
- `PolicyAggregateRule` elevates matching combinations or repetitions.
- `SecurityAssessment` can only tighten final decisions.
- Success returns minimal `policy_decisions` plus one deterministic workflow status.
- Failures raise `PlanPolicyError` with a content-free code.

## Compatibility

The change is additive to graph state already containing `policy_decisions`. Output
statuses match `routeAfterPolicy`. It does not change REST, WebSocket, database,
provider or package contracts.

This preliminary decision does not replace 130003–130006 desktop authorization,
approval binding or execution-time TOCTOU checks.

## Rollback

Remove the policy module exports and restore 120006 to planned. Do not route an
unreviewed plan directly to approval or dispatch.
