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
    FinalResponseError,
    FinalResponseRecord,
    FinalResponseService,
    FinalResponseStoreConflictError,
    renderFinalResponse,
    verifyOutcome,
)


NOW = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Store:
    def __init__(self, loaded=None, load_error=None, record_error=None, override=None):
        self.loaded, self.load_error = loaded, load_error
        self.record_error, self.override = record_error, override
        self.loads, self.records = [], []

    async def load_response(self, response_id, *, actor_id, device_id):
        self.loads.append((response_id, actor_id, device_id))
        if self.load_error:
            raise self.load_error
        return self.loaded

    async def record_or_get_response(self, request):
        self.records.append(request)
        if self.record_error:
            raise self.record_error
        if self.override is not None:
            return self.override
        return FinalResponseRecord(
            request=request, stored_at=NOW, created=True
        )


def service(store=None, clock=None):
    return FinalResponseService(
        store=store or Store(), clock=clock or (lambda: NOW)
    )


async def terminal_state(status="succeeded"):
    base = verification_state()
    verified = await verifyOutcome(
        base,
        service=verification_service(),
        runtime_thread_id=THREAD_ID,
    )
    base["observations"] = verified["observations"]
    base["status"] = status
    base["final_response"] = None
    base["errors"] = []
    return base


@pytest.mark.anyio
async def test_renders_verified_success_from_stored_evidence_only():
    state = await terminal_state()
    store = Store()

    delta = await renderFinalResponse(
        state, service=service(store), runtime_thread_id=THREAD_ID
    )

    response = delta["final_response"]
    assert response["status"] == "succeeded"
    assert response["verification_outcome"] == "succeeded"
    assert "independently verified" in response["summary"]
    assert len(response["evidence_reference_ids"]) == 3
    assert len(response["receipt_reference_ids"]) == 2
    assert response["unresolved_issue_codes"] == []
    assert len(store.records) == 1
    encoded = str(response)
    assert "private" not in encoded
    assert "chain" not in encoded


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "summary_fragment", "issue"),
    [
        ("cancelled", "cancelled", "task_cancelled"),
        ("denied", "denied", None),
        ("expired", "approval expired", "approval_expired"),
        ("failed", "did not complete", None),
    ],
)
async def test_terminal_templates_without_fabricated_success(
    status, summary_fragment, issue
):
    state = await terminal_state()
    state["observations"] = []
    state["status"] = status

    response = (
        await renderFinalResponse(
            state, service=service(), runtime_thread_id=THREAD_ID
        )
    )["final_response"]

    assert summary_fragment in response["summary"].lower()
    assert "completed and all" not in response["summary"].lower()
    if issue:
        assert issue in response["unresolved_issue_codes"]


@pytest.mark.anyio
async def test_uncertain_verification_uses_honest_template():
    state = await terminal_state()
    aggregate = state["observations"][-1]
    aggregate["outcome"] = "uncertain"
    aggregate["passed_count"] = 0
    aggregate["uncertain_count"] = 3
    for item in state["observations"][:-1]:
        item["verdict"] = "uncertain"
        item["evidence_reference_ids"] = []
        item["reason_code"] = "probe_unavailable"
        item["retryable"] = True
    state["revision_count"] = 2
    aggregate["revision"] = 2
    aggregate["recoverable"] = False
    state["status"] = "failed"

    response = (
        await renderFinalResponse(
            state, service=service(), runtime_thread_id=THREAD_ID
        )
    )["final_response"]

    assert response["verification_outcome"] == "uncertain"
    assert "could not be verified" in response["summary"]


@pytest.mark.anyio
async def test_status_mismatch_and_missing_verification_fail_closed():
    state = await terminal_state()
    state["status"] = "partially_succeeded"
    with pytest.raises(FinalResponseError) as mismatch:
        await renderFinalResponse(
            state, service=service(), runtime_thread_id=THREAD_ID
        )
    assert mismatch.value.code == "final_response_status_mismatch"

    state["observations"] = []
    with pytest.raises(FinalResponseError) as missing:
        await renderFinalResponse(
            state, service=service(), runtime_thread_id=THREAD_ID
        )
    assert missing.value.code == "final_response_verification_missing"


