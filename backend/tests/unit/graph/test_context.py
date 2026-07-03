from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from jarvis.graph import (
    ContextClassification,
    ContextKind,
    ContextLoadError,
    ContextLoadSettings,
    ContextReference,
    ContextSources,
    loadBoundedContext,
)


ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
TASK_ID = "tsk_" + "a" * 32
SECRET_CONTENT = "Continue the private project without rewriting this."


def state() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "request": {
            "input": {
                "type": "text",
                "content": SECRET_CONTENT,
            }
        },
        "context_refs": [],
        "errors": [],
        "status": "planning",
    }


def reference(
    kind: ContextKind,
    suffix: str,
    *,
    actor_id: str = ACTOR_ID,
    device_id: str | None = DEVICE_ID,
) -> ContextReference:
    prefix = {
        ContextKind.PROJECT: "prj_",
        ContextKind.CAPABILITY: "cap_",
        ContextKind.POLICY: "pol_",
        ContextKind.MEMORY: "mem_",
    }[kind]
    return ContextReference(
        reference_id=prefix + suffix,
        kind=kind,
        actor_id=actor_id,
        device_id=device_id,
        classification=(
            ContextClassification.PERSONAL
            if kind is ContextKind.MEMORY
            else ContextClassification.INTERNAL
        ),
        version="1.0.0",
    )


class FakeSource:
    def __init__(
        self,
        records: object,
        *,
        error: BaseException | None = None,
        delay: float = 0,
    ) -> None:
        self.records = records
        self.error = error
        self.delay = delay
        self.calls: list[tuple[object, int]] = []

    async def load_references(self, query, *, limit: int):
        self.calls.append((query, limit))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.records


def sources(
    *,
    project: object | None = None,
    capability: object | None = None,
    policy: object | None = None,
    memory: object | None = None,
) -> ContextSources:
    return ContextSources(
        project=(
            project
            if isinstance(project, FakeSource)
            else FakeSource(
                project
                if project is not None
                else [
                    reference(
                        ContextKind.PROJECT,
                        "project01",
                        device_id=None,
                    )
                ]
            )
        ),
        capability=(
            capability
            if isinstance(capability, FakeSource)
            else FakeSource(
                capability
                if capability is not None
                else [reference(ContextKind.CAPABILITY, "manifest01")]
            )
        ),
        policy=(
            policy
            if isinstance(policy, FakeSource)
            else FakeSource(
                policy
                if policy is not None
                else [reference(ContextKind.POLICY, "baseline01")]
            )
        ),
        memory=(
            memory
            if isinstance(memory, FakeSource)
            else FakeSource(
                memory
                if memory is not None
                else [
                    reference(
                        ContextKind.MEMORY,
                        "memory0001",
                        device_id=None,
                    )
                ]
            )
        ),
    )


def run_load(
    selected_sources: ContextSources,
    *,
    current_state: dict[str, Any] | None = None,
    settings: ContextLoadSettings | None = None,
):
    return asyncio.run(
        loadBoundedContext(
            current_state or state(),
            sources=selected_sources,
            settings=settings,
        )
    )


def test_loads_only_opaque_authorized_references_in_fixed_order() -> None:
    selected = sources(
        project=[
            reference(
                ContextKind.PROJECT,
                "project01",
                device_id=None,
            ),
            reference(
                ContextKind.PROJECT,
                "project02",
                device_id=None,
            ),
        ],
        memory=[
            reference(
                ContextKind.MEMORY,
                "memory0001",
                device_id=None,
            ),
            reference(
                ContextKind.MEMORY,
                "memory0002",
                device_id=None,
            ),
        ],
    )

    delta = run_load(selected)

    assert delta == {
        "context_refs": [
            "pol_baseline01",
            "cap_manifest01",
            "prj_project01",
            "prj_project02",
            "mem_memory0001",
            "mem_memory0002",
        ]
    }
    assert SECRET_CONTENT not in str(delta)
    assert all(isinstance(item, str) for item in delta["context_refs"])


