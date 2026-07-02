# Stage 01 — FastAPI and Data Baseline

## Dependencies

Stage 00 complete. The `jarvis` PostgreSQL schema exists; application objects do not.

## Functions

110000–110006, 110010–110011, 140001–140005, 190004.

## Steps

1. Create backend package with settings, domain/application/API/persistence boundaries.
2. Add FastAPI lifespan and dependency initialization with fake model/graph.
3. Configure PostgreSQL with schema-qualified `jarvis` objects and least-privilege connection settings.
4. Create migration baseline for tasks, task events, outbox, actions, attempts, approvals, policies and migration metadata.
5. Implement repositories with transactions, optimistic concurrency and immutable event sequence.
6. Implement `POST /api/v1/tasks`, task lookup, event pagination and cancellation.
7. Add liveness/readiness endpoints and stable error envelope.
8. Add an outbox publisher interface with in-process test implementation; Redis remains optional.
9. Add idempotency handling for task creation.
10. Add backup command/runbook for only the `jarvis` schema.
11. Run migrations against disposable DB first, then explicitly approved target environment.

## Required tests

- Migration up from empty schema and compatibility check from prior baseline.
- Duplicate task key/same payload returns same task; different payload returns conflict.
- Concurrent event append preserves unique ordering.
- Transaction rollback leaves neither event nor outbox half-written.
- Restart preserves task/event retrieval.
- SQL objects remain inside `jarvis`; no modification to `public` or unrelated schemas.

## Exit gate

Backend starts and shuts down cleanly, creates/retrieves/cancels durable tasks, replays ordered events after restart, reports dependency health, and restores a test backup. No LangGraph or desktop side effect is claimed yet.
