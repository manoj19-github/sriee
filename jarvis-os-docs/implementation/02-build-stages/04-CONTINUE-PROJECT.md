# Stage 04 — “Continue Project” Vertical Slice

## Dependencies

Stages 00–03 complete. User has a safe test project and Docker/VS Code only if their steps are enabled.

## Functions

150007, 160007, 160010–160011, 170000–170006, 170009–170013.

## Steps

1. Implement project registry UI/API with canonical root, runbook and health checks.
2. Define typed runbook: apps, ProcessSpecs, Compose project, dependencies and verification.
3. Implement read-only workspace and Git inspection with exclusions/limits.
4. Implement “continue project” intent and plan builder.
5. Add registered VS Code adapter and verify opened workspace.
6. Add bounded ProcessSpec executor with argument arrays, job ownership and output limits.
7. Add Git fetch/update logic; block update for dirty/conflicted worktree.
8. Add Compose validation, start and health adapters with unsafe configuration denial.
9. Render plan and approvals; execute dependency order with cancellation.
10. Verify Git, app, processes, containers and application health separately.
11. Produce readiness summary that names partial/unverified components.
12. Package a deterministic demo project/scenario for repeatable VM testing.

## Acceptance matrix

Clean/current; clean/behind; dirty; conflicted; Docker unavailable; one service unhealthy; VS Code absent; network offline; cancellation during start; desktop/backend crash; duplicate dispatch; stale runbook path; malicious project instruction.

## Exit gate

The demo request reaches the correct verified outcome for every matrix case, never discards local changes, never runs unregistered command, and recovers without repeating completed side effects.
