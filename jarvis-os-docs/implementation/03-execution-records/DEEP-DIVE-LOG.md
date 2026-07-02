# Step-by-Step Deep-Dive Log

Create a deep dive for a consequential decision, incident, security finding, unexpected production behavior or evidence that invalidates an assumption.

## Entry template

### DD-YYYYMMDD-NNN — Question

- Global IDs/stage:
- Context/deadline:
- Evidence and measurements:
- Constraints:
- Options considered:
- Experiments:
- Decision:
- Tradeoffs:
- Security/privacy effect:
- Confidence/unknowns:
- Revisit trigger/date:
- ADR/issues/tests:

## DD-20260702-001 — Separate planning from execution

- Global IDs/stage: 120004–120011, 130003–130006, 160001–160013 / foundation.
- Evidence: model behavior is probabilistic; Windows actions require local identity, canonical resources, receipts and native verification.
- Options: direct Python tools; C# executes model prose; C# executes typed policy-validated actions.
- Decision: typed actions with independent local policy and action-bound approval.
- Tradeoff: more contract work in exchange for an enforceable security and recovery boundary.
- Revisit: transport can evolve; authority separation does not.

## DD-20260702-002 — Isolate database objects in `jarvis`

- Global IDs/stage: 140000–140005 / infrastructure.
- Evidence: user supplied an existing database used by another application and requested a separate project schema.
- Decision: all JARVIS objects MUST be schema-qualified under `jarvis`; migrations MUST prove they do not modify `public` or unrelated schemas.
- Security/privacy effect: credentials are never copied into source or documentation and should be rotated after plaintext exposure.
- Revisit: separate database/role before production isolation or scaling.
