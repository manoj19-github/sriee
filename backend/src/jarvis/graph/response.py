"""Evidence-grounded final response rendering for Global ID 120013."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from jarvis.graph.approval_resume import ApprovalResult
from jarvis.graph.dispatch import PriorActionResult
from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)
from jarvis.graph.plan import PlanDraft
from jarvis.graph.policy import PolicyDecision, PolicyDecisionKind
from jarvis.graph.verification import (
    CriterionObservation,
    OutcomeVerification,
    VerifiedOutcome,
    _validate_verification_semantics,
)


RESPONSE_ID_PATTERN = re.compile(r"^rsp_[0-9a-f]{24}$")
ISSUE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
FINAL_RESPONSE_VERSION = "1.0"
TerminalStatus = Literal[
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
    "denied",
    "expired",
]

SUMMARY_TEMPLATES = {
    "succeeded": (
        "Task completed and all stored success criteria were independently verified."
    ),
    "partially_succeeded": (
        "Task completed partially; stored evidence confirms some criteria failed."
    ),
    "failed": "Task did not complete successfully; unresolved issues remain.",
    "uncertain": (
        "Task outcome could not be verified after the available revision attempts."
    ),
    "cancelled": "Task was cancelled before verified completion.",
    "denied": "Task was denied by policy or user decision; denied actions were not run.",
    "expired": "Task stopped because the required approval expired.",
}


class FinalResponseError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS final response rendering failed: {code}")


class FinalResponseStoreConflictError(RuntimeError):
    """A different immutable response already owns this identity."""


class FinalResponse(BaseModel):
    """Bounded API/checkpoint projection containing evidence references only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["task.final_response"] = "task.final_response"
    version: Literal["1.0"] = FINAL_RESPONSE_VERSION
    response_id: str = Field(pattern=RESPONSE_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    status: TerminalStatus
    summary: str = Field(min_length=1, max_length=300)
    verification_outcome: VerifiedOutcome | None = None
    verification_id: str | None = Field(
        default=None, pattern=r"^vrf_[0-9a-f]{24}$"
    )
    evidence_reference_ids: tuple[str, ...] = Field(default=(), max_length=64)
    receipt_reference_ids: tuple[str, ...] = Field(default=(), max_length=16)
    unresolved_issue_codes: tuple[str, ...] = Field(default=(), max_length=64)
    rendered_at: datetime

    @field_validator("rendered_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("response time must be aware")
        return value

    @field_validator("unresolved_issue_codes")
    @classmethod
    def issues(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if (
            len(value) != len(set(value))
            or tuple(sorted(value)) != value
            or any(not ISSUE_CODE_PATTERN.fullmatch(item) for item in value)
        ):
            raise ValueError("response issues are invalid")
        return value

    @field_validator("evidence_reference_ids", "receipt_reference_ids")
    @classmethod
    def unique_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or tuple(sorted(value)) != value:
            raise ValueError("response references are invalid")
        return value


class FinalResponsePersistenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    response: FinalResponse


class FinalResponseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request: FinalResponsePersistenceRequest
    stored_at: datetime
    created: bool

    @field_validator("stored_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("storage time must be aware")
        return value


class FinalResponseStore(Protocol):
    async def load_response(
        self, response_id: str, *, actor_id: str, device_id: str
    ) -> FinalResponseRecord | None:
        """Load one immutable actor/device-owned response."""

    async def record_or_get_response(
        self, request: FinalResponsePersistenceRequest
    ) -> FinalResponseRecord:
        """Persist once or return the existing response."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class FinalResponseService:
    store: FinalResponseStore
    clock: Callable[[], datetime] = _utc_now


@dataclass(frozen=True, slots=True)
class _Evidence:
    task_id: str
    thread_id: str
    actor_id: str
    device_id: str
    status: TerminalStatus
    verification: OutcomeVerification | None
    evidence_ids: tuple[str, ...]
    receipt_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]


def _load_evidence(
    state: Mapping[str, Any], *, runtime_thread_id: str
) -> _Evidence:
    status = state.get("status")
    task_id, thread_id = state.get("task_id"), state.get("thread_id")
    actor_id, device_id = state.get("actor_id"), state.get("device_id")
    if status not in SUMMARY_TEMPLATES or status == "uncertain":
        raise FinalResponseError("final_response_state_invalid")
    if (
        not isinstance(task_id, str)
        or not TASK_ID_PATTERN.fullmatch(task_id)
        or not isinstance(thread_id, str)
        or not THREAD_ID_PATTERN.fullmatch(thread_id)
        or runtime_thread_id != thread_id
        or not isinstance(actor_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(actor_id)
        or not isinstance(device_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(device_id)
    ):
        raise FinalResponseError("final_response_identity_invalid")
    try:
        results = tuple(
            PriorActionResult.model_validate(item)
            for item in state.get("action_results", ())
        )
        plan = (
            PlanDraft.model_validate(state["plan"])
            if state.get("plan") is not None
            else None
        )
        decisions = tuple(
            PolicyDecision.model_validate(item)
            for item in state.get("policy_decisions", ())
        )
    except (ValidationError, TypeError, ValueError):
        raise FinalResponseError("final_response_evidence_invalid") from None
    raw_observations = state.get("observations", ())
    if not isinstance(raw_observations, Sequence) or isinstance(
        raw_observations, (str, bytes, bytearray)
    ):
        raise FinalResponseError("final_response_evidence_invalid")
    aggregates, criteria = [], []
    for item in raw_observations:
        if not isinstance(item, Mapping):
            continue
        try:
            if item.get("type") == "outcome.verification":
                aggregates.append(OutcomeVerification.model_validate(item))
            elif item.get("type") == "verification.criterion":
                criteria.append(CriterionObservation.model_validate(item))
        except ValidationError:
            raise FinalResponseError("final_response_evidence_invalid") from None
    verification = aggregates[-1] if aggregates else None
    matching = tuple(
        item
        for item in criteria
        if verification is not None
        and item.verification_id == verification.verification_id
    )
    if verification is not None:
        if plan is None:
            raise FinalResponseError("final_response_evidence_invalid")
        try:
            _validate_verification_semantics(
                verification, matching, plan=plan, results=results,
                max_revision_count=2,
            )
        except Exception:
            raise FinalResponseError("final_response_evidence_invalid") from None
    if status in {"succeeded", "partially_succeeded"} and verification is None:
        raise FinalResponseError("final_response_verification_missing")
    if (
        status == "succeeded"
        and verification.outcome is not VerifiedOutcome.SUCCEEDED
    ) or (
        status == "partially_succeeded"
        and verification.outcome is not VerifiedOutcome.PARTIALLY_SUCCEEDED
    ):
        raise FinalResponseError("final_response_status_mismatch")
    issues = {
        item.reason_code for item in matching if item.reason_code is not None
    }
    issues.update(
        code
        for decision in decisions
        if decision.decision is PolicyDecisionKind.DENY
        for code in decision.reason_codes
    )
    pending = state.get("pending_approval")
    if pending is not None:
        try:
            approval = ApprovalResult.model_validate(pending)
        except ValidationError:
            approval = None
        if approval is not None and approval.outcome in {"denied", "expired"}:
            issues.add(f"approval_{approval.outcome}")
    if status == "cancelled":
        issues.add("task_cancelled")
    if status == "expired":
        issues.add("approval_expired")
    for error in state.get("errors", ()):
        if isinstance(error, Mapping):
            code = error.get("code")
            if isinstance(code, str) and ISSUE_CODE_PATTERN.fullmatch(code):
                issues.add(code)
    return _Evidence(
        task_id=task_id, thread_id=thread_id, actor_id=actor_id,
        device_id=device_id, status=status, verification=verification,
        evidence_ids=tuple(sorted({
            evidence for item in matching
            for evidence in item.evidence_reference_ids
        })),
        receipt_ids=tuple(sorted({item.receipt_id for item in results})),
        issue_codes=tuple(sorted(issues)),
    )


def _response_id(evidence: _Evidence) -> str:
    canonical = json.dumps(
        {
            "task": evidence.task_id, "thread": evidence.thread_id,
            "status": evidence.status,
            "verification": (
                evidence.verification.verification_id
                if evidence.verification else None
            ),
            "issues": evidence.issue_codes,
        },
        sort_keys=True, separators=(",", ":"),
    )
    return "rsp_" + hashlib.sha256(canonical.encode()).hexdigest()[:24]


def _render(evidence: _Evidence, rendered_at: datetime) -> FinalResponse:
    verification_outcome = (
        evidence.verification.outcome if evidence.verification else None
    )
    template_key = (
        "uncertain"
        if evidence.status == "failed"
        and verification_outcome is VerifiedOutcome.UNCERTAIN
        else evidence.status
    )
    return FinalResponse(
        response_id=_response_id(evidence),
        task_id=evidence.task_id, thread_id=evidence.thread_id,
        status=evidence.status, summary=SUMMARY_TEMPLATES[template_key],
        verification_outcome=verification_outcome,
        verification_id=(
            evidence.verification.verification_id
            if evidence.verification else None
        ),
        evidence_reference_ids=evidence.evidence_ids,
        receipt_reference_ids=evidence.receipt_ids,
        unresolved_issue_codes=evidence.issue_codes,
        rendered_at=rendered_at,
    )


def _validate_record(
    value: object, *, expected_id: str, actor_id: str, device_id: str
) -> FinalResponseRecord:
    if not isinstance(value, FinalResponseRecord):
        raise FinalResponseError("final_response_record_invalid")
    try:
        record = FinalResponseRecord.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise FinalResponseError("final_response_record_invalid") from None
    if (
        record.request.actor_id != actor_id
        or record.request.device_id != device_id
        or record.request.response.response_id != expected_id
        or record.stored_at < record.request.response.rendered_at
    ):
        raise FinalResponseError("final_response_record_invalid")
    return record


async def renderFinalResponse(
    state: Mapping[str, Any], *, service: FinalResponseService,
    runtime_thread_id: str,
) -> dict[str, Any]:
    """Render and persist a concise response grounded only in stored evidence."""

    evidence = _load_evidence(state, runtime_thread_id=runtime_thread_id)
    expected_id = _response_id(evidence)
    existing = state.get("final_response")
    if existing is not None:
        try:
            response = FinalResponse.model_validate(existing)
        except ValidationError:
            raise FinalResponseError("final_response_checkpoint_invalid") from None
        if response.response_id != expected_id:
            raise FinalResponseError("final_response_checkpoint_invalid")
        return {"final_response": response.model_dump(mode="json")}
    try:
        loaded = await service.store.load_response(
            expected_id, actor_id=evidence.actor_id, device_id=evidence.device_id
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        raise FinalResponseError("final_response_store_unavailable") from None
    if loaded is not None:
        return {"final_response": _validate_record(
            loaded, expected_id=expected_id, actor_id=evidence.actor_id,
            device_id=evidence.device_id,
        ).request.response.model_dump(mode="json")}
    now = service.clock()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise FinalResponseError("final_response_clock_invalid")
    request = FinalResponsePersistenceRequest(
        actor_id=evidence.actor_id, device_id=evidence.device_id,
        response=_render(evidence, now),
    )
    try:
        raw = await service.store.record_or_get_response(request)
    except asyncio.CancelledError:
        raise
    except FinalResponseStoreConflictError:
        raise FinalResponseError("final_response_record_conflict") from None
    except Exception:
        raise FinalResponseError("final_response_store_unavailable") from None
    record = _validate_record(
        raw, expected_id=expected_id, actor_id=evidence.actor_id,
        device_id=evidence.device_id,
    )
    return {"final_response": record.request.response.model_dump(mode="json")}
