from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from jarvis.graph import (
    CriterionVerdict,
    OutcomeVerification,
    PlanActionDraft,
    PlanArgument,
    PlanDraft,
    PlanSuccessCriterion,
    PriorActionResult,
    VerificationError,
    VerificationProbeDescriptor,
    VerificationProbeResult,
    VerificationRecord,
    VerificationService,
    VerificationSettings,
    VerificationStoreConflictError,
    VerifiedOutcome,
    verifyOutcome,
)


TASK_ID = "tsk_" + "a" * 32
THREAD_ID = "thr_" + "b" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
ACTION_INSPECT = "act_" + "1" * 24
ACTION_UPDATE = "act_" + "2" * 24
CRITERION_INSPECT = "crt_" + "3" * 24
CRITERION_CHANGE = "crt_" + "4" * 24
CRITERION_TESTS = "crt_" + "5" * 24
RECEIPT_INSPECT = "rcp_receipt01"
RECEIPT_UPDATE = "rcp_receipt02"
COMPLETED_AT = datetime(2026, 7, 4, 8, 0, tzinfo=timezone.utc)
REQUESTED_AT = COMPLETED_AT + timedelta(minutes=1)
VERIFIED_AT = REQUESTED_AT + timedelta(seconds=1)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def plan() -> PlanDraft:
    return PlanDraft(
        objective="modify_project",
        assumptions=(),
        actions=(
            PlanActionDraft(
                action_id=ACTION_INSPECT,
                capability_id="project.inspect",
                capability_version="1.0.0",
                arguments=(
                    PlanArgument(
                        name="project",
                        value="res_project001",
                    ),
                ),
                dependencies=(),
                timeout_seconds=30,
            ),
            PlanActionDraft(
                action_id=ACTION_UPDATE,
                capability_id="project.update",
                capability_version="1.2.0",
                arguments=(
                    PlanArgument(
                        name="project",
                        value="res_project001",
                    ),
                    PlanArgument(name="mode", value="safe_fix"),
                ),
                dependencies=(ACTION_INSPECT,),
                timeout_seconds=120,
            ),
        ),
        success_criteria=(
            PlanSuccessCriterion(
                criterion_id=CRITERION_INSPECT,
                action_id=ACTION_INSPECT,
                verification_code="inspection_recorded",
            ),
            PlanSuccessCriterion(
                criterion_id=CRITERION_CHANGE,
                action_id=ACTION_UPDATE,
                verification_code="change_observed",
            ),
            PlanSuccessCriterion(
                criterion_id=CRITERION_TESTS,
                action_id=ACTION_UPDATE,
                verification_code="tests_passed",
            ),
        ),
        warnings=(),
    )


def action_result(
    action_id: str,
    receipt_id: str,
    *,
    outcome: str = "succeeded",
) -> PriorActionResult:
    return PriorActionResult(
        dispatch_id=(
            "dsp_" + ("6" if action_id == ACTION_INSPECT else "7") * 24
        ),
        action_id=action_id,
        receipt_id=receipt_id,
        outcome=outcome,
        completed_at=COMPLETED_AT,
    )


