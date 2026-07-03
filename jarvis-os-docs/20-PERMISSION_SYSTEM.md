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

## Sensors and companion mode

Camera, microphone, screen capture and biometric enrollment are separate capabilities; enabling Sriee companion mode grants none of them automatically. Each grant declares device, purpose, activation mode, foreground/ambient scope, retention, provider egress, expiry and indicator behavior.

The permission center provides one-action mute, camera off and **Stop Sriee** controls. Stop ends active capture/playback and proactive routines immediately; optional revoke also removes eligible remembered sensor grants. OS privacy controls and hardware shutters cannot be overridden.

Broad machine assistance is composed from narrow capabilities rather than a “full control” grant. Companion-originated actions use the same risk tier, preview, approval digest, cancellation, verification and audit rules as requests from the normal task UI.

## Approval object

Contains approval ID, actor/device IDs, action digest, human-readable preview, exact resource scope, policy version, issued/expiry times, nonce, decision, and authenticator evidence. Any action change invalidates approval. “Approve all” cannot cover R3.

The graph pause binds one action only. Its digest also covers task/thread identity,
capability/version, sorted typed parameters and dependencies, timeout, verification
definitions and preliminary policy decision/version. A replay uses the same
deterministic approval identity and cannot extend expiry or append another request
event. Other `ask` actions require their own later approval.

## Remembered grants

Only eligible R1/R2 capabilities may be remembered. Grants are narrow, visible, expiring, revocable, and constrained by project/resource. A model cannot request or edit grants directly.

## TOCTOU defense

Immediately before execution, re-resolve canonical resources, re-evaluate policy, verify approval signature/digest/expiry, and reject changed files/windows/targets when material to safety.

## Graph preliminary decisions

The graph stores one minimal preliminary decision per action to route plans toward
denial, native approval or execution. Aggregate rules evaluate combinations and
repeated capabilities so risk cannot be reduced by splitting one effect across
multiple actions. These records are checkpoint evidence only: the local desktop
policy engine remains authoritative and re-evaluates every action immediately before
dispatch.
