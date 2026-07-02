from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.config.settings import Settings, load_settings
from jarvis.main import create_application
from jarvis.runtime.lifecycle import (
    REQUIRED_RESOURCE_ORDER,
    ApplicationRuntime,
    DependencyHealth,
    LifecycleShutdownError,
    LifecycleStartupError,
    ResourceSpec,
    RuntimeState,
    manageApplicationLifespan,
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


class FakeResource:
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        healthy: bool = True,
        fail_start: bool = False,
        fail_close: bool = False,
    ) -> None:
        self.name = name
        self.events = events
        self.healthy = healthy
        self.fail_start = fail_start
        self.fail_close = fail_close

    async def start(self) -> None:
        self.events.append(f"start:{self.name}")
        if self.fail_start:
            raise RuntimeError("secret=startup-detail")

    async def check_health(self) -> DependencyHealth:
        self.events.append(f"health:{self.name}")
        return DependencyHealth(
            ready=self.healthy,
            code="ready" if self.healthy else "not_ready",
        )

    async def close(self) -> None:
        self.events.append(f"close:{self.name}")
        if self.fail_close:
            raise RuntimeError("secret=shutdown-detail")


class FakeWorkers(FakeResource):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        drain_delay: float = 0,
        fail_close: bool = False,
    ) -> None:
        super().__init__(name, events, fail_close=fail_close)
        self.drain_delay = drain_delay

    async def drain(self) -> None:
        self.events.append("drain:workers")
        await asyncio.sleep(self.drain_delay)


def resource_specs(
    events: list[str],
    *,
    fail_start: str | None = None,
    unhealthy: str | None = None,
    fail_close: str | None = None,
    worker_drain_delay: float = 0,
) -> Sequence[ResourceSpec]:
    specs: list[ResourceSpec] = []
    for name in REQUIRED_RESOURCE_ORDER:
        if name == "workers":
            resource = FakeWorkers(
                name,
                events,
                drain_delay=worker_drain_delay,
                fail_close=fail_close == name,
            )
        else:
            resource = FakeResource(
                name,
                events,
                healthy=unhealthy != name,
                fail_start=fail_start == name,
                fail_close=fail_close == name,
            )

        async def factory(instance=resource):
            return instance

        specs.append(
            ResourceSpec(
                name=name,
                factory=factory,
                close_timeout_seconds=0.1,
            )
        )
    return specs


def test_fastapi_lifespan_starts_checks_drains_and_closes_in_order() -> None:
    events: list[str] = []
    app = create_application(settings(), resource_specs(events))

    with TestClient(app):
        readiness = app.state.runtime.readiness
        assert readiness.ready is True
        assert readiness.accepting_work is True
        assert readiness.state is RuntimeState.READY
        assert tuple(readiness.dependencies) == REQUIRED_RESOURCE_ORDER
        assert len(readiness.settings_fingerprint) == 16

    assert app.state.runtime.state is RuntimeState.STOPPED
    assert app.state.runtime.accepting_work is False
    assert events == [
        *[
            event
            for name in REQUIRED_RESOURCE_ORDER
            for event in (f"start:{name}", f"health:{name}")
        ],
        "drain:workers",
        *[f"close:{name}" for name in reversed(REQUIRED_RESOURCE_ORDER)],
    ]


def test_startup_failure_rolls_back_all_started_resources() -> None:
    events: list[str] = []
    runtime = ApplicationRuntime(
        settings(),
        resource_specs(events, fail_start="graph"),
    )

    with pytest.raises(LifecycleStartupError) as captured:
        asyncio.run(runtime.start())

    assert captured.value.resource_name == "graph"
    assert "secret=startup-detail" not in str(captured.value)
    assert runtime.state is RuntimeState.FAILED
    assert runtime.readiness.ready is False
    assert "start:providers" not in events
    assert events[-4:] == [
        "close:graph",
        "close:checkpointer",
        "close:database",
        "close:telemetry",
    ]


def test_unhealthy_dependency_is_not_ready_and_rolls_back() -> None:
    events: list[str] = []
    runtime = ApplicationRuntime(
        settings(),
        resource_specs(events, unhealthy="database"),
    )

    with pytest.raises(LifecycleStartupError) as captured:
        asyncio.run(runtime.start())

    assert captured.value.failure_code == "database_startup_failed"
    assert runtime.readiness.ready is False
    assert events[-2:] == ["close:database", "close:telemetry"]


def test_shutdown_stops_intake_and_continues_after_close_failure() -> None:
    events: list[str] = []
    runtime = ApplicationRuntime(
        settings(),
        resource_specs(events, fail_close="providers"),
    )

    async def exercise() -> None:
        await runtime.start()
        with pytest.raises(LifecycleShutdownError) as captured:
            await runtime.shutdown()
        assert captured.value.failure_codes == ("providers_close_failed",)
        assert "secret=shutdown-detail" not in str(captured.value)

    asyncio.run(exercise())

    assert runtime.accepting_work is False
    assert runtime.state is RuntimeState.FAILED
    assert events[-1] == "close:telemetry"


def test_worker_drain_timeout_still_closes_every_resource() -> None:
    events: list[str] = []
    runtime = ApplicationRuntime(
        settings(),
        resource_specs(events, worker_drain_delay=0.05),
        worker_drain_timeout_seconds=0.001,
    )

    async def exercise() -> None:
        await runtime.start()
        with pytest.raises(LifecycleShutdownError) as captured:
            await runtime.shutdown()
        assert captured.value.failure_codes == ("workers_drain_failed",)

    asyncio.run(exercise())

    assert events[-6:] == [
        f"close:{name}" for name in reversed(REQUIRED_RESOURCE_ORDER)
    ]
    assert runtime.state is RuntimeState.FAILED


def test_lifespan_rejects_app_without_runtime() -> None:
    app = FastAPI()

    async def exercise() -> None:
        with pytest.raises(LifecycleStartupError) as captured:
            async with manageApplicationLifespan(app):
                pass
        assert captured.value.failure_code == "runtime_not_configured"

    asyncio.run(exercise())


def test_runtime_requires_every_resource_in_exact_order() -> None:
    events: list[str] = []

    with pytest.raises(ValueError, match="required startup order"):
        ApplicationRuntime(settings(), resource_specs(events)[:-1])


def test_readiness_dependency_view_is_immutable() -> None:
    events: list[str] = []
    runtime = ApplicationRuntime(settings(), resource_specs(events))

    async def exercise() -> None:
        await runtime.start()
        with pytest.raises(TypeError):
            runtime.readiness.dependencies["database"] = DependencyHealth(False)
        await runtime.shutdown()

    asyncio.run(exercise())
