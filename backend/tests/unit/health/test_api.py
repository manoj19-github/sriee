from __future__ import annotations

import asyncio
from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.config.settings import Settings, load_settings
from jarvis.health import router as health_router
from jarvis.main import create_application
from jarvis.runtime.lifecycle import (
    REQUIRED_RESOURCE_ORDER,
    DependencyHealth,
    ResourceSpec,
)


def settings() -> Settings:
    return load_settings(
        overrides={
            "DB_HOST": "db.internal",
            "DB_NAME": "jarvis_test",
            "DB_USER": "jarvis_test",
            "DB_PASSWORD": "database-password",
            "DEFAULT_SCHEMA": "jarvis",
            "JWT_ACCESS_SECRET": "a" * 32,
            "JWT_REFRESH_SECRET": "b" * 32,
        }
    )


class ProbeResource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ready = True
        self.code = "ready"
        self.raise_health = False
        self.health_delay = 0.0
        self.health_checks = 0

    async def start(self) -> None:
        return None

    async def check_health(self) -> DependencyHealth:
        self.health_checks += 1
        if self.health_delay:
            await asyncio.sleep(self.health_delay)
        if self.raise_health:
            raise RuntimeError("secret=dependency-diagnostic")
        return DependencyHealth(ready=self.ready, code=self.code)

    async def close(self) -> None:
        return None


def resource_specs(
    resources: dict[str, ProbeResource],
    *,
    health_timeout_seconds: float = 0.1,
) -> Sequence[ResourceSpec]:
    specs: list[ResourceSpec] = []
    for name in REQUIRED_RESOURCE_ORDER:
        resource = ProbeResource(name)
        resources[name] = resource

        async def factory(instance=resource):
            return instance

        specs.append(
            ResourceSpec(
                name=name,
                factory=factory,
                health_timeout_seconds=health_timeout_seconds,
                close_timeout_seconds=0.1,
            )
        )
    return specs


def test_live_and_ready_are_separate_sanitized_probes() -> None:
    resources: dict[str, ProbeResource] = {}
    app = create_application(settings(), resource_specs(resources))

    with TestClient(app) as client:
        live = client.get("/health/live")

        assert live.status_code == 200
        assert live.json() == {"status": "live", "state": "ready"}
        assert all(resource.health_checks == 1 for resource in resources.values())

        ready = client.get("/health/ready")
        assert ready.status_code == 200
        payload = ready.json()
        assert payload["status"] == "ready"
        assert payload["state"] == "ready"
        assert payload["accepting_work"] is True
        assert payload["failure_code"] is None
        assert tuple(payload["dependencies"]) == REQUIRED_RESOURCE_ORDER
        assert all(
            dependency == {"ready": True, "code": "ready"}
            for dependency in payload["dependencies"].values()
        )
        assert all(resource.health_checks == 2 for resource in resources.values())
        assert "settings_fingerprint" not in ready.text
        assert "database-password" not in ready.text

        metrics = app.state.health_reporter.metrics
        assert metrics.liveness_checks == 1
        assert metrics.readiness_checks == 1
        assert metrics.degraded_readiness_checks == 0
        assert metrics.dependency_failures == 0


def test_provider_outage_degrades_readiness_but_liveness_stays_up() -> None:
    resources: dict[str, ProbeResource] = {}
    app = create_application(settings(), resource_specs(resources))

    with TestClient(app) as client:
        resources["providers"].ready = False
        resources["providers"].code = "unavailable"

        degraded = client.get("/health/ready")
        assert degraded.status_code == 503
        assert degraded.json()["status"] == "not_ready"
        assert degraded.json()["state"] == "ready"
        assert degraded.json()["accepting_work"] is False
        assert degraded.json()["failure_code"] == "providers_unavailable"
        assert degraded.json()["dependencies"]["providers"] == {
            "ready": False,
            "code": "unavailable",
        }

        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "live"

        resources["providers"].ready = True
        resources["providers"].code = "ready"
        recovered = client.get("/health/ready")
        assert recovered.status_code == 200
        assert recovered.json()["status"] == "ready"
        assert recovered.json()["accepting_work"] is True

        metrics = app.state.health_reporter.metrics
        assert metrics.readiness_checks == 2
        assert metrics.degraded_readiness_checks == 1
        assert metrics.dependency_failures == 1


def test_health_exception_is_sanitized_and_does_not_kill_process() -> None:
    resources: dict[str, ProbeResource] = {}
    app = create_application(settings(), resource_specs(resources))

    with TestClient(app) as client:
        resources["database"].raise_health = True

        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["failure_code"] == "database_health_check_failed"
        assert response.json()["dependencies"]["database"] == {
            "ready": False,
            "code": "health_check_failed",
        }
        assert "secret=dependency-diagnostic" not in response.text
        assert client.get("/health/live").status_code == 200


def test_health_timeout_fails_closed_with_safe_code() -> None:
    resources: dict[str, ProbeResource] = {}
    app = create_application(
        settings(),
        resource_specs(resources, health_timeout_seconds=0.001),
    )

    with TestClient(app) as client:
        resources["checkpointer"].health_delay = 0.05

        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["failure_code"] == (
            "checkpointer_health_check_failed"
        )
        assert response.json()["dependencies"]["checkpointer"]["code"] == (
            "health_check_failed"
        )
        assert client.get("/health/live").status_code == 200


def test_missing_runtime_is_live_but_not_ready() -> None:
    app = FastAPI()
    app.include_router(health_router)

    with TestClient(app) as client:
        assert client.get("/health/live").json() == {
            "status": "live",
            "state": "unavailable",
        }

        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json() == {
            "status": "not_ready",
            "state": "unavailable",
            "accepting_work": False,
            "dependencies": {},
            "failure_code": "runtime_unavailable",
        }
