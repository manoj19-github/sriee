# Implementation Documentation Rules

## Canonical naming

`{platform}-{component}-{function}-{mandatory|optional}-{priority}-{completion}-{lifecycle}-{version}`

Example:

`python-fastapi-create-task-mandatory-p0-planned-current-v1`

## Values

- Requirement: `mandatory`, `optional`
- Priority: `p0` release-blocking, `p1` important, `p2` later, `p3` exploratory
- Completion: `planned`, `in-progress`, `blocked`, `complete`
- Lifecycle: `current`, `old`, `deprecated`, `removed`
- Version: `v1`, `v2`, incremented when behavior or contract materially changes

## Function record

Every row MUST define:

- Immutable Global ID.
- Canonical name and implementation-facing function name.
- Observable behavior, including failure behavior where important.
- Reads and writes across local, database, API, event, model, OS, and external boundaries.
- Honest completion/lifecycle status.
- Security, idempotency, verification, or dependency notes.

## Status transitions

`planned → in-progress → complete`

`planned|in-progress → blocked → in-progress`

`complete/current → complete/deprecated → complete/removed`

Completion requires code review, deterministic tests, relevant integration tests, security checks, documentation update, and a test-log receipt. A prototype, generated file, passing happy path, or schema-only change is not complete.

## Change rule

Before changing code, database objects, API/event contracts, prompts, policy, or operational behavior:

1. Locate the Global ID.
2. Update the function row and version/status if needed.
3. Create a coding-log entry referencing the ID.
4. Implement the smallest stage-compatible change.
5. Record tests against the same ID.
6. Add a deep dive for incidents, surprising behavior, security decisions, or architectural tradeoffs.
7. Add a version-log entry when any shipped contract or behavior changes.

Global IDs are never reused. Removed functions remain in the map as historical records.
