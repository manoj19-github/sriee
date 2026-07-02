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

## Milestone 5 — Sriee companion

Female voice profile, text/voice relationship settings, morning/evening briefings, consented routines, original stories/jokes, opt-in playful romantic conversation, and immediate stop/private controls.

## Milestone 6 — Developer coach and general wellness

Developer profile, learning plans, trusted progress, quizzes/challenges, workflow help, project/career coaching, achievements, bounded proactive prompts, manual wellness records, optional connectors, configurable care reminders and non-diagnostic check-ins.

## Milestone 7 — Visible sensors

Camera session controls, local presence, optional enrolled-face personalization, uncertain expression cues, document/QR scanning and biometric deletion/liveness evaluation.

## Milestone 8 — Integrations

Calendar/reminders, notifications, media, system health, browser/research and draft-first email behind independent adapters and grants.

## Milestone 9 — Extensibility

Out-of-process plugin SDK, signing, permission review, sample plugins.

## Later, only with evidence

Browser transactions, email/calendar writes, elevation broker, remote control plane, smart home, mobile/wearable synchronization and multi-user features. Each requires its own threat model and opt-in launch gate.

## Explicitly never on autopilot

Purchases, production deployment, messages/publication, account security changes, destructive cleanup, security bypass, and inferred health/emotional judgments.