@pytest.mark.anyio
async def test_checkpoint_replay_performs_no_store_io():
    state = await terminal_state()
    first = await renderFinalResponse(
        state, service=service(), runtime_thread_id=THREAD_ID
    )
    state["final_response"] = first["final_response"]
    store = Store(load_error=AssertionError("must not load"))

    replay = await renderFinalResponse(
        state, service=service(store), runtime_thread_id=THREAD_ID
    )

    assert replay == first
    assert store.loads == []


@pytest.mark.anyio
async def test_stale_checkpoint_loads_persisted_response():
    state = await terminal_state()
    first_store = Store()
    first = await renderFinalResponse(
        state, service=service(first_store), runtime_thread_id=THREAD_ID
    )
    record = FinalResponseRecord(
        request=first_store.records[0], stored_at=NOW, created=False
    )
    loaded = Store(loaded=record)

    recovered = await renderFinalResponse(
        state, service=service(loaded), runtime_thread_id=THREAD_ID
    )

    assert recovered == first
    assert loaded.records == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "planning", "final_response_state_invalid"),
        ("task_id", "bad", "final_response_identity_invalid"),
        ("thread_id", "bad", "final_response_identity_invalid"),
        ("actor_id", "x", "final_response_identity_invalid"),
        ("device_id", "x", "final_response_identity_invalid"),
        ("action_results", [{"bad": "value"}], "final_response_evidence_invalid"),
        ("observations", "bad", "final_response_evidence_invalid"),
    ],
)
async def test_invalid_state_is_rejected(field, value, code):
    state = await terminal_state()
    state[field] = value
    with pytest.raises(FinalResponseError) as caught:
        await renderFinalResponse(
            state, service=service(), runtime_thread_id=THREAD_ID
        )
    assert caught.value.code == code


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["load", "record", "conflict"])
async def test_store_failures_are_sanitized(phase):
    state = await terminal_state()
    error = (
        FinalResponseStoreConflictError()
        if phase == "conflict"
        else RuntimeError("private detail")
    )
    store = Store(
        load_error=error if phase == "load" else None,
        record_error=error if phase != "load" else None,
    )
    with pytest.raises(FinalResponseError) as caught:
        await renderFinalResponse(
            state, service=service(store), runtime_thread_id=THREAD_ID
        )
    assert caught.value.code == (
        "final_response_record_conflict"
        if phase == "conflict"
        else "final_response_store_unavailable"
    )
    assert "private" not in str(caught.value)


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["load", "record"])
async def test_cancellation_propagates(phase):
    state = await terminal_state()
    store = Store(
        load_error=asyncio.CancelledError() if phase == "load" else None,
        record_error=asyncio.CancelledError() if phase == "record" else None,
    )
    with pytest.raises(asyncio.CancelledError):
        await renderFinalResponse(
            state, service=service(store), runtime_thread_id=THREAD_ID
        )


@pytest.mark.anyio
async def test_malformed_record_clock_and_checkpoint_fail_closed():
    state = await terminal_state()
    with pytest.raises(FinalResponseError) as record:
        await renderFinalResponse(
            state,
            service=service(Store(override={"bad": "record"})),
            runtime_thread_id=THREAD_ID,
        )
    assert record.value.code == "final_response_record_invalid"

    with pytest.raises(FinalResponseError) as clock:
        await renderFinalResponse(
            state,
            service=service(clock=lambda: datetime(2026, 7, 4)),
            runtime_thread_id=THREAD_ID,
        )
    assert clock.value.code == "final_response_clock_invalid"

    state["final_response"] = {"bad": "response"}
    with pytest.raises(FinalResponseError) as checkpoint:
        await renderFinalResponse(
            state, service=service(), runtime_thread_id=THREAD_ID
        )
    assert checkpoint.value.code == "final_response_checkpoint_invalid"
