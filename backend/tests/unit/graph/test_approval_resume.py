from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from jarvis.graph import (
    ApprovalResolutionConsumedError,
    ApprovalResolutionRecord,
    ApprovalResumeError,
    PendingApprovalRecord,
    PendingApprovalRequest,
    resumeApproval,
)
from jarvis.graph.approval import ApprovalActionPreview


TASK_ID = "tsk_" + "a" * 32
THREAD_ID = "thr_" + "b" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
ACTION_ID = "act_" + "c" * 24
DECISION_ID = "pdc_" + "d" * 24
APPROVAL_ID = "apr_" + "e" * 24
ACTION_DIGEST = "f" * 64
EVENT_ID = "evt_pendingapproval00000001"
NOW = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
EXPIRES_AT = NOW + timedelta(minutes=5)


def pending_record() -> PendingApprovalRecord:
    preview = ApprovalActionPreview(
        summary="Approve project.update for 1 registered resource(s).",
        action_id=ACTION_ID,
        capability_id="project.update",
        capability_version="1.0.0",
        parameters=(),
        resource_ids=("res_project001",),
        dependency_action_ids=(),
        verification_codes=("tests_passed",),
        timeout_seconds=90,
        risk_tier="r2",
        reason_codes=("scoped_project_mutation",),
        policy_reference_id="pol_policy001",
        policy_version="1.0.0",
        action_digest=ACTION_DIGEST,
    )
    request = PendingApprovalRequest(
        approval_id=APPROVAL_ID,
        task_id=TASK_ID,
        thread_id=THREAD_ID,
        actor_id=ACTOR_ID,
        device_id=DEVICE_ID,
        action_id=ACTION_ID,
        action_digest=ACTION_DIGEST,
        decision_id=DECISION_ID,
        risk_tier="r2",
        policy_reference_id="pol_policy001",
        policy_version="1.0.0",
        preview=preview,
        expires_after_seconds=300,
    )
    return PendingApprovalRecord(
        request=request,
        event_id=EVENT_ID,
        issued_at=NOW,
        expires_at=EXPIRES_AT,
    )


def state(*, decision: str = "approve") -> dict[str, Any]:
    record = pending_record().model_dump(mode="json")
    record["resume"] = {
        "approval_id": APPROVAL_ID,
        "action_digest": ACTION_DIGEST,
        "decision": decision,
    }
    return {
        "contract_version": "1.0",
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "pending_approval": record,
        "status": "awaiting_approval",
    }


class FakeResolutionStore:
    def __init__(
        self,
        *,
        outcome: str | None = None,
        decided_at: datetime | None = None,
        result: object | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.outcome = outcome
        self.decided_at = decided_at
        self.result = result
        self.error = error
        self.calls = []
        self._claimed: set[str] = set()
        self._lock = asyncio.Lock()

    async def resolve_pending_approval(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        async with self._lock:
            if request.approval_id in self._claimed:
                raise ApprovalResolutionConsumedError
            self._claimed.add(request.approval_id)
        outcome = self.outcome or (
            "approved" if request.decision == "approve" else "denied"
        )
        decided_at = self.decided_at or (
            request.expires_at
            if outcome == "expired"
            else request.issued_at + timedelta(seconds=30)
        )
        resolution_id = (
            "ars_"
            + hashlib.sha256(
                f"{request.approval_id}:{outcome}".encode()
            ).hexdigest()[:24]
        )
        return ApprovalResolutionRecord(
            request=request,
            resolution_id=resolution_id,
            outcome=outcome,
            decided_at=decided_at,
        )


async def assert_rejected(
    selected_state: dict[str, Any],
    code: str,
    *,
    store: FakeResolutionStore | None = None,
    runtime_thread_id: str = THREAD_ID,
) -> None:
    with pytest.raises(ApprovalResumeError) as captured:
        await resumeApproval(
            selected_state,
            service=store or FakeResolutionStore(),
            runtime_thread_id=runtime_thread_id,
        )
    assert captured.value.code == code


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("decision", "outcome", "status"),
    [
        ("approve", "approved", "executing"),
        ("deny", "denied", "denied"),
        ("approve", "expired", "expired"),
    ],
)
async def test_routes_authoritative_outcomes(
    decision: str,
    outcome: str,
    status: str,
) -> None:
    store = FakeResolutionStore(outcome=outcome)

    result = await resumeApproval(
        state(decision=decision),
        service=store,
        runtime_thread_id=THREAD_ID,
    )

    assert result["status"] == status
    approval_result = result["pending_approval"]
    assert approval_result["type"] == "approval.result"
    assert approval_result["outcome"] == outcome
    assert approval_result["approval_id"] == APPROVAL_ID
    assert approval_result["thread_id"] == THREAD_ID
    assert approval_result["action_id"] == ACTION_ID
    assert approval_result["action_digest"] == ACTION_DIGEST
    assert "resume" not in approval_result
    assert store.calls[0].pending_event_id == EVENT_ID


@pytest.mark.anyio
async def test_requires_runtime_thread_to_match_pending_interrupt() -> None:
    store = FakeResolutionStore()

    await assert_rejected(
        state(),
        "approval_resume_thread_mismatch",
        store=store,
        runtime_thread_id="thr_" + "9" * 32,
    )

    assert store.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["task_id", "thread_id", "actor_id", "device_id"])
