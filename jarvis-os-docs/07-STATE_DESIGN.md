# State Design

## Canonical graph state

```python
class JarvisState(TypedDict):
    contract_version: str
    task_id: str
    thread_id: str
    actor_id: str
    device_id: str
    request: dict
    context_refs: list[str]
    intent: dict | None
    plan: dict | None
    policy_decisions: list[dict]
    pending_approval: dict | None
    action_results: Annotated[list[dict], operator.add]
    observations: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]
    status: str
    revision_count: int
    final_response: dict | None
```

State stores references to large artifacts, not screenshots or repositories. Reducer-backed lists append immutable events. Mutable derived views are rebuilt from events.

## State machine

`created → planning → awaiting_approval → executing → verifying → terminal`

Terminal states: `succeeded`, `partially_succeeded`, `failed`, `cancelled`, `denied`, `expired`.

Only declared transitions are accepted. Cancellation can enter from every non-terminal state. A terminal task is never reopened; continuation creates a child task linked by `parent_task_id`.

## Identifiers

Use UUIDv7/ULID-style sortable IDs. `action_id` identifies semantics; `attempt_id` identifies an execution try; `idempotency_key` deduplicates equivalent side effects; `correlation_id` links distributed telemetry.

## Serialization

Persist JSON-compatible values with explicit schema versions. Never checkpoint file handles, clients, callbacks, secrets, or model objects. Migrations MUST be forward-tested against representative saved checkpoints before release.

## Invariants

- A dispatched action has exactly one policy decision.
- An `ask` action has a matching unexpired approval digest before execution.
- Results are append-only and identify executor/device.
- The final response cites only stored observations/results.
- Redaction occurs before persistence and telemetry export.

`policy_decisions` contains minimal immutable projections: stable decision/action IDs,
`allow|ask|deny`, R0–R4 tier, fixed reason codes, policy reference/version, optional
opaque scoped-grant reference and whether fresh approval is required. It excludes
action arguments, policy rule bodies, model prose and secrets.
