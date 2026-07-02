from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from packaging.version import Version

from jarvis.security.desktop_auth import (
    AuthenticatedPrincipal,
    ContractRange,
    authenticateDesktopSession,
)
from jarvis.tasks.api import router
from jarvis.tasks.models import CreateTaskRequest, TaskInput, TaskInputType
from jarvis.tasks.repository import InMemoryTaskRepository
from jarvis.tasks.service import InMemoryOutboxNotifier, TaskCreationService


NOW = datetime.now(UTC)
IDEMPOTENCY_KEY = "idem-000000000001"
CORRELATION_ID = "corr-000000000001"


def principal(
    *,
    actor_id: str = "actor-001",
    device_id: str = "device-001",
    contract_version: str = "1.2.0",
) -> AuthenticatedPrincipal:
    contracts = ContractRange.parse("1.0.0", "1.5.0")
    return AuthenticatedPrincipal(
        actor_id=actor_id,
        device_id=device_id,
        session_id="session-001",
        token_id="token-001",
        contract_version=Version(contract_version),
        contract_range=contracts,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )


def task_request(
    content: str = "Continue my JARVIS backend work.",
    input_type: TaskInputType = TaskInputType.TEXT,
) -> CreateTaskRequest:
    return CreateTaskRequest(
        input=TaskInput(type=input_type, content=content)
    )


def request_body(
    content: str = "Continue my JARVIS backend work.",
    input_type: str = "text",
) -> dict[str, object]:
    return {"input": {"type": input_type, "content": content}}


def request_headers(
    *,
    idempotency_key: str = IDEMPOTENCY_KEY,
    correlation_id: str = CORRELATION_ID,
) -> dict[str, str]:
    return {
        "Idempotency-Key": idempotency_key,
        "X-Correlation-Id": correlation_id,
    }


def application(
    service: TaskCreationService | None,
    authenticated_principal: AuthenticatedPrincipal | None = None,
) -> FastAPI:
    app = FastAPI()
    if service is not None:
        app.state.task_creation_service = service
    if authenticated_principal is not None:
        app.dependency_overrides[authenticateDesktopSession] = (
            lambda: authenticated_principal
        )
    app.include_router(router)
    return app


def service(
    *,
    repository: InMemoryTaskRepository | None = None,
    notifier: InMemoryOutboxNotifier | None = None,
) -> tuple[TaskCreationService, InMemoryTaskRepository, InMemoryOutboxNotifier]:
    task_repository = repository or InMemoryTaskRepository()
    outbox_notifier = notifier or InMemoryOutboxNotifier()
    return (
        TaskCreationService(
            task_repository,
            outbox_notifier,
            clock=lambda: NOW,
        ),
        task_repository,
        outbox_notifier,
    )


def test_creates_task_initial_event_outbox_and_dispatch_notification() -> None:
    task_service, repository, notifier = service()

    with TestClient(application(task_service, principal())) as client:
        response = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=request_headers(),
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 202
    assert response.json()["created"] is True
    assert response.json()["status"] == "created"
    assert response.json()["event_sequence"] == 1
    assert response.json()["task_id"] == tasks[0].task_id
    assert len(tasks) == len(events) == len(outbox) == 1
    assert events[0].event_type == "task.created"
    assert events[0].sequence == 1
    assert "content" not in events[0].data
    assert outbox[0].event_type == "graph.task.requested"
    assert outbox[0].aggregate_id == tasks[0].task_id
    assert notifier.task_ids == [tasks[0].task_id]


def test_same_idempotency_key_and_payload_returns_original_without_duplicates() -> None:
    task_service, repository, notifier = service()
    app = application(task_service, principal())

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=request_headers(),
        )
        replay = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=request_headers(correlation_id="corr-000000000002"),
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert first.status_code == replay.status_code == 202
    assert first.json()["task_id"] == replay.json()["task_id"]
    assert first.json()["created"] is True
    assert replay.json()["created"] is False
    assert len(tasks) == len(events) == len(outbox) == 1
    assert notifier.task_ids == [first.json()["task_id"]]


