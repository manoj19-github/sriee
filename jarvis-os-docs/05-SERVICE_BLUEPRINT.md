# Service Blueprint

| Stage | User experience | Desktop/frontstage | Backend/backstage | Evidence and recovery |
|---|---|---|---|---|
| Invoke | Types or speaks request | Captures input; shows task ID | Creates task and initial event | Request visible; cancel available |
| Understand | Sees interpretation | Shows selected project/context | Classifies intent; retrieves minimal context | User can correct scope |
| Plan | Reviews steps | Renders typed plan | Planner and policy evaluate actions | Plan digest and risk badges |
| Approve | Confirms material changes | Native approval card | Graph interrupt persists state | Expiry, scope, deny/edit |
| Execute | Watches progress | Executor runs one bounded action | Orchestrator dispatches dependencies | Per-action status; dedupe |
| Verify | Sees checks | Native adapters inspect state | Verifier compares postconditions | Retry safe reads or recover |
| Complete | Gets concise result | Notification and task history | Final state and memory candidate | Audit ID; undo where supported |

## Service ownership

- Desktop team: UX, permissions, native adapters, local identity.
- AI platform: graph, prompts, provider gateway, evaluation.
- Backend: APIs, persistence, scheduling, event stream.
- Security: threat model, signing, policy baselines, incident response.
- Quality: contract, integration, VM, safety, and evaluation suites.

## Failure promises

- Offline: registered deterministic workflows remain available; cloud-only steps are marked unavailable.
- Approval timeout: no execution; task stays resumable or expires by policy.
- Partial execution: completed actions remain visible; dependents stop; rollback is offered only when known safe.
- Executor crash: an action with an existing receipt is reconciled before retry.
- Model error: no malformed action crosses the executor boundary.

## Support artifacts

Every task exposes a redacted diagnostic bundle containing versions, correlation IDs, state transitions, policy decisions, timings, and adapter errors. It excludes prompt secrets, credentials, and raw personal artifacts by default.
