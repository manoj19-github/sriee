"""Independent postcondition verification for Global ID 120011."""

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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from jarvis.graph.context import REFERENCE_VERSION_PATTERN
from jarvis.graph.dispatch import RECEIPT_ID_PATTERN, PriorActionResult
from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)
from jarvis.graph.plan import (
    CAPABILITY_ID_PATTERN,
    RESOURCE_ID_PATTERN,
    VERIFICATION_CODE_PATTERN,
    PlanActionDraft,
    PlanArgument,
    PlanDraft,
    PlanSuccessCriterion,
)


VERIFICATION_ID_PATTERN = re.compile(r"^vrf_[0-9a-f]{24}$")
OBSERVATION_ID_PATTERN = re.compile(r"^obs_[0-9a-f]{24}$")
EVIDENCE_ID_PATTERN = re.compile(r"^evd_[A-Za-z0-9_-]{8,128}$")
PROBE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
VERIFICATION_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
VERIFICATION_VERSION = "1.0"


class VerificationError(RuntimeError):
    """A content-free verification failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS outcome verification failed: {code}")


class VerificationStoreConflictError(RuntimeError):
    """A different immutable verification already owns this identity."""


class CriterionVerdict(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class VerifiedOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class VerificationProbeDescriptor(BaseModel):
    """Trusted registry metadata for one independent read-only probe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_id: str = Field(pattern=PROBE_ID_PATTERN.pattern)
    capability_id: str = Field(pattern=CAPABILITY_ID_PATTERN.pattern)
    capability_version: str = Field(
        pattern=REFERENCE_VERSION_PATTERN.pattern
    )
    verification_code: str = Field(
        pattern=VERIFICATION_CODE_PATTERN.pattern
    )
    read_only: Literal[True] = True


class VerificationProbeRequest(BaseModel):
    """Bounded receipt/resource input for one independent postcondition read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verification_id: str = Field(pattern=VERIFICATION_ID_PATTERN.pattern)
    criterion_id: str = Field(pattern=r"^crt_[0-9a-f]{24}$")
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    capability_id: str = Field(pattern=CAPABILITY_ID_PATTERN.pattern)
    capability_version: str = Field(
        pattern=REFERENCE_VERSION_PATTERN.pattern
    )
    verification_code: str = Field(
        pattern=VERIFICATION_CODE_PATTERN.pattern
    )
    receipt_id: str = Field(pattern=RECEIPT_ID_PATTERN.pattern)
    arguments: tuple[PlanArgument, ...] = Field(
        default=(),
        max_length=12,
    )
    resource_ids: tuple[str, ...] = Field(default=(), max_length=12)
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("verification request time must be aware")
        return value

    @model_validator(mode="after")
    def validate_members(self) -> VerificationProbeRequest:
        names = [item.name for item in self.arguments]
        if (
            len(names) != len(set(names))
            or len(self.resource_ids) != len(set(self.resource_ids))
            or any(
                not RESOURCE_ID_PATTERN.fullmatch(item)
                for item in self.resource_ids
            )
        ):
            raise ValueError("verification request members are invalid")
        return self


class VerificationProbeResult(BaseModel):
    """Typed evidence returned by an independent read path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["independent_read"] = "independent_read"
    read_only: Literal[True] = True
    probe_id: str = Field(pattern=PROBE_ID_PATTERN.pattern)
    verification_id: str = Field(pattern=VERIFICATION_ID_PATTERN.pattern)
    criterion_id: str = Field(pattern=r"^crt_[0-9a-f]{24}$")
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    receipt_id: str = Field(pattern=RECEIPT_ID_PATTERN.pattern)
    verdict: CriterionVerdict
    evidence_reference_ids: tuple[str, ...] = Field(
        default=(),
        max_length=8,
    )
    reason_code: str | None = Field(
        default=None,
        pattern=VERIFICATION_REASON_PATTERN.pattern,
    )
    retryable: bool = False
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("verification observation time must be aware")
        return value

    @model_validator(mode="after")
    def validate_result(self) -> VerificationProbeResult:
        evidence = self.evidence_reference_ids
        if (
            len(evidence) != len(set(evidence))
            or any(
                not EVIDENCE_ID_PATTERN.fullmatch(item)
                for item in evidence
            )
            or (
                self.verdict is CriterionVerdict.PASSED
                and (
                    not evidence
                    or self.reason_code is not None
                    or self.retryable
                )
            )
            or (
                self.verdict is CriterionVerdict.FAILED
                and (not evidence or self.reason_code is None)
            )
            or (
                self.verdict is CriterionVerdict.UNCERTAIN
                and self.reason_code is None
            )
        ):
            raise ValueError("verification probe result is invalid")
        return self


