# Coding Guidelines

## Shared

- Optimize for correctness, explicit contracts, and readable failure paths.
- Keep domain logic independent of FastAPI, LangGraph, WPF, and databases.
- Validate at boundaries; model impossible states with types.
- Structured errors have stable codes and safe messages.
- Time, randomness, filesystem, processes, and models are injected.
- No secrets, personal content, or raw prompts in logs.
- Comments explain constraints and reasons, not syntax.

## Python

Python 3.12+, type annotations, Ruff formatting/linting, strict Pyright or mypy, pytest, Pydantic at transport boundaries. Async functions are used for real async I/O, not decorative wrapping. Avoid mutable globals and import-time clients. Graph nodes are small, deterministic where possible, and return state deltas.

## C#

Current supported .NET LTS, nullable enabled, warnings as errors, analyzers, async with cancellation, records for contracts, `SafeHandle` for native resources, and MVVM separation. Do not use `async void` except UI event handlers. P/Invoke and elevation code require security review.

## Review checklist

Acceptance criteria met; permissions/risk classified; untrusted input handled; cancellation/timeouts/idempotency considered; telemetry safe; tests include failure paths; contracts/migrations compatible; docs/log updated; rollback credible.
