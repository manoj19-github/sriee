"""Replay-safe durable approval pause for Global ID 120007."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from langgraph.types import interrupt
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from jarvis.graph.context import REFERENCE_VERSION_PATTERN
from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)
from jarvis.graph.plan import (
    CAPABILITY_ID_PATTERN,
    PlanActionDraft,
    PlanDraft,
    ScalarValue,
)
from jarvis.graph.policy import PolicyDecision, PolicyDecisionKind


APPROVAL_ID_PATTERN = re.compile(r"^apr_[0-9a-f]{24}$")
ACTION_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EVENT_ID_PATTERN = re.compile(r"^evt_[A-Za-z0-9_-]{8,128}$")
APPROVAL_DIGEST_VERSION = "sha256-v1"
APPROVAL_PREVIEW_VERSION = "1.0"
APPROVAL_INTERRUPT_VERSION = "1.0"


class ApprovalPauseError(RuntimeError):
    """A content-free approval pause failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS approval pause failed: {code}")


class ApprovalPreviewParameter(BaseModel):
    """One exact typed binding shown by trusted approval UI."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: ScalarValue


class ApprovalActionPreview(BaseModel):
    """Bounded JSON-safe preview for one exact action only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = APPROVAL_PREVIEW_VERSION
    summary: str = Field(min_length=1, max_length=300)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    capability_id: str = Field(pattern=CAPABILITY_ID_PATTERN.pattern)
    capability_version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    parameters: tuple[ApprovalPreviewParameter, ...] = Field(
        default=(),
        max_length=12,
    )
    resource_ids: tuple[str, ...] = Field(default=(), max_length=12)
    dependency_action_ids: tuple[str, ...] = Field(
        default=(),
        max_length=8,
    )
    verification_codes: tuple[str, ...] = Field(
        min_length=1,
        max_length=16,
    )
    timeout_seconds: int = Field(ge=1, le=600)
    risk_tier: str = Field(pattern=r"^r[0-4]$")
    reason_codes: tuple[str, ...] = Field(min_length=1, max_length=40)
    policy_reference_id: str = Field(pattern=r"^pol_[A-Za-z0-9_-]{8,128}$")
    policy_version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    action_digest: str = Field(pattern=ACTION_DIGEST_PATTERN.pattern)
    digest_version: Literal["sha256-v1"] = APPROVAL_DIGEST_VERSION

    @model_validator(mode="after")
    def validate_preview_members(self) -> ApprovalActionPreview:
        parameter_names = [item.name for item in self.parameters]
        if (
            len(parameter_names) != len(set(parameter_names))
            or len(self.resource_ids) != len(set(self.resource_ids))
            or len(self.dependency_action_ids)
            != len(set(self.dependency_action_ids))
            or len(self.verification_codes)
            != len(set(self.verification_codes))
            or len(self.reason_codes) != len(set(self.reason_codes))
            or any(
                not re.fullmatch(r"^res_[A-Za-z0-9_-]{8,128}$", item)
                for item in self.resource_ids
            )
        ):
            raise ValueError("approval preview members are invalid")
        return self


class PendingApprovalRequest(BaseModel):
    """Idempotent atomic persistence request issued before interrupt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(pattern=APPROVAL_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    action_digest: str = Field(pattern=ACTION_DIGEST_PATTERN.pattern)
    decision_id: str = Field(pattern=r"^pdc_[0-9a-f]{24}$")
    risk_tier: str = Field(pattern=r"^r[0-4]$")
    policy_reference_id: str = Field(pattern=r"^pol_[A-Za-z0-9_-]{8,128}$")
    policy_version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    preview: ApprovalActionPreview
    expires_after_seconds: int = Field(ge=30, le=3_600)


class PendingApprovalRecord(BaseModel):
    """Persisted approval/event identity returned by the atomic store."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: PendingApprovalRequest
    event_id: str = Field(pattern=EVENT_ID_PATTERN.pattern)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> PendingApprovalRecord:
        if (
            self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or (
                self.expires_at - self.issued_at
            ).total_seconds()
            != self.request.expires_after_seconds
        ):
            raise ValueError("approval timestamps are invalid")
        return self


class ApprovalInterruptPayload(BaseModel):
    """Durable JSON payload surfaced to the trusted desktop."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["approval.required"] = "approval.required"
    version: Literal["1.0"] = APPROVAL_INTERRUPT_VERSION
    approval_id: str = Field(pattern=APPROVAL_ID_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    action_digest: str = Field(pattern=ACTION_DIGEST_PATTERN.pattern)
    issued_at: datetime
    expires_at: datetime
    preview: ApprovalActionPreview


class ApprovalResumeCandidate(BaseModel):
    """Strict transport shape passed to the later resume validator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(pattern=APPROVAL_ID_PATTERN.pattern)
    action_digest: str = Field(pattern=ACTION_DIGEST_PATTERN.pattern)
    decision: Literal["approve", "deny"]


class PendingApprovalStore(Protocol):
    async def create_or_get_pending_approval(
        self,
        request: PendingApprovalRequest,
    ) -> PendingApprovalRecord:
        """Atomically create approval+event once or return the exact existing row."""


