from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from backend.tests.unit.graph.test_verification import (
    THREAD_ID,
    service as verification_service,
    state as verification_state,
)
from jarvis.graph import (
    ReflectionError,
    ReflectionRecord,
    ReflectionService,
    ReflectionStoreConflictError,
    proposeTaskReflection,
    verifyOutcome,
)


NOW = datetime(2026, 7, 4, 14, 0, tzinfo=timezone.utc)
VERSIONS = [
    {"kind": "prompt", "component_id": "jarvis.planner", "version": "1.0.0"},
    {"kind": "test", "component_id": "graph.verification", "version": "1.0.0"},
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Store:
    def __init__(self, loaded=None, load_error=None, record_error=None, override=None):
        self.loaded, self.load_error = loaded, load_error
        self.record_error, self.override = record_error, override
        self.loads, self.records = [], []

    async def load_candidate(self, candidate_id, *, actor_id, device_id):
        self.loads.append((candidate_id, actor_id, device_id))
        if self.load_error:
            raise self.load_error
        return self.loaded

    async def record_or_get_candidate(self, actor_id, device_id, candidate):
        self.records.append((actor_id, device_id, candidate))
        if self.record_error:
            raise self.record_error
        if self.override is not None:
            return self.override
        return ReflectionRecord(
            actor_id=actor_id, device_id=device_id, candidate=candidate,
            stored_at=NOW, created=True,
        )


def service(store=None, clock=None):
    return ReflectionService(
        store=store or Store(), clock=clock or (lambda: NOW)
    )


async def verified_state():
    state = verification_state()
    delta = await verifyOutcome(
        state, service=verification_service(), runtime_thread_id=THREAD_ID
    )
    state["observations"] = delta["observations"]
    state["status"] = "succeeded"
    state["errors"] = []
    return state


def make_failed(state):
    for item in state["observations"][:-1]:
        item["verdict"] = "failed"
        item["reason_code"] = "postcondition_not_met"
        item["retryable"] = False
    agg = state["observations"][-1]
    agg["outcome"] = "failed"
    agg["passed_count"] = 0
    agg["failed_count"] = agg["criterion_count"]
    state["status"] = "failed"


@pytest.mark.anyio
async def test_success_without_correction_produces_no_fabricated_learning():
    result = await proposeTaskReflection(
        await verified_state(), service=service(),
        runtime_thread_id=THREAD_ID, current_versions=VERSIONS,
    )
    assert result == {
        "reflection_candidate": None,
        "reason_code": "insufficient_evidence",
    }


@pytest.mark.anyio
async def test_verified_failure_proposes_review_only_test_fixture():
    state = await verified_state()
    make_failed(state)
    store = Store()

    result = await proposeTaskReflection(
        state, service=service(store), runtime_thread_id=THREAD_ID,
        current_versions=VERSIONS,
    )

    candidate = result["reflection_candidate"]
    assert candidate["kind"] == "test_improvement"
    assert candidate["recommendation_code"] == "add_failure_fixture"
    assert candidate["review_required"] is True
    assert candidate["automatic_application"] is False
    assert candidate["issue_codes"] == ["postcondition_not_met"]
    assert len(store.records) == 1


@pytest.mark.anyio
async def test_user_correction_proposes_prompt_review():
    state = await verified_state()
    evidence = state["observations"][0]["evidence_reference_ids"][0]
    correction = {
        "correction_id": "ucr_correction01",
        "task_id": state["task_id"], "thread_id": state["thread_id"],
        "actor_id": state["actor_id"], "device_id": state["device_id"],
        "code": "incorrect_scope",
        "evidence_reference_ids": [evidence],
        "corrected_at": NOW.isoformat(),
    }
    result = await proposeTaskReflection(
        state, service=service(), runtime_thread_id=THREAD_ID,
        current_versions=VERSIONS, user_correction=correction,
    )
    candidate = result["reflection_candidate"]
    assert candidate["kind"] == "prompt_review"
    assert candidate["recommendation_code"] == "review_prompt_contract"
    assert candidate["user_correction_id"] == "ucr_correction01"


@pytest.mark.anyio
async def test_store_replay_is_stable():
    state = await verified_state()
    make_failed(state)
    first_store = Store()
    first = await proposeTaskReflection(
        state, service=service(first_store), runtime_thread_id=THREAD_ID,
        current_versions=VERSIONS,
    )
    _, _, candidate = first_store.records[0]
    loaded = ReflectionRecord(
        actor_id=state["actor_id"], device_id=state["device_id"],
        candidate=candidate, stored_at=NOW, created=False,
    )
    replay_store = Store(loaded=loaded)
    replay = await proposeTaskReflection(
        state, service=service(replay_store), runtime_thread_id=THREAD_ID,
        current_versions=VERSIONS,
    )
    assert replay == first
    assert replay_store.records == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "planning", "reflection_state_invalid"),
        ("task_id", "bad", "reflection_identity_invalid"),
        ("actor_id", "x", "reflection_identity_invalid"),
        ("plan", {}, "reflection_evidence_invalid"),
        ("observations", [], "reflection_verification_missing"),
    ],
)
async def test_invalid_state_rejected(field, value, code):
    state = await verified_state()
    state[field] = value
    with pytest.raises(ReflectionError) as caught:
        await proposeTaskReflection(
            state, service=service(), runtime_thread_id=THREAD_ID,
            current_versions=VERSIONS,
        )
    assert caught.value.code == code


