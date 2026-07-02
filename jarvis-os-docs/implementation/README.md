# JARVIS OS Step-by-Step Implementation Handbook

This handbook turns the architecture documents into a controlled build sequence. It follows the supplied function-map format: every function has a global ID, canonical lifecycle name, exact reads and writes, status, and change rule.

## Start here

1. [Documentation rules](00-program/00-DOCUMENTATION-RULES.md)
2. [Global ID registry](00-program/01-GLOBAL-ID-REGISTRY.md)
3. [Delivery sequence](00-program/02-DELIVERY-SEQUENCE.md)
4. [Sriee companion program](00-program/03-SRIEE-COMPANION-PROGRAM.md)
5. [Capability delivery program](00-program/04-CAPABILITY-ROADMAP.md)
6. [Developer coach and wellness program](00-program/05-DEVELOPER-COACH-WELLNESS-PROGRAM.md)
7. Read the function map for the component being changed.
8. Execute the matching build-stage guide.
9. Append coding, testing, deep-dive, and version records.

Current truth: [Status dashboard](STATUS-DASHBOARD.md).

Mandatory per-function execution records:

- [Coding logs](coding-log/)
- [Testing logs](testing-log/)
- [Versioning logs](versioning-log/)
- [Git delivery logs](git-log/)

Program-level and historical records:

- [Coding register](03-execution-records/CODING-LOG.md)
- [Testing register](03-execution-records/TESTING-LOG.md)
- [Deep-dive log](03-execution-records/DEEP-DIVE-LOG.md)
- [Version register](03-execution-records/VERSION-LOG.md)
- [Blocker log](03-execution-records/BLOCKER-LOG.md)

## Function maps

| Range | Component | Map |
|---|---|---|
| 110000–110099 | FastAPI platform | [fastapi-platform](01-function-maps/110-FASTAPI-PLATFORM.md) |
| 120000–120099 | LangGraph brain | [langgraph-brain](01-function-maps/120-LANGGRAPH-BRAIN.md) |
| 130000–130099 | Security and policy | [security-policy](01-function-maps/130-SECURITY-POLICY.md) |
| 140000–140099 | Data, memory, and RAG | [data-memory-rag](01-function-maps/140-DATA-MEMORY-RAG.md) |
| 150000–150099 | C# desktop shell | [desktop-shell](01-function-maps/150-CSHARP-DESKTOP-SHELL.md) |
| 160000–160099 | Windows executor | [windows-executor](01-function-maps/160-WINDOWS-EXECUTOR.md) |
| 170000–170099 | Developer integrations | [developer-integrations](01-function-maps/170-DEVELOPER-INTEGRATIONS.md) |
| 180000–180099 | Voice and vision | [voice-vision](01-function-maps/180-VOICE-VISION.md) |
| 190000–190099 | Observability and operations | [operations](01-function-maps/190-OBSERVABILITY-OPERATIONS.md) |
| 200000–200099 | Plugin platform | [plugin-platform](01-function-maps/200-PLUGIN-PLATFORM.md) |
| 210000–210099 | Sriee companion experience | [sriee-companion](01-function-maps/210-SRIEE-COMPANION.md) |
| 220000–220099 | Developer coach and wellness | [developer-coach-wellness](01-function-maps/220-DEVELOPER-COACH-WELLNESS.md) |

## Build stages

Stages are executed in numeric order. A later stage may be explored, but implementation cannot be marked complete until all dependency and exit gates pass.

| Stage | Outcome |
|---|---|
| 00 | Repository and contract foundation |
| 01 | FastAPI and PostgreSQL baseline |
| 02 | LangGraph task lifecycle |
| 03 | WPF desktop and secure transport |
| 04 | First “continue project” vertical slice |
| 05 | Coding, Git, terminal, and Docker assistance |
| 06 | Memory, RAG, voice, vision, Sriee, developer coaching, and general wellness |
| 07 | Plugins, hardening, packaging, and release |

## Status truth

Documentation existing does not mean software exists. At this baseline all application functions are `planned`. A function becomes `in-progress` only with linked code work, and `complete` only when its specified acceptance evidence is recorded in the test log.
