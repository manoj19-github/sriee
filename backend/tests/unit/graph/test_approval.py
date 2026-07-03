from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from jarvis.graph import (
    ApprovalPauseError,
    ApprovalPauseService,
    ApprovalPauseSettings,
    JarvisState,
    PendingApprovalRecord,
    PolicyDecision,
    PolicyDecisionKind,
    RiskTier,
    pauseForApproval,
)


TASK_ID = "tsk_" + "f" * 32
THREAD_ID = "thr_" + "f" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
POLICY_REF = "pol_policy001"
RESOURCE_ID = "res_project001"
ACTION_INSPECT = "act_" + "1" * 24
ACTION_UPDATE = "act_" + "2" * 24
DECISION_INSPECT = "pdc_" + "3" * 24
DECISION_UPDATE = "pdc_" + "4" * 24
NOW = datetime(2026, 7, 3, 9, 0, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def plan() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "objective": "modify_project",
        "assumptions": ["current_context"],
        "actions": [
            {
                "action_id": ACTION_INSPECT,
                "capability_id": "project.inspect",
                "capability_version": "1.0.0",
                "arguments": [
                    {"name": "project", "value": RESOURCE_ID},
                ],
                "dependencies": [],
                "timeout_seconds": 20,
            },
            {
                "action_id": ACTION_UPDATE,
                "capability_id": "project.update",
                "capability_version": "1.2.0",
                "arguments": [
                    {"name": "mode", "value": "safe_fix"},
                    {"name": "project", "value": RESOURCE_ID},
                ],
                "dependencies": [ACTION_INSPECT],
                "timeout_seconds": 90,
            },
        ],
        "success_criteria": [
            {
                "criterion_id": "crt_" + "5" * 24,
                "action_id": ACTION_INSPECT,
                "verification_code": "inspection_recorded",
            },
            {
                "criterion_id": "crt_" + "6" * 24,
                "action_id": ACTION_UPDATE,
                "verification_code": "tests_passed",
            },
        ],
        "warnings": ["state_may_change"],
    }


def decision(
    *,
    action_id: str,
    decision_id: str,
    selected: PolicyDecisionKind,
    risk_tier: RiskTier,
) -> dict[str, Any]:
    return PolicyDecision(
        decision_id=decision_id,
        action_id=action_id,
        decision=selected,
        risk_tier=risk_tier,
        reason_codes=(
            "read_only_inspection"
            if selected is PolicyDecisionKind.ALLOW
            else "scoped_project_mutation",
        ),
        policy_reference_id=POLICY_REF,
        policy_version="1.0.0",
        requires_fresh_approval=(
            selected is PolicyDecisionKind.ASK
        ),
    ).model_dump(mode="json")


def state() -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "request": {"input_type": "text", "content": "update project"},
        "context_refs": [POLICY_REF, "cap_manifest01", "prj_project001"],
        "intent": None,
        "plan": plan(),
        "policy_decisions": [
            decision(
                action_id=ACTION_INSPECT,
                decision_id=DECISION_INSPECT,
                selected=PolicyDecisionKind.ALLOW,
                risk_tier=RiskTier.R0,
            ),
            decision(
                action_id=ACTION_UPDATE,
                decision_id=DECISION_UPDATE,
                selected=PolicyDecisionKind.ASK,
                risk_tier=RiskTier.R2,
            ),
        ],
        "pending_approval": None,
        "action_results": [],
        "observations": [],
        "errors": [],
        "status": "awaiting_approval",
        "revision_count": 0,
        "final_response": None,
    }


