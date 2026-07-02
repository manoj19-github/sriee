from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from jarvis.config.settings import load_settings
from jarvis.security.desktop_auth import (
    ContractRange,
    DesktopSessionAuthenticator,
    DesktopSessionRecord,
    DesktopSessionToken,
    DeviceRecord,
    DeviceStatus,
    InMemoryDeviceRegistry,
    InMemoryNonceStore,
    InMemorySessionRegistry,
    SessionStatus,
)
from jarvis.tasks.models import (
    CreateTaskRequest,
    TaskEvent,
    TaskInput,
    TaskInputType,
)
from jarvis.tasks.repository import InMemoryTaskRepository
from jarvis.tasks.service import (
    InMemoryOutboxNotifier,
    TaskCreationService,
    TaskEventQueryService,
)
from jarvis.websocket.session import (
    InMemoryTaskEventBroker,
    LiveConnectionRegistry,
    WebSocketSessionService,
    router,
    streamTaskEvents,
)


NOW = datetime.now(UTC)
SECRET = "a" * 32
DEVICE_ID = "device-001"
ACTOR_ID = "actor-001"
SESSION_ID = "session-001"
CONTRACTS = ContractRange.parse("1.0.0", "1.5.0")


def authenticator() -> DesktopSessionAuthenticator:
    settings = load_settings(
        overrides={
            "DB_HOST": "db.internal",
            "DB_NAME": "jarvis_test",
            "DB_USER": "jarvis_test",
            "DB_PASSWORD": "database-password",
            "DEFAULT_SCHEMA": "jarvis",
            "JWT_ACCESS_SECRET": SECRET,
            "JWT_REFRESH_SECRET": "b" * 32,
        }
    )
    return DesktopSessionAuthenticator(
        settings=settings,
        devices=InMemoryDeviceRegistry(
            [
                DeviceRecord(
                    device_id=DEVICE_ID,
                    actor_id=ACTOR_ID,
                    status=DeviceStatus.ACTIVE,
                    session_epoch=1,
                    contract_range=CONTRACTS,
                )
            ]
        ),
        sessions=InMemorySessionRegistry(
            [
                DesktopSessionRecord(
                    session_id=SESSION_ID,
                    device_id=DEVICE_ID,
                    actor_id=ACTOR_ID,
                    status=SessionStatus.ACTIVE,
                    session_epoch=1,
                    expires_at=NOW + timedelta(minutes=10),
                    contract_range=CONTRACTS,
                )
            ]
        ),
        nonces=InMemoryNonceStore(),
        supported_contracts=CONTRACTS,
    )


def websocket_headers(
    *,
    protocol: str = "1.0",
    include_credentials: bool = True,
) -> dict[str, str]:
    headers = {"X-Protocol-Version": protocol}
    if include_credentials:
        headers.update(
            {
                "Authorization": "Bearer "
                + DesktopSessionToken(SECRET).issue(
                    actor_id=ACTOR_ID,
                    device_id=DEVICE_ID,
                    session_id=SESSION_ID,
                    session_epoch=1,
                    contract_range=CONTRACTS,
                    issued_at=NOW,
                ),
                "X-Device-Id": DEVICE_ID,
                "X-Contract-Version": "1.2.0",
                "X-Request-Nonce": str(uuid4()),
            }
        )
    return headers


def seed_task(
    repository: InMemoryTaskRepository,
    *,
    suffix: str = "0001",
    through_sequence: int = 1,
) -> str:
    creation = TaskCreationService(
        repository,
        InMemoryOutboxNotifier(),
        clock=lambda: NOW,
    )

    async def seed() -> str:
        outcome = await creation.create(
            request=CreateTaskRequest(
                input=TaskInput(type=TaskInputType.TEXT, content="WebSocket task")
            ),
            principal=(
                await authenticator().authenticate(
                    authorization=websocket_headers()["Authorization"],
                    device_id=DEVICE_ID,
                    contract_version="1.2.0",
                    request_nonce=str(uuid4()),
                )
            ),
            idempotency_key=f"idem-websocket-{suffix}",
            correlation_id=f"corr-websocket-{suffix}",
        )
        for sequence in range(2, through_sequence + 1):
            await repository.append_event_for_test(
                TaskEvent(
                    event_id=f"evt_socket{suffix}{sequence:04d}",
                    task_id=outcome.task.task_id,
                    sequence=sequence,
                    event_type="task.progressed",
                    schema_version="1.0",
                    occurred_at=NOW + timedelta(seconds=sequence),
                    correlation_id=f"corr-websocket-{suffix}",
                    data={"step": sequence},
                )
            )
        return outcome.task.task_id

    return asyncio.run(seed())


def application(
    repository: InMemoryTaskRepository,
    *,
    max_subscriptions: int = 4,
    max_frame_bytes: int = 4096,
    max_messages_per_minute: int = 20,
) -> tuple[FastAPI, WebSocketSessionService]:
    service = WebSocketSessionService(
        authenticator=authenticator(),
        events=TaskEventQueryService(repository),
        connections=LiveConnectionRegistry(
            max_connections=4,
            max_subscriptions=max_subscriptions,
        ),
        broker=InMemoryTaskEventBroker(queue_size=4),
        max_frame_bytes=max_frame_bytes,
        max_messages_per_minute=max_messages_per_minute,
    )
    app = FastAPI()
    app.state.websocket_session_service = service
    app.include_router(router)
    return app, service