@dataclass(frozen=True, slots=True)
class ApprovalPauseSettings:
    expires_after_seconds: int = 300
    max_interrupt_payload_bytes: int = 32 * 1024
    max_resume_payload_bytes: int = 16 * 1024


@dataclass(frozen=True, slots=True)
class ApprovalPauseService:
    store: PendingApprovalStore
    interrupt_fn: Callable[[Any], Any] = interrupt
    settings: ApprovalPauseSettings = ApprovalPauseSettings()


def _validate_settings(settings: ApprovalPauseSettings) -> None:
    if (
        settings.expires_after_seconds < 30
        or settings.expires_after_seconds > 3_600
        or settings.max_interrupt_payload_bytes < 1_024
        or settings.max_interrupt_payload_bytes > 64 * 1024
        or settings.max_resume_payload_bytes < 256
        or settings.max_resume_payload_bytes > 32 * 1024
    ):
        raise ApprovalPauseError("approval_pause_settings_incompatible")


def _validate_state(
    state: Mapping[str, Any],
) -> tuple[str, str, str, str, PlanDraft, tuple[PolicyDecision, ...]]:
    if (
        state.get("status") != "awaiting_approval"
        or state.get("pending_approval") is not None
    ):
        raise ApprovalPauseError("approval_pause_state_invalid")
    task_id = state.get("task_id")
    thread_id = state.get("thread_id")
    actor_id = state.get("actor_id")
    device_id = state.get("device_id")
    if (
        not isinstance(task_id, str)
        or not TASK_ID_PATTERN.fullmatch(task_id)
        or not isinstance(thread_id, str)
        or not THREAD_ID_PATTERN.fullmatch(thread_id)
        or not isinstance(actor_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(actor_id)
        or not isinstance(device_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(device_id)
    ):
        raise ApprovalPauseError("approval_pause_identity_invalid")
    try:
        plan = PlanDraft.model_validate(state.get("plan"))
        decisions = tuple(
            PolicyDecision.model_validate(item)
            for item in state.get("policy_decisions", ())
        )
    except (ValidationError, TypeError, ValueError):
        raise ApprovalPauseError("approval_pause_contract_invalid") from None
    action_ids = tuple(action.action_id for action in plan.actions)
    decision_ids = tuple(item.action_id for item in decisions)
    if (
        plan.schema_version != "1.0"
        or not action_ids
        or len(decision_ids) != len(set(decision_ids))
        or set(decision_ids) != set(action_ids)
        or any(
            item.decision is PolicyDecisionKind.DENY
            for item in decisions
        )
    ):
        raise ApprovalPauseError("approval_pause_contract_invalid")
    asks = [
        item
        for item in decisions
        if item.decision is PolicyDecisionKind.ASK
    ]
    if (
        not asks
        or any(not item.requires_fresh_approval for item in asks)
        or len({item.policy_reference_id for item in decisions}) != 1
        or len({item.policy_version for item in decisions}) != 1
    ):
        raise ApprovalPauseError("approval_pause_contract_invalid")
    return task_id, thread_id, actor_id, device_id, plan, decisions


def _selected_action(
    plan: PlanDraft,
    decisions: tuple[PolicyDecision, ...],
) -> tuple[PlanActionDraft, PolicyDecision]:
    by_action = {item.action_id: item for item in decisions}
    for action in plan.actions:
        decision = by_action[action.action_id]
        if decision.decision is PolicyDecisionKind.ASK:
            return action, decision
    raise ApprovalPauseError("approval_pause_contract_invalid")


def _digest_action(
    *,
    task_id: str,
    thread_id: str,
    actor_id: str,
    device_id: str,
    action: PlanActionDraft,
    decision: PolicyDecision,
    verification_codes: tuple[str, ...],
) -> str:
    payload = {
        "digest_version": APPROVAL_DIGEST_VERSION,
        "task_id": task_id,
        "thread_id": thread_id,
        "actor_id": actor_id,
        "device_id": device_id,
        "action": {
            "action_id": action.action_id,
            "capability_id": action.capability_id,
            "capability_version": action.capability_version,
            "arguments": sorted(
                (
                    argument.model_dump(mode="json")
                    for argument in action.arguments
                ),
                key=lambda item: item["name"],
            ),
            "dependencies": sorted(action.dependencies),
            "timeout_seconds": action.timeout_seconds,
        },
        "verification_codes": sorted(verification_codes),
        "policy": {
            "decision_id": decision.decision_id,
            "decision": decision.decision.value,
            "risk_tier": decision.risk_tier.value,
            "policy_reference_id": decision.policy_reference_id,
            "policy_version": decision.policy_version,
        },
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _approval_id(
    task_id: str,
    action_id: str,
    action_digest: str,
) -> str:
    value = f"{task_id}:{action_id}:{action_digest}".encode()
    return "apr_" + hashlib.sha256(value).hexdigest()[:24]


def _build_request(
    *,
    task_id: str,
    thread_id: str,
    actor_id: str,
    device_id: str,
    plan: PlanDraft,
    action: PlanActionDraft,
    decision: PolicyDecision,
    settings: ApprovalPauseSettings,
) -> PendingApprovalRequest:
    verification_codes = tuple(
        sorted(
            criterion.verification_code
            for criterion in plan.success_criteria
            if criterion.action_id == action.action_id
        )
    )
    if not verification_codes:
        raise ApprovalPauseError("approval_pause_contract_invalid")
    action_digest = _digest_action(
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        action=action,
        decision=decision,
        verification_codes=verification_codes,
    )
    resources = tuple(
        sorted(
            {
                argument.value
                for argument in action.arguments
                if (
                    isinstance(argument.value, str)
                    and argument.value.startswith("res_")
                )
            }
        )
    )
    preview = ApprovalActionPreview(
        summary=(
            f"Approve {action.capability_id} for "
            f"{len(resources)} registered resource(s)."
        ),
        action_id=action.action_id,
        capability_id=action.capability_id,
        capability_version=action.capability_version,
        parameters=tuple(
            ApprovalPreviewParameter(
                name=item.name,
                value=item.value,
            )
            for item in sorted(
                action.arguments,
                key=lambda item: item.name,
            )
        ),
        resource_ids=resources,
        dependency_action_ids=tuple(sorted(action.dependencies)),
        verification_codes=verification_codes,
        timeout_seconds=action.timeout_seconds,
        risk_tier=decision.risk_tier.value,
        reason_codes=decision.reason_codes,
        policy_reference_id=decision.policy_reference_id,
        policy_version=decision.policy_version,
        action_digest=action_digest,
    )
    return PendingApprovalRequest(
        approval_id=_approval_id(
            task_id,
            action.action_id,
            action_digest,
        ),
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        action_id=action.action_id,
        action_digest=action_digest,
        decision_id=decision.decision_id,
        risk_tier=decision.risk_tier.value,
        policy_reference_id=decision.policy_reference_id,
        policy_version=decision.policy_version,
        preview=preview,
        expires_after_seconds=settings.expires_after_seconds,
    )


def _validate_record(
    value: object,
    request: PendingApprovalRequest,
) -> PendingApprovalRecord:
    if not isinstance(value, PendingApprovalRecord):
        raise ApprovalPauseError("approval_persistence_invalid")
    try:
        record = PendingApprovalRecord.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise ApprovalPauseError("approval_persistence_invalid") from None
    if record.request != request:
        raise ApprovalPauseError("approval_persistence_conflict")
    return record


def _json_bytes(value: object, *, error_code: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError):
        raise ApprovalPauseError(error_code) from None


def _interrupt_payload(
    record: PendingApprovalRecord,
) -> ApprovalInterruptPayload:
    request = record.request
    return ApprovalInterruptPayload(
        approval_id=request.approval_id,
        task_id=request.task_id,
        thread_id=request.thread_id,
        actor_id=request.actor_id,
        device_id=request.device_id,
        action_digest=request.action_digest,
        issued_at=record.issued_at,
        expires_at=record.expires_at,
        preview=request.preview,
    )


def _validate_resume_value(
    value: object,
    *,
    max_bytes: int,
) -> dict[str, str]:
    if len(
        _json_bytes(
            value,
            error_code="approval_resume_payload_invalid",
        )
    ) > max_bytes:
        raise ApprovalPauseError("approval_resume_payload_invalid")
    try:
        candidate = ApprovalResumeCandidate.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise ApprovalPauseError("approval_resume_payload_invalid") from None
    return candidate.model_dump(mode="json")


async def pauseForApproval(
    state: Mapping[str, Any],
    *,
    service: ApprovalPauseService,
) -> dict[str, Any]:
    """Persist one exact approval idempotently, then durably interrupt."""

    settings = service.settings
    _validate_settings(settings)
    (
        task_id,
        thread_id,
        actor_id,
        device_id,
        plan,
        decisions,
    ) = _validate_state(state)
    action, decision = _selected_action(plan, decisions)
    request = _build_request(
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        plan=plan,
        action=action,
        decision=decision,
        settings=settings,
    )
    try:
        raw_record = await service.store.create_or_get_pending_approval(
            request
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        raise ApprovalPauseError("approval_persistence_unavailable") from None
    record = _validate_record(raw_record, request)
    interrupt_payload = _interrupt_payload(record).model_dump(mode="json")
    if len(
        _json_bytes(
            interrupt_payload,
            error_code="approval_interrupt_payload_invalid",
        )
    ) > settings.max_interrupt_payload_bytes:
        raise ApprovalPauseError("approval_interrupt_payload_invalid")

    # Do not catch this call: LangGraph raises its control-flow interrupt here.
    resume_value = service.interrupt_fn(interrupt_payload)
    safe_resume = _validate_resume_value(
        resume_value,
        max_bytes=settings.max_resume_payload_bytes,
    )
    return {
        "pending_approval": {
            **record.model_dump(mode="json"),
            "resume": safe_resume,
        },
        "status": "awaiting_approval",
    }
