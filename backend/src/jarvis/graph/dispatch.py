"""Replay-safe, resource-bounded action dispatch for Global ID 120009."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from jarvis.graph.approval import (
    ACTION_DIGEST_PATTERN,
    APPROVAL_ID_PATTERN,
    EVENT_ID_PATTERN,
    _digest_action,
)
from jarvis.graph.approval_resume import (
    RESOLUTION_ID_PATTERN,
    ApprovalResult,
)
from jarvis.graph.context import REFERENCE_VERSION_PATTERN
from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)
from jarvis.graph.plan import (
    CAPABILITY_ID_PATTERN,
    IDENTIFIER_VALUE_PATTERN,
    PARAMETER_NAME_PATTERN,
    RESOURCE_ID_PATTERN,
    VERIFICATION_CODE_PATTERN,
    PlanActionDraft,
    PlanDraft,
    ScalarValue,
)
from jarvis.graph.policy import PolicyDecision, PolicyDecisionKind


DISPATCH_ID_PATTERN = re.compile(r"^dsp_[0-9a-f]{24}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")
OUTBOX_ID_PATTERN = re.compile(r"^out_[A-Za-z0-9_-]{8,128}$")
LEASE_ID_PATTERN = re.compile(r"^lse_[A-Za-z0-9_-]{8,128}$")
RECEIPT_ID_PATTERN = re.compile(r"^rcp_[A-Za-z0-9_-]{8,128}$")
ACTION_REQUEST_VERSION = "1.0"
ACTION_RESULT_VERSION = "1.0"


class ActionDispatchError(RuntimeError):
    """A content-free dispatch failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS action dispatch failed: {code}")


class ActionDispatchCapacityError(RuntimeError):
    """The atomic store cannot reserve bounded dispatch capacity."""


class ActionRequestArgument(BaseModel):
    """One exact scalar binding sent to the trusted executor."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    name: str = Field(pattern=PARAMETER_NAME_PATTERN.pattern)
    value: ScalarValue

    @field_validator("value")
    @classmethod
    def validate_string_value(cls, value: ScalarValue) -> ScalarValue:
        if isinstance(value, str) and not IDENTIFIER_VALUE_PATTERN.fullmatch(
            value
        ):
            raise ValueError("action request strings must be identifiers")
        return value


class ActionPolicyProof(BaseModel):
    """Minimal preliminary policy evidence bound to one action request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(pattern=r"^pdc_[0-9a-f]{24}$")
    decision: Literal["allow", "ask"]
    risk_tier: str = Field(pattern=r"^r[0-3]$")
    policy_reference_id: str = Field(pattern=r"^pol_[A-Za-z0-9_-]{8,128}$")
    policy_version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    grant_reference_id: str | None = Field(
        default=None,
        pattern=r"^grt_[A-Za-z0-9_-]{8,128}$",
    )


