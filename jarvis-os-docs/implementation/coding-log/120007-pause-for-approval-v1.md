# Coding Log — 120007 Pause For Approval v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120007` |
| Status | Complete |

## Delivered behavior

1. Added asynchronous `pauseForApproval` and immutable approval contracts.
2. Validates awaiting-approval state, complete one-per-action policy coverage and the
   absence of deny decisions before pausing.
3. Selects only the first plan-ordered `ask`; no approval can cover multiple actions.
4. Canonically hashes task/thread, actor/device, exact action, typed parameters,
   dependencies, timeout, verification codes and policy decision/version.
5. Derives stable approval identity from the exact action digest.
6. Builds a bounded JSON-safe preview with exact parameter and opaque-resource scope.
7. Calls an injected atomic create-or-get store before interrupt; replay sends the
   identical request so approval and event are persisted once.
8. Invokes LangGraph `interrupt()` outside exception handling and performs no action.
9. Restricts resume transport to approval ID, action digest and approve/deny before
   allowing it into checkpoint state.
10. Sanitizes persistence, record-conflict and payload failures while preserving
    cancellation.

## Replay and security boundary

LangGraph restarts an interrupted node from its beginning on resume, so every
operation before `interrupt()` is deterministic and idempotent. The store contract
must atomically create approval+event or return the exact existing record without
extending expiry. The node does not authenticate/consume the decision or dispatch an
action; those remain separate 120008/120009 responsibilities.

## Package impact

No package changed. The implementation uses pinned LangGraph, Pydantic and standard
library modules already represented by the 75 exact root requirement pins.
