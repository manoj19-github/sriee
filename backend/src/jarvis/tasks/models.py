"""Typed task creation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskInputType(StrEnum):
    TEXT = "text"
    TRANSCRIPT = "transcript"


class TaskStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"
    EXPIRED = "expired"


class TaskOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"
    EXPIRED = "expired"


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: TaskInputType
    content: str = Field(min_length=1, max_length=16_000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task content cannot be blank")
        if "\x00" in value:
            raise ValueError("task content cannot contain NUL")
        return value


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: TaskInput


class CreateTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: TaskStatus
    created: bool
    event_sequence: int
    accepted_at: datetime


class PlanSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    revision: int = Field(ge=1)
    status: str = Field(min_length=1, max_length=64)


class PendingApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(pattern=r"^apr_[A-Za-z0-9_-]{8,128}$")
    action_id: str = Field(pattern=r"^act_[A-Za-z0-9_-]{8,128}$")
    risk_tier: str = Field(pattern=r"^R[0-4]$")
    expires_at: datetime


class ArtifactReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: str = Field(pattern=r"^art_[A-Za-z0-9_-]{8,128}$")
    requires_separate_authorization: bool = True


class TaskResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: TaskOutcome
    summary: str = Field(min_length=1, max_length=2_000)
    artifact_references: tuple[ArtifactReferenceResponse, ...] = ()


class TaskSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: TaskStatus
    plan: PlanSnapshotResponse | None
    pending_approval: PendingApprovalResponse | None
    result: TaskResultResponse | None
    created_at: datetime
    updated_at: datetime


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(pattern=r"^evt_[A-Za-z0-9_-]{8,128}$")
    task_id: str
    sequence: int = Field(ge=1)
    type: str = Field(min_length=1, max_length=128)
    schema_version: str = Field(min_length=1, max_length=32)
    occurred_at: datetime
    correlation_id: str
    data: dict[str, Any]


class TaskEventPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    events: tuple[TaskEventResponse, ...]
    next_cursor: int = Field(ge=0)
    has_more: bool


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    actor_id: str
    device_id: str
    contract_version: str
    input_type: TaskInputType
    input_content: str
    status: TaskStatus
    idempotency_key: str
    request_hash: str
    correlation_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TaskEvent:
    event_id: str
    task_id: str
    sequence: int
    event_type: str
    schema_version: str
    occurred_at: datetime
    correlation_id: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    outbox_id: str
    event_type: str
    schema_version: str
    aggregate_id: str
    occurred_at: datetime
    correlation_id: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TaskCreationBundle:
    task: TaskRecord
    event: TaskEvent
    outbox: OutboxRecord


@dataclass(frozen=True, slots=True)
class TaskCreationOutcome:
    task: TaskRecord
    event: TaskEvent
    outbox: OutboxRecord
    created: bool


@dataclass(frozen=True, slots=True)
class PlanProjection:
    revision: int
    status: str


@dataclass(frozen=True, slots=True)
class PendingApprovalProjection:
    approval_id: str
    action_id: str
    risk_tier: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TaskResultProjection:
    outcome: TaskOutcome
    summary: str
    artifact_reference_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskProjectionRecord:
    task_id: str
    actor_id: str
    device_id: str
    status: TaskStatus
    plan: PlanProjection | None
    pending_approval: PendingApprovalProjection | None
    result: TaskResultProjection | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TaskEventPageRecord:
    task_id: str
    events: tuple[TaskEvent, ...]
    next_cursor: int
    has_more: bool