def state(
    *,
    results: list[dict[str, Any]] | None = None,
    revision: int = 0,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_results = results
    if selected_results is None:
        selected_results = [
            action_result(
                ACTION_INSPECT,
                RECEIPT_INSPECT,
            ).model_dump(mode="json"),
            action_result(
                ACTION_UPDATE,
                RECEIPT_UPDATE,
            ).model_dump(mode="json"),
        ]
    return {
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "plan": plan().model_dump(mode="json"),
        "action_results": selected_results,
        "observations": observations or [],
        "revision_count": revision,
        "status": "verifying",
    }


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self.values = list(values)

    def __call__(self) -> datetime:
        return self.values.pop(0)


class FakeProbe:
    def __init__(
        self,
        *,
        capability_id: str,
        capability_version: str,
        verification_code: str,
        verdict: CriterionVerdict = CriterionVerdict.PASSED,
        retryable: bool = False,
        error: BaseException | None = None,
        delay: float = 0,
        result_override: object | None = None,
    ) -> None:
        self.descriptor = VerificationProbeDescriptor(
            probe_id=f"probe.{verification_code}",
            capability_id=capability_id,
            capability_version=capability_version,
            verification_code=verification_code,
        )
        self.verdict = verdict
        self.retryable = retryable
        self.error = error
        self.delay = delay
        self.result_override = result_override
        self.requests = []

    async def verify(self, request):
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        if self.result_override is not None:
            return self.result_override
        passed = self.verdict is CriterionVerdict.PASSED
        return VerificationProbeResult(
            probe_id=self.descriptor.probe_id,
            verification_id=request.verification_id,
            criterion_id=request.criterion_id,
            action_id=request.action_id,
            receipt_id=request.receipt_id,
            verdict=self.verdict,
            evidence_reference_ids=(
                (f"evd_{request.criterion_id[-8:]}",)
                if self.verdict is not CriterionVerdict.UNCERTAIN
                else ()
            ),
            reason_code=None if passed else "postcondition_not_met",
            retryable=False if passed else self.retryable,
            observed_at=REQUESTED_AT,
        )


class FakeRegistry:
    def __init__(
        self,
        overrides: dict[str, object] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.error = error
        self.calls = []
        self.probes = {
            "inspection_recorded": FakeProbe(
                capability_id="project.inspect",
                capability_version="1.0.0",
                verification_code="inspection_recorded",
            ),
            "change_observed": FakeProbe(
                capability_id="project.update",
                capability_version="1.2.0",
                verification_code="change_observed",
            ),
            "tests_passed": FakeProbe(
                capability_id="project.update",
                capability_version="1.2.0",
                verification_code="tests_passed",
            ),
        }
        self.probes.update(overrides or {})

    def resolve_probe(
        self,
        verification_code: str,
        *,
        capability_id: str,
        capability_version: str,
    ):
        self.calls.append(
            (verification_code, capability_id, capability_version)
        )
        if self.error is not None:
            raise self.error
        return self.probes.get(verification_code)


class FakeStore:
    def __init__(
        self,
        *,
        loaded: object | None = None,
        load_error: BaseException | None = None,
        record_error: BaseException | None = None,
        record_override: object | None = None,
    ) -> None:
        self.loaded = loaded
        self.load_error = load_error
        self.record_error = record_error
        self.record_override = record_override
        self.load_calls = []
        self.record_calls = []

    async def load_verification(
        self,
        verification_id: str,
        *,
        actor_id: str,
        device_id: str,
    ):
        self.load_calls.append((verification_id, actor_id, device_id))
        if self.load_error is not None:
            raise self.load_error
        return self.loaded

    async def record_or_get_verification(self, request):
        self.record_calls.append(request)
        if self.record_error is not None:
            raise self.record_error
        if self.record_override is not None:
            return self.record_override
        return VerificationRecord(
            request=request,
            stored_at=VERIFIED_AT,
            created=True,
        )


def service(
    *,
    registry: FakeRegistry | None = None,
    store: FakeStore | None = None,
    settings: VerificationSettings | None = None,
    clock=None,
) -> VerificationService:
    return VerificationService(
        registry=registry or FakeRegistry(),
        store=store or FakeStore(),
        settings=settings or VerificationSettings(),
        clock=clock or SequenceClock(REQUESTED_AT, VERIFIED_AT),
    )


def aggregate(delta: dict[str, Any]) -> dict[str, Any]:
    return delta["observations"][-1]


@pytest.mark.anyio
async def test_all_independent_postconditions_pass() -> None:
    registry = FakeRegistry()
    store = FakeStore()
    original = state()
    before = deepcopy(original)

    delta = await verifyOutcome(
        original,
        service=service(registry=registry, store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert original == before
    assert delta["status"] == "succeeded"
    assert len(delta["observations"]) == 4
    assert aggregate(delta)["outcome"] == "succeeded"
    assert aggregate(delta)["passed_count"] == 3
    assert aggregate(delta)["recoverable"] is False
    assert len(store.record_calls) == 1
    assert len(registry.calls) == 3


@pytest.mark.anyio
async def test_executor_success_does_not_override_failed_postcondition() -> None:
    registry = FakeRegistry(
        {
            "change_observed": FakeProbe(
                capability_id="project.update",
                capability_version="1.2.0",
                verification_code="change_observed",
                verdict=CriterionVerdict.FAILED,
            ),
            "tests_passed": FakeProbe(
                capability_id="project.update",
                capability_version="1.2.0",
                verification_code="tests_passed",
                verdict=CriterionVerdict.FAILED,
            ),
        }
    )

    delta = await verifyOutcome(
        state(),
        service=service(registry=registry),
        runtime_thread_id=THREAD_ID,
    )

    assert delta["status"] == "partially_succeeded"
    assert aggregate(delta)["outcome"] == "partially_succeeded"
    assert aggregate(delta)["failed_count"] == 2


@pytest.mark.anyio
async def test_executor_failure_can_still_have_verified_success() -> None:
    results = [
        action_result(
            ACTION_INSPECT,
            RECEIPT_INSPECT,
            outcome="failed",
        ).model_dump(mode="json"),
        action_result(
            ACTION_UPDATE,
            RECEIPT_UPDATE,
            outcome="uncertain",
        ).model_dump(mode="json"),
    ]

    delta = await verifyOutcome(
        state(results=results),
        service=service(),
        runtime_thread_id=THREAD_ID,
    )

    assert delta["status"] == "succeeded"
    assert aggregate(delta)["outcome"] == "succeeded"


@pytest.mark.anyio
async def test_all_failed_postconditions_classify_failed() -> None:
    registry = FakeRegistry(
        {
            code: FakeProbe(
                capability_id=(
                    "project.inspect"
                    if code == "inspection_recorded"
                    else "project.update"
                ),
                capability_version=(
                    "1.0.0"
                    if code == "inspection_recorded"
                    else "1.2.0"
                ),
                verification_code=code,
                verdict=CriterionVerdict.FAILED,
            )
            for code in (
                "inspection_recorded",
                "change_observed",
                "tests_passed",
            )
        }
    )

    delta = await verifyOutcome(
        state(),
        service=service(registry=registry),
        runtime_thread_id=THREAD_ID,
    )

    assert delta["status"] == "failed"
    assert aggregate(delta)["outcome"] == "failed"


@pytest.mark.anyio
async def test_retryable_uncertainty_routes_to_revision() -> None:
    uncertain = FakeProbe(
        capability_id="project.update",
        capability_version="1.2.0",
        verification_code="tests_passed",
        verdict=CriterionVerdict.UNCERTAIN,
        retryable=True,
    )

    delta = await verifyOutcome(
        state(),
        service=service(
            registry=FakeRegistry({"tests_passed": uncertain})
        ),
        runtime_thread_id=THREAD_ID,
    )

    assert delta["status"] == "planning"
    assert aggregate(delta)["outcome"] == "uncertain"
    assert aggregate(delta)["recoverable"] is True


@pytest.mark.anyio
async def test_exhausted_uncertainty_terminates_failed_but_stays_explicit() -> None:
    uncertain = FakeProbe(
        capability_id="project.update",
        capability_version="1.2.0",
        verification_code="tests_passed",
        verdict=CriterionVerdict.UNCERTAIN,
        retryable=True,
    )

    delta = await verifyOutcome(
        state(revision=2),
        service=service(
            registry=FakeRegistry({"tests_passed": uncertain})
        ),
        runtime_thread_id=THREAD_ID,
    )

    assert delta["status"] == "failed"
    assert aggregate(delta)["outcome"] == "uncertain"
    assert aggregate(delta)["recoverable"] is False


@pytest.mark.anyio
async def test_retryable_failure_requires_every_issue_to_be_retryable() -> None:
    retryable = FakeProbe(
        capability_id="project.update",
        capability_version="1.2.0",
        verification_code="change_observed",
        verdict=CriterionVerdict.FAILED,
        retryable=True,
    )
    permanent = FakeProbe(
        capability_id="project.update",
        capability_version="1.2.0",
        verification_code="tests_passed",
        verdict=CriterionVerdict.FAILED,
        retryable=False,
    )

    mixed = await verifyOutcome(
        state(),
        service=service(
            registry=FakeRegistry(
                {
                    "change_observed": retryable,
                    "tests_passed": permanent,
                }
            )
        ),
        runtime_thread_id=THREAD_ID,
    )
    retry_only = await verifyOutcome(
        state(),
        service=service(
            registry=FakeRegistry(
                {
                    "change_observed": retryable,
                    "tests_passed": FakeProbe(
                        capability_id="project.update",
                        capability_version="1.2.0",
                        verification_code="tests_passed",
                        verdict=CriterionVerdict.FAILED,
                        retryable=True,
                    ),
                }
            )
        ),
        runtime_thread_id=THREAD_ID,
    )

    assert mixed["status"] == "partially_succeeded"
    assert aggregate(mixed)["recoverable"] is False
    assert retry_only["status"] == "planning"
    assert aggregate(retry_only)["recoverable"] is True


@pytest.mark.anyio
async def test_missing_action_result_is_explicit_uncertainty_without_probe() -> None:
    registry = FakeRegistry()
    results = [
        action_result(
            ACTION_INSPECT,
            RECEIPT_INSPECT,
        ).model_dump(mode="json")
    ]

    delta = await verifyOutcome(
        state(results=results),
        service=service(registry=registry),
        runtime_thread_id=THREAD_ID,
    )

    assert delta["status"] == "planning"
    assert aggregate(delta)["outcome"] == "uncertain"
    missing = [
        item
        for item in delta["observations"][:-1]
        if item["reason_code"] == "action_result_missing"
    ]
    assert len(missing) == 2
    assert {call[0] for call in registry.calls} == {
        "inspection_recorded"
    }


@pytest.mark.anyio
async def test_missing_probe_timeout_and_exception_become_uncertain() -> None:
    registry = FakeRegistry(
        {
            "inspection_recorded": None,
            "change_observed": FakeProbe(
                capability_id="project.update",
                capability_version="1.2.0",
                verification_code="change_observed",
                delay=0.05,
            ),
            "tests_passed": FakeProbe(
                capability_id="project.update",
                capability_version="1.2.0",
                verification_code="tests_passed",
                error=RuntimeError("private probe detail"),
            ),
        }
    )

    delta = await verifyOutcome(
        state(),
        service=service(
            registry=registry,
            settings=VerificationSettings(probe_timeout_seconds=0.01),
        ),
        runtime_thread_id=THREAD_ID,
    )

    reasons = {
        item["reason_code"] for item in delta["observations"][:-1]
    }
    assert reasons == {
        "probe_unavailable",
        "probe_timeout",
    }
    assert aggregate(delta)["outcome"] == "uncertain"


@pytest.mark.anyio
async def test_probe_receives_exact_receipt_resources_and_identity() -> None:
    registry = FakeRegistry()

    await verifyOutcome(
        state(),
        service=service(registry=registry),
        runtime_thread_id=THREAD_ID,
    )

    request = registry.probes["change_observed"].requests[0]
    assert request.task_id == TASK_ID
    assert request.thread_id == THREAD_ID
    assert request.actor_id == ACTOR_ID
    assert request.device_id == DEVICE_ID
    assert request.receipt_id == RECEIPT_UPDATE
    assert request.resource_ids == ("res_project001",)
    assert request.arguments == plan().actions[1].arguments


@pytest.mark.anyio
async def test_stale_checkpoint_recovers_existing_store_record_without_probes() -> None:
    first_store = FakeStore()
    first = await verifyOutcome(
        state(),
        service=service(store=first_store),
        runtime_thread_id=THREAD_ID,
    )
    record = VerificationRecord(
        request=first_store.record_calls[0],
        stored_at=VERIFIED_AT,
        created=False,
    )
    registry = FakeRegistry(error=AssertionError("probe must not run"))
    loaded_store = FakeStore(loaded=record)

    recovered = await verifyOutcome(
        state(),
        service=service(registry=registry, store=loaded_store),
        runtime_thread_id=THREAD_ID,
    )

    assert recovered == first
    assert loaded_store.record_calls == []
    assert registry.calls == []


@pytest.mark.anyio
async def test_checkpoint_replay_emits_no_duplicate_observations_or_io() -> None:
    first_store = FakeStore()
    first = await verifyOutcome(
        state(),
        service=service(store=first_store),
        runtime_thread_id=THREAD_ID,
    )
    registry = FakeRegistry(error=AssertionError("probe must not run"))
    store = FakeStore(load_error=AssertionError("store must not run"))

    replay = await verifyOutcome(
        state(observations=first["observations"]),
        service=service(registry=registry, store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert replay == {"observations": [], "status": "succeeded"}
    assert registry.calls == []
    assert store.load_calls == []


@pytest.mark.anyio
async def test_partial_checkpoint_verification_is_rejected() -> None:
    first = await verifyOutcome(
        state(),
        service=service(),
        runtime_thread_id=THREAD_ID,
    )

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(observations=first["observations"][:-1]),
            service=service(),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_checkpoint_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "executing", "verification_state_invalid"),
        ("task_id", "bad", "verification_identity_invalid"),
        ("thread_id", "bad", "verification_identity_invalid"),
        ("actor_id", "x", "verification_identity_invalid"),
        ("device_id", "x", "verification_identity_invalid"),
        ("revision_count", -1, "verification_identity_invalid"),
        ("revision_count", True, "verification_identity_invalid"),
        ("plan", {}, "verification_contract_invalid"),
        ("action_results", [{"bad": "record"}], "verification_contract_invalid"),
        ("observations", "bad", "verification_contract_invalid"),
    ],
)
async def test_invalid_state_is_rejected(
    field: str,
    value: object,
    code: str,
) -> None:
    invalid = state()
    invalid[field] = value

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            invalid,
            service=service(),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == code


@pytest.mark.anyio
async def test_runtime_thread_mismatch_is_rejected_before_io() -> None:
    store = FakeStore()

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(store=store),
            runtime_thread_id="thr_" + "f" * 32,
        )

    assert caught.value.code == "verification_identity_invalid"
    assert store.load_calls == []


@pytest.mark.anyio
async def test_duplicate_or_unknown_action_results_are_rejected() -> None:
    duplicate = action_result(
        ACTION_INSPECT,
        RECEIPT_INSPECT,
    ).model_dump(mode="json")
    with pytest.raises(VerificationError) as duplicate_error:
        await verifyOutcome(
            state(results=[duplicate, duplicate]),
            service=service(),
            runtime_thread_id=THREAD_ID,
        )
    assert duplicate_error.value.code == "verification_contract_invalid"

    unknown = action_result(
        "act_" + "9" * 24,
        "rcp_receipt09",
    ).model_dump(mode="json")
    with pytest.raises(VerificationError) as unknown_error:
        await verifyOutcome(
            state(results=[unknown]),
            service=service(),
            runtime_thread_id=THREAD_ID,
        )
    assert unknown_error.value.code == "verification_contract_invalid"


@pytest.mark.anyio
async def test_invalid_probe_descriptor_fails_closed() -> None:
    probe = FakeProbe(
        capability_id="project.inspect",
        capability_version="1.0.0",
        verification_code="inspection_recorded",
    )
    probe.descriptor = probe.descriptor.model_copy(
        update={"capability_version": "9.0.0"}
    )

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(
                registry=FakeRegistry({"inspection_recorded": probe})
            ),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_probe_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        {"verification_id": "vrf_" + "9" * 24},
        {"criterion_id": "crt_" + "9" * 24},
        {"action_id": "act_" + "9" * 24},
        {"receipt_id": "rcp_different01"},
        {"probe_id": "probe.different"},
        {"observed_at": COMPLETED_AT - timedelta(seconds=1)},
    ],
)
async def test_mismatched_probe_result_fails_closed(
    change: dict[str, object],
) -> None:
    base = VerificationProbeResult(
        probe_id="probe.inspection_recorded",
        verification_id="vrf_" + "8" * 24,
        criterion_id=CRITERION_INSPECT,
        action_id=ACTION_INSPECT,
        receipt_id=RECEIPT_INSPECT,
        verdict=CriterionVerdict.PASSED,
        evidence_reference_ids=("evd_evidence01",),
        observed_at=REQUESTED_AT,
    )
    invalid_result = base.model_copy(update=change)
    probe = FakeProbe(
        capability_id="project.inspect",
        capability_version="1.0.0",
        verification_code="inspection_recorded",
        result_override=invalid_result,
    )

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(
                registry=FakeRegistry({"inspection_recorded": probe})
            ),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_probe_invalid"


