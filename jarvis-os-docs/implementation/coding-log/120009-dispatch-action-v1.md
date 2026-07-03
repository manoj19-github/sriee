# Coding Log — 120009 Dispatch Action v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120009` |
| Status | Complete |

## Delivered behavior

1. Added asynchronous `dispatchAction` and immutable request, proof, prior-result,
   concurrency-limit and dispatch-record contracts.
2. Requires `executing` state and exact runtime/checkpoint thread identity.
3. Revalidates plan, complete unique policy coverage, known unique prior results and
   the absence of deny decisions.
4. Selects only the first plan-ordered unresolved action whose declared dependencies
   all have successful collected results.
5. Rejects complete plans, blocked dependencies, unknown/duplicate/malformed results
   and selected actions without verification criteria.
6. For `ask`, requires a consumed approved result for the exact action/thread and
   recomputes the 120007 actor/device/thread/policy/action digest in constant time.
7. Canonicalizes sorted typed arguments, opaque resources, dependencies and
   verification codes into a bounded versioned `action.request`.
8. Excludes free-form strings/executable prose and includes only minimal policy and
   optional approval proof.
9. Derives a stable dispatch ID and a SHA-256 idempotency key over the complete
   security-relevant request.
10. Calls one injected atomic store operation to reserve trusted global/resource
    capacity and create queued state, event, outbox and expiring lease exactly once.
11. Validates exact replay records and lease duration, sanitizes failures, reports
    capacity separately and preserves cancellation.
12. Returns only `executing` graph status and never calls an executor.

## Concurrency and replay boundary

The store contract owns the transaction that checks global and per-resource
in-flight counts, reserves the resource lease and persists state/event/outbox.
The default permits 16 total queued/in-flight actions and one per exact opaque
resource. A node replay sends the identical request and must return the same record
without another reservation or durable message.

## Package impact

No package changed. The implementation uses pinned Pydantic and standard-library
modules already represented by the 75 exact, duplicate-free root requirement pins.
