# LangGraph Architecture

```mermaid
flowchart TD
  S([START]) --> N[normalize_request]
  N --> C[load_context]
  C --> I[classify_intent]
  I --> P[plan]
  P --> V[validate_plan]
  V --> Y[policy]
  Y -->|deny| R[respond]
  Y -->|ask| A[approval interrupt]
  A -->|approved| E[dispatch]
  A -->|denied| R
  Y -->|allow| E
  E --> Q[collect results]
  Q --> K[verify]
  K -->|recoverable| P
  K --> R
  R --> Z([END])
```

## Design rules

- Nodes return state deltas; reducers are explicit.
- The graph owns workflow state, not open sockets or native handles.
- Planning may fan out read-only specialists. Side effects use a dependency-ordered lane.
- Every run has stable `task_id` and LangGraph `thread_id`.
- Production uses a durable PostgreSQL checkpointer.
- Dynamic `interrupt()` is the approval mechanism. Interrupt payloads are JSON-serializable.
- Code before an interrupt is pure or idempotent because its node restarts on resume.
- Side effects live after approval in separate nodes.
- Recursion, retries, plan revisions, tokens, time, and cost are bounded.

## Routing

Deterministic routing handles contract validity, risk, availability, and status. A model may recommend an agent but cannot override routing constraints. Unknown intent routes to clarification or safe response, never a general-purpose terminal.

## Specialist subgraphs

Coding, desktop, Git, Docker, browser, research, memory, voice, and vision specialists produce observations or proposed actions under narrow schemas. They do not grant one another permissions. Use subgraphs when a domain needs its own state and evaluation set, not merely to create impressive diagrams.

## Recovery

Transient read failures retry with jitter. Side-effect retry requires idempotency support and reconciliation. A plan can be revised at most twice automatically. Resume uses the same thread and an approval payload bound to the pending interrupt.

## Evaluation hooks

Capture intent correctness, plan validity, unnecessary actions, policy agreement, tool selection, verification quality, latency, cost, and user correction. Store sanitized datasets separately from production personal memory.

## Implemented graph construction v1

`buildJarvisGraph` compiles a fixed thirteen-node topology from an exact node registry.
The registry, state schema, append reducers, graph/state versions and checkpointer
binding are validated before LangGraph compilation. Policy, approval and verification
branches route only from explicit workflow status values; an unknown value fails
closed with a safe contract code.

Construction attaches an injected saver that the trusted composition root marks
durable, but does not open a database connection or invoke any node. The production
PostgreSQL saver and checkpoint migrations remain separate work under Global ID
`140004`.

The implemented `normalizeRequest` entry node validates the existing task envelope,
principal identifiers, v1 transport contract and starting status. It preserves valid
task/thread IDs; when absent, it assigns one task ID and derives the thread ID from it.
The node preserves user text or transcript content exactly and returns only the
normalized request/identity/status delta. It performs no retrieval, classification,
model call or persistence.

The implemented `loadBoundedContext` node queries injected project, capability,
policy and memory reference sources concurrently with strict per-source deadlines and
limits. Policy and capability references are mandatory and device-bound; project and
memory source outages degrade through safe retryable state errors. Every returned
reference is checked against actor/device ownership and its declared kind/prefix.
Only ordered opaque IDs enter `context_refs`; source content and arbitrary metadata
cannot be represented by the reference contract.

The implemented `classifyIntent` node resolves those references ephemerally and uses
the environment-routed structured-model gateway to produce a fixed intent,
confidence, target,
authorized scope and ambiguity codes. Application rules—not the model—decide whether
the intent is consequential or requires clarification.

The implemented `createPlanDraft` node consumes only a non-ambiguous intent and an
injected actor/device-bound planning bundle. It accepts registered capability/version
pairs, typed scalar bindings, opaque resources, earlier-step dependencies and
declared verification codes. Stable action and criterion IDs are application-derived.
Raw paths, command text, nested payloads and model risk/policy decisions cannot enter
the plan projection. Capability availability remains distinct from permission.

The implemented `validatePlan` node independently revalidates the checkpointed draft
before policy evaluation. It re-resolves the current actor/device-bound capability
manifest and opaque resources, validates typed bindings and exact versions, checks
the complete dependency graph for unknown edges, self-dependencies and cycles, and
rejects duplicate action semantics. Every action must have at least one verification
definition declared by its capability. Trusted limits bound action/criterion counts,
arguments, dependency edges, aggregate timeout and critical-path timeout. All
failures use content-free typed codes; no model call or side effect occurs.

The implemented `evaluatePlanPolicy` node resolves the one actor/device-bound policy
snapshot referenced by the task and produces exactly one preliminary decision for
every validated action. Unknown capability/version pairs use the R4 default deny.
Risk floors enforce R4 deny, forbid R3 allow and require a scoped grant for R2 allow.
Aggregate rules match related or repeated capabilities across the complete plan and
elevate all matches together, preventing a higher-risk operation from being split
into individually permissive steps. An optional security specialist may recommend a
higher risk or stricter decision; equal/weaker advice is ignored. Any deny routes the
whole plan to `denied`, otherwise ask routes to `awaiting_approval`, and all-allow
routes to `executing`.

This graph decision is defense in depth, not final authorization. The trusted desktop
policy engine re-resolves resources, evaluates current grants/policy and validates any
approval immediately before execution under 130003–130006.

