# JARVIS OS Engineering Handbook

Status: design baseline  
Last reviewed: 2026-07-02  
Target: Windows-first, local-first AI operating environment

This repository is the source of truth for JARVIS OS: a Python/FastAPI/LangGraph reasoning service paired with a C#/.NET Windows executor. JARVIS is not a chatbot with unrestricted tools. It is a policy-governed task system in which models propose typed actions and a native host independently authorizes, executes, and audits them.

## Reading paths

- Product: `00-VISION.md` → `02-PRODUCT_REQUIREMENTS.md` → `05-SERVICE_BLUEPRINT.md`
- Architecture: `03-SYSTEM_ARCHITECTURE.md` → `04-TECH_INFRA.md` → `06-LANGGRAPH_ARCHITECTURE.md`
- Contracts: `20-PERMISSION_SYSTEM.md` → `26-API_SPECIFICATION.md` → `27-WEBSOCKET_PROTOCOL.md`
- Delivery: `29-CODING_GUIDELINES.md` → `31-TESTING_GUIDE.md` → `35-VERSIONING.md` → `37-CI_CD.md`
- Operations: `33-DEBUG_LOG.md` → `34-DEEP_DIVE_LOG.md` → `39-MONITORING.md`
- Runtime behavior: `01-MASTER_PROMPT.md` and `prompts/`
- Step-by-step implementation: `implementation/README.md`
- Consolidated capability roadmap: `41-SRIEE_CAPABILITY_ROADMAP.md`
- Developer coach and wellness: `42-DEVELOPER_COACH_WELLNESS.md`

## Non-negotiable invariants

1. The model never receives direct OS authority.
2. Every action is schema-validated, policy-evaluated, scoped, time-bounded, and audited.
3. High-risk work requires an explicit, action-bound approval.
4. Plans and execution results use versioned contracts; prose is never executable.
5. Side effects are idempotent where possible and carry an idempotency key.
6. Secrets, raw microphone streams, screenshots, and personal memory are private by default.
7. “Always listening” means local wake-word detection, visible state, and an immediate hardware/software kill control.
8. The system reports uncertainty and partial failure honestly.

## Documentation conventions

RFC 2119 words (`MUST`, `SHOULD`, `MAY`) are normative. Each material architecture change adds an ADR. Living logs are append-only. Mermaid diagrams are explanatory; JSON Schema/OpenAPI and code are authoritative.

## Definition of documentation complete

A feature is document-ready only when its owner, inputs, outputs, permission class, failure behavior, telemetry, tests, rollback, and user-visible experience are defined.