@pytest.mark.parametrize(
    "changed_body",
    [
        request_body(content="A different request"),
        request_body(input_type="transcript"),
    ],
)
def test_mismatched_idempotency_reuse_returns_conflict(
    changed_body: dict[str, object],
) -> None:
    task_service, repository, _ = service()
    app = application(task_service, principal())

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=request_headers(),
        )
        conflict = client.post(
            "/api/v1/tasks",
            json=changed_body,
            headers=request_headers(),
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert accepted.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_key_conflict"
    assert len(tasks) == len(events) == len(outbox) == 1


def test_idempotency_scope_is_actor_and_device() -> None:
    task_service, repository, notifier = service()

    async def exercise() -> None:
        first = await task_service.create(
            request=task_request(),
            principal=principal(actor_id="actor-001"),
            idempotency_key=IDEMPOTENCY_KEY,
            correlation_id=CORRELATION_ID,
        )
        second = await task_service.create(
            request=task_request(),
            principal=principal(actor_id="actor-002"),
            idempotency_key=IDEMPOTENCY_KEY,
            correlation_id=CORRELATION_ID,
        )
        assert first.task.task_id != second.task.task_id

    asyncio.run(exercise())
    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert len(tasks) == len(events) == len(outbox) == 2
    assert len(notifier.task_ids) == 2


def test_concurrent_identical_requests_create_exactly_one_transaction() -> None:
    task_service, repository, notifier = service()

    async def exercise():
        return await asyncio.gather(
            *[
                task_service.create(
                    request=task_request(),
                    principal=principal(),
                    idempotency_key=IDEMPOTENCY_KEY,
                    correlation_id=CORRELATION_ID,
                )
                for _ in range(10)
            ]
        )

    outcomes = asyncio.run(exercise())
    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert sum(outcome.created for outcome in outcomes) == 1
    assert len({outcome.task.task_id for outcome in outcomes}) == 1
    assert len(tasks) == len(events) == len(outbox) == 1
    assert len(notifier.task_ids) == 1


def test_notifier_failure_does_not_lose_durable_outbox_intent() -> None:
    failing_notifier = InMemoryOutboxNotifier(fail=True)
    task_service, repository, _ = service(notifier=failing_notifier)

    with TestClient(application(task_service, principal())) as client:
        response = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=request_headers(),
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 202
    assert len(tasks) == len(events) == len(outbox) == 1
    assert outbox[0].aggregate_id == response.json()["task_id"]


@pytest.mark.parametrize(
    "body",
    [
        request_body(content="   "),
        request_body(content="x" * 16_001),
        {"input": {"type": "text", "content": "valid", "extra": True}},
        {"input": {"type": "unknown", "content": "valid"}},
    ],
)
def test_invalid_task_payload_returns_validation_error(
    body: dict[str, object],
) -> None:
    task_service, repository, _ = service()

    with TestClient(application(task_service, principal())) as client:
        response = client.post(
            "/api/v1/tasks",
            json=body,
            headers=request_headers(),
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 422
    assert len(tasks) == len(events) == len(outbox) == 0


@pytest.mark.parametrize(
    "headers",
    [
        request_headers(idempotency_key="short"),
        request_headers(idempotency_key="invalid key with spaces"),
        request_headers(correlation_id="short"),
    ],
)
def test_invalid_request_identifiers_return_stable_error(
    headers: dict[str, str],
) -> None:
    task_service, repository, _ = service()

    with TestClient(application(task_service, principal())) as client:
        response = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=headers,
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request_identifier"
    assert len(tasks) == len(events) == len(outbox) == 0


def test_transcript_input_is_accepted_and_stored_as_transcript() -> None:
    task_service, repository, _ = service()

    with TestClient(application(task_service, principal())) as client:
        response = client.post(
            "/api/v1/tasks",
            json=request_body(input_type="transcript"),
            headers=request_headers(),
        )

    tasks, _, _ = asyncio.run(repository.snapshot())
    assert response.status_code == 202
    assert tasks[0].input_type is TaskInputType.TRANSCRIPT


def test_endpoint_requires_authentication_even_on_loopback() -> None:
    task_service, repository, _ = service()

    with TestClient(application(task_service)) as client:
        response = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=request_headers(),
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "desktop_authentication_unavailable"
    assert len(tasks) == len(events) == len(outbox) == 0


def test_endpoint_fails_safely_when_task_service_is_unavailable() -> None:
    with TestClient(application(None, principal())) as client:
        response = client.post(
            "/api/v1/tasks",
            json=request_body(),
            headers=request_headers(),
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "task_service_unavailable"
