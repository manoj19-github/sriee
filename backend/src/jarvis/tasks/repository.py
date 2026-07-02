"""Atomic task/event/outbox repository contract."""

from __future__ import annotations

import asyncio
import hmac
from dataclasses import replace
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from jarvis.tasks.models import (
    ApprovalDecision,
    ApprovalDecisionOutcome,
    ApprovalRecord,
    ApprovalStatus,
    OutboxRecord,
    PendingApprovalProjection,
    TaskCancellationOutcome,
    TaskCreationBundle,
    TaskCreationOutcome,
    TaskEvent,
    TaskEventPageRecord,
    TaskProjectionRecord,
    TaskRecord,
    TaskStatus,
)


class IdempotencyConflictError(RuntimeError):
    """The idempotency key already belongs to a different request payload."""


class TaskRepository(Protocol):
    async def create_or_get(
        self,
        bundle: TaskCreationBundle,
    ) -> TaskCreationOutcome:
        """Atomically create task/event/outbox or return the matching task."""


class TaskQueryRepository(Protocol):
    async def get_projection(self, task_id: str) -> TaskProjectionRecord | None:
        """Return the current task projection."""


class TaskEventQueryRepository(Protocol):
    async def list_authorized_events(
        self,
        *,
        task_id: str,
        actor_id: str,
        device_id: str,
        after_sequence: int,
        limit: int,
    ) -> TaskEventPageRecord | None:
        """Return an authorized stable page or none without leaking ownership."""


class TaskControlRepository(Protocol):
    async def request_cancellation(
        self,
        *,
        task_id: str,
        actor_id: str,
        device_id: str,
        correlation_id: str,
        occurred_at: datetime,
    ) -> TaskCancellationOutcome | None:
        """Atomically record cancellation intent or return current terminal state."""

    async def decide_approval(
        self,
        *,
        approval_id: str,
        actor_id: str,
        device_id: str,
        action_digest: str,
        decision: ApprovalDecision,
        correlation_id: str,
        decided_at: datetime,
    ) -> ApprovalDecisionOutcome | None:
        """Atomically consume one matching pending approval."""


