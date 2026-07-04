"""Review-only task reflection candidates for Global ID 120015."""

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

from jarvis.graph.dispatch import PriorActionResult
from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)
from jarvis.graph.plan import PlanDraft
from jarvis.graph.verification import (
    CriterionObservation,
    OutcomeVerification,
    VerifiedOutcome,
    _validate_verification_semantics,
)


REFLECTION_ID_PATTERN = re.compile(r"^rfc_[0-9a-f]{24}$")
CORRECTION_ID_PATTERN = re.compile(r"^ucr_[A-Za-z0-9_-]{8,128}$")
COMPONENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
VERSION_PATTERN = re.compile(r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")
SAFE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


class ReflectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS task reflection failed: {code}")


class ReflectionStoreConflictError(RuntimeError):
    """A different immutable candidate already owns this identity."""


class ComponentKind(StrEnum):
    PROMPT = "prompt"
    TEST = "test"
    TOOL = "tool"
    POLICY = "policy"


class CorrectionCode(StrEnum):
    INCORRECT_INTENT = "incorrect_intent"
    INCORRECT_SCOPE = "incorrect_scope"
    INCORRECT_RESULT = "incorrect_result"
    MISSING_CONSTRAINT = "missing_constraint"


class ReflectionKind(StrEnum):
    PROMPT_REVIEW = "prompt_review"
    TEST_IMPROVEMENT = "test_improvement"
    VERIFICATION_REVIEW = "verification_review"


class RecommendationCode(StrEnum):
    REVIEW_PROMPT_CONTRACT = "review_prompt_contract"
    ADD_REGRESSION_CASE = "add_regression_case"
    ADD_FAILURE_FIXTURE = "add_failure_fixture"
    ADD_VERIFICATION_FIXTURE = "add_verification_fixture"


class ComponentVersionReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ComponentKind
    component_id: str = Field(pattern=COMPONENT_ID_PATTERN.pattern)
    version: str = Field(pattern=VERSION_PATTERN.pattern)


class UserCorrection(BaseModel):
    """Identity-bound fixed-code correction; no free-form user text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correction_id: str = Field(pattern=CORRECTION_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    code: CorrectionCode
    evidence_reference_ids: tuple[str, ...] = Field(default=(), max_length=16)
    corrected_at: datetime

    @field_validator("corrected_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("correction time must be aware")
        return value


SUMMARY = {
    RecommendationCode.REVIEW_PROMPT_CONTRACT: (
        "Review the current prompt contract against the correction and evidence."
    ),
    RecommendationCode.ADD_REGRESSION_CASE: (
        "Review a regression test candidate grounded in the corrected task outcome."
    ),
    RecommendationCode.ADD_FAILURE_FIXTURE: (
        "Review a failure fixture candidate grounded in verified failed criteria."
    ),
    RecommendationCode.ADD_VERIFICATION_FIXTURE: (
        "Review a verification fixture candidate for the unresolved postcondition."
    ),
}


class TaskReflectionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["task.reflection_candidate"] = "task.reflection_candidate"
    version: Literal["1.0"] = "1.0"
    candidate_id: str = Field(pattern=REFLECTION_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    kind: ReflectionKind
    recommendation_code: RecommendationCode
    summary: str = Field(min_length=1, max_length=200)
    issue_codes: tuple[str, ...] = Field(default=(), max_length=32)
    evidence_reference_ids: tuple[str, ...] = Field(default=(), max_length=32)
    component_versions: tuple[ComponentVersionReference, ...] = Field(
        min_length=1, max_length=16
    )
    user_correction_id: str | None = Field(
        default=None, pattern=CORRECTION_ID_PATTERN.pattern
    )
    review_required: Literal[True] = True
    automatic_application: Literal[False] = False
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("candidate time must be aware")
        return value

    @field_validator("issue_codes", "evidence_reference_ids")
    @classmethod
    def sorted_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or tuple(sorted(value)) != value:
            raise ValueError("candidate values must be sorted and unique")
        return value


class ReflectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    candidate: TaskReflectionCandidate
    stored_at: datetime
    created: bool


class ReflectionStore(Protocol):
    async def load_candidate(
        self, candidate_id: str, *, actor_id: str, device_id: str
    ) -> ReflectionRecord | None: ...

    async def record_or_get_candidate(
        self, actor_id: str, device_id: str, candidate: TaskReflectionCandidate
    ) -> ReflectionRecord: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ReflectionService:
    store: ReflectionStore
    clock: Callable[[], datetime] = _utc_now


def _load_verified(state: Mapping[str, Any], runtime_thread_id: str):
    task_id, thread_id = state.get("task_id"), state.get("thread_id")
    actor_id, device_id = state.get("actor_id"), state.get("device_id")
    revision = state.get("revision_count")
    if state.get("status") not in {
        "succeeded", "partially_succeeded", "failed"
    }:
        raise ReflectionError("reflection_state_invalid")
    if (
        not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id)
        or not isinstance(thread_id, str) or runtime_thread_id != thread_id
        or not isinstance(actor_id, str) or not PRINCIPAL_ID_PATTERN.fullmatch(actor_id)
        or not isinstance(device_id, str) or not PRINCIPAL_ID_PATTERN.fullmatch(device_id)
        or type(revision) is not int or revision < 0 or revision > 2
    ):
        raise ReflectionError("reflection_identity_invalid")
    try:
        plan = PlanDraft.model_validate(state.get("plan"))
        results = tuple(
            PriorActionResult.model_validate(item)
            for item in state.get("action_results", ())
        )
    except (ValidationError, TypeError, ValueError):
        raise ReflectionError("reflection_evidence_invalid") from None
    observations = state.get("observations", ())
    if not isinstance(observations, Sequence) or isinstance(
        observations, (str, bytes, bytearray)
    ):
        raise ReflectionError("reflection_evidence_invalid")
    aggregates, criteria = [], []
    for raw in observations:
        if not isinstance(raw, Mapping):
            continue
        try:
            if raw.get("type") == "outcome.verification":
                aggregates.append(OutcomeVerification.model_validate(raw))
            elif raw.get("type") == "verification.criterion":
                criteria.append(CriterionObservation.model_validate(raw))
        except ValidationError:
            raise ReflectionError("reflection_evidence_invalid") from None
    if not aggregates:
        raise ReflectionError("reflection_verification_missing")
    aggregate = aggregates[-1]
    matching = tuple(
        item for item in criteria
        if item.verification_id == aggregate.verification_id
    )
    try:
        _validate_verification_semantics(
            aggregate, matching, plan=plan, results=results,
            max_revision_count=2,
        )
    except Exception:
        raise ReflectionError("reflection_evidence_invalid") from None
    return task_id, thread_id, actor_id, device_id, aggregate, matching


def _versions(value: object) -> tuple[ComponentVersionReference, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReflectionError("reflection_versions_invalid")
    try:
        refs = tuple(ComponentVersionReference.model_validate(item) for item in value)
    except ValidationError:
        raise ReflectionError("reflection_versions_invalid") from None
    keys = [(item.kind, item.component_id) for item in refs]
    if not refs or len(keys) != len(set(keys)):
        raise ReflectionError("reflection_versions_invalid")
    return tuple(sorted(refs, key=lambda item: (item.kind.value, item.component_id)))


def _correction(value, *, ids, evidence) -> UserCorrection | None:
    if value is None:
        return None
    try:
        item = UserCorrection.model_validate(value)
    except ValidationError:
        raise ReflectionError("reflection_correction_invalid") from None
    if (
        (item.task_id, item.thread_id, item.actor_id, item.device_id) != ids
        or not set(item.evidence_reference_ids).issubset(evidence)
    ):
        raise ReflectionError("reflection_correction_invalid")
    return item


def _proposal(aggregate, criteria, correction, safe_errors):
    evidence = {
        ref for item in criteria for ref in item.evidence_reference_ids
    }
    issues = {
        item.reason_code for item in criteria if item.reason_code is not None
    }
    issues.update(safe_errors)
    if correction is not None:
        evidence.update(correction.evidence_reference_ids)
        if correction.code in {
            CorrectionCode.INCORRECT_INTENT,
            CorrectionCode.INCORRECT_SCOPE,
            CorrectionCode.MISSING_CONSTRAINT,
        }:
            return (
                ReflectionKind.PROMPT_REVIEW,
                RecommendationCode.REVIEW_PROMPT_CONTRACT,
                evidence, issues,
            )
        return (
            ReflectionKind.TEST_IMPROVEMENT,
            RecommendationCode.ADD_REGRESSION_CASE,
            evidence, issues,
        )
    if aggregate.outcome is VerifiedOutcome.UNCERTAIN:
        return (
            ReflectionKind.VERIFICATION_REVIEW,
            RecommendationCode.ADD_VERIFICATION_FIXTURE,
            evidence, issues,
        )
    if aggregate.outcome in {
        VerifiedOutcome.FAILED, VerifiedOutcome.PARTIALLY_SUCCEEDED
    } and issues:
        return (
            ReflectionKind.TEST_IMPROVEMENT,
            RecommendationCode.ADD_FAILURE_FIXTURE,
            evidence, issues,
        )
    return None


async def proposeTaskReflection(
    state: Mapping[str, Any], *, service: ReflectionService,
    runtime_thread_id: str, current_versions: object,
    user_correction: object | None = None,
) -> dict[str, Any]:
    """Persist one review-only evidence-grounded candidate or return none."""

    task_id, thread_id, actor_id, device_id, aggregate, criteria = (
        _load_verified(state, runtime_thread_id)
    )
    versions = _versions(current_versions)
    evidence = {
        ref for item in criteria for ref in item.evidence_reference_ids
    }
    correction = _correction(
        user_correction,
        ids=(task_id, thread_id, actor_id, device_id),
        evidence=evidence,
    )
    safe_errors = {
        code
        for item in state.get("errors", ())
        if isinstance(item, Mapping)
        and isinstance((code := item.get("code")), str)
        and SAFE_CODE_PATTERN.fullmatch(code)
    }
    proposal = _proposal(aggregate, criteria, correction, safe_errors)
    if proposal is None:
        return {"reflection_candidate": None, "reason_code": "insufficient_evidence"}
    kind, recommendation, evidence, issues = proposal
    seed = json.dumps(
        {
            "task": task_id, "verification": aggregate.verification_id,
            "recommendation": recommendation.value,
            "correction": correction.correction_id if correction else None,
            "versions": [item.model_dump(mode="json") for item in versions],
        },
        sort_keys=True, separators=(",", ":"),
    )
    candidate_id = "rfc_" + hashlib.sha256(seed.encode()).hexdigest()[:24]
    try:
        loaded = await service.store.load_candidate(
            candidate_id, actor_id=actor_id, device_id=device_id
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        raise ReflectionError("reflection_store_unavailable") from None
    if loaded is not None:
        record = loaded
    else:
        now = service.clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ReflectionError("reflection_clock_invalid")
        candidate = TaskReflectionCandidate(
            candidate_id=candidate_id, task_id=task_id, thread_id=thread_id,
            kind=kind, recommendation_code=recommendation,
            summary=SUMMARY[recommendation],
            issue_codes=tuple(sorted(issues)),
            evidence_reference_ids=tuple(sorted(evidence)),
            component_versions=versions,
            user_correction_id=correction.correction_id if correction else None,
            created_at=now,
        )
        try:
            record = await service.store.record_or_get_candidate(
                actor_id, device_id, candidate
            )
        except asyncio.CancelledError:
            raise
        except ReflectionStoreConflictError:
            raise ReflectionError("reflection_record_conflict") from None
        except Exception:
            raise ReflectionError("reflection_store_unavailable") from None
    if not isinstance(record, ReflectionRecord):
        raise ReflectionError("reflection_record_invalid")
    try:
        record = ReflectionRecord.model_validate(record.model_dump(mode="json"))
    except Exception:
        raise ReflectionError("reflection_record_invalid") from None
    if (
        record.actor_id != actor_id or record.device_id != device_id
        or record.candidate.candidate_id != candidate_id
        or record.stored_at < record.candidate.created_at
    ):
        raise ReflectionError("reflection_record_invalid")
    return {
        "reflection_candidate": record.candidate.model_dump(mode="json"),
        "reason_code": "review_candidate_created",
    }
