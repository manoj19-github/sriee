from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from jarvis.graph import (
    ActionDispatchCapacityError,
    ActionDispatchError,
    ActionDispatchRecord,
    ActionDispatchService,
    ActionDispatchSettings,
    ApprovalResult,
    PolicyDecision,
    PolicyDecisionKind,
    PriorActionResult,
    RiskTier,
    dispatchAction,
)
from jarvis.graph.approval import _digest_action
from jarvis.graph.plan import PlanDraft


TASK_ID = "tsk_" + "1" * 32
THREAD_ID = "thr_" + "2" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
ACTION_INSPECT = "act_" + "3" * 24
ACTION_UPDATE = "act_" + "4" * 24
DECISION_INSPECT = "pdc_" + "5" * 24
DECISION_UPDATE = "pdc_" + "6" * 24
RESOURCE_ID = "res_project001"
POLICY_REF = "pol_policy001"
NOW = datetime(2026, 7, 3, 11, 0, tzinfo=UTC)


def action(
    *,
    action_id: str,
    capability_id: str,
    arguments: list[dict[str, Any]],
    dependencies: list[str],
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "capability_id": capability_id,
        "capability_version": "1.0.0",
        "arguments": arguments,
        "dependencies": dependencies,
        "timeout_seconds": timeout_seconds,
    }


def plan(*, include_dependency: bool = False) -> dict[str, Any]:
    actions = [
        action(
            action_id=ACTION_INSPECT,
            capability_id="project.inspect",
            arguments=[{"name": "project", "value": RESOURCE_ID}],
            dependencies=[],
            timeout_seconds=20,
        )
    ]
    criteria = [
        {
            "criterion_id": "crt_" + "7" * 24,
            "action_id": ACTION_INSPECT,
            "verification_code": "inspection_recorded",
        }
    ]
    if include_dependency:
        actions.append(
            action(
                action_id=ACTION_UPDATE,
                capability_id="project.update",
                arguments=[
                    {"name": "mode", "value": "safe_fix"},
                    {"name": "project", "value": RESOURCE_ID},
                ],
                dependencies=[ACTION_INSPECT],
                timeout_seconds=90,
            )
        )
        criteria.append(
            {
                "criterion_id": "crt_" + "8" * 24,
                "action_id": ACTION_UPDATE,
                "verification_code": "tests_passed",
            }
        )
    return {
        "schema_version": "1.0",
        "objective": "modify_project",
        "assumptions": ["current_context"],
        "actions": actions,
        "success_criteria": criteria,
        "warnings": ["state_may_change"],
    }


def decision(
    *,
    action_id: str,
    decision_id: str,
    selected: PolicyDecisionKind = PolicyDecisionKind.ALLOW,
    risk_tier: RiskTier = RiskTier.R0,
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
        grant_reference_id=None,
        requires_fresh_approval=(
            selected is PolicyDecisionKind.ASK
        ),
    ).model_dump(mode="json")


def prior_result(
    *,
    action_id: str = ACTION_INSPECT,
    outcome: str = "succeeded",
) -> dict[str, Any]:
    return PriorActionResult(
        dispatch_id="dsp_" + "9" * 24,
        action_id=action_id,
        receipt_id="rcp_receipt00000001",
        outcome=outcome,
        completed_at=NOW,
    ).model_dump(mode="json")


def approval_result(
    *,
    action_id: str = ACTION_INSPECT,
    outcome: str = "approved",
    action_digest: str | None = None,
) -> dict[str, Any]:
    selected_plan = PlanDraft.model_validate(plan())
    selected_action = selected_plan.actions[0]
    selected_decision = PolicyDecision.model_validate(
        decision(
            action_id=ACTION_INSPECT,
            decision_id=DECISION_INSPECT,
            selected=PolicyDecisionKind.ASK,
            risk_tier=RiskTier.R2,
        )
    )
    digest = action_digest or _digest_action(
        task_id=TASK_ID,
        thread_id=THREAD_ID,
        actor_id=ACTOR_ID,
        device_id=DEVICE_ID,
        action=selected_action,
        decision=selected_decision,
        verification_codes=("inspection_recorded",),
    )
    return ApprovalResult(
        approval_id="apr_" + "a" * 24,
        resolution_id="ars_" + "b" * 24,
        thread_id=THREAD_ID,
        action_id=action_id,
        action_digest=digest,
        outcome=outcome,
        decided_at=NOW,
    ).model_dump(mode="json")


