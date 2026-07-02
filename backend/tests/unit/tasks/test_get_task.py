from __future__ import annotations

import asyncio
from dataclasses import replace
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
    PendingApprovalProjection,
    PlanProjection,
    TaskInput,
    TaskInputType,
    TaskOutcome,
    TaskResultProjection,
    TaskStatus,
)
from jarvis.tasks.repository import InMemoryTaskRepository
from jarvis.tasks.service import (
    InMemoryOutboxNotifier,
    TaskCreationService,
    TaskQueryService,
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
    owner: AuthenticatedPrincipal | None = None,
) -> str:
    creation_service = TaskCreationService(
        repository,
        InMemoryOutboxNotifier(),
        clock=lambda: NOW,
    )

    async def create() -> str:
        outcome = await creation_service.create(
            request=CreateTaskRequest(
                input=TaskInput(
                    type=TaskInputType.TEXT,
                    content="Private task input that must not be returned.",
                )
            ),
            principal=owner or principal(),
            idempotency_key="idem-get-task-0001",
            correlation_id="corr-get-task-0001",
        )
        return outcome.task.task_id

    return asyncio.run(create())


def application(
    repository: InMemoryTaskRepository,
    request_principal: AuthenticatedPrincipal | None,
    *,
    configure_service: bool = True,
) -> FastAPI:
    app = FastAPI()
    if configure_service:
        app.state.task_query_service = TaskQueryService(repository)
    if request_principal is not None:
        app.dependency_overrides[authenticateDesktopSession] = (
            lambda: request_principal
        )
    app.include_router(router)
    return app


def test_returns_minimal_created_task_snapshot_without_private_input() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, principal())) as client:
        response = client.get(f"/api/v1/tasks/{task_id}")

    payload = response.json()
    serialized = response.text
    assert response.status_code == 200
    assert payload == {
        "task_id": task_id,
        "status": "created",
        "plan": None,
        "pending_approval": None,
        "result": None,
        "created_at": payload["created_at"],
        "updated_at": payload["updated_at"],
    }
    assert payload["created_at"] == payload["updated_at"]
    for forbidden in (
        "Private task input",
        "actor-001",
        "device-001",
        "idempotency",
        "request_hash",
    ):
        assert forbidden not in serialized


def test_returns_plan_pending_approval_without_action_payload() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    async def update_projection() -> None:
        current = await repository.get_projection(task_id)
        assert current is not None
        await repository.replace_projection(
            replace(
                current,
                status=TaskStatus.AWAITING_APPROVAL,
                plan=PlanProjection(revision=3, status="validated"),
                pending_approval=PendingApprovalProjection(
                    approval_id="apr_approval0001",
                    action_id="act_action000001",
                    risk_tier="R2",
                    expires_at=NOW + timedelta(minutes=2),
                ),
                updated_at=NOW + timedelta(seconds=5),
            )
        )

    asyncio.run(update_projection())
    with TestClient(application(repository, principal())) as client:
        response = client.get(f"/api/v1/tasks/{task_id}")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "awaiting_approval"
    assert payload["plan"] == {"revision": 3, "status": "validated"}
    assert payload["pending_approval"]["approval_id"] == "apr_approval0001"
    assert payload["pending_approval"]["action_id"] == "act_action000001"
    assert payload["pending_approval"]["risk_tier"] == "R2"
    assert "parameters" not in response.text
    assert "payload" not in response.text


def test_returns_result_summary_with_opaque_authorized_references_only() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    async def update_projection() -> None:
        current = await repository.get_projection(task_id)
        assert current is not None
        await repository.replace_projection(
            replace(
                current,
                status=TaskStatus.SUCCEEDED,
                plan=PlanProjection(revision=4, status="completed"),
                pending_approval=None,
                result=TaskResultProjection(
                    outcome=TaskOutcome.SUCCEEDED,
                    summary="Workspace readiness was verified.",
                    artifact_reference_ids=(
                        "art_report000001",
                        "art_logfile00001",
                    ),
                ),
                updated_at=NOW + timedelta(seconds=10),
            )
        )

    asyncio.run(update_projection())
    with TestClient(application(repository, principal())) as client:
        response = client.get(f"/api/v1/tasks/{task_id}")

    payload = response.json()
    assert response.status_code == 200
    assert payload["result"]["outcome"] == "succeeded"
    assert payload["result"]["summary"] == "Workspace readiness was verified."
    assert payload["result"]["artifact_references"] == [
        {
            "reference_id": "art_report000001",
            "requires_separate_authorization": True,
        },
        {
            "reference_id": "art_logfile00001",
            "requires_separate_authorization": True,
        },
    ]
    for forbidden in ("content", "url", "path", "download", "bytes"):
        assert forbidden not in str(payload["result"]["artifact_references"]).lower()


@pytest.mark.parametrize(
    "request_principal",
    [
        principal(actor_id="actor-002"),
        principal(device_id="device-002"),
    ],
)
def test_wrong_actor_or_device_receives_same_not_found_response(
    request_principal: AuthenticatedPrincipal,
) -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, request_principal)) as client:
        response = client.get(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


@pytest.mark.parametrize(
    "task_id",
    [
        "tsk_" + "f" * 32,
        "not-a-task",
        "tsk_ABC",
    ],
)
def test_unknown_and_malformed_ids_share_not_found_response(task_id: str) -> None:
    repository = InMemoryTaskRepository()

    with TestClient(application(repository, principal())) as client:
        response = client.get(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


def test_get_is_read_only() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)
    before = asyncio.run(repository.snapshot())

    with TestClient(application(repository, principal())) as client:
        for _ in range(3):
            assert client.get(f"/api/v1/tasks/{task_id}").status_code == 200

    after = asyncio.run(repository.snapshot())
    assert before == after


def test_endpoint_requires_authentication() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(application(repository, None)) as client:
        response = client.get(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "desktop_authentication_unavailable"


def test_endpoint_fails_safely_when_query_service_is_unavailable() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(
        application(repository, principal(), configure_service=False)
    ) as client:
        response = client.get(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "task_query_service_unavailable"
