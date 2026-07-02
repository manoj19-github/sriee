# Deep-Dive Log

Deep dives capture durable learning from architecture, performance, security, or incident research.

## Template

### DD-YYYYMMDD-NNN — Question

- Context and decision deadline:
- Authors/reviewers:
- Evidence and measurements:
- Constraints:
- Options:
- Tradeoffs:
- Experiments:
- Decision/recommendation:
- Confidence and assumptions:
- Risks/mitigations:
- Revisit trigger/date:
- Related ADR/issues:

## DD-20260702-001 — Planning/execution separation

- Question: where should Windows authority live?
- Evidence: model behavior is probabilistic; native Windows operations need canonical resources, session context, OS APIs, and independent authorization.
- Options: Python executes directly; C# executes model prose; C# executes typed actions after local policy.
- Decision: the third option. Python/LangGraph produces versioned `ActionRequest` plans. C# revalidates contract, resource, policy, approval, idempotency, and postcondition.
- Tradeoff: more contracts and integration testing, in exchange for a small enforceable trust boundary and reliable Windows adapters.
- Revisit trigger: none for authority; transport may evolve without collapsing the boundary.
