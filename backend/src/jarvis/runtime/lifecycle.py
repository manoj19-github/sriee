"""Fail-safe FastAPI resource lifecycle for Global ID 110001."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from fastapi import FastAPI

from jarvis.config.settings import Settings


REQUIRED_RESOURCE_ORDER = (
    "telemetry",
    "database",
    "checkpointer",
    "graph",
    "providers",
    "workers",
)


class RuntimeState(StrEnum):
    """Observable states for the local backend runtime."""

    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    """A bounded, non-sensitive dependency health result."""

    ready: bool
    code: str = "ready"

    def __post_init__(self) -> None:
        if not self.code or not self.code.replace("_", "").isalnum():
            raise ValueError("dependency health code must be a safe identifier")


@runtime_checkable
class ManagedResource(Protocol):
    """Contract implemented by every lifecycle-managed dependency."""

    async def start(self) -> None:
        """Initialize the resource."""

    async def check_health(self) -> DependencyHealth:
        """Return a sanitized readiness result."""

    async def close(self) -> None:
        """Release the resource safely."""


@runtime_checkable
class DrainableResource(Protocol):
    """Optional contract for workers that can stop intake and drain work."""

    async def drain(self) -> None:
        """Finish already-accepted safe work."""


ResourceFactory = Callable[[], Awaitable[ManagedResource]]


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """Factory and bounded shutdown behavior for one dependency."""

    name: str
    factory: ResourceFactory
    health_timeout_seconds: float = 5.0
    close_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.name not in REQUIRED_RESOURCE_ORDER:
            raise ValueError(f"unknown managed resource: {self.name}")
        if self.health_timeout_seconds <= 0:
            raise ValueError("health timeout must be greater than zero")
        if self.close_timeout_seconds <= 0:
            raise ValueError("close timeout must be greater than zero")


@dataclass(frozen=True, slots=True)
class RuntimeReadiness:
    """Secret-safe runtime state used by health endpoints and diagnostics."""

    state: RuntimeState
    ready: bool
    accepting_work: bool
    settings_fingerprint: str
    dependencies: Mapping[str, DependencyHealth]
    failure_code: str | None


class LifecycleStartupError(RuntimeError):
    """Sanitized startup failure that never includes dependency exception text."""

    def __init__(self, resource_name: str, failure_code: str) -> None:
        self.resource_name = resource_name
        self.failure_code = failure_code
        super().__init__(
            f"JARVIS startup failed for resource '{resource_name}' "
            f"({failure_code})"
        )


class LifecycleShutdownError(RuntimeError):
    """Sanitized aggregate shutdown failure."""

    def __init__(self, failure_codes: Sequence[str]) -> None:
        self.failure_codes = tuple(failure_codes)
        super().__init__(
            "JARVIS shutdown completed with resource errors: "
            + ", ".join(self.failure_codes)
        )


@dataclass(slots=True)
class ApplicationRuntime:
    """Owns startup, readiness, draining, rollback, and resource shutdown."""

    settings: Settings
    resource_specs: Sequence[ResourceSpec]
    worker_drain_timeout_seconds: float = 30.0
    state: RuntimeState = field(default=RuntimeState.CREATED, init=False)
    accepting_work: bool = field(default=False, init=False)
    _active: list[tuple[ResourceSpec, ManagedResource]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _health: dict[str, DependencyHealth] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _failure_code: str | None = field(default=None, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        names = tuple(spec.name for spec in self.resource_specs)
        if names != REQUIRED_RESOURCE_ORDER:
            raise ValueError(
                "resources must be configured exactly once in required startup order"
            )
        if self.worker_drain_timeout_seconds <= 0:
            raise ValueError("worker drain timeout must be greater than zero")

    @property
    def readiness(self) -> RuntimeReadiness:
        """Return an immutable, secret-safe readiness snapshot."""

        return RuntimeReadiness(
            state=self.state,
            ready=self.state is RuntimeState.READY and self.accepting_work,
            accepting_work=self.accepting_work,
            settings_fingerprint=self.settings.safe_fingerprint(),
            dependencies=MappingProxyType(dict(self._health)),
            failure_code=self._failure_code,
        )

    async def start(self) -> None:
        """Start and health-check all resources or roll back completely."""

        async with self._lock:
            if self.state not in {RuntimeState.CREATED, RuntimeState.STOPPED}:
                raise LifecycleStartupError("runtime", "invalid_start_state")

            self.state = RuntimeState.STARTING
            self.accepting_work = False
            self._failure_code = None
            self._health.clear()
            self._active.clear()
            current_name = "runtime"

            try:
                for spec in self.resource_specs:
                    current_name = spec.name
                    resource = await spec.factory()
                    self._active.append((spec, resource))
                    await resource.start()
                    health = await asyncio.wait_for(
                        resource.check_health(),
                        timeout=spec.health_timeout_seconds,
                    )
                    if not isinstance(health, DependencyHealth):
                        raise RuntimeError("invalid_dependency_health")
                    self._health[spec.name] = health
                    if not health.ready:
                        raise RuntimeError("dependency_not_ready")
            except BaseException as error:
                self.accepting_work = False
                self._failure_code = f"{current_name}_startup_failed"
                await self._close_all()
                self.state = RuntimeState.FAILED
                raise LifecycleStartupError(
                    current_name,
                    self._failure_code,
                ) from error

            self.accepting_work = True
            self.state = RuntimeState.READY

    async def refresh_readiness(self) -> RuntimeReadiness:
        """Re-probe active dependencies without changing process liveness."""

        async with self._lock:
            if self.state is not RuntimeState.READY:
                return self.readiness

            all_ready = len(self._active) == len(REQUIRED_RESOURCE_ORDER)
            first_failure: str | None = None

            for spec, resource in self._active:
                try:
                    health = await asyncio.wait_for(
                        resource.check_health(),
                        timeout=spec.health_timeout_seconds,
                    )
                    if not isinstance(health, DependencyHealth):
                        raise RuntimeError("invalid_dependency_health")
                except Exception:
                    health = DependencyHealth(
                        ready=False,
                        code="health_check_failed",
                    )

                self._health[spec.name] = health
                if not health.ready:
                    all_ready = False
                    if first_failure is None:
                        first_failure = f"{spec.name}_{health.code}"

            self.accepting_work = all_ready
            self._failure_code = first_failure
            return self.readiness

    async def shutdown(self) -> None:
        """Stop intake, drain bounded workers, and close every resource."""

        async with self._lock:
            if self.state in {RuntimeState.CREATED, RuntimeState.STOPPED}:
                self.accepting_work = False
                self.state = RuntimeState.STOPPED
                return

            self.accepting_work = False
            self.state = RuntimeState.DRAINING
            failures: list[str] = []

            workers = next(
                (
                    resource
                    for spec, resource in self._active
                    if spec.name == "workers"
                ),
                None,
            )
            if isinstance(workers, DrainableResource):
                try:
                    await asyncio.wait_for(
                        workers.drain(),
                        timeout=self.worker_drain_timeout_seconds,
                    )
                except BaseException:
                    failures.append("workers_drain_failed")

            failures.extend(await self._close_all())
            if failures:
                self.state = RuntimeState.FAILED
                self._failure_code = failures[0]
                raise LifecycleShutdownError(failures)

            self.state = RuntimeState.STOPPED
            self._failure_code = None

    async def _close_all(self) -> list[str]:
        """Close active resources in reverse order and continue after errors."""

        failures: list[str] = []
        while self._active:
            spec, resource = self._active.pop()
            try:
                await asyncio.wait_for(
                    resource.close(),
                    timeout=spec.close_timeout_seconds,
                )
            except BaseException:
                failures.append(f"{spec.name}_close_failed")
            finally:
                self._health.pop(spec.name, None)
        return failures


@asynccontextmanager
async def manage_application_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan entry point backed by :class:`ApplicationRuntime`."""

    runtime = getattr(app.state, "runtime", None)
    if not isinstance(runtime, ApplicationRuntime):
        raise LifecycleStartupError("runtime", "runtime_not_configured")

    await runtime.start()
    try:
        yield
    finally:
        await runtime.shutdown()


def manageApplicationLifespan(app: FastAPI):
    """Canonical function-map entry point for Global ID 110001."""

    return manage_application_lifespan(app)