class ReadOnlyVerificationProbe(Protocol):
    descriptor: VerificationProbeDescriptor

    async def verify(
        self,
        request: VerificationProbeRequest,
    ) -> VerificationProbeResult:
        """Read an independent postcondition without causing a side effect."""


class VerificationProbeRegistry(Protocol):
    def resolve_probe(
        self,
        verification_code: str,
        *,
        capability_id: str,
        capability_version: str,
    ) -> ReadOnlyVerificationProbe | None:
        """Resolve an exact capability/version-bound read-only probe."""


class CriterionObservation(BaseModel):
    """Checkpoint-safe evidence for one plan success criterion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["verification.criterion"] = "verification.criterion"
    version: Literal["1.0"] = VERIFICATION_VERSION
    observation_id: str = Field(pattern=OBSERVATION_ID_PATTERN.pattern)
    verification_id: str = Field(pattern=VERIFICATION_ID_PATTERN.pattern)
    criterion_id: str = Field(pattern=r"^crt_[0-9a-f]{24}$")
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    receipt_id: str | None = Field(
        default=None,
        pattern=RECEIPT_ID_PATTERN.pattern,
    )
    verification_code: str = Field(
        pattern=VERIFICATION_CODE_PATTERN.pattern
    )
    probe_id: str = Field(pattern=PROBE_ID_PATTERN.pattern)
    verdict: CriterionVerdict
    evidence_reference_ids: tuple[str, ...] = Field(
        default=(),
        max_length=8,
    )
    reason_code: str | None = Field(
        default=None,
        pattern=VERIFICATION_REASON_PATTERN.pattern,
    )
    retryable: bool
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("criterion observation time must be aware")
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> CriterionObservation:
        evidence = self.evidence_reference_ids
        is_system = self.probe_id == "system.verification"
        if (
            len(evidence) != len(set(evidence))
            or any(
                not EVIDENCE_ID_PATTERN.fullmatch(item)
                for item in evidence
            )
            or (
                self.verdict is CriterionVerdict.PASSED
                and (
                    not evidence
                    or self.reason_code is not None
                    or self.retryable
                )
            )
            or (
                self.verdict is CriterionVerdict.FAILED
                and (not evidence or self.reason_code is None)
            )
            or (
                self.verdict is CriterionVerdict.UNCERTAIN
                and self.reason_code is None
            )
            or (
                is_system
                and (
                    self.verdict is not CriterionVerdict.UNCERTAIN
                    or self.evidence_reference_ids
                    or self.reason_code
                    not in {
                        "action_result_missing",
                        "probe_timeout",
                        "probe_unavailable",
                    }
                    or not self.retryable
                )
            )
            or (not is_system and self.receipt_id is None)
        ):
            raise ValueError("criterion evidence is invalid")
        return self


class OutcomeVerification(BaseModel):
    """Aggregate deterministic outcome retained as graph evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["outcome.verification"] = "outcome.verification"
    version: Literal["1.0"] = VERIFICATION_VERSION
    verification_id: str = Field(pattern=VERIFICATION_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    revision: int = Field(ge=0, le=2)
    outcome: VerifiedOutcome
    recoverable: bool
    criterion_count: int = Field(ge=1, le=16)
    passed_count: int = Field(ge=0, le=16)
    failed_count: int = Field(ge=0, le=16)
    uncertain_count: int = Field(ge=0, le=16)
    action_count: int = Field(ge=1, le=8)
    action_result_count: int = Field(ge=0, le=8)
    verified_at: datetime

    @field_validator("verified_at")
    @classmethod
    def validate_verified_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("outcome verification time must be aware")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> OutcomeVerification:
        if (
            self.passed_count
            + self.failed_count
            + self.uncertain_count
            != self.criterion_count
            or self.action_result_count > self.action_count
            or (self.outcome is VerifiedOutcome.SUCCEEDED and self.recoverable)
        ):
            raise ValueError("outcome verification counts are invalid")
        return self


class VerificationPersistenceRequest(BaseModel):
    """Identity-bound immutable verification payload for atomic persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    criterion_observations: tuple[CriterionObservation, ...] = Field(
        min_length=1,
        max_length=16,
    )
    outcome: OutcomeVerification


class VerificationRecord(BaseModel):
    """Authoritative persisted verification record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: VerificationPersistenceRequest
    stored_at: datetime
    created: bool

    @field_validator("stored_at")
    @classmethod
    def validate_stored_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("verification storage time must be aware")
        return value

    @model_validator(mode="after")
    def validate_record(self) -> VerificationRecord:
        if self.stored_at < self.request.outcome.verified_at:
            raise ValueError("verification record time is invalid")
        return self


class VerificationStore(Protocol):
    async def load_verification(
        self,
        verification_id: str,
        *,
        actor_id: str,
        device_id: str,
    ) -> VerificationRecord | None:
        """Load an existing actor/device-owned immutable verification."""

    async def record_or_get_verification(
        self,
        request: VerificationPersistenceRequest,
    ) -> VerificationRecord:
        """Atomically persist once or return the existing verification."""


@dataclass(frozen=True, slots=True)
class VerificationSettings:
    probe_timeout_seconds: float = 5.0
    max_concurrency: int = 4
    max_revision_count: int = 2


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class VerificationService:
    registry: VerificationProbeRegistry
    store: VerificationStore
    settings: VerificationSettings = VerificationSettings()
    clock: Callable[[], datetime] = _utc_now


def _validate_settings(settings: VerificationSettings) -> None:
    if (
        settings.probe_timeout_seconds <= 0
        or settings.probe_timeout_seconds > 30
        or settings.max_concurrency < 1
        or settings.max_concurrency > 16
        or settings.max_revision_count < 0
        or settings.max_revision_count > 2
    ):
        raise VerificationError("verification_settings_incompatible")


def _aware_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise VerificationError("verification_clock_invalid")
    return value


def _verification_id(
    task_id: str,
    thread_id: str,
    revision: int,
    plan: PlanDraft,
) -> str:
    canonical = json.dumps(
        plan.model_dump(mode="json"),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    seed = f"{task_id}:{thread_id}:{revision}:{canonical}".encode()
    return "vrf_" + hashlib.sha256(seed).hexdigest()[:24]


def _observation_id(verification_id: str, criterion_id: str) -> str:
    seed = f"{verification_id}:{criterion_id}".encode()
    return "obs_" + hashlib.sha256(seed).hexdigest()[:24]


def _load_state(
    state: Mapping[str, Any],
    *,
    runtime_thread_id: str,
    max_revision_count: int,
) -> tuple[
    str,
    str,
    str,
    str,
    int,
    PlanDraft,
    tuple[PriorActionResult, ...],
    Sequence[object],
]:
    if state.get("status") != "verifying":
        raise VerificationError("verification_state_invalid")
    task_id = state.get("task_id")
    thread_id = state.get("thread_id")
    actor_id = state.get("actor_id")
    device_id = state.get("device_id")
    revision = state.get("revision_count")
    if (
        not isinstance(task_id, str)
        or not TASK_ID_PATTERN.fullmatch(task_id)
        or not isinstance(thread_id, str)
        or not THREAD_ID_PATTERN.fullmatch(thread_id)
        or not isinstance(runtime_thread_id, str)
        or not THREAD_ID_PATTERN.fullmatch(runtime_thread_id)
        or runtime_thread_id != thread_id
        or not isinstance(actor_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(actor_id)
        or not isinstance(device_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(device_id)
        or type(revision) is not int
        or revision < 0
        or revision > max_revision_count
    ):
        raise VerificationError("verification_identity_invalid")
    try:
        plan = PlanDraft.model_validate(state.get("plan"))
        results = tuple(
            PriorActionResult.model_validate(item)
            for item in state.get("action_results", ())
        )
    except (ValidationError, TypeError, ValueError):
        raise VerificationError("verification_contract_invalid") from None
    raw_observations = state.get("observations", ())
    if not isinstance(raw_observations, Sequence) or isinstance(
        raw_observations,
        (str, bytes, bytearray),
    ):
        raise VerificationError("verification_contract_invalid")
    action_ids = tuple(action.action_id for action in plan.actions)
    result_ids = tuple(item.action_id for item in results)
    if (
        plan.schema_version != "1.0"
        or not action_ids
        or len(action_ids) != len(set(action_ids))
        or len(result_ids) != len(set(result_ids))
        or not set(result_ids).issubset(action_ids)
    ):
        raise VerificationError("verification_contract_invalid")
    return (
        task_id,
        thread_id,
        actor_id,
        device_id,
        revision,
        plan,
        results,
        raw_observations,
    )


def _status_for(outcome: OutcomeVerification) -> str:
    if outcome.recoverable:
        return "planning"
    if outcome.outcome is VerifiedOutcome.SUCCEEDED:
        return "succeeded"
    if outcome.outcome is VerifiedOutcome.PARTIALLY_SUCCEEDED:
        return "partially_succeeded"
    return "failed"


def _validate_checkpoint_replay(
    raw_observations: Sequence[object],
    *,
    verification_id: str,
    task_id: str,
    thread_id: str,
    revision: int,
    plan: PlanDraft,
    results: tuple[PriorActionResult, ...],
    max_revision_count: int,
) -> OutcomeVerification | None:
    criteria: list[CriterionObservation] = []
    aggregate: OutcomeVerification | None = None
    for raw in raw_observations:
        if not isinstance(raw, Mapping):
            continue
        raw_type = raw.get("type")
        if raw_type == "verification.criterion" and raw.get(
            "verification_id"
        ) == verification_id:
            try:
                criteria.append(CriterionObservation.model_validate(raw))
            except ValidationError:
                raise VerificationError(
                    "verification_checkpoint_invalid"
                ) from None
        elif raw_type == "outcome.verification" and raw.get(
            "verification_id"
        ) == verification_id:
            if aggregate is not None:
                raise VerificationError("verification_checkpoint_invalid")
            try:
                aggregate = OutcomeVerification.model_validate(raw)
            except ValidationError:
                raise VerificationError(
                    "verification_checkpoint_invalid"
                ) from None
    if aggregate is None:
        if criteria:
            raise VerificationError("verification_checkpoint_invalid")
        return None
    expected_criteria = {
        criterion.criterion_id for criterion in plan.success_criteria
    }
    if (
        aggregate.task_id != task_id
        or aggregate.thread_id != thread_id
        or aggregate.revision != revision
        or aggregate.criterion_count != len(expected_criteria)
        or aggregate.action_count != len(plan.actions)
        or aggregate.action_result_count != len(results)
        or len(criteria) != len(expected_criteria)
        or {item.criterion_id for item in criteria} != expected_criteria
        or any(item.verification_id != verification_id for item in criteria)
    ):
        raise VerificationError("verification_checkpoint_invalid")
    try:
        _validate_verification_semantics(
            aggregate,
            tuple(criteria),
            plan=plan,
            results=results,
            max_revision_count=max_revision_count,
        )
    except VerificationError:
        raise VerificationError("verification_checkpoint_invalid") from None
    return aggregate


def _resource_ids(action: PlanActionDraft) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                argument.value
                for argument in action.arguments
                if isinstance(argument.value, str)
                and RESOURCE_ID_PATTERN.fullmatch(argument.value)
            }
        )
    )


def _system_observation(
    *,
    verification_id: str,
    criterion: PlanSuccessCriterion,
    receipt_id: str | None,
    reason_code: str,
    observed_at: datetime,
) -> CriterionObservation:
    return CriterionObservation(
        observation_id=_observation_id(
            verification_id,
            criterion.criterion_id,
        ),
        verification_id=verification_id,
        criterion_id=criterion.criterion_id,
        action_id=criterion.action_id,
        receipt_id=receipt_id,
        verification_code=criterion.verification_code,
        probe_id="system.verification",
        verdict=CriterionVerdict.UNCERTAIN,
        evidence_reference_ids=(),
        reason_code=reason_code,
        retryable=True,
        observed_at=observed_at,
    )


async def _run_criterion(
    *,
    verification_id: str,
    task_id: str,
    thread_id: str,
    actor_id: str,
    device_id: str,
    criterion: PlanSuccessCriterion,
    action: PlanActionDraft,
    result: PriorActionResult | None,
    registry: VerificationProbeRegistry,
    timeout: float,
    semaphore: asyncio.Semaphore,
    requested_at: datetime,
) -> CriterionObservation:
    if result is None:
        return _system_observation(
            verification_id=verification_id,
            criterion=criterion,
            receipt_id=None,
            reason_code="action_result_missing",
            observed_at=requested_at,
        )
    try:
        probe = registry.resolve_probe(
            criterion.verification_code,
            capability_id=action.capability_id,
            capability_version=action.capability_version,
        )
    except Exception:
        raise VerificationError("verification_registry_unavailable") from None
    if probe is None:
        return _system_observation(
            verification_id=verification_id,
            criterion=criterion,
            receipt_id=result.receipt_id,
            reason_code="probe_unavailable",
            observed_at=requested_at,
        )
    descriptor = getattr(probe, "descriptor", None)
    if (
        not isinstance(descriptor, VerificationProbeDescriptor)
        or descriptor.capability_id != action.capability_id
        or descriptor.capability_version != action.capability_version
        or descriptor.verification_code != criterion.verification_code
        or descriptor.read_only is not True
    ):
        raise VerificationError("verification_probe_invalid")
    request = VerificationProbeRequest(
        verification_id=verification_id,
        criterion_id=criterion.criterion_id,
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        action_id=action.action_id,
        capability_id=action.capability_id,
        capability_version=action.capability_version,
        verification_code=criterion.verification_code,
        receipt_id=result.receipt_id,
        arguments=action.arguments,
        resource_ids=_resource_ids(action),
        requested_at=requested_at,
    )
    try:
        async with semaphore:
            raw_result = await asyncio.wait_for(
                probe.verify(request),
                timeout=timeout,
            )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        return _system_observation(
            verification_id=verification_id,
            criterion=criterion,
            receipt_id=result.receipt_id,
            reason_code="probe_timeout",
            observed_at=requested_at,
        )
    except Exception:
        return _system_observation(
            verification_id=verification_id,
            criterion=criterion,
            receipt_id=result.receipt_id,
            reason_code="probe_unavailable",
            observed_at=requested_at,
        )
    if not isinstance(raw_result, VerificationProbeResult):
        raise VerificationError("verification_probe_invalid")
    try:
        probe_result = VerificationProbeResult.model_validate(
            raw_result.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise VerificationError("verification_probe_invalid") from None
    if (
        probe_result.probe_id != descriptor.probe_id
        or probe_result.verification_id != verification_id
        or probe_result.criterion_id != criterion.criterion_id
        or probe_result.action_id != action.action_id
        or probe_result.receipt_id != result.receipt_id
        or probe_result.observed_at < requested_at
        or probe_result.observed_at < result.completed_at
    ):
        raise VerificationError("verification_probe_invalid")
    return CriterionObservation(
        observation_id=_observation_id(
            verification_id,
            criterion.criterion_id,
        ),
        verification_id=verification_id,
        criterion_id=criterion.criterion_id,
        action_id=action.action_id,
        receipt_id=result.receipt_id,
        verification_code=criterion.verification_code,
        probe_id=probe_result.probe_id,
        verdict=probe_result.verdict,
        evidence_reference_ids=probe_result.evidence_reference_ids,
        reason_code=probe_result.reason_code,
        retryable=probe_result.retryable,
        observed_at=probe_result.observed_at,
    )


def _classify_outcome(
    observations: tuple[CriterionObservation, ...],
) -> VerifiedOutcome:
    verdicts = {item.verdict for item in observations}
    if verdicts == {CriterionVerdict.PASSED}:
        return VerifiedOutcome.SUCCEEDED
    if CriterionVerdict.UNCERTAIN in verdicts:
        return VerifiedOutcome.UNCERTAIN
    if CriterionVerdict.PASSED in verdicts:
        return VerifiedOutcome.PARTIALLY_SUCCEEDED
    return VerifiedOutcome.FAILED


def _validate_verification_semantics(
    aggregate: OutcomeVerification,
    observations: tuple[CriterionObservation, ...],
    *,
    plan: PlanDraft,
    results: tuple[PriorActionResult, ...],
    max_revision_count: int,
) -> None:
    expected = {
        criterion.criterion_id: criterion
        for criterion in plan.success_criteria
    }
    result_by_action = {item.action_id: item for item in results}
    issues = [
        item
        for item in observations
        if item.verdict is not CriterionVerdict.PASSED
    ]
    expected_recoverable = (
        bool(issues)
        and all(item.retryable for item in issues)
        and aggregate.revision < max_revision_count
    )
    if (
        len(observations) != len(expected)
        or {item.criterion_id for item in observations} != set(expected)
        or any(
            item.verification_id != aggregate.verification_id
            or item.observation_id
            != _observation_id(
                aggregate.verification_id,
                item.criterion_id,
            )
            or item.action_id != expected[item.criterion_id].action_id
            or item.verification_code
            != expected[item.criterion_id].verification_code
            or (
                item.action_id in result_by_action
                and item.receipt_id
                != result_by_action[item.action_id].receipt_id
            )
            or (
                item.action_id not in result_by_action
                and (
                    item.receipt_id is not None
                    or item.probe_id != "system.verification"
                    or item.reason_code != "action_result_missing"
                )
            )
            for item in observations
        )
        or aggregate.criterion_count != len(observations)
        or aggregate.action_count != len(plan.actions)
        or aggregate.action_result_count != len(results)
        or aggregate.outcome is not _classify_outcome(observations)
        or aggregate.recoverable != expected_recoverable
        or aggregate.passed_count
        != sum(
            item.verdict is CriterionVerdict.PASSED
            for item in observations
        )
        or aggregate.failed_count
        != sum(
            item.verdict is CriterionVerdict.FAILED
            for item in observations
        )
        or aggregate.uncertain_count
        != sum(
            item.verdict is CriterionVerdict.UNCERTAIN
            for item in observations
        )
        or any(
            item.observed_at > aggregate.verified_at
            for item in observations
        )
    ):
        raise VerificationError("verification_record_invalid")


def _aggregate(
    *,
    verification_id: str,
    task_id: str,
    thread_id: str,
    revision: int,
    plan: PlanDraft,
    result_count: int,
    observations: tuple[CriterionObservation, ...],
    max_revision_count: int,
    verified_at: datetime,
) -> OutcomeVerification:
    outcome = _classify_outcome(observations)
    issues = [
        item
        for item in observations
        if item.verdict is not CriterionVerdict.PASSED
    ]
    recoverable = (
        bool(issues)
        and all(item.retryable for item in issues)
        and revision < max_revision_count
    )
    return OutcomeVerification(
        verification_id=verification_id,
        task_id=task_id,
        thread_id=thread_id,
        revision=revision,
        outcome=outcome,
        recoverable=recoverable,
        criterion_count=len(observations),
        passed_count=sum(
            item.verdict is CriterionVerdict.PASSED
            for item in observations
        ),
        failed_count=sum(
            item.verdict is CriterionVerdict.FAILED
            for item in observations
        ),
        uncertain_count=sum(
            item.verdict is CriterionVerdict.UNCERTAIN
            for item in observations
        ),
        action_count=len(plan.actions),
        action_result_count=result_count,
        verified_at=verified_at,
    )


def _validate_record(
    value: object,
    *,
    verification_id: str,
    actor_id: str,
    device_id: str,
    plan: PlanDraft,
    results: tuple[PriorActionResult, ...],
    max_revision_count: int,
) -> VerificationRecord:
    if not isinstance(value, VerificationRecord):
        raise VerificationError("verification_record_invalid")
    try:
        record = VerificationRecord.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise VerificationError("verification_record_invalid") from None
    request = record.request
    observations = request.criterion_observations
    if (
        request.actor_id != actor_id
        or request.device_id != device_id
        or request.outcome.verification_id != verification_id
    ):
        raise VerificationError("verification_record_invalid")
    _validate_verification_semantics(
        request.outcome,
        observations,
        plan=plan,
        results=results,
        max_revision_count=max_revision_count,
    )
    return record


async def verifyOutcome(
    state: Mapping[str, Any],
    *,
    service: VerificationService,
    runtime_thread_id: str,
) -> dict[str, Any]:
    """Independently verify every plan criterion and classify task outcome."""

    settings = service.settings
    _validate_settings(settings)
    (
        task_id,
        thread_id,
        actor_id,
        device_id,
        revision,
        plan,
        results,
        raw_observations,
    ) = _load_state(
        state,
        runtime_thread_id=runtime_thread_id,
        max_revision_count=settings.max_revision_count,
    )
    verification_id = _verification_id(
        task_id,
        thread_id,
        revision,
        plan,
    )
    replay = _validate_checkpoint_replay(
        raw_observations,
        verification_id=verification_id,
        task_id=task_id,
        thread_id=thread_id,
        revision=revision,
        plan=plan,
        results=results,
        max_revision_count=settings.max_revision_count,
    )
    if replay is not None:
        return {"observations": [], "status": _status_for(replay)}

    try:
        loaded = await service.store.load_verification(
            verification_id,
            actor_id=actor_id,
            device_id=device_id,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        raise VerificationError("verification_store_unavailable") from None
    if loaded is not None:
        record = _validate_record(
            loaded,
            verification_id=verification_id,
            actor_id=actor_id,
            device_id=device_id,
            plan=plan,
            results=results,
            max_revision_count=settings.max_revision_count,
        )
        return {
            "observations": [
                *(
                    item.model_dump(mode="json")
                    for item in record.request.criterion_observations
                ),
                record.request.outcome.model_dump(mode="json"),
            ],
            "status": _status_for(record.request.outcome),
        }

    requested_at = _aware_now(service.clock)
    by_action = {item.action_id: item for item in results}
    actions = {item.action_id: item for item in plan.actions}
    semaphore = asyncio.Semaphore(settings.max_concurrency)
    tasks = [
        asyncio.create_task(
            _run_criterion(
                verification_id=verification_id,
                task_id=task_id,
                thread_id=thread_id,
                actor_id=actor_id,
                device_id=device_id,
                criterion=criterion,
                action=actions[criterion.action_id],
                result=by_action.get(criterion.action_id),
                registry=service.registry,
                timeout=settings.probe_timeout_seconds,
                semaphore=semaphore,
                requested_at=requested_at,
            )
        )
        for criterion in plan.success_criteria
    ]
    try:
        criterion_observations = tuple(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    verified_at = _aware_now(service.clock)
    if verified_at < requested_at or any(
        item.observed_at > verified_at for item in criterion_observations
    ):
        raise VerificationError("verification_clock_invalid")
    aggregate = _aggregate(
        verification_id=verification_id,
        task_id=task_id,
        thread_id=thread_id,
        revision=revision,
        plan=plan,
        result_count=len(results),
        observations=criterion_observations,
        max_revision_count=settings.max_revision_count,
        verified_at=verified_at,
    )
    persistence_request = VerificationPersistenceRequest(
        actor_id=actor_id,
        device_id=device_id,
        criterion_observations=criterion_observations,
        outcome=aggregate,
    )
    try:
        raw_record = await service.store.record_or_get_verification(
            persistence_request
        )
    except asyncio.CancelledError:
        raise
    except VerificationStoreConflictError:
        raise VerificationError("verification_record_conflict") from None
    except Exception:
        raise VerificationError("verification_store_unavailable") from None
    record = _validate_record(
        raw_record,
        verification_id=verification_id,
        actor_id=actor_id,
        device_id=device_id,
        plan=plan,
        results=results,
        max_revision_count=settings.max_revision_count,
    )
    return {
        "observations": [
            *(
                item.model_dump(mode="json")
                for item in record.request.criterion_observations
            ),
            record.request.outcome.model_dump(mode="json"),
        ],
        "status": _status_for(record.request.outcome),
    }
