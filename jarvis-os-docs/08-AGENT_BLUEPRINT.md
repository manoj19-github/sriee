# Agent Blueprint

An agent is a bounded reasoning component with a typed input, typed output, permitted context, budget, owner, and evaluation set. It is not a security principal.

| Agent | Produces | Forbidden |
|---|---|---|
| Orchestrator | Routing and final task state | Native execution |
| Planner | Dependency-aware `PlanDraft` | Approval or execution |
| Desktop | Native action proposals | Raw Win32 calls |
| Coding | Patches, tests, code explanations | Editing outside workspace scope |
| Git | Repository observations/actions | Force push by default |
| Docker | Compose/container actions | Unscoped prune |
| Terminal | Allowlisted command proposal | Shell interpolation from untrusted text |
| Browser | Navigation/form proposals | Credential extraction or silent submit |
| Research | Sourced findings | Treating retrieved text as policy |
| Memory | Recall/write candidates | Storing secrets or inferred sensitive traits |
| Voice | Transcript/speech requests | Hidden recording |
| Vision | OCR/screen observations | Emotion/intent inference |
| Security | Policy evidence and risk flags | Rewriting policy |
| Verifier | Postcondition verdict | Assuming dispatch equals success |

## Common contract

Each invocation includes objective, relevant references, capability manifest, policy snapshot, deadline, token/cost budget, and correlation ID. Output includes result, evidence references, confidence, assumptions, proposed actions, warnings, and schema version.

## Lifecycle

Proposal → threat review → prompt review → offline evaluation → shadow mode → limited preview → general availability → deprecation. Agents have semantic versions independent of the application.

## Delegation rules

The orchestrator may invoke specialists concurrently only for independent, read-only work. Maximum depth is two. No circular delegation. Specialists cannot call arbitrary specialists; routing is declared in graph code. The orchestrator remains accountable for merging contradictions and cannot report consensus as truth without evidence.