class FakeStore:
    def __init__(
        self,
        *,
        result: object | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = []
        self.records: dict[str, PendingApprovalRecord] = {}
        self.events: list[str] = []

    async def create_or_get_pending_approval(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        existing = self.records.get(request.approval_id)
        if existing is not None:
            if existing.request != request:
                raise RuntimeError("idempotency conflict")
            return existing
        event_id = (
            "evt_"
            + hashlib.sha256(
                request.approval_id.encode()
            ).hexdigest()[:24]
        )
        record = PendingApprovalRecord(
            request=request,
            event_id=event_id,
            issued_at=NOW,
            expires_at=NOW
            + timedelta(seconds=request.expires_after_seconds),
        )
        self.records[request.approval_id] = record
        self.events.append(event_id)
        return record


class PauseSignal(RuntimeError):
    pass


class CapturingInterrupt:
    def __init__(
        self,
        *,
        resume: object | None = None,
        should_pause: bool = False,
    ) -> None:
        self.resume = resume
        self.should_pause = should_pause
        self.payloads = []

    def __call__(self, payload):
        self.payloads.append(payload)
        if self.should_pause:
            raise PauseSignal
        return (
            self.resume
            if self.resume is not None
            else {
                "approval_id": payload["approval_id"],
                "action_digest": payload["action_digest"],
                "decision": "approve",
            }
        )


def service(
    *,
    store: FakeStore | None = None,
    interrupt_fn: CapturingInterrupt | None = None,
    settings: ApprovalPauseSettings | None = None,
) -> ApprovalPauseService:
    return ApprovalPauseService(
        store=store or FakeStore(),
        interrupt_fn=interrupt_fn or CapturingInterrupt(),
        settings=settings or ApprovalPauseSettings(),
    )


async def assert_rejected(
    selected_state: dict[str, Any],
    code: str,
    *,
    selected_service: ApprovalPauseService | None = None,
) -> None:
    with pytest.raises(ApprovalPauseError) as captured:
        await pauseForApproval(
            selected_state,
            service=selected_service or service(),
        )
    assert captured.value.code == code


@pytest.mark.anyio
async def test_persists_exact_preview_before_interrupt() -> None:
    store = FakeStore()
    interrupt_fn = CapturingInterrupt(should_pause=True)

    with pytest.raises(PauseSignal):
        await pauseForApproval(
            state(),
            service=service(
                store=store,
                interrupt_fn=interrupt_fn,
            ),
        )

    assert len(store.records) == 1
    assert len(store.events) == 1
    request = store.calls[0]
    assert request.action_id == ACTION_UPDATE
    assert request.preview.action_id == ACTION_UPDATE
    assert request.preview.resource_ids == (RESOURCE_ID,)
    assert request.preview.verification_codes == ("tests_passed",)
    assert [item.name for item in request.preview.parameters] == [
        "mode",
        "project",
    ]
    assert request.preview.parameters[0].value == "safe_fix"
    assert request.preview.dependency_action_ids == (ACTION_INSPECT,)
    assert request.action_digest == request.preview.action_digest
    assert len(request.action_digest) == 64
    assert interrupt_fn.payloads[0]["type"] == "approval.required"
    assert interrupt_fn.payloads[0]["approval_id"] == request.approval_id
    assert interrupt_fn.payloads[0]["preview"]["action_id"] == ACTION_UPDATE
    assert ACTION_INSPECT not in str(
        interrupt_fn.payloads[0]["preview"]["parameters"]
    )


@pytest.mark.anyio
async def test_replay_reuses_approval_and_event_then_returns_resume_value() -> None:
    store = FakeStore()
    first_interrupt = CapturingInterrupt(should_pause=True)
    with pytest.raises(PauseSignal):
        await pauseForApproval(
            state(),
            service=service(
                store=store,
                interrupt_fn=first_interrupt,
            ),
        )

    resume = {
        "approval_id": next(iter(store.records)),
        "action_digest": store.calls[0].action_digest,
        "decision": "approve",
    }
    resumed_interrupt = CapturingInterrupt(resume=resume)
    result = await pauseForApproval(
        state(),
        service=service(
            store=store,
            interrupt_fn=resumed_interrupt,
        ),
    )

    assert len(store.calls) == 2
    assert len(store.records) == 1
    assert len(store.events) == 1
    assert store.calls[0] == store.calls[1]
    assert first_interrupt.payloads == resumed_interrupt.payloads
    assert result["status"] == "awaiting_approval"
    assert result["pending_approval"]["resume"] == resume
    assert result["pending_approval"]["request"]["action_id"] == ACTION_UPDATE


@pytest.mark.anyio
async def test_action_digest_is_canonical_and_binds_material_changes() -> None:
    baseline_store = FakeStore()
    baseline = await pauseForApproval(
        state(),
        service=service(store=baseline_store),
    )

    reordered = state()
    reordered["plan"]["actions"][1]["arguments"].reverse()
    reordered_store = FakeStore()
    canonical = await pauseForApproval(
        reordered,
        service=service(store=reordered_store),
    )

    changed = state()
    changed["plan"]["actions"][1]["arguments"][0]["value"] = "format_only"
    changed_store = FakeStore()
    modified = await pauseForApproval(
        changed,
        service=service(store=changed_store),
    )

    baseline_request = baseline["pending_approval"]["request"]
    canonical_request = canonical["pending_approval"]["request"]
    modified_request = modified["pending_approval"]["request"]
    assert baseline_request["action_digest"] == canonical_request["action_digest"]
    assert baseline_request["approval_id"] == canonical_request["approval_id"]
    assert baseline_request["action_digest"] != modified_request["action_digest"]
    assert baseline_request["approval_id"] != modified_request["approval_id"]


@pytest.mark.anyio
async def test_selects_only_first_ask_without_blanket_approval() -> None:
    selected_state = state()
    selected_state["policy_decisions"][0] = decision(
        action_id=ACTION_INSPECT,
        decision_id=DECISION_INSPECT,
        selected=PolicyDecisionKind.ASK,
        risk_tier=RiskTier.R1,
    )
    store = FakeStore()

    result = await pauseForApproval(
        selected_state,
        service=service(store=store),
    )

    request = result["pending_approval"]["request"]
    assert request["action_id"] == ACTION_INSPECT
    assert request["preview"]["action_id"] == ACTION_INSPECT
    assert ACTION_UPDATE not in str(request["preview"])


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "executing", "approval_pause_state_invalid"),
        (
            "pending_approval",
            {"approval_id": "existing"},
            "approval_pause_state_invalid",
        ),
        ("task_id", "unsafe", "approval_pause_identity_invalid"),
        ("thread_id", "unsafe", "approval_pause_identity_invalid"),
        ("plan", None, "approval_pause_contract_invalid"),
        ("policy_decisions", [], "approval_pause_contract_invalid"),
    ],
)
async def test_rejects_invalid_state(
    field: str,
    value: object,
    code: str,
) -> None:
    invalid = state()
    invalid[field] = value

    await assert_rejected(invalid, code)


