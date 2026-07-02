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
