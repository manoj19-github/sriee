# Roadmap

## Milestone 0 — Contracts and threat model

Repository, ADRs, action/event schemas, policy matrix, fake executor, task state machine, golden safety tests.

Exit: Python and C# contract tests agree; forged/changed approvals fail.

## Milestone 1 — Vertical slice

WPF shell, FastAPI lifecycle, WebSocket replay, LangGraph plan/interrupt/resume, project registry, open VS Code, start declared processes/Compose, health verification.

Exit: “continue project” passes clean/dirty/offline/crash/cancel scenarios in a Windows VM.

## Milestone 2 — Developer copilot

Scoped file patches, build/test, Git reads and controlled mutations, Docker logs, diagnostics.

## Milestone 3 — Context

Memory controls, project RAG, UI Automation, request-scoped screen OCR.

## Milestone 4 — Voice

Local wake word/STT/TTS, visible privacy controls, accessibility and noisy-room evaluation.

## Milestone 5 — Extensibility

Out-of-process plugin SDK, signing, permission review, sample plugins.

## Later, only with evidence

Browser transactions, email/calendar writes, elevation broker, remote control plane, and camera features. Each requires its own threat model and opt-in launch gate.

## Explicitly never on autopilot

Purchases, production deployment, messages/publication, account security changes, destructive cleanup, security bypass, and inferred health/emotional judgments.
