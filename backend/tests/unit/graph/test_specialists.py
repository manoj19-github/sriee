from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from jarvis.graph import (
    ApprovedSpecialistWorkflow,
    SpecialistDescriptor,
    SpecialistOutputContract,
    SpecialistResult,
    SpecialistRole,
    SpecialistScopedContext,
    SpecialistStep,
    SpecialistWorkflowDefinition,
    SpecialistWorkflowError,
    SpecialistWorkflowService,
    SpecialistWorkflowSettings,
    coordinateSpecialistWorkflow,
)
from jarvis.graph.specialists import _digest, _stable


NOW = datetime(2026, 7, 4, 16, 0, tzinfo=timezone.utc)
TASK = "tsk_" + "a" * 32
THREAD = "thr_" + "b" * 32


@pytest.fixture
def anyio_backend():
    return "asyncio"


def definition():
    return SpecialistWorkflowDefinition(
        workflow_id="wfl_workflow01",
        version="1.0.0",
        steps=(
            SpecialistStep(
                step_id="stp_research", specialist_id="agent.research",
                specialist_version="1.0.0", role="research",
                output_contract="research_evidence", depth=1,
                timeout_seconds=1,
            ),
            SpecialistStep(
                step_id="stp_review", specialist_id="agent.reviewer",
                specialist_version="1.0.0", role="reviewer",
                output_contract="review_assessment",
                depends_on=("stp_research",), depth=2, timeout_seconds=1,
            ),
        ),
    )


def approved(**changes):
    item = ApprovedSpecialistWorkflow(
        definition=definition(), definition_digest=_digest(definition()),
        actor_id="actor-001", device_id="device-001",
        approved_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=10),
    ).model_dump(mode="json")
    item.update(changes)
    return item


def context(**changes):
    item = SpecialistScopedContext(
        task_id=TASK, thread_id=THREAD, actor_id="actor-001",
        device_id="device-001",
        reference_ids=("ctx_context001", "evd_evidence01"),
    ).model_dump(mode="json")
    item.update(changes)
    return item


class Runner:
    def __init__(self, role, output, *, status="succeeded", error=None, delay=0, override=None):
        self.descriptor = SpecialistDescriptor(
            specialist_id=f"agent.{role}", version="1.0.0",
            role=role, output_contract=output,
        )
        self.status, self.error, self.delay, self.override = status, error, delay, override
        self.requests = []

    async def run(self, request):
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        if self.override is not None:
            return self.override
        return SpecialistResult(
            provenance_id=_stable("spv_", request.execution_id, request.step.step_id),
            execution_id=request.execution_id, step_id=request.step.step_id,
            specialist_id=self.descriptor.specialist_id,
            specialist_version="1.0.0", role=self.descriptor.role,
            output_contract=self.descriptor.output_contract, status=self.status,
            evidence_reference_ids=("evd_result001",) if self.status == "succeeded" else (),
            proposal_reference_ids=("prop_proposal01",) if self.status == "succeeded" else (),
            reason_codes=() if self.status == "succeeded" else ("specialist_failed",),
            started_at=NOW, completed_at=NOW,
        )


class Registry:
    def __init__(self, overrides=None, error=None):
        self.runners = {
            ("agent.research", "1.0.0"): Runner("research", "research_evidence"),
            ("agent.reviewer", "1.0.0"): Runner("reviewer", "review_assessment"),
        }
        self.runners.update(overrides or {})
        self.error = error

    def resolve(self, specialist_id, version):
        if self.error:
            raise self.error
        return self.runners.get((specialist_id, version))


def service(registry=None, settings=None, clock=None):
    return SpecialistWorkflowService(
        registry=registry or Registry(),
        settings=settings or SpecialistWorkflowSettings(),
        clock=clock or (lambda: NOW),
    )


@pytest.mark.anyio
async def test_runs_typed_handoffs_and_non_authoritative_provenance():
    registry = Registry()
    delta = await coordinateSpecialistWorkflow(
        approved(), context(), service=service(registry),
        runtime_thread_id=THREAD,
    )
    result = delta["observations"][0]
    assert result["status"] == "succeeded"
    assert result["consensus_is_evidence"] is False
    assert result["requires_standard_action_pipeline"] is True
    review_request = registry.runners[("agent.reviewer", "1.0.0")].requests[0]
    assert len(review_request.dependency_result_ids) == 1
    assert review_request.dependency_evidence_reference_ids == ("evd_result001",)
    assert review_request.context_reference_ids == ("ctx_context001", "evd_evidence01")


@pytest.mark.anyio
async def test_failed_dependency_skips_dependent_step():
    registry = Registry({
        ("agent.research", "1.0.0"): Runner(
            "research", "research_evidence", status="failed"
        )
    })
    result = (await coordinateSpecialistWorkflow(
        approved(), context(), service=service(registry),
        runtime_thread_id=THREAD,
    ))["observations"][0]
    assert result["status"] == "failed"
    assert result["step_results"][1]["status"] == "skipped"
    assert registry.runners[("agent.reviewer", "1.0.0")].requests == []


@pytest.mark.anyio
async def test_timeout_is_uncertain_and_blocks_dependency():
    registry = Registry({
        ("agent.research", "1.0.0"): Runner(
            "research", "research_evidence", delay=.2
        )
    })
    data = approved()
    data["definition"]["steps"][0]["timeout_seconds"] = .1
    data["definition_digest"] = _digest(
        SpecialistWorkflowDefinition.model_validate(data["definition"])
    )
    result = (await coordinateSpecialistWorkflow(
        data, context(), service=service(registry), runtime_thread_id=THREAD
    ))["observations"][0]
    assert result["status"] == "uncertain"
    assert result["step_results"][0]["reason_codes"] == ["specialist_timeout"]