def test_passes_exact_ephemeral_query_and_source_limits_without_state_mutation() -> None:
    selected = sources()
    current_state = state()
    original = deepcopy(current_state)

    run_load(selected, current_state=current_state)

    assert current_state == original
    expected_limits = {
        "project": 4,
        "capability": 1,
        "policy": 1,
        "memory": 8,
    }
    for source_name, expected_limit in expected_limits.items():
        source = getattr(selected, source_name)
        query, limit = source.calls[0]
        assert query.task_id == TASK_ID
        assert query.actor_id == ACTOR_ID
        assert query.device_id == DEVICE_ID
        assert query.input_type == "text"
        assert query.content == (
            SECRET_CONTENT
            if source_name in {"project", "memory"}
            else None
        )
        assert query.purpose == "task_planning"
        assert SECRET_CONTENT not in repr(query)
        assert limit == expected_limit


@pytest.mark.parametrize(
    "source_name",
    ["policy", "capability"],
)
def test_required_source_failure_fails_closed(
    source_name: str,
) -> None:
    selected = sources()
    setattr_source = FakeSource([], error=RuntimeError("private failure"))
    selected = ContextSources(
        project=selected.project,
        capability=(
            setattr_source
            if source_name == "capability"
            else selected.capability
        ),
        policy=(
            setattr_source if source_name == "policy" else selected.policy
        ),
        memory=selected.memory,
    )

    with pytest.raises(ContextLoadError) as captured:
        run_load(selected)

    assert captured.value.code == f"{source_name}_context_unavailable"
    assert "private failure" not in str(captured.value)


@pytest.mark.parametrize(
    "source_name",
    ["policy", "capability"],
)
def test_required_source_must_return_exactly_one_reference(
    source_name: str,
) -> None:
    selected = sources(
        **{
            source_name: [],
        }
    )

    with pytest.raises(ContextLoadError) as captured:
        run_load(selected)

    assert captured.value.code == "required_context_missing"


def test_optional_source_failures_are_recorded_without_blocking_security_context() -> None:
    selected = sources(
        project=FakeSource([], error=RuntimeError("project details")),
        memory=FakeSource([], error=RuntimeError("memory details")),
    )

    delta = run_load(selected)

    assert delta == {
        "context_refs": ["pol_baseline01", "cap_manifest01"],
        "errors": [
            {
                "code": "project_context_unavailable",
                "source": "project",
                "retryable": True,
            },
            {
                "code": "memory_context_unavailable",
                "source": "memory",
                "retryable": True,
            },
        ],
    }
    assert "details" not in str(delta)


@pytest.mark.parametrize(
    ("source_name", "required"),
    [
        ("policy", True),
        ("project", False),
    ],
)
def test_source_timeouts_are_bounded_and_sanitized(
    source_name: str,
    required: bool,
) -> None:
    delayed = FakeSource([], delay=0.05)
    defaults = sources()
    selected = ContextSources(
        project=delayed if source_name == "project" else defaults.project,
        capability=defaults.capability,
        policy=delayed if source_name == "policy" else defaults.policy,
        memory=defaults.memory,
    )
    timeout_settings = ContextLoadSettings(source_timeout_seconds=0.005)

    if required:
        with pytest.raises(ContextLoadError) as captured:
            run_load(selected, settings=timeout_settings)
        assert captured.value.code == "policy_context_unavailable"
    else:
        delta = run_load(selected, settings=timeout_settings)
        assert delta["errors"] == [
            {
                "code": "project_context_unavailable",
                "source": "project",
                "retryable": True,
            }
        ]


@pytest.mark.parametrize(
    ("kind", "source_name"),
    [
        (ContextKind.MEMORY, "project"),
        (ContextKind.PROJECT, "memory"),
        (ContextKind.PROJECT, "policy"),
        (ContextKind.POLICY, "capability"),
    ],
)
def test_rejects_reference_kind_from_wrong_source(
    kind: ContextKind,
    source_name: str,
) -> None:
    defaults = sources()
    wrong = [reference(kind, "wrongkind1")]
    selected = ContextSources(
        project=FakeSource(wrong) if source_name == "project" else defaults.project,
        capability=(
            FakeSource(wrong)
            if source_name == "capability"
            else defaults.capability
        ),
        policy=FakeSource(wrong) if source_name == "policy" else defaults.policy,
        memory=FakeSource(wrong) if source_name == "memory" else defaults.memory,
    )

    with pytest.raises(ContextLoadError) as captured:
        run_load(selected)

    assert captured.value.code == "context_reference_invalid"


