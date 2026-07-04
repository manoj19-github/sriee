from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from jarvis.graph import (
    CapabilityDefinition,
    CapabilityManifest,
    CapabilityParameter,
    ContextKind,
    CriterionObservation,
    CriterionVerdict,
    ModelPlanDraft,
    ParameterKind,
    PlanContextBundle,
    PlanContextSummary,
    PlanDraftError,
    PlanResource,
    PlanRevisionError,
    PlanRevisionRecord,
    PlanRevisionService,
    PlanRevisionSettings,
    PlanRevisionStoreConflictError,
    ScopeCorrection,
    VerifiedOutcome,
    revisePlan,
)
from jarvis.graph.plan import _project_plan
from jarvis.graph.verification import (
    OutcomeVerification,
    _observation_id,
    _verification_id,
)
from jarvis.providers.ollama import OllamaChatResponse, OllamaProviderError


TASK_ID = "tsk_" + "a" * 32
THREAD_ID = "thr_" + "b" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
REFS = ("pol_policy001", "cap_manifest01", "prj_project001")
RESOURCE = "res_project001"
NOW = datetime(2026, 7, 4, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def prior_model_payload() -> dict[str, Any]:
    return {
        "objective": "modify_project",
        "assumptions": [],
        "actions": [
            {
                "step_id": "step_inspect",
                "capability_id": "project.inspect",
                "capability_version": "1.0.0",
                "arguments": [{"name": "project", "value": RESOURCE}],
                "depends_on": [],
                "timeout_seconds": 20,
            }
        ],
        "success_criteria": [
            {
                "step_id": "step_inspect",
                "verification_code": "inspection_recorded",
            }
        ],
        "warnings": [],
    }


def revised_payload() -> dict[str, Any]:
    payload = prior_model_payload()
    payload["actions"].append(
        {
            "step_id": "step_repair",
            "capability_id": "project.repair",
            "capability_version": "1.0.0",
            "arguments": [
                {"name": "project", "value": RESOURCE},
                {"name": "mode", "value": "safe_fix"},
            ],
            "depends_on": [],
            "timeout_seconds": 90,
        }
    )
    payload["success_criteria"].append(
        {
            "step_id": "step_repair",
            "verification_code": "repair_observed",
        }
    )
    return payload


def prior_plan():
    return _project_plan(
        TASK_ID,
        ModelPlanDraft.model_validate(prior_model_payload()),
    )


def manifest() -> CapabilityManifest:
    resource = CapabilityParameter(
        name="project",
        kind=ParameterKind.RESOURCE,
        resource_types=("project",),
    )
    return CapabilityManifest(
        reference_id=REFS[1],
        version="1.0.0",
        actor_id=ACTOR_ID,
        device_id=DEVICE_ID,
        capabilities=(
            CapabilityDefinition(
                capability_id="project.inspect",
                version="1.0.0",
                description="Inspect the registered project.",
                parameters=(resource,),
                verification_codes=("inspection_recorded",),
                max_timeout_seconds=30,
                reversible=True,
            ),
            CapabilityDefinition(
                capability_id="project.repair",
                version="1.0.0",
                description="Apply one registered safe repair mode.",
                parameters=(
                    resource,
                    CapabilityParameter(
                        name="mode",
                        kind=ParameterKind.ENUM,
                        allowed_values=("safe_fix",),
                    ),
                ),
                verification_codes=("repair_observed",),
                max_timeout_seconds=120,
                reversible=True,
            ),
        ),
    )


def bundle() -> PlanContextBundle:
    return PlanContextBundle(
        summaries=(
            PlanContextSummary(
                reference_id=REFS[0],
                kind=ContextKind.POLICY,
                summary="Current policy.",
            ),
            PlanContextSummary(
                reference_id=REFS[1],
                kind=ContextKind.CAPABILITY,
                summary="Current capabilities.",
            ),
            PlanContextSummary(
                reference_id=REFS[2],
                kind=ContextKind.PROJECT,
                summary="Inspection failed and a safe repair is available.",
            ),
        ),
        manifest=manifest(),
        resources=(
            PlanResource(
                resource_id=RESOURCE,
                resource_type="project",
                label="Selected project",
            ),
        ),
    )


def result():
    action = prior_plan().actions[0]
    return {
        "type": "action.result",
        "version": "1.0",
        "dispatch_id": "dsp_" + "d" * 24,
        "action_id": action.action_id,
        "receipt_id": "rcp_receipt01",
        "outcome": "failed",
        "completed_at": NOW.isoformat(),
    }


def evidence(revision: int = 0, *, recoverable: bool = True):
    selected_plan = prior_plan()
    verification_id = _verification_id(
        TASK_ID, THREAD_ID, revision, selected_plan
    )
    criterion = selected_plan.success_criteria[0]
    observation = CriterionObservation(
        observation_id=_observation_id(
            verification_id, criterion.criterion_id
        ),
        verification_id=verification_id,
        criterion_id=criterion.criterion_id,
        action_id=criterion.action_id,
        receipt_id="rcp_receipt01",
        verification_code=criterion.verification_code,
        probe_id="probe.inspection",
        verdict=CriterionVerdict.FAILED,
        evidence_reference_ids=("evd_failure01",),
        reason_code="postcondition_not_met",
        retryable=recoverable,
        observed_at=NOW + timedelta(seconds=1),
    )
    aggregate = OutcomeVerification(
        verification_id=verification_id,
        task_id=TASK_ID,
        thread_id=THREAD_ID,
        revision=revision,
        outcome=VerifiedOutcome.FAILED,
        recoverable=recoverable,
        criterion_count=1,
        passed_count=0,
        failed_count=1,
        uncertain_count=0,
        action_count=1,
        action_result_count=1,
        verified_at=NOW + timedelta(seconds=2),
    )
    return [
        observation.model_dump(mode="json"),
        aggregate.model_dump(mode="json"),
    ]


def state(
    *,
    revision: int = 0,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "context_refs": list(REFS),
        "intent": {
            "name": "modify_project",
            "confidence": 0.95,
            "scope": {
                "target": "project",
                "context_refs": [REFS[2]],
            },
            "ambiguities": [],
            "consequential": True,
            "needs_clarification": False,
        },
        "plan": prior_plan().model_dump(mode="json"),
        "policy_decisions": [{"old": "must-clear"}],
        "pending_approval": {"old": "must-clear"},
        "action_results": [result()],
        "observations": (
            evidence(revision)
            if observations is None
            else observations
        ),
        "revision_count": revision,
        "status": "planning",
    }


def response(payload: object = None, *, structured: bool = True):
    selected = revised_payload() if payload is None else payload
    return OllamaChatResponse(
        model="qwen3:4b-instruct",
        content=(
            selected if isinstance(selected, str) else json.dumps(selected)
        ),
        prompt_tokens=50,
        output_tokens=30,
        total_duration_ns=100,
        structured=structured,
    )


class FakeGateway:
    def __init__(self, values=None):
        self.values = values or [response()]
        self.requests = []

    async def chat(self, request):
        self.requests.append(request)
        value = self.values[len(self.requests) - 1]
        if isinstance(value, BaseException):
            raise value
        return value


class FakeResolver:
    def __init__(self, value=None, error=None, delay=0):
        self.value = bundle() if value is None else value
        self.error = error
        self.delay = delay
        self.calls = []

    async def resolve_plan_context(
        self, reference_ids, *, actor_id, device_id
    ):
        self.calls.append((reference_ids, actor_id, device_id))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.value


class FakeStore:
    def __init__(
        self, *, loaded=None, load_error=None, record_error=None, override=None
    ):
        self.loaded = loaded
        self.load_error = load_error
        self.record_error = record_error
        self.override = override
        self.load_calls = []
        self.record_calls = []

    async def load_revision(
        self, revision_id, *, actor_id, device_id
    ):
        self.load_calls.append((revision_id, actor_id, device_id))
        if self.load_error:
            raise self.load_error
        return self.loaded

    async def record_or_get_revision(self, request):
        self.record_calls.append(request)
        if self.record_error:
            raise self.record_error
        if self.override is not None:
            return self.override
        return PlanRevisionRecord(
            request=request,
            stored_at=NOW + timedelta(minutes=1),
            created=True,
        )


def service(
    *, gateway=None, resolver=None, store=None, settings=None, clock=None
):
    return PlanRevisionService(
        gateway=gateway or FakeGateway(),
        resolver=resolver or FakeResolver(),
        store=store or FakeStore(),
        settings=settings or PlanRevisionSettings(),
        clock=clock or (lambda: NOW),
    )


@pytest.mark.anyio
async def test_creates_immutable_revision_and_resets_authorization() -> None:
    original = state()
    before = deepcopy(original)
    store = FakeStore()

    delta = await revisePlan(
        original,
        service=service(store=store),
        runtime_thread_id=THREAD_ID,
    )

    assert original == before
    assert delta["revision_count"] == 1
    assert delta["status"] == "planning"
    assert delta["policy_decisions"] == []
    assert delta["pending_approval"] is None
    assert "action_results" not in delta
    assert delta["plan"]["actions"][0] == before["plan"]["actions"][0]
    assert len(delta["plan"]["actions"]) == 2
    assert len(store.record_calls) == 1


@pytest.mark.anyio
async def test_revision_prompt_contains_only_typed_evidence_and_untrusted_context():
    gateway = FakeGateway()

    await revisePlan(
        state(),
        service=service(gateway=gateway),
        runtime_thread_id=THREAD_ID,
    )

    request = gateway.requests[0]
    payload = json.loads(request.messages[1].content)
    assert request.response_schema["type"] == "object"
    assert payload["verification"]["recoverable"] is True
    assert payload["action_results"][0]["outcome"] == "failed"
    assert all(
        item["trust"] == "untrusted_data"
        for item in payload["context_summaries"]
    )
    assert "Never return raw paths" in request.messages[0].content


def mutate(mutator):
    payload = revised_payload()
    mutator(payload)
    return payload


INVALID_REVISIONS = [
    "not-json",
    prior_model_payload(),
    mutate(
        lambda p: p["actions"][1].update(
            depends_on=["step_inspect"]
        )
    ),
    mutate(
        lambda p: p["actions"][1].update(
            capability_id="project.unknown"
        )
    ),
]


@pytest.mark.anyio
@pytest.mark.parametrize("invalid", INVALID_REVISIONS)
async def test_invalid_revision_gets_one_content_free_repair(invalid) -> None:
    gateway = FakeGateway([response(invalid), response()])

    delta = await revisePlan(
        state(),
        service=service(gateway=gateway),
        runtime_thread_id=THREAD_ID,
    )

    assert delta["revision_count"] == 1
    assert len(gateway.requests) == 2
    repair = " ".join(
        message.content for message in gateway.requests[1].messages
    )
    rejected = invalid if isinstance(invalid, str) else json.dumps(invalid)
    assert rejected not in repair
    assert "prior revision response" in repair


@pytest.mark.anyio
async def test_two_invalid_outputs_fail_closed() -> None:
    gateway = FakeGateway([response("bad-one"), response("bad-two")])

    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            state(),
            service=service(gateway=gateway),
            runtime_thread_id=THREAD_ID,
        )

    assert caught.value.code == "revision_model_output_invalid"
    assert len(gateway.requests) == 2


