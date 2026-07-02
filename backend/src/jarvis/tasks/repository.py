"""Atomic task/event/outbox repository contract."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Protocol

from jarvis.tasks.models import (
    OutboxRecord,
    TaskCreationBundle,
    TaskCreationOutcome,
    TaskEvent,
    TaskRecord,
)


class IdempotencyConflictError(RuntimeError):
    """The idempotency key already belongs to a different request payload."""


class TaskRepository(Protocol):
    async def create_or_get(
        self,
        bundle: TaskCreationBundle,
    ) -> TaskCreationOutcome:
        """Atomically create task/event/outbox or return the matching task."""


class InMemoryTaskRepository:
    """Concurrency-safe development/test implementation of the atomic contract."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_idempotency: dict[
            tuple[str, str, str],
            TaskCreationOutcome,
        ] = {}
        self._tasks: dict[str, TaskRecord] = {}
        self._events: list[TaskEvent] = []
        self._outbox: list[OutboxRecord] = []

    async def create_or_get(
        self,
        bundle: TaskCreationBundle,
    ) -> TaskCreationOutcome:
        scope = (
            bundle.task.actor_id,
            bundle.task.device_id,
            bundle.task.idempotency_key,
        )
        async with self._lock:
            existing = self._by_idempotency.get(scope)
            if existing is not None:
                if existing.task.request_hash != bundle.task.request_hash:
                    raise IdempotencyConflictError
                return replace(existing, created=False)

            outcome = TaskCreationOutcome(
                task=bundle.task,
                event=bundle.event,
                outbox=bundle.outbox,
                created=True,
            )
            self._tasks[bundle.task.task_id] = bundle.task
            self._events.append(bundle.event)
            self._outbox.append(bundle.outbox)
            self._by_idempotency[scope] = outcome
            return outcome

    async def snapshot(
        self,
    ) -> tuple[tuple[TaskRecord, ...], tuple[TaskEvent, ...], tuple[OutboxRecord, ...]]:
        async with self._lock:
            return (
                tuple(self._tasks.values()),
                tuple(self._events),
                tuple(self._outbox),
            )
