from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from jarvis.graph import (
    ActionDispatchRecord,
    ActionDispatchRequest,
    ActionPolicyProof,
    ActionRequestArgument,
    ActionResultCollectionRecord,
    ActionResultConflictError,
    ActionResultCorrelationError,
    ActionResultError,
    ActionResultNotFoundError,
    ActionResultService,
    ActionResultSettings,
    ExecutorActionResult,
    PriorActionResult,
    collectActionResult,
)


TASK_ID = "tsk_" + "1" * 32
THREAD_ID = "thr_" + "2" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
ACTION_ID = "act_" + "3" * 24
DISPATCH_ID = "dsp_" + "4" * 24
IDEMPOTENCY_KEY = "5" * 64
ATTEMPT_ID = "atm_attempt00000001"
RECEIPT_ID = "rcp_receipt00000001"
NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


def plan() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "objective": "modify_project",
        "assumptions": ["current_context"],
        "actions": [
            {
                "action_id": ACTION_ID,
                "capability_id": "project.inspect",
                "capability_version": "1.0.0",
                "arguments": [
                    {
                        "name": "project",
                        "value": "res_project001",
                    }
                ],
                "dependencies": [],
                "timeout_seconds": 60,
            }
        ],
        "success_criteria": [
            {
                "criterion_id": "crt_" + "6" * 24,
                "action_id": ACTION_ID,
                "verification_code": "inspection_recorded",
            }
        ],
        "warnings": ["state_may_change"],
    }


def dispatch_record() -> ActionDispatchRecord:
    request = ActionDispatchRequest(
        dispatch_id=DISPATCH_ID,
        idempotency_key=IDEMPOTENCY_KEY,
        task_id=TASK_ID,
        thread_id=THREAD_ID,
        actor_id=ACTOR_ID,
        device_id=DEVICE_ID,
        action_id=ACTION_ID,
        capability_id="project.inspect",
        capability_version="1.0.0",
        arguments=(
            ActionRequestArgument(
                name="project",
                value="res_project001",
            ),
        ),
        resource_ids=("res_project001",),
        dependency_action_ids=(),
        verification_codes=("inspection_recorded",),
        timeout_seconds=60,
        policy=ActionPolicyProof(
            decision_id="pdc_" + "7" * 24,
            decision="allow",
            risk_tier="r0",
            policy_reference_id="pol_policy001",
            policy_version="1.0.0",
        ),
    )
    return ActionDispatchRecord(
        request=request,
        event_id="evt_dispatch00000001",
        outbox_id="out_dispatch00000001",
        lease_id="lse_dispatch00000001",
        queued_at=NOW,
        lease_expires_at=NOW + timedelta(seconds=90),
        reserved_resource_ids=("res_project001",),
    )


def candidate(
    *,
    outcome: str = "succeeded",
    error_code: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    **changes: Any,
) -> dict[str, Any]:
    selected_error = error_code
    if outcome != "succeeded" and selected_error is None:
        selected_error = {
            "failed": "executor_failed",
            "cancelled": "action_cancelled",
            "uncertain": "receipt_uncertain",
        }[outcome]
    value = {
        "type": "action.result",
        "version": "1.0",
        "dispatch_id": DISPATCH_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "action_id": ACTION_ID,
        "attempt_id": ATTEMPT_ID,
        "receipt_id": RECEIPT_ID,
        "executor_device_id": DEVICE_ID,
        "outcome": outcome,
        "started_at": (
            started_at or NOW + timedelta(seconds=1)
        ).isoformat(),
        "completed_at": (
            completed_at or NOW + timedelta(seconds=10)
        ).isoformat(),
        "artifact_reference_ids": ["art_result00000001"],
        "error_code": selected_error,
    }
    value.update(changes)
    return value


def state(
    *,
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "plan": plan(),
        "action_results": results or [],
        "status": "executing",
    }


