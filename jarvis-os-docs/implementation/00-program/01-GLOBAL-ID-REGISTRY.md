# Global ID Registry

| Range | Owner/component | Status | Notes |
|---|---|---|---|
| 110000–110099 | Python FastAPI platform | allocated | REST, WebSocket, lifecycle, task service |
| 120000–120099 | LangGraph brain | allocated | state, planning, approval, execution, verification |
| 130000–130099 | Security and policy | allocated | identity, policy, approvals, secrets, audit |
| 140000–140099 | Data, memory, and RAG | allocated | PostgreSQL, migrations, artifacts, retrieval |
| 150000–150099 | C# WPF desktop shell | allocated | MVVM UI, task timeline, approval UX |
| 160000–160099 | Windows executor | allocated | adapters, processes, windows, files, receipts |
| 170000–170099 | Developer integrations | allocated | project, terminal, Git, Docker, VS Code |
| 180000–180099 | Voice and vision | allocated | wake word, STT/TTS, UIA, OCR, capture |
| 190000–190099 | Observability and operations | allocated | telemetry, health, packaging, recovery |
| 200000–200099 | Plugin platform | allocated | manifest, signature, sandbox, lifecycle |
| 210000–219999 | Future first-party components | reserved | allocate via architecture review |

## Allocation rules

IDs are assigned sequentially inside the owning range and never encode database primary keys. Moving a function to another component does not change its ID. A replacement function receives a new ID and links the superseded ID in Notes.

## Current infrastructure facts

- PostgreSQL database: existing external database selected by the user.
- PostgreSQL schema: `jarvis` exists and is owned by the configured application database role.
- Application tables/migrations: not created.
- Redis namespace/data: not created.
- Source repository/application projects: not created.

Secrets, host addresses, passwords, and tokens MUST NOT be copied into this handbook.