@pytest.mark.anyio
async def test_rejects_decision_coverage_deny_and_no_ask() -> None:
    missing = state()
    missing["policy_decisions"].pop()
    await assert_rejected(missing, "approval_pause_contract_invalid")

    denied = state()
    denied["policy_decisions"][1] = decision(
        action_id=ACTION_UPDATE,
        decision_id=DECISION_UPDATE,
        selected=PolicyDecisionKind.DENY,
        risk_tier=RiskTier.R4,
    )
    await assert_rejected(denied, "approval_pause_contract_invalid")

    no_ask = state()
    no_ask["policy_decisions"][1] = decision(
        action_id=ACTION_UPDATE,
        decision_id=DECISION_UPDATE,
        selected=PolicyDecisionKind.ALLOW,
        risk_tier=RiskTier.R0,
    )
    await assert_rejected(no_ask, "approval_pause_contract_invalid")


@pytest.mark.anyio
async def test_store_failures_and_invalid_records_are_sanitized() -> None:
    await assert_rejected(
        state(),
        "approval_persistence_unavailable",
        selected_service=service(
            store=FakeStore(error=RuntimeError("private"))
        ),
    )
    await assert_rejected(
        state(),
        "approval_persistence_invalid",
        selected_service=service(store=FakeStore(result=object())),
    )

    valid_store = FakeStore()
    await pauseForApproval(
        state(),
        service=service(store=valid_store),
    )
    record = next(iter(valid_store.records.values()))
    conflicting_request = record.request.model_copy(
        update={"decision_id": "pdc_" + "9" * 24}
    )
    conflict = record.model_copy(update={"request": conflicting_request})
    await assert_rejected(
        state(),
        "approval_persistence_conflict",
        selected_service=service(store=FakeStore(result=conflict)),
    )


@pytest.mark.anyio
async def test_store_cancellation_propagates() -> None:
    with pytest.raises(asyncio.CancelledError):
        await pauseForApproval(
            state(),
            service=service(
                store=FakeStore(error=asyncio.CancelledError())
            ),
        )


@pytest.mark.anyio
async def test_rejects_invalid_or_oversized_resume_payload() -> None:
    await assert_rejected(
        state(),
        "approval_resume_payload_invalid",
        selected_service=service(
            interrupt_fn=CapturingInterrupt(resume=object())
        ),
    )
    await assert_rejected(
        state(),
        "approval_resume_payload_invalid",
        selected_service=service(
            interrupt_fn=CapturingInterrupt(
                resume={
                    "approval_id": "apr_" + "7" * 24,
                    "action_digest": "8" * 64,
                    "decision": "approve",
                    "private": "must-not-checkpoint",
                }
            )
        ),
    )
    await assert_rejected(
        state(),
        "approval_resume_payload_invalid",
        selected_service=service(
            interrupt_fn=CapturingInterrupt(
                resume={"value": "x" * 1_000}
            ),
            settings=ApprovalPauseSettings(
                max_resume_payload_bytes=256
            ),
        ),
    )


@pytest.mark.anyio
async def test_rejects_incompatible_settings_before_persistence() -> None:
    store = FakeStore()

    await assert_rejected(
        state(),
        "approval_pause_settings_incompatible",
        selected_service=service(
            store=store,
            settings=ApprovalPauseSettings(
                expires_after_seconds=10
            ),
        ),
    )

    assert store.calls == []


@pytest.mark.anyio
async def test_real_langgraph_interrupt_is_durable_and_replay_safe() -> None:
    store = FakeStore()
    graph = StateGraph(JarvisState)

    async def pause_node(graph_state):
        return await pauseForApproval(
            graph_state,
            service=ApprovalPauseService(store=store),
        )

    graph.add_node("pause", pause_node)
    graph.add_edge(START, "pause")
    graph.add_edge("pause", END)
    compiled = graph.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": THREAD_ID}}

    interrupted = await compiled.ainvoke(state(), config=config)

    assert len(interrupted["__interrupt__"]) == 1
    payload = interrupted["__interrupt__"][0].value
    assert payload["type"] == "approval.required"
    assert len(store.records) == 1
    assert len(store.events) == 1

    resume = {
        "approval_id": payload["approval_id"],
        "action_digest": payload["action_digest"],
        "decision": "approve",
    }
    completed = await compiled.ainvoke(
        Command(resume=resume),
        config=config,
    )

    assert completed["pending_approval"]["resume"] == resume
    assert len(store.calls) == 2
    assert len(store.records) == 1
    assert len(store.events) == 1