@pytest.mark.anyio
async def test_second_revision_allowed_and_third_rejected() -> None:
    second = await revisePlan(
        state(revision=1),
        service=service(),
        runtime_thread_id=THREAD_ID,
    )
    assert second["revision_count"] == 2

    exhausted = state()
    exhausted["revision_count"] = 2
    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            exhausted,
            service=service(),
            runtime_thread_id=THREAD_ID,
        )
    assert caught.value.code == "revision_identity_invalid"


@pytest.mark.anyio
async def test_requires_recoverable_evidence_without_scope_correction() -> None:
    for observations in ([], evidence(recoverable=False)):
        with pytest.raises(PlanRevisionError) as caught:
            await revisePlan(
                state(observations=observations),
                service=service(),
                runtime_thread_id=THREAD_ID,
            )
        assert caught.value.code == "revision_trigger_invalid"


def correction(**changes) -> dict[str, Any]:
    value = ScopeCorrection(
        correction_id="scp_correction01",
        task_id=TASK_ID,
        thread_id=THREAD_ID,
        actor_id=ACTOR_ID,
        device_id=DEVICE_ID,
        prior_revision=0,
        reason="resource_corrected",
        context_reference_ids=(REFS[2],),
        resource_ids=(RESOURCE,),
        corrected_at=NOW,
    ).model_dump(mode="json")
    value.update(changes)
    return value