@pytest.mark.anyio
async def test_non_contract_probe_result_fails_closed() -> None:
    probe = FakeProbe(
        capability_id="project.inspect",
        capability_version="1.0.0",
        verification_code="inspection_recorded",
        result_override={"verdict": "passed"},
    )

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(
                registry=FakeRegistry({"inspection_recorded": probe})
            ),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_probe_invalid"


@pytest.mark.anyio
async def test_registry_failure_is_sanitized() -> None:
    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(
                registry=FakeRegistry(
                    error=RuntimeError("private registry detail")
                )
            ),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_registry_unavailable"
    assert "private registry detail" not in str(caught.value)


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["load", "record", "conflict"])
async def test_store_failures_are_sanitized(
    phase: str,
) -> None:
    error: BaseException = (
        VerificationStoreConflictError()
        if phase == "conflict"
        else RuntimeError("private store detail")
    )
    store = FakeStore(
        load_error=error if phase == "load" else None,
        record_error=error if phase != "load" else None,
    )

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(store=store),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == (
        "verification_record_conflict"
        if phase == "conflict"
        else "verification_store_unavailable"
    )
    assert "private store detail" not in str(caught.value)


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["load", "record"])
async def test_malformed_store_record_fails_closed(phase: str) -> None:
    store = FakeStore(
        loaded={"bad": "record"} if phase == "load" else None,
        record_override={"bad": "record"} if phase == "record" else None,
    )

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(store=store),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_record_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tamper",
    ["outcome", "receipt", "observation_id"],
)
async def test_semantically_forged_store_record_fails_closed(
    tamper: str,
) -> None:
    initial_store = FakeStore()
    await verifyOutcome(
        state(),
        service=service(store=initial_store),
        runtime_thread_id=THREAD_ID,
    )
    request = initial_store.record_calls[0]
    observations = list(request.criterion_observations)
    outcome = request.outcome
    if tamper == "outcome":
        outcome = outcome.model_copy(
            update={"outcome": VerifiedOutcome.FAILED}
        )
    elif tamper == "receipt":
        observations[0] = observations[0].model_copy(
            update={"receipt_id": "rcp_forged001"}
        )
    else:
        observations[0] = observations[0].model_copy(
            update={"observation_id": "obs_" + "9" * 24}
        )
    forged_request = request.model_copy(
        update={
            "criterion_observations": tuple(observations),
            "outcome": outcome,
        }
    )
    forged_record = VerificationRecord.model_construct(
        request=forged_request,
        stored_at=VERIFIED_AT,
        created=False,
    )

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(store=FakeStore(loaded=forged_record)),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_record_invalid"


