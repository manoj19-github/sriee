"""Bounded desktop WebSocket protocol for Global IDs 110008 and 110009."""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocketDisconnect

from jarvis.errors import (
    WebSocketProtocolError,
    resolveCorrelationId,
    webSocketErrorFrame,
)
from jarvis.security.desktop_auth import (
    AuthenticatedPrincipal,
    DesktopSessionAuthenticator,
)
from jarvis.tasks.models import TaskEvent, TaskEventResponse
from jarvis.tasks.service import TaskEventQueryService, TaskNotFoundError


router = APIRouter()


@dataclass(slots=True)
class LiveConnection:
    connection_id: str
    principal: AuthenticatedPrincipal
    protocol_version: str
    subscriptions: set[str] = field(default_factory=set)


class LiveConnectionRegistry:
    def __init__(
        self,
        *,
        max_connections: int = 32,
        max_subscriptions: int = 16,
    ) -> None:
        self.max_connections = max_connections
        self.max_subscriptions = max_subscriptions
        self._connections: dict[str, LiveConnection] = {}
        self._lock = asyncio.Lock()

    async def open(
        self,
        principal: AuthenticatedPrincipal,
        protocol_version: str,
    ) -> LiveConnection | None:
        async with self._lock:
            if len(self._connections) >= self.max_connections:
                return None
            connection = LiveConnection(
                connection_id=f"ws_{uuid4().hex}",
                principal=principal,
                protocol_version=protocol_version,
            )
            self._connections[connection.connection_id] = connection
            return connection

    async def close(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    async def subscribe(self, connection_id: str, task_id: str) -> bool:
        async with self._lock:
            connection = self._connections.get(connection_id)
            if connection is None:
                return False
            if task_id in connection.subscriptions:
                return True
            if len(connection.subscriptions) >= self.max_subscriptions:
                return False
            connection.subscriptions.add(task_id)
            return True

    async def unsubscribe(self, connection_id: str, task_id: str) -> None:
        async with self._lock:
            connection = self._connections.get(connection_id)
            if connection is not None:
                connection.subscriptions.discard(task_id)

    async def count(self) -> int:
        async with self._lock:
            return len(self._connections)


@dataclass(frozen=True, slots=True)
class BrokerMessage:
    kind: str
    task_id: str
    event: TaskEvent | None = None
    reason: str | None = None


class InMemoryTaskEventBroker:
    """Bounded live fan-out; durable recovery remains the event-page API."""

    def __init__(self, *, queue_size: int = 128) -> None:
        if queue_size < 1:
            raise ValueError("queue size must be positive")
        self._queue_size = queue_size
        self._queues: dict[str, asyncio.Queue[BrokerMessage]] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def register(self, connection_id: str) -> asyncio.Queue[BrokerMessage]:
        async with self._lock:
            queue: asyncio.Queue[BrokerMessage] = asyncio.Queue(
                maxsize=self._queue_size
            )
            self._queues[connection_id] = queue
            self._subscriptions[connection_id] = set()
            return queue

    async def unregister(self, connection_id: str) -> None:
        async with self._lock:
            self._queues.pop(connection_id, None)
            self._subscriptions.pop(connection_id, None)

    async def subscribe(self, connection_id: str, task_id: str) -> None:
        async with self._lock:
            if connection_id in self._subscriptions:
                self._subscriptions[connection_id].add(task_id)

    async def unsubscribe(self, connection_id: str, task_id: str) -> None:
        async with self._lock:
            if connection_id in self._subscriptions:
                self._subscriptions[connection_id].discard(task_id)

    async def publish(self, event: TaskEvent) -> None:
        async with self._lock:
            targets = [
                (connection_id, self._queues[connection_id])
                for connection_id, tasks in self._subscriptions.items()
                if event.task_id in tasks and connection_id in self._queues
            ]
            for connection_id, queue in targets:
                message = BrokerMessage("event", event.task_id, event=event)
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(
                        BrokerMessage(
                            "resync",
                            event.task_id,
                            reason="buffer_overflow",
                        )
                    )
                    self._subscriptions[connection_id].discard(event.task_id)


class WebSocketSessionService:
    def __init__(
        self,
        *,
        authenticator: DesktopSessionAuthenticator,
        events: TaskEventQueryService,
        connections: LiveConnectionRegistry,
        broker: InMemoryTaskEventBroker,
        protocol_version: str = "1.0",
        max_frame_bytes: int = 64 * 1024,
        max_messages_per_minute: int = 120,
    ) -> None:
        self.authenticator = authenticator
        self.events = events
        self.connections = connections
        self.broker = broker
        self.protocol_version = protocol_version
        self.max_frame_bytes = max_frame_bytes
        self.max_messages_per_minute = max_messages_per_minute


def _event_frame(event: TaskEvent) -> dict[str, Any]:
    response = TaskEventResponse(
        event_id=event.event_id,
        task_id=event.task_id,
        sequence=event.sequence,
        type=event.event_type,
        schema_version=event.schema_version,
        occurred_at=event.occurred_at,
        correlation_id=event.correlation_id,
        data=dict(event.data),
    )
    return {
        "type": "task.event",
        "version": "1.0",
        "payload": jsonable_encoder(response),
    }


async def streamTaskEvents(
    websocket: WebSocket,
    *,
    service: TaskEventQueryService,
    principal: AuthenticatedPrincipal,
    task_id: str,
    after_sequence: int,
    page_size: int = 100,
) -> int:
    """Replay durable events in order and return the final sent cursor."""

    cursor = after_sequence
    while True:
        page = await service.list(
            task_id=task_id,
            principal=principal,
            after_sequence=cursor,
            limit=page_size,
        )
        for event in page.events:
            await websocket.send_json(_event_frame(event))
            cursor = event.sequence
        if not page.has_more:
            return cursor


@router.websocket("/api/v1/ws")
async def openWebSocketSession(websocket: WebSocket) -> None:
    """Authenticate, negotiate, bound, replay, and stream one desktop session."""

    service = getattr(websocket.app.state, "websocket_session_service", None)
    if not isinstance(service, WebSocketSessionService):
        await websocket.close(code=1013)
        return
    protocol = websocket.headers.get("x-protocol-version")
    if protocol != service.protocol_version:
        await websocket.close(code=4406)
        return
    try:
        principal = await service.authenticator.authenticate(
            authorization=websocket.headers.get("authorization"),
            device_id=websocket.headers.get("x-device-id"),
            contract_version=websocket.headers.get("x-contract-version"),
            request_nonce=websocket.headers.get("x-request-nonce"),
        )
    except HTTPException as error:
        await websocket.close(code=4406 if error.status_code == 426 else 4401)
        return
    connection = await service.connections.open(principal, protocol)
    if connection is None:
        await websocket.close(code=4429)
        return
    queue = await service.broker.register(connection.connection_id)
    cursors: dict[str, int] = {}
    timestamps: deque[float] = deque()
    correlation_id = resolveCorrelationId(
        websocket.headers.get("x-correlation-id")
    )
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "welcome",
            "version": service.protocol_version,
            "payload": {
                "connection_id": connection.connection_id,
                "contract_version": str(principal.contract_version),
                "max_subscriptions": service.connections.max_subscriptions,
                "max_frame_bytes": service.max_frame_bytes,
            },
        }
    )
    receive_task: asyncio.Task[str] | None = None
    broker_task: asyncio.Task[BrokerMessage] | None = None
    try:
        while True:
            receive_task = asyncio.create_task(websocket.receive_text())
            broker_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {receive_task, broker_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            if receive_task in done:
                raw = receive_task.result()
                if len(raw.encode("utf-8")) > service.max_frame_bytes:
                    await websocket.close(code=1009)
                    return
                now = time.monotonic()
                while timestamps and timestamps[0] <= now - 60:
                    timestamps.popleft()
                if len(timestamps) >= service.max_messages_per_minute:
                    await websocket.close(code=4408)
                    return
                timestamps.append(now)
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        webSocketErrorFrame(
                            WebSocketProtocolError("invalid_json"),
                            correlation_id=correlation_id,
                        )
                    )
                    continue
                frame_type = frame.get("type") if isinstance(frame, dict) else None
                payload = frame.get("payload", {}) if isinstance(frame, dict) else {}
                if frame_type == "ping":
                    await websocket.send_json({"type": "pong", "payload": {}})
                elif frame_type == "task.subscribe":
                    task_id = payload.get("task_id")
                    after = payload.get("after_sequence", 0)
                    if not isinstance(task_id, str) or not isinstance(after, int):
                        await websocket.send_json(
                            webSocketErrorFrame(
                                WebSocketProtocolError(
                                    "invalid_subscription"
                                ),
                                correlation_id=correlation_id,
                            )
                        )
                        continue
                    if not await service.connections.subscribe(
                        connection.connection_id,
                        task_id,
                    ):
                        await websocket.send_json(
                            webSocketErrorFrame(
                                WebSocketProtocolError("subscription_limit"),
                                correlation_id=correlation_id,
                            )
                        )
                        continue
                    await service.broker.subscribe(
                        connection.connection_id,
                        task_id,
                    )
                    try:
                        cursor = await streamTaskEvents(
                            websocket,
                            service=service.events,
                            principal=principal,
                            task_id=task_id,
                            after_sequence=after,
                        )
                    except (TaskNotFoundError, ValueError):
                        await service.connections.unsubscribe(
                            connection.connection_id,
                            task_id,
                        )
                        await service.broker.unsubscribe(
                            connection.connection_id,
                            task_id,
                        )
                        await websocket.send_json(
                            webSocketErrorFrame(
                                WebSocketProtocolError("subscription_denied"),
                                correlation_id=correlation_id,
                            )
                        )
                        continue
                    cursors[task_id] = cursor
                    await websocket.send_json(
                        {
                            "type": "task.subscribed",
                            "payload": {
                                "task_id": task_id,
                                "cursor": cursor,
                            },
                        }
                    )
                elif frame_type == "task.unsubscribe":
                    task_id = payload.get("task_id")
                    if isinstance(task_id, str):
                        cursors.pop(task_id, None)
                        await service.connections.unsubscribe(
                            connection.connection_id,
                            task_id,
                        )
                        await service.broker.unsubscribe(
                            connection.connection_id,
                            task_id,
                        )
                        await websocket.send_json(
                            {
                                "type": "task.unsubscribed",
                                "payload": {"task_id": task_id},
                            }
                        )
                else:
                    await websocket.send_json(
                        webSocketErrorFrame(
                            WebSocketProtocolError("unknown_frame"),
                            correlation_id=correlation_id,
                        )
                    )

            if broker_task in done:
                message = broker_task.result()
                cursor = cursors.get(message.task_id)
                if cursor is None:
                    continue
                if message.kind == "resync":
                    cursors.pop(message.task_id, None)
                    await service.connections.unsubscribe(
                        connection.connection_id,
                        message.task_id,
                    )
                    await websocket.send_json(
                        {
                            "type": "resync.required",
                            "payload": {
                                "task_id": message.task_id,
                                "after_sequence": cursor,
                                "reason": message.reason,
                            },
                        }
                    )
                elif message.event is not None:
                    if message.event.sequence <= cursor:
                        continue
                    if message.event.sequence != cursor + 1:
                        cursors.pop(message.task_id, None)
                        await service.connections.unsubscribe(
                            connection.connection_id,
                            message.task_id,
                        )
                        await service.broker.unsubscribe(
                            connection.connection_id,
                            message.task_id,
                        )
                        await websocket.send_json(
                            {
                                "type": "resync.required",
                                "payload": {
                                    "task_id": message.task_id,
                                    "after_sequence": cursor,
                                    "reason": "sequence_gap",
                                },
                            }
                        )
                    else:
                        await websocket.send_json(_event_frame(message.event))
                        cursors[message.task_id] = message.event.sequence
            receive_task = None
            broker_task = None
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        active_tasks = [
            task
            for task in (receive_task, broker_task)
            if task is not None
        ]
        for task in active_tasks:
            if not task.done():
                task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        await service.broker.unregister(connection.connection_id)
        await service.connections.close(connection.connection_id)