@pytest.mark.anyio
async def test_identity_bound_scope_correction_can_trigger_revision() -> None:
    delta = await revisePlan(
        state(observations=[]),
        service=service(),
        runtime_thread_id=THREAD_ID,
        scope_correction=correction(),
    )

    assert delta["revision_count"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "candidate",
    [
        correction(actor_id="actor-other"),
        correction(prior_revision=1),
        correction(resource_ids=["res_unknown001"]),
        correction(context_reference_ids=["prj_unknown001"]),
    ],
)
async def test_invalid_scope_correction_is_rejected(candidate) -> None:
    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            state(observations=[]),
            service=service(),
            runtime_thread_id=THREAD_ID,
            scope_correction=candidate,
        )
    assert caught.value.code == "scope_correction_invalid"


@pytest.mark.anyio
async def test_store_replay_skips_model_and_returns_exact_revision() -> None:
    first_store = FakeStore()
    first = await revisePlan(
        state(),
        service=service(store=first_store),
        runtime_thread_id=THREAD_ID,
    )
    record = PlanRevisionRecord(
        request=first_store.record_calls[0],
        stored_at=NOW + timedelta(minutes=1),
        created=False,
    )
    gateway = FakeGateway([AssertionError("model must not run")])
    replay = await revisePlan(
        state(),
        service=service(
            gateway=gateway,
            store=FakeStore(loaded=record),
        ),
        runtime_thread_id=THREAD_ID,
    )

    assert replay == first
    assert gateway.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "verifying", "revision_state_invalid"),
        ("task_id", "bad", "revision_identity_invalid"),
        ("thread_id", "bad", "revision_identity_invalid"),
        ("actor_id", "x", "revision_identity_invalid"),
        ("device_id", "x", "revision_identity_invalid"),
        ("revision_count", -1, "revision_identity_invalid"),
        ("context_refs", [], "revision_context_invalid"),
        ("intent", {}, "revision_contract_invalid"),
        ("plan", {}, "revision_contract_invalid"),
        ("action_results", [{"bad": "value"}], "revision_contract_invalid"),
        ("observations", "bad", "revision_evidence_invalid"),
    ],
)
async def test_invalid_state_is_rejected(field, value, code) -> None:
    invalid = state()
    invalid[field] = value
    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            invalid,
            service=service(),
            runtime_thread_id=THREAD_ID,
        )
    assert caught.value.code == code


