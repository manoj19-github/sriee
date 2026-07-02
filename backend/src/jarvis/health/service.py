"""Health-reporting service for Global ID 110010."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from jarvis.runtime.lifecycle import (
    ApplicationRuntime,
    DependencyHealth,
    RuntimeState,
)


class HealthProbe(StrEnum):
    """Supported health probe types."""

    LIVENESS = "liveness"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Bounded, secret-safe health result."""

    probe: HealthProbe
    healthy: bool
    state: RuntimeState
    accepting_work: bool
    dependencies: Mapping[str, DependencyHealth]
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class HealthMetricsSnapshot:
    """Content-free counters for operational metrics export."""

    liveness_checks: int
    readiness_checks: int
    degraded_readiness_checks: int
    dependency_failures: int


class HealthReporter:
    """Separates process liveness from dynamic dependency readiness."""

    def __init__(self, runtime: ApplicationRuntime) -> None:
        self._runtime = runtime
        self._liveness_checks = 0
        self._readiness_checks = 0
        self._degraded_readiness_checks = 0
        self._dependency_failures = 0

    @property
    def metrics(self) -> HealthMetricsSnapshot:
        """Return immutable content-free health counters."""

        return HealthMetricsSnapshot(
            liveness_checks=self._liveness_checks,
            readiness_checks=self._readiness_checks,
            degraded_readiness_checks=self._degraded_readiness_checks,
            dependency_failures=self._dependency_failures,
        )

    async def report(self, probe: HealthProbe) -> HealthReport:
        """Create one liveness or readiness report."""

        if probe is HealthProbe.LIVENESS:
            self._liveness_checks += 1
            snapshot = self._runtime.readiness
            return HealthReport(
                probe=probe,
                healthy=True,
                state=snapshot.state,
                accepting_work=snapshot.accepting_work,
                dependencies={},
                failure_code=None,
            )

        self._readiness_checks += 1
        snapshot = await self._runtime.refresh_readiness()
        dependency_failures = sum(
            not dependency.ready
            for dependency in snapshot.dependencies.values()
        )
        self._dependency_failures += dependency_failures
        if not snapshot.ready:
            self._degraded_readiness_checks += 1

        return HealthReport(
            probe=probe,
            healthy=snapshot.ready,
            state=snapshot.state,
            accepting_work=snapshot.accepting_work,
            dependencies=snapshot.dependencies,
            failure_code=snapshot.failure_code,
        )


async def reportHealth(
    reporter: HealthReporter,
    probe: HealthProbe,
) -> HealthReport:
    """Canonical function-map entry point for health probes."""

    return await reporter.report(probe)
