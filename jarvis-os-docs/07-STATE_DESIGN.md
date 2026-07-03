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

`pending_approval` contains the persisted request/event identity, timezone-aware
issue/expiry times, exact bounded action preview and—only after interrupt resume—a
strict `{approval_id, action_digest, decision}` candidate. The preview is
JSON-compatible and contains no executable prose or arbitrary nested payload. The
next node validates semantic identity, expiry and one-time use before changing
status. After a successful atomic claim, the same field is replaced by a bounded
`approval.result` projection containing only version, approval/resolution/thread/
action identity, digest, outcome and decision time; raw resume transport is removed.

Before dispatch, `action_results` accepts only strict versioned collected-result
projections with dispatch/action/receipt identity, terminal outcome and timezone-
aware completion time. Dispatch uses successful outcomes solely to satisfy declared
dependencies; failed, cancelled or uncertain results never unlock dependents.
Queued action state remains authoritative in the database rather than being
misrepresented as a completed graph result.

Collection appends only the minimal `action.result` v1 projection:
`dispatch_id`, `action_id`, `receipt_id`, terminal outcome and completion time.
Attempt details, safe error code and artifact references remain in the correlated
durable result/event rather than being copied into graph state. Action, dispatch and
receipt identities are unique in one checkpoint. A late or timeout-overrun receipt
is `uncertain`; only later verification can determine task success.