class FakeResultStore:
    def __init__(
        self,
        *,
        dispatch: ActionDispatchRecord | None = None,
        result: object | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.dispatch = dispatch or dispatch_record()
        self.result = result
        self.error = error
        self.calls = []
        self.collections: dict[str, ActionResultCollectionRecord] = {}
        self.events: list[str] = []
        self.released_leases: list[str] = []
        self._lock = asyncio.Lock()

    async def collect_or_get_action_result(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        async with self._lock:
            candidate_value = request.candidate
            dispatched = self.dispatch.request
            if request.actor_id != dispatched.actor_id:
                raise ActionResultNotFoundError
            if (
                candidate_value.dispatch_id != dispatched.dispatch_id
                or candidate_value.idempotency_key
                != dispatched.idempotency_key
                or candidate_value.task_id != dispatched.task_id
                or candidate_value.thread_id != dispatched.thread_id
                or candidate_value.action_id != dispatched.action_id
                or candidate_value.executor_device_id
                != dispatched.device_id
            ):
                raise ActionResultCorrelationError
            existing = self.collections.get(candidate_value.dispatch_id)
            if existing is not None:
                if existing.request != request:
                    raise ActionResultConflictError
                return existing.model_copy(update={"created": False})
            duration = (
                candidate_value.completed_at
                - candidate_value.started_at
            ).total_seconds()
            late = (
                candidate_value.completed_at
                > self.dispatch.lease_expires_at
                or duration > dispatched.timeout_seconds
            )
            outcome = (
                "uncertain"
                if late
                else candidate_value.outcome
            )
            suffix = hashlib.sha256(
                candidate_value.receipt_id.encode()
            ).hexdigest()[:24]
            record = ActionResultCollectionRecord(
                request=request,
                dispatch=self.dispatch,
                result=PriorActionResult(
                    dispatch_id=candidate_value.dispatch_id,
                    action_id=candidate_value.action_id,
                    receipt_id=candidate_value.receipt_id,
                    outcome=outcome,
                    completed_at=candidate_value.completed_at,
                ),
                event_id="evt_" + suffix,
                collected_at=candidate_value.completed_at
                + timedelta(seconds=1),
                created=True,
            )
            self.collections[candidate_value.dispatch_id] = record
            self.events.append(record.event_id)
            self.released_leases.append(self.dispatch.lease_id)
            return record


def service(
    *,
    store: FakeResultStore | None = None,
    settings: ActionResultSettings | None = None,
) -> ActionResultService:
    return ActionResultService(
        store=store or FakeResultStore(),
        settings=settings or ActionResultSettings(),
    )


async def assert_rejected(
    selected_state: dict[str, Any],
    selected_candidate: object,
    code: str,
    *,
    selected_service: ActionResultService | None = None,
    runtime_thread_id: str = THREAD_ID,
) -> None:
    with pytest.raises(ActionResultError) as captured:
        await collectActionResult(
            selected_state,
            selected_candidate,
            service=selected_service or service(),
            runtime_thread_id=runtime_thread_id,
        )
    assert captured.value.code == code


@pytest.mark.anyio
async def test_correlates_persists_releases_and_appends_success() -> None:
    store = FakeResultStore()

    result = await collectActionResult(
        state(),
        candidate(),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert result["status"] == "verifying"
    assert len(result["action_results"]) == 1
    projection = result["action_results"][0]
    assert projection["type"] == "action.result"
    assert projection["dispatch_id"] == DISPATCH_ID
    assert projection["action_id"] == ACTION_ID
    assert projection["receipt_id"] == RECEIPT_ID
    assert projection["outcome"] == "succeeded"
    assert len(store.collections) == len(store.events) == 1
    assert store.released_leases == ["lse_dispatch00000001"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("failed", "failed"),
        ("cancelled", "cancelled"),
        ("uncertain", "uncertain"),
    ],
)
async def test_preserves_non_success_terminal_outcomes(
    outcome: str,
    expected: str,
) -> None:
    result = await collectActionResult(
        state(),
        candidate(outcome=outcome),
        service=service(),
        runtime_thread_id=THREAD_ID,
    )

    assert result["action_results"][0]["outcome"] == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("started_at", "completed_at"),
    [
        (
            NOW + timedelta(seconds=1),
            NOW + timedelta(seconds=91),
        ),
        (
            NOW + timedelta(seconds=1),
            NOW + timedelta(seconds=62),
        ),
    ],
)
async def test_late_or_overrun_success_becomes_uncertain(
    started_at: datetime,
    completed_at: datetime,
) -> None:
    result = await collectActionResult(
        state(),
        candidate(
            started_at=started_at,
            completed_at=completed_at,
        ),
        service=service(),
        runtime_thread_id=THREAD_ID,
    )

    assert result["action_results"][0]["outcome"] == "uncertain"


@pytest.mark.anyio
async def test_store_duplicate_recovers_stale_checkpoint_without_reapplying() -> None:
    store = FakeResultStore()
    selected_state = state()

    first = await collectActionResult(
        selected_state,
        candidate(),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )
    replay = await collectActionResult(
        selected_state,
        candidate(),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert first == replay
    assert len(store.calls) == 2
    assert len(store.collections) == len(store.events) == 1
    assert len(store.released_leases) == 1


@pytest.mark.anyio
async def test_checkpoint_duplicate_returns_empty_append_delta() -> None:
    store = FakeResultStore()
    first = await collectActionResult(
        state(),
        candidate(),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )
    checkpoint = state(results=first["action_results"])

    duplicate = await collectActionResult(
        checkpoint,
        candidate(),
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert duplicate == {
        "action_results": [],
        "status": "verifying",
    }
    assert len(store.events) == 1


@pytest.mark.anyio
async def test_conflicting_checkpoint_result_is_rejected() -> None:
    store = FakeResultStore()
    conflicting = PriorActionResult(
        dispatch_id=DISPATCH_ID,
        action_id=ACTION_ID,
        receipt_id="rcp_otherreceipt001",
        outcome="failed",
        completed_at=NOW + timedelta(seconds=10),
    ).model_dump(mode="json")

    await assert_rejected(
        state(results=[conflicting]),
        candidate(),
        "action_result_state_conflict",
        selected_service=service(store=store),
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", "tsk_" + "8" * 32),
        ("thread_id", "thr_" + "8" * 32),
        ("executor_device_id", "device-002"),
        ("action_id", "act_" + "8" * 24),
    ],
)
async def test_rejects_candidate_state_mismatch(
    field: str,
    value: str,
) -> None:
    await assert_rejected(
        state(),
        candidate(**{field: value}),
        "action_result_candidate_mismatch",
    )


@pytest.mark.anyio
async def test_store_rejects_pending_dispatch_correlation_mismatch() -> None:
    await assert_rejected(
        state(),
        candidate(idempotency_key="8" * 64),
        "action_result_candidate_mismatch",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid",
    [
        {"private": "raw output"},
        candidate(private="must-not-persist"),
        candidate(
            outcome="succeeded",
            error_code="unexpected_error",
        ),
        {
            **candidate(outcome="failed"),
            "error_code": None,
        },
        candidate(
            started_at=NOW + timedelta(seconds=20),
            completed_at=NOW + timedelta(seconds=10),
        ),
        candidate(
            artifact_reference_ids=[
                "art_result00000001",
                "art_result00000001",
            ]
        ),
    ],
)
async def test_rejects_malformed_or_extra_result_payload(
    invalid: object,
) -> None:
    await assert_rejected(
        state(),
        invalid,
        "action_result_payload_invalid",
    )


@pytest.mark.anyio
async def test_rejects_non_json_and_oversized_payload() -> None:
    await assert_rejected(
        state(),
        object(),
        "action_result_payload_invalid",
    )
    oversized = candidate(
        artifact_reference_ids=[
            f"art_{index:08d}" + "x" * 120
            for index in range(16)
        ]
    )
    await assert_rejected(
        state(),
        oversized,
        "action_result_payload_too_large",
        selected_service=service(
            settings=ActionResultSettings(
                max_result_bytes=512
            )
        ),
    )


@pytest.mark.anyio
async def test_rejects_invalid_state_identity_thread_and_settings() -> None:
    invalid_status = state()
    invalid_status["status"] = "verifying"
    await assert_rejected(
        invalid_status,
        candidate(),
        "action_result_state_invalid",
    )

    invalid_identity = state()
    invalid_identity["actor_id"] = "unsafe value"
    await assert_rejected(
        invalid_identity,
        candidate(),
        "action_result_identity_invalid",
    )

    await assert_rejected(
        state(),
        candidate(),
        "action_result_thread_mismatch",
        runtime_thread_id="thr_" + "9" * 32,
    )

    store = FakeResultStore()
    await assert_rejected(
        state(),
        candidate(),
        "action_result_settings_incompatible",
        selected_service=service(
            store=store,
            settings=ActionResultSettings(
                max_result_bytes=128
            ),
        ),
    )
    assert store.calls == []


@pytest.mark.anyio
async def test_rejects_malformed_or_duplicate_checkpoint_results() -> None:
    malformed = state(results=[{"private": "value"}])
    await assert_rejected(
        malformed,
        candidate(),
        "action_result_state_contract_invalid",
    )

    duplicate = PriorActionResult(
        dispatch_id=DISPATCH_ID,
        action_id=ACTION_ID,
        receipt_id=RECEIPT_ID,
        outcome="succeeded",
        completed_at=NOW + timedelta(seconds=10),
    ).model_dump(mode="json")
    duplicated = state(results=[duplicate, deepcopy(duplicate)])
    await assert_rejected(
        duplicated,
        candidate(),
        "action_result_state_contract_invalid",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ActionResultNotFoundError(), "action_result_not_found"),
        (
            ActionResultCorrelationError(),
            "action_result_candidate_mismatch",
        ),
        (
            ActionResultConflictError(),
            "action_result_receipt_conflict",
        ),
        (RuntimeError("private"), "action_result_unavailable"),
    ],
)
async def test_store_failures_are_sanitized(
    error: BaseException,
    code: str,
) -> None:
    await assert_rejected(
        state(),
        candidate(),
        code,
        selected_service=service(
            store=FakeResultStore(error=error)
        ),
    )


