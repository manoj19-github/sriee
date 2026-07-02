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


NOW = datetime.now(UTC)


def principal(
    *,
    actor_id: str = "actor-001",
    device_id: str = "device-001",
) -> AuthenticatedPrincipal:
    contracts = ContractRange.parse("1.0.0", "1.5.0")
    return AuthenticatedPrincipal(
        actor_id=actor_id,
        device_id=device_id,
        session_id="session-001",
        token_id="token-001",
        contract_version=Version("1.2.0"),
        contract_range=contracts,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )


def seed_task(
    repository: InMemoryTaskRepository,
    *,
    owner: AuthenticatedPrincipal | None = None,
    id_suffix: str = "0001",
) -> str:
    service = TaskCreationService(
        repository,
        InMemoryOutboxNotifier(),
        clock=lambda: NOW,
    )

    async def create() -> str:
        outcome = await service.create(
            request=CreateTaskRequest(
                input=TaskInput(
                    type=TaskInputType.TEXT,
                    content="Private content excluded from event pages.",
                )
            ),
            principal=owner or principal(),
            idempotency_key=f"idem-events-{id_suffix}",
            correlation_id=f"corr-events-{id_suffix}",
        )
        return outcome.task.task_id

    return asyncio.run(create())


def append_events(
    repository: InMemoryTaskRepository,
    task_id: str,
    *,
    through_sequence: int,
    marker: str = "primary",
) -> None:
    async def append() -> None:
        for sequence in range(2, through_sequence + 1):
            await repository.append_event_for_test(
                TaskEvent(
                    event_id=f"evt_{marker}{sequence:08d}",
                    task_id=task_id,
                    sequence=sequence,
                    event_type="task.progressed",
                    schema_version="1.0",
                    occurred_at=NOW + timedelta(seconds=sequence),
                    correlation_id="corr-events-0001",
                    data={"step": sequence, "state": f"step_{sequence}"},
                )
            )

    asyncio.run(append())


def application(
    repository: InMemoryTaskRepository,
    request_principal: AuthenticatedPrincipal | None,
    *,
    configure_service: bool = True,
) -> FastAPI:
    app = FastAPI()
    if configure_service:
        app.state.task_event_query_service = TaskEventQueryService(repository)
    if request_principal is not None:
        app.dependency_overrides[authenticateDesktopSession] = (
            lambda: request_principal
        )
    app.include_router(router)
    return app


def test_returns_sequence_ordered_page_after_exclusive_cursor() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)
    append_events(repository, task_id, through_sequence=6)

    with TestClient(application(repository, principal())) as client:
        response = client.get(
            f"/api/v1/tasks/{task_id}/events",
            params={"after_sequence": 2, "limit": 3},
        )

    payload = response.json()
    assert response.status_code == 200
    assert [event["sequence"] for event in payload["events"]] == [3, 4, 5]
    assert payload["next_cursor"] == 5
    assert payload["has_more"] is True
    assert all(event["task_id"] == task_id for event in payload["events"])


def test_paginates_without_gaps_or_duplicates() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)
    append_events(repository, task_id, through_sequence=6)

    with TestClient(application(repository, principal())) as client:
        first = client.get(
            f"/api/v1/tasks/{task_id}/events",
            params={"after_sequence": 0, "limit": 2},
        ).json()
        second = client.get(
            f"/api/v1/tasks/{task_id}/events",
            params={"after_sequence": first["next_cursor"], "limit": 2},
        ).json()
        third = client.get(
            f"/api/v1/tasks/{task_id}/events",
            params={"after_sequence": second["next_cursor"], "limit": 2},
        ).json()

    sequences = [
        event["sequence"]
        for page in (first, second, third)
        for event in page["events"]
    ]
    assert sequences == [1, 2, 3, 4, 5, 6]
    assert first["has_more"] is True
    assert second["has_more"] is True
    assert third["has_more"] is False
    assert third["next_cursor"] == 6


def test_empty_page_preserves_requested_cursor() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, principal())) as client:
        response = client.get(
            f"/api/v1/tasks/{task_id}/events",
            params={"after_sequence": 99, "limit": 10},
        )

    assert response.status_code == 200
    assert response.json()["events"] == []
    assert response.json()["next_cursor"] == 99
    assert response.json()["has_more"] is False


def test_repeated_page_is_stable_and_read_only() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)
    append_events(repository, task_id, through_sequence=3)
    before = asyncio.run(repository.snapshot())

    with TestClient(application(repository, principal())) as client:
        first = client.get(f"/api/v1/tasks/{task_id}/events")
        second = client.get(f"/api/v1/tasks/{task_id}/events")

    after = asyncio.run(repository.snapshot())
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert before == after


def test_event_page_excludes_private_task_and_owner_data() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, principal())) as client:
        response = client.get(f"/api/v1/tasks/{task_id}/events")

    serialized = response.text
    assert response.status_code == 200
    for forbidden in (
        "Private content",
        "actor-001",
        "device-001",
        "idempotency",
        "request_hash",
    ):
        assert forbidden not in serialized


def test_events_are_isolated_between_tasks() -> None:
    repository = InMemoryTaskRepository()
    first_task = seed_task(repository, id_suffix="0001")
    second_task = seed_task(repository, id_suffix="0002")
    append_events(repository, first_task, through_sequence=3, marker="first")
    append_events(repository, second_task, through_sequence=2, marker="second")

    with TestClient(application(repository, principal())) as client:
        first = client.get(f"/api/v1/tasks/{first_task}/events").json()
        second = client.get(f"/api/v1/tasks/{second_task}/events").json()

    assert [event["sequence"] for event in first["events"]] == [1, 2, 3]
    assert [event["sequence"] for event in second["events"]] == [1, 2]
    assert all(event["task_id"] == first_task for event in first["events"])
    assert all(event["task_id"] == second_task for event in second["events"])


@pytest.mark.parametrize(
    "request_principal",
    [
        principal(actor_id="actor-002"),
        principal(device_id="device-002"),
    ],
)
def test_wrong_actor_or_device_receives_not_found(
    request_principal: AuthenticatedPrincipal,
) -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, request_principal)) as client:
        response = client.get(f"/api/v1/tasks/{task_id}/events")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


@pytest.mark.parametrize(
    "task_id",
    ["tsk_" + "f" * 32, "not-a-task", "tsk_ABC"],
)
def test_unknown_and_malformed_task_ids_share_not_found(task_id: str) -> None:
    repository = InMemoryTaskRepository()

    with TestClient(application(repository, principal())) as client:
        response = client.get(f"/api/v1/tasks/{task_id}/events")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


@pytest.mark.parametrize(
    "query",
    [
        {"after_sequence": -1},
        {"after_sequence": "invalid"},
        {"limit": 0},
        {"limit": 101},
        {"limit": "invalid"},
    ],
)
def test_invalid_pagination_returns_validation_error(
    query: dict[str, object],
) -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, principal())) as client:
        response = client.get(
            f"/api/v1/tasks/{task_id}/events",
            params=query,
        )

    assert response.status_code == 422


def test_endpoint_requires_authentication() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, None)) as client:
        response = client.get(f"/api/v1/tasks/{task_id}/events")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "desktop_authentication_unavailable"


def test_endpoint_fails_safely_when_event_service_is_unavailable() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(
        application(repository, principal(), configure_service=False)
    ) as client:
        response = client.get(f"/api/v1/tasks/{task_id}/events")

    assert response.status_code == 503
    assert (
        response.json()["detail"]["code"]
        == "task_event_query_service_unavailable"
    )
