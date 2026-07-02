# Database Design

## Core tables

`users`, `devices`, `projects`, `tasks`, `task_events`, `plans`, `actions`, `action_attempts`, `approvals`, `policy_versions`, `capability_grants`, `memories`, `artifacts`, `audit_records`, `plugin_installations`, plus LangGraph checkpoint tables.

## Constraints

Tasks own ordered events. Plans are immutable revisions. Actions reference one plan revision and have unique idempotency keys within executor scope. Approvals reference an action digest. Attempts append; reconciliation chooses effective result. Soft deletion is not used for secrets or user-requested erasure.

## Operations

Use UTC timestamps, explicit enums/check constraints, foreign keys, and least-privilege DB roles. Encrypt classified columns/artifacts. Migrations are forward-only in releases, transactional where supported, backed up, rehearsed on production-shaped data, and paired with application compatibility windows.

Indexes begin with task event ordering, pending actions/approvals, idempotency, memory scope/expiry, and audit correlation. Measure before adding vector or partition complexity.