The implemented `pauseForApproval` node selects only the first plan-ordered `ask`
action. It canonically binds task/thread, actor/device, exact capability/version,
sorted typed arguments/dependencies, timeout, verification definitions and policy
decision/version into a `sha256-v1` digest. A deterministic approval ID lets the
injected store atomically create the pending approval and event once or return the
same record when LangGraph restarts the node on resume.

Only after persistence succeeds does the node call `interrupt()` with a bounded
JSON-safe preview containing the exact action, parameters, opaque resource scope,
risk, reasons, digest and expiry. No exception handler surrounds the interrupt
control flow. Resume input is checkpointed only after it matches the strict
approval-ID/digest/approve-or-deny transport shape; semantic authentication and
consumption remain 120008. Execution stays in later nodes.

The implemented `resumeApproval` node revalidates the complete pending checkpoint,
including cross-field action/digest/policy bindings, before consulting storage. It
requires the runtime LangGraph thread and checkpoint task/thread/actor/device
identities to match the persisted request, then compares the resume approval ID and
digest in constant time. An injected store must atomically authenticate and claim
the identity-complete decision once, returning an authoritative approved, denied or
expired resolution with time consistency enforced by the typed contract.

Only a bounded versioned result projection remains in checkpoint state. Approved
routes to `executing`, denied to `denied`, and a decision resolved at or after expiry
to `expired`. Duplicate/concurrent resolution fails closed, and this node performs
no action dispatch or side effect beyond the atomic decision claim.

The implemented `dispatchAction` node selects only the first plan-ordered unresolved
action whose dependencies have collected successful results. It requires exact
one-per-action policy coverage with no deny, validates the active runtime thread,
and permits an `ask` action only when the consumed approval names the same action
and its digest recomputes exactly from task/thread, actor/device, action,
verification and preliminary policy fields.

The node canonicalizes a bounded `action.request` containing typed scalar bindings,
opaque resource IDs, dependencies, verification codes, timeout, minimal policy
proof and—only for `ask`—minimal approval proof. Free-form strings, executable
prose, unknown result actions, duplicate results and incomplete dependencies fail
before persistence.

Dispatch never invokes an executor directly. One injected atomic store operation
must enforce trusted global/per-resource in-flight limits while creating or
returning the exact queued action state, event, outbox record and expiring resource
lease. Stable dispatch identity plus a full-request SHA-256 idempotency key make node
replay safe: it cannot append another event/outbox or acquire a second lease.

The implemented `collectActionResult` node accepts a strict JSON result envelope
containing dispatch/idempotency/task/thread/action/attempt/receipt/device identity,
terminal outcome, timezone-aware execution times, a safe error code and opaque
artifact references. Raw executor output, extra fields, non-JSON values and
oversized payloads are rejected before persistence.

An injected store atomically correlates the candidate with the actor/device-owned
queued dispatch, writes one immutable result/event and releases its resource lease,
or returns the exact existing collection for duplicate delivery. The returned
record is revalidated against the original request and dispatch. A result completing
after lease expiry or running beyond its action timeout is projected as `uncertain`,
never trusted as late success.

Graph replay distinguishes durable and checkpoint idempotency. If storage committed
but the graph checkpoint is stale, the stored minimal result is appended so evidence
is not lost. If that exact action/dispatch/receipt already exists in graph state, the
node returns an empty append delta so reducers cannot duplicate it. Any different
result for the action fails closed. Collection transitions to `verifying`; it does
not equate executor success with verified task success.

The implemented `verifyOutcome` node resolves a read-only probe for each exact
capability/version/verification-code criterion and supplies only typed action
bindings, opaque resources and the correlated receipt identity. Executor outcome is
not used as criterion proof: a successful receipt can fail verification, while an
executor failure may still have independently observable successful postconditions.

Definite pass/fail evidence requires opaque evidence references. Missing receipts,
missing probes, timeout and read-path outage become explicit uncertainty; malformed,
stale or mis-correlated probe evidence fails closed. The application deterministically
derives succeeded, partially succeeded, failed or uncertain from all criteria.
Revision occurs only when every unresolved criterion is retryable and the two-
revision budget remains.

One immutable verification record is loaded or recorded through an injected store.
Stable plan/revision identity makes database recovery and checkpoint replay safe.
Stored/checkpointed outcome, counts, recovery, criterion/action/receipt bindings,
evidence timing and observation IDs are recomputed before routing, so a structurally
valid forged aggregate cannot change workflow status.

The implemented `revisePlan` node accepts only current-revision recoverable
verification evidence or an identity-bound corrected-scope candidate and enforces
the two-revision ceiling. It resolves current registered capabilities/resources and
uses the same strict typed plan schema as initial planning.

The model may return only corrective actions. Application code merges every action
and criterion already backed by an append-only result, rejects new dependencies on
unsuccessful receipts, validates the complete revised plan and persists one stable
immutable revision. Projection increments `revision_count`, clears preliminary
policy and pending approval, and returns to `planning`; results and observations
remain append-only evidence.

The implemented `renderFinalResponse` node revalidates terminal status against stored
verification, policy, approval and receipt projections, then applies fixed concise
templates. Succeeded/partially-succeeded claims require matching independent
verification; exhausted uncertainty is described as unverified rather than failed.
Only opaque evidence/receipt references and fixed unresolved codes are exposed.

One stable actor/device-owned response is loaded or persisted before checkpoint
projection. Exact checkpoint replay performs no I/O, and no model prose,
chain-of-thought, raw artifact content or guessed completion can enter the response.
