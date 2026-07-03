"""Authenticated, single-use approval resume for Global ID 120008."""

from __future__ import annotations

import asyncio
import hmac
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from jarvis.graph.approval import (
    ACTION_DIGEST_PATTERN,
    APPROVAL_ID_PATTERN,
    EVENT_ID_PATTERN,
    ApprovalResumeCandidate,
    PendingApprovalRecord,
    PendingApprovalRequest,
)
from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)


RESOLUTION_ID_PATTERN = r"^ars_[0-9a-f]{24}$"
APPROVAL_RESULT_VERSION = "1.0"
ApprovalOutcome = Literal["approved", "denied", "expired"]


class ApprovalResumeError(RuntimeError):
    """A content-free resume failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS approval resume failed: {code}")


class ApprovalResolutionConsumedError(RuntimeError):
    """The atomic resolver has already claimed this approval decision."""


class ApprovalCheckpoint(BaseModel):
    """Exact checkpoint envelope produced by ``pauseForApproval``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: PendingApprovalRequest
    event_id: str = Field(pattern=EVENT_ID_PATTERN.pattern)
    issued_at: datetime
    expires_at: datetime
    resume: ApprovalResumeCandidate

    @model_validator(mode="after")
    def validate_pending_record(self) -> ApprovalCheckpoint:
        PendingApprovalRecord(
            request=self.request,
            event_id=self.event_id,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
        )
        preview = self.request.preview
        if (
            preview.action_id != self.request.action_id
            or preview.action_digest != self.request.action_digest
            or preview.risk_tier != self.request.risk_tier
            or preview.policy_reference_id
            != self.request.policy_reference_id
            or preview.policy_version != self.request.policy_version
        ):
            raise ValueError("approval checkpoint bindings are invalid")
        return self


class ApprovalResolutionRequest(BaseModel):
    """Identity-complete request claimed atomically by the approval store."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(pattern=APPROVAL_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    action_digest: str = Field(pattern=ACTION_DIGEST_PATTERN.pattern)
    pending_event_id: str = Field(pattern=EVENT_ID_PATTERN.pattern)
    issued_at: datetime
    expires_at: datetime
    decision: Literal["approve", "deny"]

    @model_validator(mode="after")
    def validate_times(self) -> ApprovalResolutionRequest:
        if (
            self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("approval resolution timestamps are invalid")
        return self


class ApprovalResolutionRecord(BaseModel):
    """Authoritative one-time resolution returned by the atomic store."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ApprovalResolutionRequest
    resolution_id: str = Field(pattern=RESOLUTION_ID_PATTERN)
    outcome: ApprovalOutcome
    decided_at: datetime

    @model_validator(mode="after")
    def validate_outcome(self) -> ApprovalResolutionRecord:
        expected = (
            "approved"
            if self.request.decision == "approve"
            else "denied"
        )
        if (
            self.decided_at.tzinfo is None
            or (
                self.outcome == "expired"
                and self.decided_at < self.request.expires_at
            )
            or (
                self.outcome != "expired"
                and (
                    self.decided_at >= self.request.expires_at
                    or self.outcome != expected
                )
            )
        ):
            raise ValueError("approval resolution outcome is invalid")
        return self


