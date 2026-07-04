# Coding Log — 120015 Propose Task Reflection v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120015` |
| Status | Complete |

## Delivered behavior

1. Revalidates terminal identity, plan/results and independent verification evidence.
2. Accepts sorted current prompt/test/tool/policy version references only.
3. Accepts optional fixed-code user corrections bound to task/thread/actor/device and
   a subset of stored opaque evidence references.
4. Returns explicit `insufficient_evidence` for clean success without correction.
5. Maps corrected intent/scope/constraint to prompt review, corrected result to
   regression review, verified failure to failure fixture and uncertainty to
   verification fixture.
6. Uses only fixed summaries/recommendation codes and opaque evidence references.
7. Marks every candidate `review_required=true` and
   `automatic_application=false`.
8. Derives stable identity from task, verification, recommendation, correction and
   current component versions.
9. Loads or atomically records one immutable actor/device-owned candidate.
10. Sanitizes store/evidence failures and preserves cancellation.

## Safety

No model or mutation adapter is called. The function cannot edit prompts, tests,
policy, tools, source, configuration or memory. A candidate is a bounded review
hypothesis, never adopted learning.

## Package impact

No package changed.