class InMemoryTaskRepository:
    """Concurrency-safe development/test implementation of the atomic contract."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_idempotency: dict[
            tuple[str, str, str],
            TaskCreationOutcome,
        ] = {}
        self._tasks: dict[str, TaskRecord] = {}
        self._projections: dict[str, TaskProjectionRecord] = {}
        self._events: list[TaskEvent] = []
        self._outbox: list[OutboxRecord] = []
        self._cancellations: dict[str, TaskCancellationOutcome] = {}
        self._approvals: dict[str, ApprovalRecord] = {}

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
            self._projections[bundle.task.task_id] = TaskProjectionRecord(
                task_id=bundle.task.task_id,
                actor_id=bundle.task.actor_id,
                device_id=bundle.task.device_id,
                status=bundle.task.status,
                plan=None,
                pending_approval=None,
                result=None,
                created_at=bundle.task.created_at,
                updated_at=bundle.task.created_at,
            )
            self._events.append(bundle.event)
            self._outbox.append(bundle.outbox)
            self._by_idempotency[scope] = outcome
            return outcome

    async def get_projection(self, task_id: str) -> TaskProjectionRecord | None:
        async with self._lock:
            return self._projections.get(task_id)

    async def replace_projection(self, projection: TaskProjectionRecord) -> None:
        """Replace a projection in development/tests after its task exists."""

        async with self._lock:
            if projection.task_id not in self._tasks:
                raise KeyError("task does not exist")
            current = self._projections[projection.task_id]
            if (
                current.actor_id != projection.actor_id
                or current.device_id != projection.device_id
                or current.created_at != projection.created_at
            ):
                raise ValueError("projection identity is immutable")
            self._projections[projection.task_id] = projection

    async def list_authorized_events(
        self,
        *,
        task_id: str,
        actor_id: str,
        device_id: str,
        after_sequence: int,
        limit: int,
    ) -> TaskEventPageRecord | None:
        async with self._lock:
            projection = self._projections.get(task_id)
            if projection is None or not (
                hmac.compare_digest(projection.actor_id, actor_id)
                and hmac.compare_digest(projection.device_id, device_id)
            ):
                return None
            ordered = sorted(
                (
                    event
                    for event in self._events
                    if event.task_id == task_id
                    and event.sequence > after_sequence
                ),
                key=lambda event: event.sequence,
            )
            window = ordered[: limit + 1]
            page_events = tuple(window[:limit])
            return TaskEventPageRecord(
                task_id=task_id,
                events=page_events,
                next_cursor=(
                    page_events[-1].sequence
                    if page_events
                    else after_sequence
                ),
                has_more=len(window) > limit,
            )

    async def append_event_for_test(self, event: TaskEvent) -> None:
        """Append one valid sequential event for development/query tests."""

        async with self._lock:
            if event.task_id not in self._tasks:
                raise KeyError("task does not exist")
            current_sequences = [
                stored.sequence
                for stored in self._events
                if stored.task_id == event.task_id
            ]
            expected = max(current_sequences, default=0) + 1
            if event.sequence != expected:
                raise ValueError("event sequence must be contiguous")
            if any(stored.event_id == event.event_id for stored in self._events):
                raise ValueError("event ID must be unique")
            self._events.append(event)

    async def request_cancellation(
        self,
        *,
        task_id: str,
        actor_id: str,
        device_id: str,
        correlation_id: str,
        occurred_at: datetime,
    ) -> TaskCancellationOutcome | None:
        terminal = {
            TaskStatus.SUCCEEDED,
            TaskStatus.PARTIALLY_SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.DENIED,
            TaskStatus.EXPIRED,
        }
        async with self._lock:
            projection = self._projections.get(task_id)
            if projection is None or not (
                hmac.compare_digest(projection.actor_id, actor_id)
                and hmac.compare_digest(projection.device_id, device_id)
            ):
                return None
            existing = self._cancellations.get(task_id)
            if existing is not None:
                return replace(existing, created=False)
            if projection.status in terminal:
                return TaskCancellationOutcome(
                    task_id=task_id,
                    status=projection.status,
                    cancellation_requested=False,
                    created=False,
                    event=None,
                    outbox=None,
                )
            sequence = max(
                event.sequence
                for event in self._events
                if event.task_id == task_id
            ) + 1
            event = TaskEvent(
                event_id=f"evt_{uuid4().hex}",
                task_id=task_id,
                sequence=sequence,
                event_type="task.cancellation_requested",
                schema_version="1.0",
                occurred_at=occurred_at,
                correlation_id=correlation_id,
                data={"previous_status": projection.status.value},
            )
            outbox = OutboxRecord(
                outbox_id=f"out_{uuid4().hex}",
                event_type="graph.task.cancel.requested",
                schema_version="1.0",
                aggregate_id=task_id,
                occurred_at=occurred_at,
                correlation_id=correlation_id,
                data={"task_id": task_id, "event_sequence": sequence},
            )
            self._events.append(event)
            self._outbox.append(outbox)
            self._projections[task_id] = replace(
                projection,
                status=TaskStatus.CANCELLATION_REQUESTED,
                updated_at=occurred_at,
            )
            outcome = TaskCancellationOutcome(
                task_id=task_id,
                status=TaskStatus.CANCELLATION_REQUESTED,
                cancellation_requested=True,
                created=True,
                event=event,
                outbox=outbox,
            )
            self._cancellations[task_id] = outcome
            return outcome

    async def decide_approval(
        self,
        *,
        approval_id: str,
        actor_id: str,
        device_id: str,
        action_digest: str,
        decision: ApprovalDecision,
        correlation_id: str,
        decided_at: datetime,
    ) -> ApprovalDecisionOutcome | None:
        async with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None or not (
                hmac.compare_digest(approval.actor_id, actor_id)
                and hmac.compare_digest(approval.device_id, device_id)
            ):
                return None
            if approval.status is not ApprovalStatus.PENDING:
                raise ApprovalConsumedError
            if approval.expires_at <= decided_at:
                raise ApprovalExpiredError
            if not hmac.compare_digest(approval.action_digest, action_digest):
                raise ApprovalDigestMismatchError
            projection = self._projections[approval.task_id]
            sequence = max(
                event.sequence
                for event in self._events
                if event.task_id == approval.task_id
            ) + 1
            updated = replace(
                approval,
                status=(
                    ApprovalStatus.APPROVED
                    if decision is ApprovalDecision.APPROVE
                    else ApprovalStatus.DENIED
                ),
                decided_at=decided_at,
                decision=decision,
            )
            event = TaskEvent(
                event_id=f"evt_{uuid4().hex}",
                task_id=approval.task_id,
                sequence=sequence,
                event_type="approval.decided",
                schema_version="1.0",
                occurred_at=decided_at,
                correlation_id=correlation_id,
                data={
                    "approval_id": approval_id,
                    "action_id": approval.action_id,
                    "decision": decision.value,
                },
            )
            outbox = OutboxRecord(
                outbox_id=f"out_{uuid4().hex}",
                event_type="graph.approval.decided",
                schema_version="1.0",
                aggregate_id=approval.task_id,
                occurred_at=decided_at,
                correlation_id=correlation_id,
                data={
                    "task_id": approval.task_id,
                    "approval_id": approval_id,
                    "decision": decision.value,
                    "event_sequence": sequence,
                },
            )
            self._approvals[approval_id] = updated
            self._events.append(event)
            self._outbox.append(outbox)
            self._projections[approval.task_id] = replace(
                projection,
                status=(
                    TaskStatus.EXECUTING
                    if decision is ApprovalDecision.APPROVE
                    else TaskStatus.DENIED
                ),
                pending_approval=None,
                updated_at=decided_at,
            )
            return ApprovalDecisionOutcome(updated, event, outbox)

    async def put_pending_approval_for_test(
        self,
        approval: ApprovalRecord,
    ) -> None:
        async with self._lock:
            projection = self._projections.get(approval.task_id)
            if projection is None:
                raise KeyError("task does not exist")
            if approval.status is not ApprovalStatus.PENDING:
                raise ValueError("approval must be pending")
            if not (
                projection.actor_id == approval.actor_id
                and projection.device_id == approval.device_id
            ):
                raise ValueError("approval ownership mismatch")
            self._approvals[approval.approval_id] = approval
            self._projections[approval.task_id] = replace(
                projection,
                status=TaskStatus.AWAITING_APPROVAL,
                pending_approval=PendingApprovalProjection(
                    approval_id=approval.approval_id,
                    action_id=approval.action_id,
                    risk_tier="R2",
                    expires_at=approval.expires_at,
                ),
            )

    async def snapshot(
        self,
    ) -> tuple[tuple[TaskRecord, ...], tuple[TaskEvent, ...], tuple[OutboxRecord, ...]]:
        async with self._lock:
            return (
                tuple(self._tasks.values()),
                tuple(self._events),
                tuple(self._outbox),
            )


class ApprovalConsumedError(RuntimeError):
    pass


class ApprovalExpiredError(RuntimeError):
    pass


class ApprovalDigestMismatchError(RuntimeError):
    pass
