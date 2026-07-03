# Coding Log — 120006 Evaluate Plan Policy v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120006` |
| Status | Complete |

## Delivered behavior

1. Added asynchronous `evaluatePlanPolicy` with typed immutable policy contracts.
2. Resolves exactly one actor/device-bound policy snapshot under a strict timeout.
3. Enforces a fixed deny/R4 default for unknown capability/version pairs.
4. Emits one stable, minimal decision for each plan action in original action order.
5. Enforces risk floors: R4 denies, R3 cannot allow, and R2 allow requires an opaque
   scoped grant reference.
6. Applies deterministic aggregate rules across related or repeated capabilities and
   elevates all matched actions together to prevent risk splitting.
7. Supports an optional bounded security assessment whose recommendations can only
   increase risk or tighten `allow → ask → deny`; weaker/equal advice is ignored.
8. Routes any-deny plans to `denied`, otherwise any-ask plans to
   `awaiting_approval`, and all-allow plans to `executing`.
9. Maps resolver/advisor errors, timeouts and malformed outputs to fixed safe codes
   while preserving cancellation.
10. Exports the policy node and contracts through `jarvis.graph`.

## Security boundary

Decision records exclude action arguments, policy rule bodies, arbitrary model prose
and secrets. This node is a preliminary graph gate only. The trusted desktop policy
engine tracked by 130003 must re-evaluate current resources, policy and grants before
execution; graph `allow` is not an executor authorization.

## Package impact

No package was added or changed. Root `requirements.txt` remains the authoritative
set of 75 exact package pins.
