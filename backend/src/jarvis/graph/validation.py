"""Deterministic fail-closed plan validation for Global ID 120005."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from jarvis.graph.context import REFERENCE_ID_PATTERN
from jarvis.graph.normalize import PRINCIPAL_ID_PATTERN, TASK_ID_PATTERN
from jarvis.graph.plan import (
    IDENTIFIER_VALUE_PATTERN,
    CapabilityDefinition,
    CapabilityParameter,
    ParameterKind,
    PlanActionDraft,
    PlanContextBundle,
    PlanContextResolver,
    PlanDraft,
    PlanResource,
)


class PlanValidationError(RuntimeError):
    """A content-free validation failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS plan validation failed: {code}")


@dataclass(frozen=True, slots=True)
class PlanValidationSettings:
    """Trusted aggregate limits applied independently of model generation."""

    max_actions: int = 8
    max_success_criteria: int = 16
    max_total_arguments: int = 64
    max_dependency_edges: int = 32
    max_total_timeout_seconds: int = 1_800
    max_critical_path_seconds: int = 900
    resolver_timeout_seconds: float = 5.0


@dataclass(frozen=True, slots=True)
class PlanValidationService:
    """Dependencies supplied by the trusted graph composition root."""

    resolver: PlanContextResolver
    settings: PlanValidationSettings = PlanValidationSettings()


def _validate_settings(settings: PlanValidationSettings) -> None:
    if (
        settings.max_actions < 1
        or settings.max_actions > 8
        or settings.max_success_criteria < settings.max_actions
        or settings.max_success_criteria > 16
        or settings.max_total_arguments < 0
        or settings.max_total_arguments > 96
        or settings.max_dependency_edges < 0
        or settings.max_dependency_edges > 56
        or settings.max_total_timeout_seconds < 1
        or settings.max_total_timeout_seconds > 4_800
        or settings.max_critical_path_seconds < 1
        or settings.max_critical_path_seconds
        > settings.max_total_timeout_seconds
        or settings.resolver_timeout_seconds <= 0
        or settings.resolver_timeout_seconds > 30
    ):
        raise PlanValidationError("plan_validation_settings_incompatible")


