# Function Map

| User capability | Orchestrator | Backend service | Desktop adapter | Data | Permission |
|---|---|---|---|---|---|
| Ask/plan task | normalize, classify, plan | TaskService, ModelGateway | UI only | tasks, events | R0 |
| Continue project | project subgraph | ProjectService | app/process/project | projects, actions | mixed |
| Open/focus app | desktop specialist | ActionDispatcher | app/window | action receipt | R1 |
| Read project file | coding specialist | ArtifactService | scoped file | artifact ref | R0/R1 |
| Edit project | coding specialist | ActionDispatcher | patch | plan/action | R2 |
| Run build/test | terminal specialist | ActionDispatcher | process | logs/receipt | R2 |
| Git fetch/pull | Git specialist | ActionDispatcher | git process | repo observation | R1/R2 |
| Git push | Git specialist | ApprovalService | git process | approval/audit | R3 |
| Docker start | Docker specialist | ActionDispatcher | Docker API/CLI | health result | R2 |
| Browse/research | research/browser | ConnectorService | browser | citations/artifacts | R0/R2 |
| Submit web form | browser specialist | ApprovalService | browser | approval/receipt | R3 |
| Recall memory | memory specialist | MemoryService | privacy UI | memories | R0 |
| Store memory | memory candidate | MemoryService | consent UI | memories | R1/R2 |
| Voice request | same task graph | TranscriptionService | audio | transcript policy | R0 |
| Screen inspect | vision specialist | VisionGateway | capture/UIA | short-lived artifact | R1/R2 |
| Cancel task | cancellation route | TaskService | process/job cancel | event | R0 |

## Cross-cutting functions

Authentication: desktop device/session identity. Authorization: desktop policy engine. Schema validation: both boundaries. Idempotency: backend dispatch plus desktop receipt store. Audit: both processes with correlation. Redaction: at collection, persistence, prompt, and export. Verification: domain-specific read adapters.

## MVP vertical slice

Implement one end-to-end path before broadening: register project → submit “continue project” → inspect → plan → approve process starts → open VS Code → start declared Compose services → probe health → report. This slice exercises every architectural boundary without pretending the full OS is already built.
