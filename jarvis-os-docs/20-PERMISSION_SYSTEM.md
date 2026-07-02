# Permission System

## Decision

`allow`, `ask`, or `deny`, produced from actor + device + capability + resource + parameters + context + policy version. Risk labels inform UX but do not replace rules.

| Tier | Examples | Default |
|---|---|---|
| R0 observe | clock, registered app list | allow |
| R1 reversible local | open app, focus window | allow/ask |
| R2 scoped mutation | edit project, start process | ask or remembered scoped grant |
| R3 external/system | push, send, install, settings | per-action ask |
| R4 prohibited | bypass security, steal credentials | deny |

## Approval object

Contains approval ID, actor/device IDs, action digest, human-readable preview, exact resource scope, policy version, issued/expiry times, nonce, decision, and authenticator evidence. Any action change invalidates approval. “Approve all” cannot cover R3.

## Remembered grants

Only eligible R1/R2 capabilities may be remembered. Grants are narrow, visible, expiring, revocable, and constrained by project/resource. A model cannot request or edit grants directly.

## TOCTOU defense

Immediately before execution, re-resolve canonical resources, re-evaluate policy, verify approval signature/digest/expiry, and reject changed files/windows/targets when material to safety.