def test_authenticated_handshake_sends_welcome_and_handles_ping() -> None:
    app, service = application(InMemoryTaskRepository())

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/ws",
            headers=websocket_headers(),
        ) as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "welcome"
            assert welcome["version"] == "1.0"
            assert welcome["payload"]["contract_version"] == "1.2.0"
            assert welcome["payload"]["max_subscriptions"] == 4
            websocket.send_json({"type": "ping", "payload": {}})
            assert websocket.receive_json()["type"] == "pong"

    assert asyncio.run(service.connections.count()) == 0


@pytest.mark.parametrize(
    ("headers", "expected_code"),
    [
        (websocket_headers(include_credentials=False), 4401),
        (websocket_headers(protocol="2.0"), 4406),
    ],
)
def test_invalid_authentication_or_protocol_is_rejected(
    headers: dict[str, str],
    expected_code: int,
) -> None:
    app, _ = application(InMemoryTaskRepository())

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as captured:
            with client.websocket_connect("/api/v1/ws", headers=headers):
                pass

    assert captured.value.code == expected_code


def test_subscribe_replays_durable_events_then_confirms_cursor() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository, through_sequence=4)
    app, _ = application(repository)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/ws",
            headers=websocket_headers(),
        ) as websocket:
            assert websocket.receive_json()["type"] == "welcome"
            websocket.send_json(
                {
                    "type": "task.subscribe",
                    "payload": {"task_id": task_id, "after_sequence": 1},
                }
            )
            frames = [websocket.receive_json() for _ in range(4)]

    assert [frame["payload"]["sequence"] for frame in frames[:3]] == [2, 3, 4]
    assert all(frame["type"] == "task.event" for frame in frames[:3])
    assert frames[3] == {
        "type": "task.subscribed",
        "payload": {"task_id": task_id, "cursor": 4},
    }


def test_subscription_limit_and_denied_task_return_bounded_errors() -> None:
    repository = InMemoryTaskRepository()
    first_task = seed_task(repository, suffix="0001")
    second_task = seed_task(repository, suffix="0002")
    app, _ = application(repository, max_subscriptions=1)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/ws",
            headers=websocket_headers(),
        ) as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "task.subscribe",
                    "payload": {"task_id": first_task, "after_sequence": 0},
                }
            )
            assert websocket.receive_json()["type"] == "task.event"
            assert websocket.receive_json()["type"] == "task.subscribed"
            websocket.send_json(
                {
                    "type": "task.subscribe",
                    "payload": {"task_id": second_task, "after_sequence": 0},
                }
            )
            limited = websocket.receive_json()

    assert limited["payload"]["code"] == "subscription_limit"


def test_frame_size_and_rate_limits_close_session() -> None:
    app, _ = application(
        InMemoryTaskRepository(),
        max_frame_bytes=32,
        max_messages_per_minute=1,
    )

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as size_disconnect:
            with client.websocket_connect(
                "/api/v1/ws",
                headers=websocket_headers(),
            ) as websocket:
                websocket.receive_json()
                websocket.send_text("x" * 64)
                websocket.receive_json()
        assert size_disconnect.value.code == 1009

        with pytest.raises(WebSocketDisconnect) as rate_disconnect:
            with client.websocket_connect(
                "/api/v1/ws",
                headers=websocket_headers(),
            ) as websocket:
                websocket.receive_json()
                websocket.send_json({"type": "ping", "payload": {}})
                websocket.receive_json()
                websocket.send_json({"type": "ping", "payload": {}})
                websocket.receive_json()
        assert rate_disconnect.value.code == 4408


def test_broker_overflow_requires_resync_and_unsubscribes() -> None:
    broker = InMemoryTaskEventBroker(queue_size=1)

    async def exercise():
        queue = await broker.register("ws_test")
        await broker.subscribe("ws_test", "tsk_" + "a" * 32)
        first = TaskEvent(
            event_id="evt_broker00001",
            task_id="tsk_" + "a" * 32,
            sequence=1,
            event_type="task.created",
            schema_version="1.0",
            occurred_at=NOW,
            correlation_id="corr-broker-0001",
            data={},
        )
        await broker.publish(first)
        await broker.publish(
            TaskEvent(
                event_id="evt_broker00002",
                task_id=first.task_id,
                sequence=2,
                event_type="task.progressed",
                schema_version="1.0",
                occurred_at=NOW,
                correlation_id="corr-broker-0001",
                data={},
            )
        )
        return await queue.get()

    message = asyncio.run(exercise())
    assert message.kind == "resync"
    assert message.reason == "buffer_overflow"


def test_stream_task_events_replays_multiple_pages_in_order() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository, through_sequence=6)
    query = TaskEventQueryService(repository)

    class CapturingWebSocket:
        def __init__(self) -> None:
            self.frames: list[dict] = []

        async def send_json(self, frame: dict) -> None:
            self.frames.append(frame)

    websocket = CapturingWebSocket()

    async def exercise() -> int:
        return await streamTaskEvents(
            websocket,  # type: ignore[arg-type]
            service=query,
            principal=(
                await authenticator().authenticate(
                    authorization=websocket_headers()["Authorization"],
                    device_id=DEVICE_ID,
                    contract_version="1.2.0",
                    request_nonce=str(uuid4()),
                )
            ),
            task_id=task_id,
            after_sequence=0,
            page_size=2,
        )

    cursor = asyncio.run(exercise())
    assert cursor == 6
    assert [frame["payload"]["sequence"] for frame in websocket.frames] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]