@pytest.mark.anyio
async def test_exact_replay_returns_empty_append():
    first = await coordinateSpecialistWorkflow(
        approved(), context(), service=service(), runtime_thread_id=THREAD
    )
    replay = await coordinateSpecialistWorkflow(
        approved(), context(), service=service(), runtime_thread_id=THREAD,
        existing_observations=first["observations"],
    )
    assert replay == {"observations": []}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("workflow", "ctx", "code"),
    [
        (approved(definition_digest="0" * 64), context(), "specialist_workflow_approval_invalid"),
        (approved(expires_at=(NOW - timedelta(seconds=1)).isoformat()), context(), "specialist_workflow_approval_invalid"),
        (approved(actor_id="actor-other"), context(), "specialist_workflow_approval_invalid"),
        (approved(), context(thread_id="bad"), "specialist_workflow_contract_invalid"),
    ],
)
async def test_invalid_approval_or_context_rejected(workflow, ctx, code):
    with pytest.raises(SpecialistWorkflowError) as caught:
        await coordinateSpecialistWorkflow(
            workflow, ctx, service=service(), runtime_thread_id=THREAD
        )
    assert caught.value.code == code


@pytest.mark.anyio
async def test_forward_dependency_and_duplicate_step_rejected():
    data = approved()
    data["definition"]["steps"][0]["depends_on"] = ["stp_review"]
    data["definition_digest"] = _digest(
        SpecialistWorkflowDefinition.model_validate(data["definition"])
    )
    with pytest.raises(SpecialistWorkflowError) as caught:
        await coordinateSpecialistWorkflow(
            data, context(), service=service(), runtime_thread_id=THREAD
        )
    assert caught.value.code == "specialist_workflow_dag_invalid"


@pytest.mark.anyio
async def test_missing_or_mismatched_specialist_contract_rejected():
    for registry in (
        Registry({("agent.research", "1.0.0"): None}),
        Registry({("agent.research", "1.0.0"): Runner("reviewer", "review_assessment")}),
    ):
        with pytest.raises(SpecialistWorkflowError) as caught:
            await coordinateSpecialistWorkflow(
                approved(), context(), service=service(registry),
                runtime_thread_id=THREAD,
            )
        assert caught.value.code == "specialist_contract_invalid"


@pytest.mark.anyio
async def test_malformed_result_and_registry_failure_sanitized():
    registry = Registry({
        ("agent.research", "1.0.0"): Runner(
            "research", "research_evidence", override={"bad": "result"}
        )
    })
    with pytest.raises(SpecialistWorkflowError) as malformed:
        await coordinateSpecialistWorkflow(
            approved(), context(), service=service(registry),
            runtime_thread_id=THREAD,
        )
    assert malformed.value.code == "specialist_result_invalid"
    with pytest.raises(SpecialistWorkflowError) as unavailable:
        await coordinateSpecialistWorkflow(
            approved(), context(),
            service=service(Registry(error=RuntimeError("private"))),
            runtime_thread_id=THREAD,
        )
    assert unavailable.value.code == "specialist_registry_unavailable"
    assert "private" not in str(unavailable.value)


@pytest.mark.anyio
async def test_runner_failure_becomes_uncertain_without_leak():
    registry = Registry({
        ("agent.research", "1.0.0"): Runner(
            "research", "research_evidence", error=RuntimeError("private")
        )
    })
    result = (await coordinateSpecialistWorkflow(
        approved(), context(), service=service(registry),
        runtime_thread_id=THREAD,
    ))["observations"][0]
    assert result["status"] == "uncertain"
    assert "private" not in str(result)


@pytest.mark.anyio
async def test_cancellation_propagates():
    registry = Registry({
        ("agent.research", "1.0.0"): Runner(
            "research", "research_evidence", error=asyncio.CancelledError()
        )
    })
    with pytest.raises(asyncio.CancelledError):
        await coordinateSpecialistWorkflow(
            approved(), context(), service=service(registry),
            runtime_thread_id=THREAD,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "settings",
    [
        SpecialistWorkflowSettings(max_steps=0),
        SpecialistWorkflowSettings(max_depth=1),
        SpecialistWorkflowSettings(max_concurrency=0),
        SpecialistWorkflowSettings(max_concurrency=9),
    ],
)
async def test_invalid_settings_rejected(settings):
    with pytest.raises(SpecialistWorkflowError) as caught:
        await coordinateSpecialistWorkflow(
            approved(), context(), service=service(settings=settings),
            runtime_thread_id=THREAD,
        )
    assert caught.value.code == "specialist_workflow_settings_invalid"


@pytest.mark.anyio
async def test_invalid_clock_and_replay_rejected():
    with pytest.raises(SpecialistWorkflowError) as clock:
        await coordinateSpecialistWorkflow(
            approved(), context(),
            service=service(clock=lambda: datetime(2026, 7, 4)),
            runtime_thread_id=THREAD,
        )
    assert clock.value.code == "specialist_workflow_clock_invalid"
    with pytest.raises(SpecialistWorkflowError) as replay:
        await coordinateSpecialistWorkflow(
            approved(), context(), service=service(),
            runtime_thread_id=THREAD,
            existing_observations=[{
                "execution_id": _stable(
                    "swf_", TASK, THREAD, "wfl_workflow01", _digest(definition())
                )
            }],
        )
    assert replay.value.code == "specialist_workflow_replay_invalid"