@pytest.mark.anyio
async def test_semantically_forged_checkpoint_aggregate_fails_closed() -> None:
    first = await verifyOutcome(
        state(),
        service=service(),
        runtime_thread_id=THREAD_ID,
    )
    forged = deepcopy(first["observations"])
    forged[-1]["outcome"] = "failed"

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(observations=forged),
            service=service(),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_checkpoint_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["probe", "load", "record"])
async def test_cancellation_propagates(phase: str) -> None:
    registry = FakeRegistry()
    store = FakeStore()
    if phase == "probe":
        registry.probes["inspection_recorded"] = FakeProbe(
            capability_id="project.inspect",
            capability_version="1.0.0",
            verification_code="inspection_recorded",
            error=asyncio.CancelledError(),
        )
    elif phase == "load":
        store.load_error = asyncio.CancelledError()
    else:
        store.record_error = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await verifyOutcome(
            state(),
            service=service(registry=registry, store=store),
            runtime_thread_id=THREAD_ID,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "settings",
    [
        VerificationSettings(probe_timeout_seconds=0),
        VerificationSettings(probe_timeout_seconds=31),
        VerificationSettings(max_concurrency=0),
        VerificationSettings(max_concurrency=17),
        VerificationSettings(max_revision_count=-1),
        VerificationSettings(max_revision_count=3),
    ],
)
async def test_invalid_settings_fail_before_io(
    settings: VerificationSettings,
) -> None:
    store = FakeStore()

    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(settings=settings, store=store),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_settings_incompatible"
    assert store.load_calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "clock",
    [
        lambda: datetime(2026, 7, 4),
        SequenceClock(REQUESTED_AT, COMPLETED_AT),
    ],
)
async def test_invalid_clock_fails_closed(clock) -> None:
    with pytest.raises(VerificationError) as caught:
        await verifyOutcome(
            state(),
            service=service(clock=clock),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "verification_clock_invalid"


def test_probe_result_contract_requires_real_evidence_for_definite_verdict() -> None:
    with pytest.raises(ValidationError):
        VerificationProbeResult(
            probe_id="probe.tests",
            verification_id="vrf_" + "8" * 24,
            criterion_id=CRITERION_TESTS,
            action_id=ACTION_UPDATE,
            receipt_id=RECEIPT_UPDATE,
            verdict="passed",
            evidence_reference_ids=(),
            observed_at=REQUESTED_AT,
        )


def test_aggregate_contract_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValidationError):
        OutcomeVerification(
            verification_id="vrf_" + "8" * 24,
            task_id=TASK_ID,
            thread_id=THREAD_ID,
            revision=0,
            outcome="succeeded",
            recoverable=False,
            criterion_count=3,
            passed_count=2,
            failed_count=0,
            uncertain_count=0,
            action_count=2,
            action_result_count=2,
            verified_at=VERIFIED_AT,
        )
