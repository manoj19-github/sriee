"""Bounded specialist workflow coordination for Global ID 120016."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)


WORKFLOW_ID_PATTERN = re.compile(r"^wfl_[A-Za-z0-9_-]{8,128}$")
STEP_ID_PATTERN = re.compile(r"^stp_[a-z0-9_]{3,63}$")
SPECIALIST_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
PROVENANCE_ID_PATTERN = re.compile(r"^spv_[0-9a-f]{24}$")
EXECUTION_ID_PATTERN = re.compile(r"^swf_[0-9a-f]{24}$")
OPAQUE_REF_PATTERN = re.compile(
    r"^(ctx|evd|art|prj|mem|pol|cap|rfc|prop)_[A-Za-z0-9_-]{8,128}$"
)
REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


class SpecialistWorkflowError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS specialist workflow failed: {code}")


class SpecialistRole(StrEnum):
    PLANNER = "planner"
    RESEARCH = "research"
    CODER = "coder"
    REVIEWER = "reviewer"
    SECURITY = "security"
    VERIFIER = "verifier"


class SpecialistOutputContract(StrEnum):
    PLAN_PROPOSAL = "plan_proposal"
    RESEARCH_EVIDENCE = "research_evidence"
    CODE_PROPOSAL = "code_proposal"
    REVIEW_ASSESSMENT = "review_assessment"
    SECURITY_ASSESSMENT = "security_assessment"
    VERIFICATION_ASSESSMENT = "verification_assessment"


class SpecialistStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str = Field(pattern=STEP_ID_PATTERN.pattern)
    specialist_id: str = Field(pattern=SPECIALIST_ID_PATTERN.pattern)
    specialist_version: str = Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")
    role: SpecialistRole
    output_contract: SpecialistOutputContract
    depends_on: tuple[str, ...] = Field(default=(), max_length=4)
    depth: int = Field(ge=1, le=2)
    timeout_seconds: float = Field(ge=0.1, le=60)
    side_effects_allowed: Literal[False] = False
    delegation_allowed: Literal[False] = False


class SpecialistWorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str = Field(pattern=WORKFLOW_ID_PATTERN.pattern)
    version: str = Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")
    steps: tuple[SpecialistStep, ...] = Field(min_length=1, max_length=8)


class ApprovedSpecialistWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    definition: SpecialistWorkflowDefinition
    definition_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    approved: Literal[True] = True
    approved_at: datetime
    expires_at: datetime


class SpecialistScopedContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    reference_ids: tuple[str, ...] = Field(default=(), max_length=32)

    @field_validator("reference_ids")
    @classmethod
    def refs(cls, value):
        if len(value) != len(set(value)) or any(
            not OPAQUE_REF_PATTERN.fullmatch(item) for item in value
        ):
            raise ValueError("scoped references invalid")
        return value


class SpecialistDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    specialist_id: str = Field(pattern=SPECIALIST_ID_PATTERN.pattern)
    version: str = Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")
    role: SpecialistRole
    output_contract: SpecialistOutputContract
    read_only: Literal[True] = True
    may_delegate: Literal[False] = False


class SpecialistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str = Field(pattern=EXECUTION_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    step: SpecialistStep
    context_reference_ids: tuple[str, ...]
    dependency_result_ids: tuple[str, ...] = ()
    dependency_evidence_reference_ids: tuple[str, ...] = ()
    started_at: datetime


class SpecialistResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_id: str = Field(pattern=PROVENANCE_ID_PATTERN.pattern)
    execution_id: str = Field(pattern=EXECUTION_ID_PATTERN.pattern)
    step_id: str = Field(pattern=STEP_ID_PATTERN.pattern)
    specialist_id: str = Field(pattern=SPECIALIST_ID_PATTERN.pattern)
    specialist_version: str
    role: SpecialistRole
    output_contract: SpecialistOutputContract
    status: Literal["succeeded", "failed", "uncertain", "skipped"]
    evidence_reference_ids: tuple[str, ...] = Field(default=(), max_length=16)
    proposal_reference_ids: tuple[str, ...] = Field(default=(), max_length=8)
    reason_codes: tuple[str, ...] = Field(default=(), max_length=8)
    started_at: datetime
    completed_at: datetime


class SpecialistRunner(Protocol):
    descriptor: SpecialistDescriptor

    async def run(self, request: SpecialistRequest) -> SpecialistResult: ...


class SpecialistRegistry(Protocol):
    def resolve(self, specialist_id: str, version: str) -> SpecialistRunner | None: ...


class SpecialistWorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["specialist.workflow_result"] = "specialist.workflow_result"
    version: Literal["1.0"] = "1.0"
    execution_id: str = Field(pattern=EXECUTION_ID_PATTERN.pattern)
    workflow_id: str = Field(pattern=WORKFLOW_ID_PATTERN.pattern)
    workflow_version: str
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    status: Literal["succeeded", "partially_succeeded", "failed", "uncertain"]
    step_results: tuple[SpecialistResult, ...]
    consensus_is_evidence: Literal[False] = False
    requires_standard_action_pipeline: Literal[True] = True
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class SpecialistWorkflowSettings:
    max_steps: int = 8
    max_depth: int = 2
    max_concurrency: int = 4


def _utc_now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SpecialistWorkflowService:
    registry: SpecialistRegistry
    settings: SpecialistWorkflowSettings = SpecialistWorkflowSettings()
    clock: Callable[[], datetime] = _utc_now


def _digest(definition: SpecialistWorkflowDefinition) -> str:
    value = json.dumps(
        definition.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(value.encode()).hexdigest()


def _validate(approved, context, settings, runtime_thread_id, now):
    try:
        approved = ApprovedSpecialistWorkflow.model_validate(approved)
        context = SpecialistScopedContext.model_validate(context)
    except ValidationError:
        raise SpecialistWorkflowError("specialist_workflow_contract_invalid") from None
    steps = approved.definition.steps
    if (
        approved.definition_digest != _digest(approved.definition)
        or approved.actor_id != context.actor_id
        or approved.device_id != context.device_id
        or runtime_thread_id != context.thread_id
        or approved.approved_at.utcoffset() is None
        or approved.expires_at.utcoffset() is None
        or not (approved.approved_at <= now < approved.expires_at)
        or len(steps) > settings.max_steps
        or max(item.depth for item in steps) > settings.max_depth
    ):
        raise SpecialistWorkflowError("specialist_workflow_approval_invalid")
    seen = set()
    depth = {}
    for step in steps:
        if (
            step.step_id in seen
            or len(step.depends_on) != len(set(step.depends_on))
            or not set(step.depends_on).issubset(seen)
            or (
                step.depends_on
                and step.depth < max(depth[item] for item in step.depends_on)
            )
        ):
            raise SpecialistWorkflowError("specialist_workflow_dag_invalid")
        seen.add(step.step_id)
        depth[step.step_id] = step.depth
    return approved, context


def _stable(prefix, *parts):
    return prefix + hashlib.sha256(":".join(parts).encode()).hexdigest()[:24]


async def coordinateSpecialistWorkflow(
    approved_workflow: object,
    scoped_context: object,
    *,
    service: SpecialistWorkflowService,
    runtime_thread_id: str,
    existing_observations: Sequence[object] = (),
) -> dict[str, Any]:
    """Run an approved read-only specialist DAG and append typed provenance."""

    settings = service.settings
    if (
        settings.max_steps < 1 or settings.max_steps > 8
        or settings.max_depth != 2
        or settings.max_concurrency < 1 or settings.max_concurrency > 8
    ):
        raise SpecialistWorkflowError("specialist_workflow_settings_invalid")
    now = service.clock()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise SpecialistWorkflowError("specialist_workflow_clock_invalid")
    approved, context = _validate(
        approved_workflow, scoped_context, settings, runtime_thread_id, now
    )
    execution_id = _stable(
        "swf_", context.task_id, context.thread_id,
        approved.definition.workflow_id, approved.definition_digest,
    )
    for raw in existing_observations:
        if isinstance(raw, Mapping) and raw.get("execution_id") == execution_id:
            try:
                SpecialistWorkflowResult.model_validate(raw)
            except ValidationError:
                raise SpecialistWorkflowError("specialist_workflow_replay_invalid") from None
            return {"observations": []}
    semaphore = asyncio.Semaphore(settings.max_concurrency)
    results = {}
    started = now
    for step in approved.definition.steps:
        dependencies = [results[item] for item in step.depends_on]
        if any(item.status != "succeeded" for item in dependencies):
            result = SpecialistResult(
                provenance_id=_stable("spv_", execution_id, step.step_id),
                execution_id=execution_id, step_id=step.step_id,
                specialist_id=step.specialist_id,
                specialist_version=step.specialist_version, role=step.role,
                output_contract=step.output_contract, status="skipped",
                reason_codes=("dependency_unsatisfied",),
                started_at=now, completed_at=now,
            )
            results[step.step_id] = result
            continue
        try:
            runner = service.registry.resolve(
                step.specialist_id, step.specialist_version
            )
        except Exception:
            raise SpecialistWorkflowError("specialist_registry_unavailable") from None
        descriptor = getattr(runner, "descriptor", None) if runner else None
        if (
            not isinstance(descriptor, SpecialistDescriptor)
            or descriptor.specialist_id != step.specialist_id
            or descriptor.version != step.specialist_version
            or descriptor.role is not step.role
            or descriptor.output_contract is not step.output_contract
        ):
            raise SpecialistWorkflowError("specialist_contract_invalid")
        request = SpecialistRequest(
            execution_id=execution_id, task_id=context.task_id,
            thread_id=context.thread_id, step=step,
            context_reference_ids=context.reference_ids,
            dependency_result_ids=tuple(item.provenance_id for item in dependencies),
            dependency_evidence_reference_ids=tuple(sorted({
                ref for item in dependencies for ref in item.evidence_reference_ids
            })),
            started_at=now,
        )
        try:
            async with semaphore:
                raw = await asyncio.wait_for(
                    runner.run(request), timeout=step.timeout_seconds
                )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raw = SpecialistResult(
                provenance_id=_stable("spv_", execution_id, step.step_id),
                execution_id=execution_id, step_id=step.step_id,
                specialist_id=step.specialist_id,
                specialist_version=step.specialist_version, role=step.role,
                output_contract=step.output_contract, status="uncertain",
                reason_codes=("specialist_timeout",),
                started_at=now, completed_at=now,
            )
        except Exception:
            raw = SpecialistResult(
                provenance_id=_stable("spv_", execution_id, step.step_id),
                execution_id=execution_id, step_id=step.step_id,
                specialist_id=step.specialist_id,
                specialist_version=step.specialist_version, role=step.role,
                output_contract=step.output_contract, status="uncertain",
                reason_codes=("specialist_unavailable",),
                started_at=now, completed_at=now,
            )
        if not isinstance(raw, SpecialistResult):
            raise SpecialistWorkflowError("specialist_result_invalid")
        try:
            result = SpecialistResult.model_validate(raw.model_dump(mode="json"))
        except Exception:
            raise SpecialistWorkflowError("specialist_result_invalid") from None
        if (
            result.provenance_id != _stable("spv_", execution_id, step.step_id)
            or result.execution_id != execution_id
            or result.step_id != step.step_id
            or result.specialist_id != step.specialist_id
            or result.specialist_version != step.specialist_version
            or result.role is not step.role
            or result.output_contract is not step.output_contract
            or result.started_at.utcoffset() is None
            or result.completed_at.utcoffset() is None
            or result.completed_at < result.started_at
            or len(result.evidence_reference_ids) != len(set(result.evidence_reference_ids))
            or len(result.proposal_reference_ids) != len(set(result.proposal_reference_ids))
            or any(not OPAQUE_REF_PATTERN.fullmatch(x) for x in (
                *result.evidence_reference_ids, *result.proposal_reference_ids
            ))
            or any(not REASON_PATTERN.fullmatch(x) for x in result.reason_codes)
        ):
            raise SpecialistWorkflowError("specialist_result_invalid")
        results[step.step_id] = result
    completed = service.clock()
    if not isinstance(completed, datetime) or completed.tzinfo is None or completed < started:
        raise SpecialistWorkflowError("specialist_workflow_clock_invalid")
    statuses = {item.status for item in results.values()}
    status = (
        "succeeded" if statuses == {"succeeded"}
        else "uncertain" if "uncertain" in statuses
        else "partially_succeeded" if "succeeded" in statuses
        else "failed"
    )
    outcome = SpecialistWorkflowResult(
        execution_id=execution_id,
        workflow_id=approved.definition.workflow_id,
        workflow_version=approved.definition.version,
        task_id=context.task_id, thread_id=context.thread_id,
        status=status,
        step_results=tuple(results[item.step_id] for item in approved.definition.steps),
        started_at=started, completed_at=completed,
    )
    return {"observations": [outcome.model_dump(mode="json")]}