async def test_rejects_checkpoint_identity_mismatch(field: str) -> None:
    invalid = state()
    invalid[field] = "thr_" + "8" * 32 if field == "thread_id" else "other-001"

    await assert_rejected(invalid, "approval_resume_identity_mismatch")


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["approval_id", "action_digest"])
async def test_rejects_resume_candidate_mismatch(field: str) -> None:
    invalid = state()
    invalid["pending_approval"]["resume"][field] = (
        "apr_" + "7" * 24 if field == "approval_id" else "7" * 64
    )

    await assert_rejected(
        invalid,
        "approval_resume_candidate_mismatch",
    )


@pytest.mark.anyio
async def test_rejects_invalid_state_checkpoint_and_thread() -> None:
    invalid_status = state()
    invalid_status["status"] = "executing"
    await assert_rejected(
        invalid_status,
        "approval_resume_state_invalid",
    )

    invalid_checkpoint = state()
    invalid_checkpoint["pending_approval"]["private"] = "discard"
    await assert_rejected(
        invalid_checkpoint,
        "approval_resume_checkpoint_invalid",
    )

    await assert_rejected(
        state(),
        "approval_resume_thread_invalid",
        runtime_thread_id="unsafe",
    )


@pytest.mark.anyio
async def test_rejects_tampered_checkpoint_bindings() -> None:
    invalid = state()
    invalid["pending_approval"]["request"]["preview"]["action_digest"] = "1" * 64

    await assert_rejected(
        invalid,
        "approval_resume_checkpoint_invalid",
    )


@pytest.mark.anyio
async def test_atomic_store_allows_only_one_resolution() -> None:
    store = FakeResolutionStore()

    outcomes = await asyncio.gather(
        resumeApproval(
            deepcopy(state()),
            service=store,
            runtime_thread_id=THREAD_ID,
        ),
        resumeApproval(
            deepcopy(state()),
            service=store,
            runtime_thread_id=THREAD_ID,
        ),
        return_exceptions=True,
    )

    successes = [item for item in outcomes if isinstance(item, dict)]
    failures = [item for item in outcomes if isinstance(item, ApprovalResumeError)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].code == "approval_resolution_consumed"


@pytest.mark.anyio
async def test_store_failures_are_sanitized_and_cancellation_propagates() -> None:
    await assert_rejected(
        state(),
        "approval_resolution_unavailable",
        store=FakeResolutionStore(error=RuntimeError("private")),
    )
    with pytest.raises(asyncio.CancelledError):
        await resumeApproval(
            state(),
            service=FakeResolutionStore(error=asyncio.CancelledError()),
            runtime_thread_id=THREAD_ID,
        )


@pytest.mark.anyio
async def test_rejects_invalid_and_conflicting_store_records() -> None:
    await assert_rejected(
        state(),
        "approval_resolution_invalid",
        store=FakeResolutionStore(result=object()),
    )

    valid_store = FakeResolutionStore()
    valid = await valid_store.resolve_pending_approval(
        # Obtain the exact typed request through the public node contract.
        # The first node call below uses a different store and remains single-use.
        (
            await _captured_request()
        )
    )
    conflict = valid.model_copy(
        update={
            "request": valid.request.model_copy(
                update={"action_id": "act_" + "6" * 24}
            )
        }
    )
    await assert_rejected(
        state(),
        "approval_resolution_conflict",
        store=FakeResolutionStore(result=conflict),
    )


async def _captured_request():
    store = FakeResolutionStore()
    await resumeApproval(
        state(),
        service=store,
        runtime_thread_id=THREAD_ID,
    )
    return store.calls[0]