def state(
    *,
    include_dependency: bool = False,
    results: list[dict[str, Any]] | None = None,
    ask_action: str | None = None,
    approval: dict[str, Any] | None = None,
    task_id: str = TASK_ID,
) -> dict[str, Any]:
    selected_plan = plan(include_dependency=include_dependency)
    decisions = []
    for selected_action in selected_plan["actions"]:
        action_id = selected_action["action_id"]
        decisions.append(
            decision(
                action_id=action_id,
                decision_id=(
                    DECISION_INSPECT
                    if action_id == ACTION_INSPECT
                    else DECISION_UPDATE
                ),
                selected=(
                    PolicyDecisionKind.ASK
                    if action_id == ask_action
                    else PolicyDecisionKind.ALLOW
                ),
                risk_tier=(
                    RiskTier.R2 if action_id == ask_action else RiskTier.R0
                ),
            )
        )
    return {
        "contract_version": "1.0",
        "task_id": task_id,
        "thread_id": THREAD_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "plan": selected_plan,
        "policy_decisions": decisions,
        "pending_approval": approval,
        "action_results": results or [],
        "status": "executing",
    }


class FakeDispatchStore:
    def __init__(
        self,
        *,
        result: object | None = None,
        error: BaseException | None = None,
        lease_grace_seconds: int = 30,
    ) -> None:
        self.result = result
        self.error = error
        self.lease_grace_seconds = lease_grace_seconds
        self.calls = []
        self.records: dict[str, ActionDispatchRecord] = {}
        self.events: list[str] = []
        self.outbox: list[str] = []
        self.leases: list[str] = []
        self._lock = asyncio.Lock()

    async def create_or_get_dispatch(self, request, *, limits):
        self.calls.append((request, limits))
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        async with self._lock:
            existing = self.records.get(request.dispatch_id)
            if existing is not None:
                if existing.request != request:
                    raise RuntimeError("idempotency conflict")
                return existing
            if len(self.records) >= limits.max_in_flight_actions:
                raise ActionDispatchCapacityError
            for resource_id in request.resource_ids:
                active = sum(
                    resource_id in record.reserved_resource_ids
                    for record in self.records.values()
                )
                if active >= limits.max_in_flight_per_resource:
                    raise ActionDispatchCapacityError
            suffix = hashlib.sha256(request.dispatch_id.encode()).hexdigest()[:24]
            record = ActionDispatchRecord(
                request=request,
                event_id="evt_" + suffix,
                outbox_id="out_" + suffix,
                lease_id="lse_" + suffix,
                queued_at=NOW,
                lease_expires_at=NOW
                + timedelta(
                    seconds=(
                        request.timeout_seconds
                        + self.lease_grace_seconds
                    )
                ),
                reserved_resource_ids=request.resource_ids,
            )
            self.records[request.dispatch_id] = record
            self.events.append(record.event_id)
            self.outbox.append(record.outbox_id)
            self.leases.append(record.lease_id)
            return record


def service(
    *,
    store: FakeDispatchStore | None = None,
    settings: ActionDispatchSettings | None = None,
) -> ActionDispatchService:
    selected_settings = settings or ActionDispatchSettings()
    return ActionDispatchService(
        store=store
        or FakeDispatchStore(
            lease_grace_seconds=selected_settings.lease_grace_seconds
        ),
        settings=selected_settings,
    )


async def assert_rejected(
    selected_state: dict[str, Any],
    code: str,
    *,
    selected_service: ActionDispatchService | None = None,
    runtime_thread_id: str = THREAD_ID,
) -> None:
    with pytest.raises(ActionDispatchError) as captured:
        await dispatchAction(
            selected_state,
            service=selected_service or service(),
            runtime_thread_id=runtime_thread_id,
        )
    assert captured.value.code == code