@pytest.mark.anyio
@pytest.mark.parametrize("versions", [[], "bad", [{"kind": "test"}]])
async def test_invalid_versions_rejected(versions):
    with pytest.raises(ReflectionError) as caught:
        await proposeTaskReflection(
            await verified_state(), service=service(),
            runtime_thread_id=THREAD_ID, current_versions=versions,
        )
    assert caught.value.code == "reflection_versions_invalid"


@pytest.mark.anyio
async def test_invalid_correction_identity_or_evidence_rejected():
    state = await verified_state()
    correction = {
        "correction_id": "ucr_correction01",
        "task_id": state["task_id"], "thread_id": state["thread_id"],
        "actor_id": "actor-other", "device_id": state["device_id"],
        "code": "incorrect_result",
        "evidence_reference_ids": ["evd_unknown01"],
        "corrected_at": NOW.isoformat(),
    }
    with pytest.raises(ReflectionError) as caught:
        await proposeTaskReflection(
            state, service=service(), runtime_thread_id=THREAD_ID,
            current_versions=VERSIONS, user_correction=correction,
        )
    assert caught.value.code == "reflection_correction_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["load", "record", "conflict"])
async def test_store_failures_sanitized(phase):
    state = await verified_state()
    make_failed(state)
    error = (
        ReflectionStoreConflictError() if phase == "conflict"
        else RuntimeError("private")
    )
    store = Store(
        load_error=error if phase == "load" else None,
        record_error=error if phase != "load" else None,
    )
    with pytest.raises(ReflectionError) as caught:
        await proposeTaskReflection(
            state, service=service(store), runtime_thread_id=THREAD_ID,
            current_versions=VERSIONS,
        )
    assert caught.value.code == (
        "reflection_record_conflict"
        if phase == "conflict" else "reflection_store_unavailable"
    )
    assert "private" not in str(caught.value)


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["load", "record"])
async def test_cancellation_propagates(phase):
    state = await verified_state()
    make_failed(state)
    store = Store(
        load_error=asyncio.CancelledError() if phase == "load" else None,
        record_error=asyncio.CancelledError() if phase == "record" else None,
    )
    with pytest.raises(asyncio.CancelledError):
        await proposeTaskReflection(
            state, service=service(store), runtime_thread_id=THREAD_ID,
            current_versions=VERSIONS,
        )


@pytest.mark.anyio
async def test_invalid_record_and_clock_fail_closed():
    state = await verified_state()
    make_failed(state)
    with pytest.raises(ReflectionError) as record:
        await proposeTaskReflection(
            state, service=service(Store(override={"bad": "record"})),
            runtime_thread_id=THREAD_ID, current_versions=VERSIONS,
        )
    assert record.value.code == "reflection_record_invalid"
    with pytest.raises(ReflectionError) as clock:
        await proposeTaskReflection(
            state, service=service(clock=lambda: datetime(2026, 7, 4)),
            runtime_thread_id=THREAD_ID, current_versions=VERSIONS,
        )
    assert clock.value.code == "reflection_clock_invalid"
