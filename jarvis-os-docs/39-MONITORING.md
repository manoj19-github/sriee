# Monitoring and Observability

## Signals

- Task counts/duration by terminal status and intent.
- Planning/model latency, tokens, provider errors, budget exhaustion.
- Policy allow/ask/deny counts and approval latency/expiry.
- Action queue/dispatch/execution/verification latency and error code.
- WebSocket connection, lag, replay, and dropped frames.
- DB/checkpoint/outbox health, queue depth, disk use.
- Desktop CPU/memory/handles/crashes and adapter health.

## Tracing

One correlation trace spans request → graph nodes → policy → approval → dispatch → executor → verification. Include IDs and safe fingerprints, never raw transcript, prompt, screen, file content, command output, tokens, or secrets by default.

## SLO starting points

99.9% local task API availability while app is running; p95 task-event delivery under 250 ms; 99% successful reconnect/replay within 10 seconds; zero unapproved high-risk executions; zero known secret leakage.

Alerts need an owner, runbook, severity, user impact, and clear condition. Local users can inspect/export a redacted diagnostic bundle and disable optional telemetry.