class ActionApprovalProof(BaseModel):
    """Consumed approval evidence for an exact ask action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(pattern=APPROVAL_ID_PATTERN.pattern)
    resolution_id: str = Field(pattern=RESOLUTION_ID_PATTERN)
    action_digest: str = Field(pattern=ACTION_DIGEST_PATTERN.pattern)
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def validate_decided_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("approval decision time must be timezone-aware")
        return value


class PriorActionResult(BaseModel):
    """Minimal collected result used only for dependency readiness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["action.result"] = "action.result"
    version: Literal["1.0"] = ACTION_RESULT_VERSION
    dispatch_id: str = Field(pattern=DISPATCH_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    receipt_id: str = Field(pattern=RECEIPT_ID_PATTERN.pattern)
    outcome: Literal["succeeded", "failed", "cancelled", "uncertain"]
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("action completion time must be timezone-aware")
        return value


class ActionDispatchRequest(BaseModel):
    """Strict JSON-safe outbox/WebSocket action request."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    type: Literal["action.request"] = "action.request"
    version: Literal["1.0"] = ACTION_REQUEST_VERSION
    dispatch_id: str = Field(pattern=DISPATCH_ID_PATTERN.pattern)
    idempotency_key: str = Field(pattern=IDEMPOTENCY_KEY_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    capability_id: str = Field(pattern=CAPABILITY_ID_PATTERN.pattern)
    capability_version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    arguments: tuple[ActionRequestArgument, ...] = Field(
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
    policy: ActionPolicyProof
    approval: ActionApprovalProof | None = None

    @model_validator(mode="after")
    def validate_request_members(self) -> ActionDispatchRequest:
        names = [item.name for item in self.arguments]
        if (
            len(names) != len(set(names))
            or tuple(names) != tuple(sorted(names))
            or len(self.resource_ids) != len(set(self.resource_ids))
            or tuple(self.resource_ids) != tuple(sorted(self.resource_ids))
            or any(
                not RESOURCE_ID_PATTERN.fullmatch(item)
                for item in self.resource_ids
            )
            or len(self.dependency_action_ids)
            != len(set(self.dependency_action_ids))
            or tuple(self.dependency_action_ids)
            != tuple(sorted(self.dependency_action_ids))
            or len(self.verification_codes)
            != len(set(self.verification_codes))
            or tuple(self.verification_codes)
            != tuple(sorted(self.verification_codes))
            or any(
                not VERIFICATION_CODE_PATTERN.fullmatch(item)
                for item in self.verification_codes
            )
            or (
                self.policy.decision == "ask"
                and self.approval is None
            )
            or (
                self.policy.decision == "allow"
                and self.approval is not None
            )
        ):
            raise ValueError("action request members are invalid")
        return self


class ActionDispatchLimits(BaseModel):
    """Concurrency limits enforced atomically by the persistence adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_in_flight_actions: int = Field(ge=1, le=64)
    max_in_flight_per_resource: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def validate_relative_limit(self) -> ActionDispatchLimits:
        if self.max_in_flight_per_resource > self.max_in_flight_actions:
            raise ValueError("resource limit exceeds global limit")
        return self


class ActionDispatchRecord(BaseModel):
    """Atomic action-state, event, outbox and resource-lease identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ActionDispatchRequest
    event_id: str = Field(pattern=EVENT_ID_PATTERN.pattern)
    outbox_id: str = Field(pattern=OUTBOX_ID_PATTERN.pattern)
    lease_id: str = Field(pattern=LEASE_ID_PATTERN.pattern)
    status: Literal["queued"] = "queued"
    queued_at: datetime
    lease_expires_at: datetime
    reserved_resource_ids: tuple[str, ...] = Field(default=(), max_length=12)

    @model_validator(mode="after")
    def validate_record(self) -> ActionDispatchRecord:
        if (
            self.queued_at.tzinfo is None
            or self.lease_expires_at.tzinfo is None
            or self.lease_expires_at <= self.queued_at
            or self.reserved_resource_ids != self.request.resource_ids
        ):
            raise ValueError("action dispatch record is invalid")
        return self


class ActionDispatchStore(Protocol):
    async def create_or_get_dispatch(
        self,
        request: ActionDispatchRequest,
        *,
        limits: ActionDispatchLimits,
    ) -> ActionDispatchRecord:
        """Atomically reserve capacity and create state/event/outbox once."""


@dataclass(frozen=True, slots=True)
class ActionDispatchSettings:
    max_in_flight_actions: int = 16
    max_in_flight_per_resource: int = 1
    lease_grace_seconds: int = 30
    max_request_bytes: int = 32 * 1024


@dataclass(frozen=True, slots=True)
class ActionDispatchService:
    store: ActionDispatchStore
    settings: ActionDispatchSettings = ActionDispatchSettings()


def _validate_settings(
    settings: ActionDispatchSettings,
) -> ActionDispatchLimits:
    if (
        settings.max_in_flight_actions < 1
        or settings.max_in_flight_actions > 64
        or settings.max_in_flight_per_resource < 1
        or settings.max_in_flight_per_resource > 8
        or settings.max_in_flight_per_resource
        > settings.max_in_flight_actions
        or settings.lease_grace_seconds < 0
        or settings.lease_grace_seconds > 300
        or settings.max_request_bytes < 1_024
        or settings.max_request_bytes > 64 * 1024
    ):
        raise ActionDispatchError("action_dispatch_settings_incompatible")
    return ActionDispatchLimits(
        max_in_flight_actions=settings.max_in_flight_actions,
        max_in_flight_per_resource=settings.max_in_flight_per_resource,
    )


def _load_state(
    state: Mapping[str, Any],
    *,
    runtime_thread_id: str,
) -> tuple[
    str,
    str,
    str,
    str,
    PlanDraft,
    tuple[PolicyDecision, ...],
    tuple[PriorActionResult, ...],
    ApprovalResult | None,
]:
    if state.get("status") != "executing":
        raise ActionDispatchError("action_dispatch_state_invalid")
    task_id = state.get("task_id")
    thread_id = state.get("thread_id")
    actor_id = state.get("actor_id")
    device_id = state.get("device_id")
    if (
        not isinstance(task_id, str)
        or not TASK_ID_PATTERN.fullmatch(task_id)
        or not isinstance(thread_id, str)
        or not THREAD_ID_PATTERN.fullmatch(thread_id)
        or not isinstance(runtime_thread_id, str)
        or not THREAD_ID_PATTERN.fullmatch(runtime_thread_id)
        or not isinstance(actor_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(actor_id)
        or not isinstance(device_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(device_id)
    ):
        raise ActionDispatchError("action_dispatch_identity_invalid")
    if runtime_thread_id != thread_id:
        raise ActionDispatchError("action_dispatch_thread_mismatch")
    try:
        plan = PlanDraft.model_validate(state.get("plan"))
        decisions = tuple(
            PolicyDecision.model_validate(item)
            for item in state.get("policy_decisions", ())
        )
        results = tuple(
            PriorActionResult.model_validate(item)
            for item in state.get("action_results", ())
        )
        approval = (
            ApprovalResult.model_validate(state["pending_approval"])
            if state.get("pending_approval") is not None
            else None
        )
    except (ValidationError, TypeError, ValueError):
        raise ActionDispatchError("action_dispatch_contract_invalid") from None
    if plan.schema_version != "1.0":
        raise ActionDispatchError("action_dispatch_contract_invalid")
    return (
        task_id,
        thread_id,
        actor_id,
        device_id,
        plan,
        decisions,
        results,
        approval,
    )


def _validate_relations(
    plan: PlanDraft,
    decisions: tuple[PolicyDecision, ...],
    results: tuple[PriorActionResult, ...],
) -> dict[str, PolicyDecision]:
    action_ids = tuple(action.action_id for action in plan.actions)
    decision_ids = tuple(item.action_id for item in decisions)
    result_ids = tuple(item.action_id for item in results)
    known = set(action_ids)
    if (
        not action_ids
        or len(action_ids) != len(set(action_ids))
        or len(decision_ids) != len(set(decision_ids))
        or set(decision_ids) != known
        or any(
            item.decision is PolicyDecisionKind.DENY
            for item in decisions
        )
        or len(result_ids) != len(set(result_ids))
        or not set(result_ids).issubset(known)
    ):
        raise ActionDispatchError("action_dispatch_contract_invalid")
    return {item.action_id: item for item in decisions}


def _select_action(
    plan: PlanDraft,
    results: tuple[PriorActionResult, ...],
) -> PlanActionDraft:
    by_action = {item.action_id: item for item in results}
    successful = {
        item.action_id
        for item in results
        if item.outcome == "succeeded"
    }
    for action in plan.actions:
        if (
            action.action_id not in by_action
            and set(action.dependencies).issubset(successful)
        ):
            return action
    if len(by_action) == len(plan.actions):
        raise ActionDispatchError("action_dispatch_plan_complete")
    raise ActionDispatchError("action_dispatch_dependencies_unsatisfied")


def _approval_proof(
    action: PlanActionDraft,
    decision: PolicyDecision,
    approval: ApprovalResult | None,
    *,
    task_id: str,
    thread_id: str,
    actor_id: str,
    device_id: str,
    verification_codes: tuple[str, ...],
) -> ActionApprovalProof | None:
    if decision.decision is PolicyDecisionKind.ALLOW:
        return None
    if (
        decision.decision is not PolicyDecisionKind.ASK
        or approval is None
        or approval.outcome != "approved"
        or approval.thread_id != thread_id
        or approval.action_id != action.action_id
    ):
        raise ActionDispatchError("action_dispatch_approval_invalid")
    expected_digest = _digest_action(
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        action=action,
        decision=decision,
        verification_codes=verification_codes,
    )
    if not hmac.compare_digest(
        approval.action_digest,
        expected_digest,
    ):
        raise ActionDispatchError("action_dispatch_approval_invalid")
    return ActionApprovalProof(
        approval_id=approval.approval_id,
        resolution_id=approval.resolution_id,
        action_digest=approval.action_digest,
        decided_at=approval.decided_at,
    )


def _canonical_payload(
    *,
    task_id: str,
    thread_id: str,
    actor_id: str,
    device_id: str,
    action: PlanActionDraft,
    decision: PolicyDecision,
    verification_codes: tuple[str, ...],
    approval: ActionApprovalProof | None,
) -> dict[str, Any]:
    return {
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
            "verification_codes": list(verification_codes),
            "timeout_seconds": action.timeout_seconds,
        },
        "policy": {
            "decision_id": decision.decision_id,
            "decision": decision.decision.value,
            "risk_tier": decision.risk_tier.value,
            "policy_reference_id": decision.policy_reference_id,
            "policy_version": decision.policy_version,
            "grant_reference_id": decision.grant_reference_id,
        },
        "approval": (
            approval.model_dump(mode="json")
            if approval is not None
            else None
        ),
    }


def _stable_dispatch_identity(
    task_id: str,
    action_id: str,
    canonical: str,
) -> tuple[str, str]:
    dispatch_seed = f"{task_id}:{action_id}".encode()
    dispatch_id = "dsp_" + hashlib.sha256(dispatch_seed).hexdigest()[:24]
    return dispatch_id, hashlib.sha256(canonical.encode()).hexdigest()


def _build_request(
    *,
    task_id: str,
    thread_id: str,
    actor_id: str,
    device_id: str,
    plan: PlanDraft,
    action: PlanActionDraft,
    decision: PolicyDecision,
    approval: ApprovalResult | None,
) -> ActionDispatchRequest:
    verification_codes = tuple(
        sorted(
            criterion.verification_code
            for criterion in plan.success_criteria
            if criterion.action_id == action.action_id
        )
    )
    if not verification_codes:
        raise ActionDispatchError("action_dispatch_contract_invalid")
    proof = _approval_proof(
        action,
        decision,
        approval,
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        verification_codes=verification_codes,
    )
    canonical_payload = _canonical_payload(
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        action=action,
        decision=decision,
        verification_codes=verification_codes,
        approval=proof,
    )
    canonical = json.dumps(
        canonical_payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    dispatch_id, idempotency_key = _stable_dispatch_identity(
        task_id,
        action.action_id,
        canonical,
    )
    resource_ids = tuple(
        sorted(
            {
                argument.value
                for argument in action.arguments
                if (
                    isinstance(argument.value, str)
                    and RESOURCE_ID_PATTERN.fullmatch(argument.value)
                )
            }
        )
    )
    return ActionDispatchRequest(
        dispatch_id=dispatch_id,
        idempotency_key=idempotency_key,
        task_id=task_id,
        thread_id=thread_id,
        actor_id=actor_id,
        device_id=device_id,
        action_id=action.action_id,
        capability_id=action.capability_id,
        capability_version=action.capability_version,
        arguments=tuple(
            ActionRequestArgument(name=item.name, value=item.value)
            for item in sorted(
                action.arguments,
                key=lambda item: item.name,
            )
        ),
        resource_ids=resource_ids,
        dependency_action_ids=tuple(sorted(action.dependencies)),
        verification_codes=verification_codes,
        timeout_seconds=action.timeout_seconds,
        policy=ActionPolicyProof(
            decision_id=decision.decision_id,
            decision=decision.decision.value,
            risk_tier=decision.risk_tier.value,
            policy_reference_id=decision.policy_reference_id,
            policy_version=decision.policy_version,
            grant_reference_id=decision.grant_reference_id,
        ),
        approval=proof,
    )


def _request_bytes(request: ActionDispatchRequest) -> bytes:
    try:
        return json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError):
        raise ActionDispatchError("action_dispatch_request_invalid") from None


def _validate_record(
    value: object,
    request: ActionDispatchRequest,
    settings: ActionDispatchSettings,
) -> ActionDispatchRecord:
    if not isinstance(value, ActionDispatchRecord):
        raise ActionDispatchError("action_dispatch_record_invalid")
    try:
        record = ActionDispatchRecord.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise ActionDispatchError("action_dispatch_record_invalid") from None
    expected_lease_seconds = (
        request.timeout_seconds + settings.lease_grace_seconds
    )
    if (
        record.request != request
        or (
            record.lease_expires_at - record.queued_at
        ).total_seconds()
        != expected_lease_seconds
    ):
        raise ActionDispatchError("action_dispatch_record_conflict")
    return record


async def dispatchAction(
    state: Mapping[str, Any],
    *,
    service: ActionDispatchService,
    runtime_thread_id: str,
) -> dict[str, Any]:
    """Persist one exact dependency-ready action request without executing it."""

    limits = _validate_settings(service.settings)
    (
        task_id,
        thread_id,
        actor_id,
        device_id,
        plan,
        decisions,
        results,
        approval,
    ) = _load_state(state, runtime_thread_id=runtime_thread_id)
    by_action = _validate_relations(plan, decisions, results)
    action = _select_action(plan, results)
    try:
        request = _build_request(
            task_id=task_id,
            thread_id=thread_id,
            actor_id=actor_id,
            device_id=device_id,
            plan=plan,
            action=action,
            decision=by_action[action.action_id],
            approval=approval,
        )
    except (ValidationError, TypeError, ValueError):
        raise ActionDispatchError("action_dispatch_contract_invalid") from None
    if len(_request_bytes(request)) > service.settings.max_request_bytes:
        raise ActionDispatchError("action_dispatch_request_too_large")
    try:
        raw_record = await service.store.create_or_get_dispatch(
            request,
            limits=limits,
        )
    except asyncio.CancelledError:
        raise
    except ActionDispatchCapacityError:
        raise ActionDispatchError("action_dispatch_capacity_exhausted") from None
    except Exception:
        raise ActionDispatchError("action_dispatch_unavailable") from None
    _validate_record(raw_record, request, service.settings)
    return {"status": "executing"}