def _validate_state(
    state: Mapping[str, Any],
) -> tuple[str, str, str, tuple[str, ...], PlanDraft]:
    if state.get("status") != "planning" or state.get("plan") is None:
        raise PlanValidationError("plan_validation_state_invalid")
    task_id = state.get("task_id")
    actor_id = state.get("actor_id")
    device_id = state.get("device_id")
    if (
        not isinstance(task_id, str)
        or not TASK_ID_PATTERN.fullmatch(task_id)
        or not isinstance(actor_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(actor_id)
        or not isinstance(device_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(device_id)
    ):
        raise PlanValidationError("plan_validation_identity_invalid")
    raw_refs = state.get("context_refs")
    if (
        not isinstance(raw_refs, list)
        or len(raw_refs) < 2
        or len(raw_refs) > 16
        or any(
            not isinstance(reference_id, str)
            or not REFERENCE_ID_PATTERN.fullmatch(reference_id)
            for reference_id in raw_refs
        )
        or len(raw_refs) != len(set(raw_refs))
        or sum(ref.startswith("cap_") for ref in raw_refs) != 1
        or sum(ref.startswith("pol_") for ref in raw_refs) != 1
    ):
        raise PlanValidationError("plan_validation_context_refs_invalid")
    try:
        plan = PlanDraft.model_validate(state["plan"])
    except (ValidationError, TypeError, ValueError):
        raise PlanValidationError("plan_schema_invalid") from None
    if plan.schema_version != "1.0":
        raise PlanValidationError("plan_schema_invalid")
    return task_id, actor_id, device_id, tuple(raw_refs), plan


def _validate_bundle(
    value: object,
    *,
    reference_ids: tuple[str, ...],
    actor_id: str,
    device_id: str,
) -> PlanContextBundle:
    if not isinstance(value, PlanContextBundle):
        raise PlanValidationError("plan_validation_context_invalid")
    try:
        bundle = PlanContextBundle.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise PlanValidationError("plan_validation_context_invalid") from None
    summary_ids = tuple(item.reference_id for item in bundle.summaries)
    capability_ref = next(
        item for item in reference_ids if item.startswith("cap_")
    )
    if (
        len(summary_ids) != len(set(summary_ids))
        or set(summary_ids) != set(reference_ids)
        or bundle.manifest.reference_id != capability_ref
        or bundle.manifest.actor_id != actor_id
        or bundle.manifest.device_id != device_id
    ):
        raise PlanValidationError("plan_validation_context_invalid")
    return bundle


def _validate_argument(
    value: object,
    parameter: CapabilityParameter,
    resources: Mapping[str, PlanResource],
) -> None:
    valid = False
    if parameter.kind is ParameterKind.BOOLEAN:
        valid = type(value) is bool
    elif parameter.kind is ParameterKind.INTEGER:
        valid = (
            type(value) is int
            and (parameter.minimum is None or value >= parameter.minimum)
            and (parameter.maximum is None or value <= parameter.maximum)
        )
    elif parameter.kind is ParameterKind.NUMBER:
        valid = (
            type(value) in {int, float}
            and (parameter.minimum is None or value >= parameter.minimum)
            and (parameter.maximum is None or value <= parameter.maximum)
        )
    elif parameter.kind is ParameterKind.ENUM:
        valid = type(value) is str and value in parameter.allowed_values
    elif parameter.kind is ParameterKind.IDENTIFIER:
        valid = type(value) is str and bool(
            IDENTIFIER_VALUE_PATTERN.fullmatch(value)
        )
    elif parameter.kind is ParameterKind.RESOURCE:
        resource = resources.get(value) if type(value) is str else None
        valid = (
            resource is not None
            and resource.resource_type in parameter.resource_types
        )
    if not valid:
        code = (
            "plan_resource_unknown"
            if parameter.kind is ParameterKind.RESOURCE
            else "plan_argument_invalid"
        )
        raise PlanValidationError(code)


def _validate_action_contract(
    action: PlanActionDraft,
    capability: CapabilityDefinition,
    resources: Mapping[str, PlanResource],
) -> None:
    if (
        action.capability_version != capability.version
        or action.timeout_seconds < 1
        or action.timeout_seconds > capability.max_timeout_seconds
    ):
        raise PlanValidationError("plan_capability_invalid")
    parameters = {
        parameter.name: parameter for parameter in capability.parameters
    }
    names = tuple(argument.name for argument in action.arguments)
    if (
        len(names) != len(set(names))
        or not set(names).issubset(parameters)
        or any(
            parameter.required and parameter.name not in names
            for parameter in capability.parameters
        )
    ):
        raise PlanValidationError("plan_argument_invalid")
    for argument in action.arguments:
        _validate_argument(
            argument.value,
            parameters[argument.name],
            resources,
        )


def _action_fingerprint(action: PlanActionDraft) -> str:
    return json.dumps(
        {
            "capability_id": action.capability_id,
            "capability_version": action.capability_version,
            "arguments": sorted(
                (
                    argument.model_dump(mode="json")
                    for argument in action.arguments
                ),
                key=lambda item: item["name"],
            ),
            "dependencies": sorted(action.dependencies),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _topological_order(
    actions: tuple[PlanActionDraft, ...],
) -> tuple[PlanActionDraft, ...]:
    by_id = {action.action_id: action for action in actions}
    incoming = {
        action.action_id: set(action.dependencies) for action in actions
    }
    if any(
        len(action.dependencies) != len(set(action.dependencies))
        for action in actions
    ) or any(
        dependency not in by_id or dependency == action_id
        for action_id, dependencies in incoming.items()
        for dependency in dependencies
    ):
        raise PlanValidationError("plan_dependency_invalid")
    ready = sorted(
        action_id for action_id, dependencies in incoming.items()
        if not dependencies
    )
    ordered: list[PlanActionDraft] = []
    while ready:
        action_id = ready.pop(0)
        ordered.append(by_id[action_id])
        for candidate in sorted(incoming):
            if action_id in incoming[candidate]:
                incoming[candidate].remove(action_id)
                if (
                    not incoming[candidate]
                    and by_id[candidate] not in ordered
                    and candidate not in ready
                ):
                    ready.append(candidate)
                    ready.sort()
    if len(ordered) != len(actions):
        raise PlanValidationError("plan_dependency_cycle")
    return tuple(ordered)


def _validate_budgets(
    plan: PlanDraft,
    order: tuple[PlanActionDraft, ...],
    settings: PlanValidationSettings,
) -> None:
    total_arguments = sum(len(action.arguments) for action in plan.actions)
    dependency_edges = sum(
        len(action.dependencies) for action in plan.actions
    )
    total_timeout = sum(action.timeout_seconds for action in plan.actions)
    if (
        not plan.actions
        or len(plan.actions) > settings.max_actions
        or not plan.success_criteria
        or len(plan.success_criteria) > settings.max_success_criteria
        or total_arguments > settings.max_total_arguments
        or dependency_edges > settings.max_dependency_edges
        or total_timeout > settings.max_total_timeout_seconds
    ):
        raise PlanValidationError("plan_budget_exceeded")
    longest_path: dict[str, int] = {}
    for action in order:
        dependency_cost = max(
            (longest_path[item] for item in action.dependencies),
            default=0,
        )
        longest_path[action.action_id] = (
            dependency_cost + action.timeout_seconds
        )
    if max(longest_path.values()) > settings.max_critical_path_seconds:
        raise PlanValidationError("plan_budget_exceeded")


def _validate_plan(
    plan: PlanDraft,
    bundle: PlanContextBundle,
    settings: PlanValidationSettings,
) -> None:
    action_ids = tuple(action.action_id for action in plan.actions)
    criterion_ids = tuple(
        criterion.criterion_id for criterion in plan.success_criteria
    )
    if (
        len(action_ids) != len(set(action_ids))
        or len(criterion_ids) != len(set(criterion_ids))
    ):
        raise PlanValidationError("plan_action_duplicate")
    order = _topological_order(plan.actions)
    _validate_budgets(plan, order, settings)

    capabilities = {
        capability.capability_id: capability
        for capability in bundle.manifest.capabilities
    }
    resources = {
        resource.resource_id: resource for resource in bundle.resources
    }
    fingerprints: set[str] = set()
    action_capabilities: dict[str, CapabilityDefinition] = {}
    for action in plan.actions:
        capability = capabilities.get(action.capability_id)
        if capability is None:
            raise PlanValidationError("plan_capability_unknown")
        _validate_action_contract(action, capability, resources)
        fingerprint = _action_fingerprint(action)
        if fingerprint in fingerprints:
            raise PlanValidationError("plan_action_duplicate")
        fingerprints.add(fingerprint)
        action_capabilities[action.action_id] = capability

    criterion_pairs: set[tuple[str, str]] = set()
    covered_actions: set[str] = set()
    for criterion in plan.success_criteria:
        capability = action_capabilities.get(criterion.action_id)
        pair = (criterion.action_id, criterion.verification_code)
        if (
            capability is None
            or criterion.verification_code
            not in capability.verification_codes
            or pair in criterion_pairs
        ):
            raise PlanValidationError("plan_verification_invalid")
        criterion_pairs.add(pair)
        covered_actions.add(criterion.action_id)
    if covered_actions != set(action_ids):
        raise PlanValidationError("plan_verification_invalid")


async def validatePlan(
    state: Mapping[str, Any],
    *,
    service: PlanValidationService,
) -> dict[str, Any]:
    """Validate one checkpointed plan against current trusted contracts."""

    settings = service.settings
    _validate_settings(settings)
    _, actor_id, device_id, reference_ids, plan = _validate_state(state)
    try:
        raw_bundle = await asyncio.wait_for(
            service.resolver.resolve_plan_context(
                reference_ids,
                actor_id=actor_id,
                device_id=device_id,
            ),
            timeout=settings.resolver_timeout_seconds,
        )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise PlanValidationError("plan_validation_context_unavailable") from None
    except Exception:
        raise PlanValidationError("plan_validation_context_unavailable") from None
    bundle = _validate_bundle(
        raw_bundle,
        reference_ids=reference_ids,
        actor_id=actor_id,
        device_id=device_id,
    )
    _validate_plan(plan, bundle, settings)
    return {"plan": plan.model_dump(mode="json")}