@pytest.mark.anyio
async def test_store_cancellation_propagates() -> None:
    with pytest.raises(asyncio.CancelledError):
        await collectActionResult(
            state(),
            candidate(),
            service=service(
                store=FakeResultStore(
                    error=asyncio.CancelledError()
                )
            ),
            runtime_thread_id=THREAD_ID,
        )


@pytest.mark.anyio
async def test_rejects_invalid_conflicting_or_tampered_store_record() -> None:
    await assert_rejected(
        state(),
        candidate(),
        "action_result_record_invalid",
        selected_service=service(
            store=FakeResultStore(result=object())
        ),
    )

    capture = FakeResultStore()
    await collectActionResult(
        state(),
        candidate(),
        service=service(store=capture),
        runtime_thread_id=THREAD_ID,
    )
    valid = next(iter(capture.collections.values()))

    conflicting_request = valid.model_copy(
        update={
            "request": valid.request.model_copy(
                update={
                    "candidate": valid.request.candidate.model_copy(
                        update={
                            "attempt_id": "atm_otherattempt001"
                        }
                    )
                }
            )
        }
    )
    await assert_rejected(
        state(),
        candidate(),
        "action_result_record_conflict",
        selected_service=service(
            store=FakeResultStore(result=conflicting_request)
        ),
    )

    tampered = valid.model_copy(
        update={
            "result": valid.result.model_copy(
                update={"outcome": "failed"}
            )
        }
    )
    await assert_rejected(
        state(),
        candidate(),
        "action_result_record_invalid",
        selected_service=service(
            store=FakeResultStore(result=tampered)
        ),
    )


def test_executor_result_model_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError):
        ExecutorActionResult.model_validate(
            candidate(
                started_at=datetime(2026, 7, 3, 12, 0),
            )
        )
