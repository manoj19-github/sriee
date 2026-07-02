"""Create-task application service."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from jarvis.security.desktop_auth import AuthenticatedPrincipal
from jarvis.tasks.models import (
    CreateTaskRequest,
    OutboxRecord,
    TaskCreationBundle,
    TaskCreationOutcome,
    TaskEvent,
    TaskRecord,
    TaskStatus,
)
from jarvis.tasks.repository import TaskRepository


SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")


class InvalidRequestIdentifierError(ValueError):
    """An idempotency or correlation identifier is unsafe or malformed."""


class OutboxNotifier(Protocol):
    async def notify(self, task_id: str) -> None:
        """Wake the dispatcher after a durable outbox record is committed."""


class InMemoryOutboxNotifier:
    def __init__(self, *, fail: bool = False) -> None:
        self.task_ids: list[str] = []
        self.fail = fail

    async def notify(self, task_id: str) -> None:
        if self.fail:
            raise RuntimeError("dispatcher unavailable")
        self.task_ids.append(task_id)


class TaskCreationService:
    def __init__(
        self,
        repository: TaskRepository,
        notifier: OutboxNotifier,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._notifier = notifier
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        request: CreateTaskRequest,
        principal: AuthenticatedPrincipal,
        idempotency_key: str,
        correlation_id: str,
    ) -> TaskCreationOutcome:
        safe_idempotency_key = self._validate_identifier(idempotency_key)
        safe_correlation_id = self._validate_identifier(correlation_id)
        now = self._clock()
        request_hash = self._hash_request(request, principal)
        task_id = f"tsk_{uuid4().hex}"
        event_id = f"evt_{uuid4().hex}"
        outbox_id = f"out_{uuid4().hex}"

        task = TaskRecord(
            task_id=task_id,
            actor_id=principal.actor_id,
            device_id=principal.device_id,
            contract_version=str(principal.contract_version),
            input_type=request.input.type,
            input_content=request.input.content,
            status=TaskStatus.CREATED,
            idempotency_key=safe_idempotency_key,
            request_hash=request_hash,
            correlation_id=safe_correlation_id,
            created_at=now,
        )
        event = TaskEvent(
            event_id=event_id,
            task_id=task_id,
            sequence=1,
            event_type="task.created",
            schema_version="1.0",
            occurred_at=now,
            correlation_id=safe_correlation_id,
            data={
                "input_type": request.input.type.value,
                "contract_version": str(principal.contract_version),
            },
        )
        outbox = OutboxRecord(
            outbox_id=outbox_id,
            event_type="graph.task.requested",
            schema_version="1.0",
            aggregate_id=task_id,
            occurred_at=now,
            correlation_id=safe_correlation_id,
            data={
                "task_id": task_id,
                "event_sequence": 1,
            },
        )
        outcome = await self._repository.create_or_get(
            TaskCreationBundle(task=task, event=event, outbox=outbox)
        )
        if outcome.created:
            try:
                await self._notifier.notify(outcome.task.task_id)
            except Exception:
                # The committed outbox record remains the durable dispatch source.
                pass
        return outcome

    @staticmethod
    def _validate_identifier(value: str) -> str:
        normalized = value.strip()
        if not SAFE_REQUEST_ID.fullmatch(normalized):
            raise InvalidRequestIdentifierError
        return normalized

    @staticmethod
    def _hash_request(
        request: CreateTaskRequest,
        principal: AuthenticatedPrincipal,
    ) -> str:
        canonical = json.dumps(
            {
                "contract_version": str(principal.contract_version),
                "input": request.input.model_dump(mode="json"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
