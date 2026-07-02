# Testing Guide

## Layers

1. Unit: domain, policy, state reducers, parsers, adapters with fakes.
2. Contract: JSON Schema/OpenAPI/events across Python and C#.
3. Graph: route, interrupt/resume, checkpoint migration, cancellation, bounded retries.
4. Integration: PostgreSQL/outbox, Redis fallback, model gateway, executor reconciliation.
5. Windows VM: apps, windows, paths, process trees, DPI, UIA, permissions, restart.
6. End-to-end: golden user workflows and partial failures.
7. AI evaluation: intent, plan validity, tool choice, faithfulness, injection resistance.
8. Security: abuse cases, fuzzing, secrets, dependency/static scans, forged approvals.
9. Performance/reliability: latency, soak, resource caps, disconnects, crash recovery.
10. Accessibility/privacy: keyboard/screen reader, indicators, retention/export/deletion.

## Release gates

All deterministic suites pass; no critical/high exploitable findings; contract compatibility passes; safety golden set has zero unapproved R3/R4 execution; migration/rollback rehearsal passes; task restart and dedupe scenarios pass; telemetry contains no seeded secrets.

## Required scenarios

Dirty Git tree, duplicate action delivery, expired/forged approval, symlink/junction escape, malicious web/file prompt, backend restart at interrupt, desktop crash mid-action, model timeout/malformed output, lost socket and event replay, cancellation during process tree, cloud unavailable, and stale project configuration.

Tests record seed, versions, environment, artifacts, and exit codes. Flaky tests are quarantined only with owner, issue, expiry, and compensating coverage.