@pytest.mark.anyio
async def test_emits_exact_allow_action_to_atomic_outbox_store() -> None:
    store = FakeDispatchStore()

    result = await dispatchAction(
        state(),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert result == {"status": "executing"}
    assert len(store.records) == len(store.events) == len(store.outbox) == 1
    assert len(store.leases) == 1
    request, limits = store.calls[0]
    assert request.type == "action.request"
    assert request.action_id == ACTION_INSPECT
    assert request.resource_ids == (RESOURCE_ID,)
    assert request.verification_codes == ("inspection_recorded",)
    assert request.policy.decision == "allow"
    assert request.approval is None
    assert limits.max_in_flight_per_resource == 1


@pytest.mark.anyio
async def test_ask_action_requires_exact_consumed_approval() -> None:
    store = FakeDispatchStore()

    await dispatchAction(
        state(
            ask_action=ACTION_INSPECT,
            approval=approval_result(),
        ),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    request = store.calls[0][0]
    assert request.policy.decision == "ask"
    assert request.approval is not None
    assert request.approval.approval_id == "apr_" + "a" * 24
    assert len(request.approval.action_digest) == 64


@pytest.mark.anyio
async def test_replay_reuses_action_event_outbox_and_lease() -> None:
    store = FakeDispatchStore()
    selected_state = state()

    await dispatchAction(
        selected_state,
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )
    await dispatchAction(
        selected_state,
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert len(store.calls) == 2
    assert store.calls[0][0] == store.calls[1][0]
    assert len(store.records) == 1
    assert len(store.events) == len(store.outbox) == len(store.leases) == 1


@pytest.mark.anyio
async def test_selects_first_dependency_ready_unresolved_action() -> None:
    store = FakeDispatchStore()

    await dispatchAction(
        state(
            include_dependency=True,
            results=[prior_result()],
        ),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    request = store.calls[0][0]
    assert request.action_id == ACTION_UPDATE
    assert request.dependency_action_ids == (ACTION_INSPECT,)
    assert request.verification_codes == ("tests_passed",)
    assert [item.name for item in request.arguments] == ["mode", "project"]


@pytest.mark.anyio
async def test_canonical_request_is_stable_and_material_changes_rekey() -> None:
    baseline_store = FakeDispatchStore()
    await dispatchAction(
        state(include_dependency=True, results=[prior_result()]),
        service=service(store=baseline_store),
        runtime_thread_id=THREAD_ID,
    )
    baseline = baseline_store.calls[0][0]

    reordered = state(include_dependency=True, results=[prior_result()])
    reordered["plan"]["actions"][1]["arguments"].reverse()
    reordered_store = FakeDispatchStore()
    await dispatchAction(
        reordered,
        service=service(store=reordered_store),
        runtime_thread_id=THREAD_ID,
    )
    canonical = reordered_store.calls[0][0]

    changed = state(include_dependency=True, results=[prior_result()])
    changed["plan"]["actions"][1]["arguments"][0]["value"] = "format_only"
    changed_store = FakeDispatchStore()
    await dispatchAction(
        changed,
        service=service(store=changed_store),
        runtime_thread_id=THREAD_ID,
    )
    modified = changed_store.calls[0][0]

    assert baseline == canonical
    assert baseline.dispatch_id == modified.dispatch_id
    assert baseline.idempotency_key != modified.idempotency_key


@pytest.mark.anyio
async def test_resource_and_global_capacity_are_bounded() -> None:
    resource_store = FakeDispatchStore()
    limits = ActionDispatchSettings(
        max_in_flight_actions=2,
        max_in_flight_per_resource=1,
    )
    await dispatchAction(
        state(),
        service=service(store=resource_store, settings=limits),
        runtime_thread_id=THREAD_ID,
    )
    await assert_rejected(
        state(task_id="tsk_" + "d" * 32),
        "action_dispatch_capacity_exhausted",
        selected_service=service(store=resource_store, settings=limits),
    )

    global_store = FakeDispatchStore()
    global_limit = ActionDispatchSettings(max_in_flight_actions=1)
    first = state()
    first["plan"]["actions"][0]["arguments"] = []
    await dispatchAction(
        first,
        service=service(store=global_store, settings=global_limit),
        runtime_thread_id=THREAD_ID,
    )
    second = state(task_id="tsk_" + "e" * 32)
    second["plan"]["actions"][0]["arguments"] = []
    await assert_rejected(
        second,
        "action_dispatch_capacity_exhausted",
        selected_service=service(store=global_store, settings=global_limit),
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("approval", "code"),
    [
        (None, "action_dispatch_approval_invalid"),
        (
            approval_result(action_id=ACTION_UPDATE),
            "action_dispatch_approval_invalid",
        ),
        (
            approval_result(action_digest="c" * 64),
            "action_dispatch_approval_invalid",
        ),
        (
            approval_result(outcome="denied"),
            "action_dispatch_state_invalid",
        ),
    ],
)
async def test_rejects_missing_mismatched_or_denied_approval(
    approval: dict[str, Any] | None,
    code: str,
) -> None:
    selected_state = state(
        ask_action=ACTION_INSPECT,
        approval=approval,
    )
    if approval is not None and approval["outcome"] == "denied":
        selected_state["status"] = "denied"

    await assert_rejected(selected_state, code)


@pytest.mark.anyio
async def test_rejects_deny_incomplete_or_duplicate_policy_coverage() -> None:
    denied = state()
    denied["policy_decisions"][0] = decision(
        action_id=ACTION_INSPECT,
        decision_id=DECISION_INSPECT,
        selected=PolicyDecisionKind.DENY,
        risk_tier=RiskTier.R4,
    )
    await assert_rejected(denied, "action_dispatch_contract_invalid")

    missing = state()
    missing["policy_decisions"] = []
    await assert_rejected(missing, "action_dispatch_contract_invalid")

    duplicate = state()
    duplicate["policy_decisions"].append(
        duplicate["policy_decisions"][0]
    )
    await assert_rejected(duplicate, "action_dispatch_contract_invalid")


@pytest.mark.anyio
async def test_rejects_unsatisfied_dependencies_and_completed_plan() -> None:
    failed = state(
        include_dependency=True,
        results=[prior_result(outcome="failed")],
    )
    await assert_rejected(
        failed,
        "action_dispatch_dependencies_unsatisfied",
    )

    complete = state(results=[prior_result()])
    await assert_rejected(
        complete,
        "action_dispatch_plan_complete",
    )


@pytest.mark.anyio
async def test_rejects_unknown_duplicate_or_malformed_prior_results() -> None:
    unknown = state(
        results=[prior_result(action_id=ACTION_UPDATE)]
    )
    await assert_rejected(unknown, "action_dispatch_contract_invalid")

    duplicate = state(results=[prior_result(), prior_result()])
    await assert_rejected(duplicate, "action_dispatch_contract_invalid")

    malformed = state()
    malformed["action_results"] = [{"private": "payload"}]
    await assert_rejected(malformed, "action_dispatch_contract_invalid")


@pytest.mark.anyio
async def test_rejects_invalid_status_identity_and_runtime_thread() -> None:
    invalid_status = state()
    invalid_status["status"] = "denied"
    await assert_rejected(
        invalid_status,
        "action_dispatch_state_invalid",
    )

    invalid_identity = state()
    invalid_identity["actor_id"] = "unsafe value"
    await assert_rejected(
        invalid_identity,
        "action_dispatch_identity_invalid",
    )

    await assert_rejected(
        state(),
        "action_dispatch_thread_mismatch",
        runtime_thread_id="thr_" + "f" * 32,
    )


@pytest.mark.anyio
async def test_rejects_unsafe_request_strings_and_missing_verification() -> None:
    unsafe = state()
    unsafe["plan"]["actions"][0]["arguments"][0]["value"] = "raw secret value"
    await assert_rejected(
        unsafe,
        "action_dispatch_contract_invalid",
    )

    missing = state()
    missing["plan"]["success_criteria"] = []
    await assert_rejected(
        missing,
        "action_dispatch_contract_invalid",
    )


@pytest.mark.anyio
async def test_rejects_oversized_request_and_incompatible_settings() -> None:
    oversized = state()
    oversized["plan"]["actions"][0]["arguments"] = [
        {
            "name": f"value_{index}",
            "value": "x" * 128,
        }
        for index in range(12)
    ]
    await assert_rejected(
        oversized,
        "action_dispatch_request_too_large",
        selected_service=service(
            settings=ActionDispatchSettings(max_request_bytes=1_024)
        ),
    )

    store = FakeDispatchStore()
    await assert_rejected(
        state(),
        "action_dispatch_settings_incompatible",
        selected_service=service(
            store=store,
            settings=ActionDispatchSettings(
                max_in_flight_actions=0
            ),
        ),
    )
    assert store.calls == []


@pytest.mark.anyio
async def test_store_failures_records_and_cancellation_are_safe() -> None:
    await assert_rejected(
        state(),
        "action_dispatch_unavailable",
        selected_service=service(
            store=FakeDispatchStore(error=RuntimeError("private"))
        ),
    )
    await assert_rejected(
        state(),
        "action_dispatch_record_invalid",
        selected_service=service(
            store=FakeDispatchStore(result=object())
        ),
    )
    with pytest.raises(asyncio.CancelledError):
        await dispatchAction(
            state(),
            service=service(
                store=FakeDispatchStore(
                    error=asyncio.CancelledError()
                )
            ),
            runtime_thread_id=THREAD_ID,
        )


@pytest.mark.anyio
async def test_conflicting_record_and_lease_duration_are_rejected() -> None:
    capture = FakeDispatchStore()
    await dispatchAction(
        state(),
        service=service(store=capture),
        runtime_thread_id=THREAD_ID,
    )
    valid = next(iter(capture.records.values()))

    conflict = valid.model_copy(
        update={
            "request": valid.request.model_copy(
                update={"action_id": ACTION_UPDATE}
            )
        }
    )
    await assert_rejected(
        state(),
        "action_dispatch_record_conflict",
        selected_service=service(
            store=FakeDispatchStore(result=conflict)
        ),
    )

    wrong_lease = valid.model_copy(
        update={
            "lease_expires_at": valid.lease_expires_at
            + timedelta(seconds=1)
        }
    )
    await assert_rejected(
        state(),
        "action_dispatch_record_conflict",
        selected_service=service(
            store=FakeDispatchStore(result=wrong_lease)
        ),
    )
