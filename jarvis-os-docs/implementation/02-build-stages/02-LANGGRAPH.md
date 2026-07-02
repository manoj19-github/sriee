# Stage 02 — LangGraph Task Lifecycle

## Dependencies

Stage 01 task/event persistence and Stage 00 fake executor.

## Functions

120000–120014, 110007, 140004, plus policy interface 130003–130006 using deterministic test implementation.

## Steps

1. Define `JarvisState`, reducers, status enum and allowed transition table.
2. Configure durable PostgreSQL checkpointer with stable task/thread mapping.
3. Implement pure normalize/context nodes using seeded project/capability data.
4. Implement provider-neutral model gateway and deterministic fake model.
5. Implement typed intent and plan outputs with one repair attempt.
6. Validate action schemas, DAG, known resources and budgets deterministically.
7. Implement allow/ask/deny routing with a test policy matrix.
8. Create approval interrupt node; keep side effects in a later dispatch node.
9. Implement resume validation, fake dispatch, result collection and independent verification.
10. Implement terminal response grounded in stored results.
11. Add cancellation, retry classification, revision limits and time/token/action budgets.
12. Add checkpoint serialization/version migration tests and sanitized graph traces.

## Required scenarios

Allow-only success; deny; approval approve/deny/expire/change; malformed model output; unknown action; cyclic plan; provider timeout; backend restart while awaiting approval; duplicate result; action timeout; cancellation at every state; partial failure; bounded revision; prompt injection in context.

## Exit gate

All scenarios pass with the fake executor, every task transition is persisted/replayable, restart does not repeat a side effect, and no model output can bypass schema or deterministic policy.