@pytest.mark.anyio
async def test_thread_mismatch_fails_before_dependencies() -> None:
    resolver = FakeResolver()
    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            state(),
            service=service(resolver=resolver),
            runtime_thread_id="thr_" + "f" * 32,
        )
    assert caught.value.code == "revision_identity_invalid"
    assert resolver.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["resolver", "model", "load", "record"])
async def test_dependency_failures_are_sanitized(phase) -> None:
    gateway = FakeGateway()
    resolver = FakeResolver()
    store = FakeStore()
    if phase == "resolver":
        resolver.error = RuntimeError("private resolver")
    elif phase == "model":
        gateway.values = [OllamaProviderError("private model")]
    elif phase == "load":
        store.load_error = RuntimeError("private load")
    else:
        store.record_error = RuntimeError("private record")
    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            state(),
            service=service(
                gateway=gateway, resolver=resolver, store=store
            ),
            runtime_thread_id=THREAD_ID,
        )
    assert caught.value.code in {
        "revision_context_unavailable",
        "revision_model_unavailable",
        "revision_store_unavailable",
    }
    assert "private" not in str(caught.value)


@pytest.mark.anyio
async def test_store_conflict_and_malformed_record_fail_closed() -> None:
    with pytest.raises(PlanRevisionError) as conflict:
        await revisePlan(
            state(),
            service=service(
                store=FakeStore(
                    record_error=PlanRevisionStoreConflictError()
                )
            ),
            runtime_thread_id=THREAD_ID,
        )
    assert conflict.value.code == "revision_record_conflict"

    with pytest.raises(PlanRevisionError) as malformed:
        await revisePlan(
            state(),
            service=service(store=FakeStore(override={"bad": "record"})),
            runtime_thread_id=THREAD_ID,
        )
    assert malformed.value.code == "revision_record_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["resolver", "model", "load", "record"])
async def test_cancellation_propagates(phase) -> None:
    gateway = FakeGateway()
    resolver = FakeResolver()
    store = FakeStore()
    if phase == "resolver":
        resolver.error = asyncio.CancelledError()
    elif phase == "model":
        gateway.values = [asyncio.CancelledError()]
    elif phase == "load":
        store.load_error = asyncio.CancelledError()
    else:
        store.record_error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await revisePlan(
            state(),
            service=service(
                gateway=gateway, resolver=resolver, store=store
            ),
            runtime_thread_id=THREAD_ID,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "settings",
    [
        PlanRevisionSettings(max_revision_count=1),
        PlanRevisionSettings(resolver_timeout_seconds=0),
        PlanRevisionSettings(resolver_timeout_seconds=31),
    ],
)
async def test_invalid_settings_fail_before_io(settings) -> None:
    resolver = FakeResolver()
    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            state(),
            service=service(settings=settings, resolver=resolver),
            runtime_thread_id=THREAD_ID,
        )
    assert caught.value.code == "revision_settings_incompatible"
    assert resolver.calls == []


@pytest.mark.anyio
async def test_invalid_clock_fails_before_persistence() -> None:
    store = FakeStore()
    with pytest.raises(PlanRevisionError) as caught:
        await revisePlan(
            state(),
            service=service(
                store=store,
                clock=lambda: datetime(2026, 7, 4),
            ),
            runtime_thread_id=THREAD_ID,
        )
    assert caught.value.code == "revision_clock_invalid"
    assert store.record_calls == []