@pytest.mark.parametrize(
    ("actor_id", "device_id"),
    [
        ("actor-002", DEVICE_ID),
        (ACTOR_ID, "device-002"),
    ],
)
def test_rejects_unauthorized_reference_ownership(
    actor_id: str,
    device_id: str,
) -> None:
    selected = sources(
        policy=[
            reference(
                ContextKind.POLICY,
                "baseline01",
                actor_id=actor_id,
                device_id=device_id,
            )
        ]
    )

    with pytest.raises(ContextLoadError) as captured:
        run_load(selected)

    assert captured.value.code == "context_authorization_failed"


def test_required_security_references_must_be_device_bound() -> None:
    selected = sources(
        capability=[
            reference(
                ContextKind.CAPABILITY,
                "manifest01",
                device_id=None,
            )
        ]
    )

    with pytest.raises(ContextLoadError) as captured:
        run_load(selected)

    assert captured.value.code == "context_authorization_failed"


def test_rejects_source_and_total_limit_overflow() -> None:
    selected = sources(
        project=[
            reference(
                ContextKind.PROJECT,
                f"project0{index}",
                device_id=None,
            )
            for index in range(1, 4)
        ],
        memory=[
            reference(
                ContextKind.MEMORY,
                f"memory000{index}",
                device_id=None,
            )
            for index in range(1, 4)
        ],
    )

    with pytest.raises(ContextLoadError) as captured:
        run_load(
            selected,
            settings=ContextLoadSettings(
                project_limit=2,
                memory_limit=3,
            ),
        )
    assert captured.value.code == "context_limit_exceeded"

    with pytest.raises(ContextLoadError) as captured:
        run_load(
            selected,
            settings=ContextLoadSettings(
                project_limit=3,
                memory_limit=3,
                total_limit=4,
            ),
        )
    assert captured.value.code == "context_limit_exceeded"


def test_rejects_duplicate_reference_ids() -> None:
    duplicate = reference(
        ContextKind.PROJECT,
        "project01",
        device_id=None,
    )
    selected = sources(project=[duplicate, duplicate])

    with pytest.raises(ContextLoadError) as captured:
        run_load(selected)

    assert captured.value.code == "context_reference_duplicate"


def test_context_reference_contract_cannot_embed_content_or_mismatch_prefix() -> None:
    with pytest.raises(ValidationError):
        ContextReference(
            reference_id="prj_project01",
            kind=ContextKind.PROJECT,
            actor_id=ACTOR_ID,
            device_id=None,
            classification=ContextClassification.INTERNAL,
            version="1.0.0",
            content=SECRET_CONTENT,
        )
    with pytest.raises(ValidationError):
        ContextReference(
            reference_id="mem_memory0001",
            kind=ContextKind.PROJECT,
            actor_id=ACTOR_ID,
            device_id=None,
            classification=ContextClassification.INTERNAL,
            version="1.0.0",
        )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "executing", "context_state_invalid"),
        ("task_id", "tsk_short", "context_identity_invalid"),
        ("actor_id", "actor with spaces", "context_identity_invalid"),
        ("device_id", "", "context_identity_invalid"),
        ("request", {}, "context_request_invalid"),
    ],
)
def test_rejects_invalid_graph_state(
    field: str,
    value: object,
    code: str,
) -> None:
    current = state()
    current[field] = value

    with pytest.raises(ContextLoadError) as captured:
        run_load(sources(), current_state=current)

    assert captured.value.code == code


@pytest.mark.parametrize(
    "settings",
    [
        ContextLoadSettings(project_limit=0),
        ContextLoadSettings(capability_limit=2),
        ContextLoadSettings(policy_limit=2),
        ContextLoadSettings(total_limit=1),
        ContextLoadSettings(source_timeout_seconds=0),
        ContextLoadSettings(source_timeout_seconds=31),
    ],
)
def test_rejects_invalid_context_settings(
    settings: ContextLoadSettings,
) -> None:
    with pytest.raises(ContextLoadError) as captured:
        run_load(sources(), settings=settings)

    assert captured.value.code == "context_settings_incompatible"


def test_cancellation_is_not_converted_to_optional_source_failure() -> None:
    selected = sources(
        project=FakeSource([], error=asyncio.CancelledError()),
    )

    with pytest.raises(asyncio.CancelledError):
        run_load(selected)