class ApprovalResult(BaseModel):
    """Bounded checkpoint-safe projection consumed by later graph nodes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["approval.result"] = "approval.result"
    version: Literal["1.0"] = APPROVAL_RESULT_VERSION
    approval_id: str = Field(pattern=APPROVAL_ID_PATTERN.pattern)
    resolution_id: str = Field(pattern=RESOLUTION_ID_PATTERN)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    action_digest: str = Field(pattern=ACTION_DIGEST_PATTERN.pattern)
    outcome: ApprovalOutcome
    decided_at: datetime


class ApprovalResolutionStore(Protocol):
    async def resolve_pending_approval(
        self,
        request: ApprovalResolutionRequest,
    ) -> ApprovalResolutionRecord:
        """Atomically authenticate and claim one approval decision once."""


def _same(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def _load_checkpoint(
    state: Mapping[str, Any],
    *,
    runtime_thread_id: str,
) -> ApprovalCheckpoint:
    if state.get("status") != "awaiting_approval":
        raise ApprovalResumeError("approval_resume_state_invalid")
    if (
        not isinstance(runtime_thread_id, str)
        or not THREAD_ID_PATTERN.fullmatch(runtime_thread_id)
    ):
        raise ApprovalResumeError("approval_resume_thread_invalid")
    try:
        checkpoint = ApprovalCheckpoint.model_validate(
            state.get("pending_approval")
        )
    except (ValidationError, TypeError, ValueError):
        raise ApprovalResumeError("approval_resume_checkpoint_invalid") from None

    request = checkpoint.request
    identities = (
        ("task_id", request.task_id, TASK_ID_PATTERN),
        ("thread_id", request.thread_id, THREAD_ID_PATTERN),
        ("actor_id", request.actor_id, PRINCIPAL_ID_PATTERN),
        ("device_id", request.device_id, PRINCIPAL_ID_PATTERN),
    )
    if any(
        not isinstance(state.get(name), str)
        or not pattern.fullmatch(state[name])
        or not _same(state[name], expected)
        for name, expected, pattern in identities
    ):
        raise ApprovalResumeError("approval_resume_identity_mismatch")
    if not _same(runtime_thread_id, request.thread_id):
        raise ApprovalResumeError("approval_resume_thread_mismatch")
    if (
        not _same(checkpoint.resume.approval_id, request.approval_id)
        or not _same(
            checkpoint.resume.action_digest,
            request.action_digest,
        )
    ):
        raise ApprovalResumeError("approval_resume_candidate_mismatch")
    return checkpoint


def _resolution_request(
    checkpoint: ApprovalCheckpoint,
) -> ApprovalResolutionRequest:
    pending = checkpoint.request
    return ApprovalResolutionRequest(
        approval_id=pending.approval_id,
        task_id=pending.task_id,
        thread_id=pending.thread_id,
        actor_id=pending.actor_id,
        device_id=pending.device_id,
        action_id=pending.action_id,
        action_digest=pending.action_digest,
        pending_event_id=checkpoint.event_id,
        issued_at=checkpoint.issued_at,
        expires_at=checkpoint.expires_at,
        decision=checkpoint.resume.decision,
    )


def _validate_resolution(
    value: object,
    request: ApprovalResolutionRequest,
) -> ApprovalResolutionRecord:
    if not isinstance(value, ApprovalResolutionRecord):
        raise ApprovalResumeError("approval_resolution_invalid")
    try:
        record = ApprovalResolutionRecord.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise ApprovalResumeError("approval_resolution_invalid") from None
    if record.request != request:
        raise ApprovalResumeError("approval_resolution_conflict")
    return record


async def resumeApproval(
    state: Mapping[str, Any],
    *,
    service: ApprovalResolutionStore,
    runtime_thread_id: str,
) -> dict[str, Any]:
    """Validate and atomically claim an exact approval resume decision."""

    checkpoint = _load_checkpoint(
        state,
        runtime_thread_id=runtime_thread_id,
    )
    request = _resolution_request(checkpoint)
    try:
        raw_resolution = await service.resolve_pending_approval(request)
    except asyncio.CancelledError:
        raise
    except ApprovalResolutionConsumedError:
        raise ApprovalResumeError("approval_resolution_consumed") from None
    except Exception:
        raise ApprovalResumeError("approval_resolution_unavailable") from None
    resolution = _validate_resolution(raw_resolution, request)
    result = ApprovalResult(
        approval_id=request.approval_id,
        resolution_id=resolution.resolution_id,
        thread_id=request.thread_id,
        action_id=request.action_id,
        action_digest=request.action_digest,
        outcome=resolution.outcome,
        decided_at=resolution.decided_at,
    )
    status = {
        "approved": "executing",
        "denied": "denied",
        "expired": "expired",
    }[resolution.outcome]
    return {
        "pending_approval": result.model_dump(mode="json"),
        "status": status,
    }
