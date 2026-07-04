# Coding Log — 120012 Revise Plan v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120012` |
| Status | Complete |

## Delivered behavior

1. Requires planning status, exact runtime thread and revision `0` or `1`.
2. Revalidates current plan, intent, append-only results and current-revision
   criterion/aggregate evidence.
3. Allows revision only from recoverable verified evidence or a strict task/thread/
   actor/device/revision-bound corrected-scope candidate.
4. Resolves the current actor/device capability manifest, resources and bounded
   summaries before loading or generating a revision.
5. Uses the existing strict non-prose `ModelPlanDraft` response schema and one
   content-free repair attempt.
6. Lets the model return only corrective actions; application code immutably merges
   every executed action and its exact criteria.
7. Rejects removal/change of executed work, unchanged plans, invalid capabilities,
   resources, arguments, criteria, DAGs and aggregate budgets.
8. Prevents new/unexecuted actions from depending on failed, cancelled or uncertain
   receipts.
9. Enforces corrected opaque-resource scope when supplied.
10. Derives stable revision identity from task/thread, next revision, prior-plan
    digest and exact trigger.
11. Loads or atomically records one immutable revision and validates returned records
    against current contracts before projection.
12. Replaces the plan, increments revision, clears policy decisions/pending approval
    and returns to planning without clearing append-only result/observation evidence.
13. Preserves cancellation and sanitizes resolver/model/store failures.

## Security and authorization

The model cannot assign persisted revision identity, erase executed history, reuse an
unsuccessful receipt as dependency proof, broaden a corrected resource scope, retain
old policy/approval, or bypass downstream validation. Availability of a capability
still grants no permission.

## Package impact

No package changed; existing exact Pydantic, HTTPX/AnyIO and provider contracts are
reused.
