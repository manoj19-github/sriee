"""Immutable executor-result collection for Global ID 120010."""

from __future__ import annotations

import asyncio
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

from jarvis.graph.approval import EVENT_ID_PATTERN
from jarvis.graph.dispatch import (
    IDEMPOTENCY_KEY_PATTERN,
    RECEIPT_ID_PATTERN,
    ActionDispatchRecord,
    PriorActionResult,
)
from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
    THREAD_ID_PATTERN,
)
from jarvis.graph.plan import PlanDraft


ATTEMPT_ID_PATTERN = re.compile(r"^atm_[A-Za-z0-9_-]{8,128}$")
ARTIFACT_ID_PATTERN = re.compile(r"^art_[A-Za-z0-9_-]{8,128}$")
RESULT_ERROR_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
EXECUTOR_RESULT_VERSION = "1.0"


class ActionResultError(RuntimeError):
    """A content-free result failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS action result collection failed: {code}")


class ActionResultNotFoundError(RuntimeError):
    """No actor/device-owned pending dispatch matches the result."""


class ActionResultCorrelationError(RuntimeError):
    """The result does not match the pending dispatch contract."""


class ActionResultConflictError(RuntimeError):
    """A different result already owns this dispatch or receipt."""


class ExecutorActionResult(BaseModel):
    """Bounded desktop-to-backend action result with no raw output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["action.result"] = "action.result"
    version: Literal["1.0"] = EXECUTOR_RESULT_VERSION
    dispatch_id: str = Field(pattern=r"^dsp_[0-9a-f]{24}$")
    idempotency_key: str = Field(pattern=IDEMPOTENCY_KEY_PATTERN.pattern)
    task_id: str = Field(pattern=TASK_ID_PATTERN.pattern)
    thread_id: str = Field(pattern=THREAD_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    attempt_id: str = Field(pattern=ATTEMPT_ID_PATTERN.pattern)
    receipt_id: str = Field(pattern=RECEIPT_ID_PATTERN.pattern)
    executor_device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    outcome: Literal["succeeded", "failed", "cancelled", "uncertain"]
    started_at: datetime
    completed_at: datetime
    artifact_reference_ids: tuple[str, ...] = Field(
        default=(),
        max_length=16,
    )
    error_code: str | None = Field(
        default=None,
        pattern=RESULT_ERROR_CODE_PATTERN.pattern,
    )

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("executor result timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_result(self) -> ExecutorActionResult:
        if (
            self.completed_at < self.started_at
            or len(self.artifact_reference_ids)
            != len(set(self.artifact_reference_ids))
            or any(
                not ARTIFACT_ID_PATTERN.fullmatch(item)
                for item in self.artifact_reference_ids
            )
            or (
                self.outcome == "succeeded"
                and self.error_code is not None
            )
            or (
                self.outcome != "succeeded"
                and self.error_code is None
            )
        ):
            raise ValueError("executor result is invalid")
        return self


class ActionResultCollectionRequest(BaseModel):
    """Identity-bound request handled by the atomic result store."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    candidate: ExecutorActionResult


class ActionResultCollectionRecord(BaseModel):
    """Authoritative result/event projection returned by atomic persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ActionResultCollectionRequest
    dispatch: ActionDispatchRecord
    result: PriorActionResult
    event_id: str = Field(pattern=EVENT_ID_PATTERN.pattern)
    collected_at: datetime
    created: bool

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("collection time must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_correlations(self) -> ActionResultCollectionRecord:
        candidate = self.request.candidate
        dispatch = self.dispatch
        dispatched = dispatch.request
        duration = (
            candidate.completed_at - candidate.started_at
        ).total_seconds()
        late_or_overrun = (
            candidate.completed_at > dispatch.lease_expires_at
            or duration > dispatched.timeout_seconds
        )
        expected_outcome = (
            "uncertain" if late_or_overrun else candidate.outcome
        )
        if (
            self.request.actor_id != dispatched.actor_id
            or candidate.dispatch_id != dispatched.dispatch_id
            or candidate.idempotency_key != dispatched.idempotency_key
            or candidate.task_id != dispatched.task_id
            or candidate.thread_id != dispatched.thread_id
            or candidate.action_id != dispatched.action_id
            or candidate.executor_device_id != dispatched.device_id
            or candidate.started_at < dispatch.queued_at
            or self.collected_at < candidate.completed_at
            or self.result.dispatch_id != candidate.dispatch_id
            or self.result.action_id != candidate.action_id
            or self.result.receipt_id != candidate.receipt_id
            or self.result.completed_at != candidate.completed_at
            or self.result.outcome != expected_outcome
        ):
            raise ValueError("action result correlations are invalid")
        return self


class ActionResultStore(Protocol):
    async def collect_or_get_action_result(
        self,
        request: ActionResultCollectionRequest,
    ) -> ActionResultCollectionRecord:
        """Atomically correlate, persist event/result and release the lease."""


@dataclass(frozen=True, slots=True)
class ActionResultSettings:
    max_result_bytes: int = 16 * 1024


@dataclass(frozen=True, slots=True)
class ActionResultService:
    store: ActionResultStore
    settings: ActionResultSettings = ActionResultSettings()


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError):
        raise ActionResultError("action_result_payload_invalid") from None


def _validate_settings(settings: ActionResultSettings) -> None:
    if (
        settings.max_result_bytes < 512
        or settings.max_result_bytes > 32 * 1024
    ):
        raise ActionResultError("action_result_settings_incompatible")


def _load_state(
    state: Mapping[str, Any],
    *,
    runtime_thread_id: str,
) -> tuple[str, str, str, str, PlanDraft, tuple[PriorActionResult, ...]]:
    if state.get("status") != "executing":
        raise ActionResultError("action_result_state_invalid")
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
        raise ActionResultError("action_result_identity_invalid")
    if runtime_thread_id != thread_id:
        raise ActionResultError("action_result_thread_mismatch")
    try:
        plan = PlanDraft.model_validate(state.get("plan"))
        results = tuple(
            PriorActionResult.model_validate(item)
            for item in state.get("action_results", ())
        )
    except (ValidationError, TypeError, ValueError):
        raise ActionResultError("action_result_state_contract_invalid") from None
    action_ids = tuple(action.action_id for action in plan.actions)
    result_actions = tuple(item.action_id for item in results)
    receipts = tuple(item.receipt_id for item in results)
    dispatches = tuple(item.dispatch_id for item in results)
    if (
        plan.schema_version != "1.0"
        or not action_ids
        or len(action_ids) != len(set(action_ids))
        or len(result_actions) != len(set(result_actions))
        or len(receipts) != len(set(receipts))
        or len(dispatches) != len(set(dispatches))
        or not set(result_actions).issubset(action_ids)
    ):
        raise ActionResultError("action_result_state_contract_invalid")
    return task_id, thread_id, actor_id, device_id, plan, results


def _validate_candidate(
    value: object,
    *,
    max_bytes: int,
    task_id: str,
    thread_id: str,
    device_id: str,
    plan: PlanDraft,
) -> ExecutorActionResult:
    if len(_json_bytes(value)) > max_bytes:
        raise ActionResultError("action_result_payload_too_large")
    try:
        candidate = ExecutorActionResult.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise ActionResultError("action_result_payload_invalid") from None
    if (
        candidate.task_id != task_id
        or candidate.thread_id != thread_id
        or candidate.executor_device_id != device_id
        or candidate.action_id
        not in {action.action_id for action in plan.actions}
    ):
        raise ActionResultError("action_result_candidate_mismatch")
    return candidate


def _validate_record(
    value: object,
    request: ActionResultCollectionRequest,
) -> ActionResultCollectionRecord:
    if not isinstance(value, ActionResultCollectionRecord):
        raise ActionResultError("action_result_record_invalid")
    try:
        record = ActionResultCollectionRecord.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise ActionResultError("action_result_record_invalid") from None
    if record.request != request:
        raise ActionResultError("action_result_record_conflict")
    return record


def _state_delta(
    record: ActionResultCollectionRecord,
    existing: tuple[PriorActionResult, ...],
) -> dict[str, Any]:
    by_action = {
        item.action_id: item
        for item in existing
    }
    current = by_action.get(record.result.action_id)
    if current is not None and current != record.result:
        raise ActionResultError("action_result_state_conflict")
    if current is not None:
        return {
            "action_results": [],
            "status": "verifying",
        }
    return {
        "action_results": [
            record.result.model_dump(mode="json")
        ],
        "status": "verifying",
    }


async def collectActionResult(
    state: Mapping[str, Any],
    candidate: object,
    *,
    service: ActionResultService,
    runtime_thread_id: str,
) -> dict[str, Any]:
    """Correlate one executor receipt and append its immutable projection once."""

    _validate_settings(service.settings)
    (
        task_id,
        thread_id,
        actor_id,
        device_id,
        plan,
        existing,
    ) = _load_state(state, runtime_thread_id=runtime_thread_id)
    result = _validate_candidate(
        candidate,
        max_bytes=service.settings.max_result_bytes,
        task_id=task_id,
        thread_id=thread_id,
        device_id=device_id,
        plan=plan,
    )
    request = ActionResultCollectionRequest(
        actor_id=actor_id,
        candidate=result,
    )
    try:
        raw_record = await service.store.collect_or_get_action_result(
            request
        )
    except asyncio.CancelledError:
        raise
    except ActionResultNotFoundError:
        raise ActionResultError("action_result_not_found") from None
    except ActionResultCorrelationError:
        raise ActionResultError("action_result_candidate_mismatch") from None
    except ActionResultConflictError:
        raise ActionResultError("action_result_receipt_conflict") from None
    except Exception:
        raise ActionResultError("action_result_unavailable") from None
    record = _validate_record(raw_record, request)
    return _state_delta(record, existing)
