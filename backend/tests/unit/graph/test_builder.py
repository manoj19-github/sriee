from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from jarvis.graph import (
    REQUIRED_NODE_NAMES,
    CheckpointerSpec,
    GraphBuildSettings,
    GraphContractError,
    JarvisState,
    NodeSpec,
    buildJarvisGraph,
    routeAfterApproval,
    routeAfterPolicy,
    routeAfterVerification,
)


THREAD_ID = "thread_graph_build_0001"


def initial_state() -> JarvisState:
    return {
        "contract_version": "1.0",
        "task_id": "tsk_" + "a" * 32,
        "thread_id": THREAD_ID,
        "actor_id": "actor-001",
        "device_id": "device-001",
        "request": {"input": "continue project"},
        "context_refs": [],
        "intent": None,
        "plan": None,
        "policy_decisions": [],
        "pending_approval": None,
        "action_results": [],
        "observations": [],
        "errors": [],
        "status": "created",
        "revision_count": 0,
        "final_response": None,
    }


def durable_checkpointer() -> CheckpointerSpec:
    return CheckpointerSpec(saver=InMemorySaver(), durable=True)


def workflow_nodes(
    *,
    policy_status: str = "executing",
    revise_once: bool = False,
    calls: list[str] | None = None,
) -> dict[str, NodeSpec]:
    call_log = calls if calls is not None else []

    def node(name: str):
        def run(state: JarvisState) -> dict[str, Any]:
            call_log.append(name)
            if name == "normalize_request":
                return {"status": "planning"}
            if name == "evaluate_policy":
                return {"status": policy_status}
            if name == "resume_approval":
                return {"status": "executing"}
            if name == "dispatch_action":
                return {"action_results": [{"source": "dispatch"}]}
            if name == "collect_action_result":
                return {"action_results": [{"source": "collect"}]}
            if name == "verify_outcome":
                if revise_once and state["revision_count"] == 0:
                    return {"status": "planning"}
                return {"status": "succeeded"}
            if name == "revise_plan":
                return {
                    "revision_count": state["revision_count"] + 1,
                    "status": "planning",
                }
            if name == "render_response":
                return {
                    "final_response": {
                        "status": state["status"],
                        "verified": state["status"] == "succeeded",
                    }
                }
            return {}

        return run

    return {name: NodeSpec(node(name)) for name in REQUIRED_NODE_NAMES}


def test_build_registers_fixed_topology_without_invoking_nodes() -> None:
    calls: list[str] = []
    checkpointer = durable_checkpointer()

    graph = buildJarvisGraph(
        nodes=workflow_nodes(calls=calls),
        checkpointer=checkpointer,
    )

    graph_nodes = set(graph.get_graph().nodes)
    assert calls == []
    assert set(REQUIRED_NODE_NAMES) <= graph_nodes
    assert graph.checkpointer is checkpointer.saver
    assert graph.name == "jarvis-core-v1"


def test_allow_route_executes_and_append_reducers_preserve_both_results() -> None:
    calls: list[str] = []
    graph = buildJarvisGraph(
        nodes=workflow_nodes(calls=calls),
        checkpointer=durable_checkpointer(),
    )

    result = graph.invoke(
        initial_state(),
        {"configurable": {"thread_id": THREAD_ID}},
    )

    assert result["status"] == "succeeded"
    assert result["action_results"] == [
        {"source": "dispatch"},
        {"source": "collect"},
    ]
    assert result["final_response"] == {
        "status": "succeeded",
        "verified": True,
    }
    assert "pause_for_approval" not in calls
    assert calls[-1] == "render_response"


def test_ask_route_passes_through_approval_before_dispatch() -> None:
    calls: list[str] = []
    graph = buildJarvisGraph(
        nodes=workflow_nodes(
            policy_status="awaiting_approval",
            calls=calls,
        ),
        checkpointer=durable_checkpointer(),
    )

    result = graph.invoke(
        initial_state(),
        {"configurable": {"thread_id": THREAD_ID}},
    )

    assert result["status"] == "succeeded"
    assert calls.index("pause_for_approval") < calls.index("resume_approval")
    assert calls.index("resume_approval") < calls.index("dispatch_action")


def test_deny_route_never_dispatches() -> None:
    calls: list[str] = []
    graph = buildJarvisGraph(
        nodes=workflow_nodes(policy_status="denied", calls=calls),
        checkpointer=durable_checkpointer(),
    )

    result = graph.invoke(
        initial_state(),
        {"configurable": {"thread_id": THREAD_ID}},
    )

    assert result["status"] == "denied"
    assert result["action_results"] == []
    assert "dispatch_action" not in calls
    assert calls[-1] == "render_response"


def test_recoverable_verification_loops_through_one_revision() -> None:
    calls: list[str] = []
    graph = buildJarvisGraph(
        nodes=workflow_nodes(revise_once=True, calls=calls),
        checkpointer=durable_checkpointer(),
    )

    result = graph.invoke(
        initial_state(),
        {
            "configurable": {"thread_id": THREAD_ID},
            "recursion_limit": 50,
        },
    )

    assert result["status"] == "succeeded"
    assert result["revision_count"] == 1
    assert calls.count("revise_plan") == 1
    assert calls.count("evaluate_policy") == 2


@pytest.mark.parametrize(
    ("router", "status", "expected"),
    [
        (routeAfterPolicy, "awaiting_approval", "pause_for_approval"),
        (routeAfterPolicy, "executing", "dispatch_action"),
        (routeAfterPolicy, "denied", "render_response"),
        (routeAfterApproval, "executing", "dispatch_action"),
        (routeAfterApproval, "expired", "render_response"),
        (routeAfterVerification, "planning", "revise_plan"),
        (routeAfterVerification, "failed", "render_response"),
    ],
)
def test_deterministic_routers_use_only_explicit_status(
    router,
    status: str,
    expected: str,
) -> None:
    state = initial_state()
    state["status"] = status

    assert router(state) == expected


@pytest.mark.parametrize(
    ("router", "code"),
    [
        (routeAfterPolicy, "invalid_policy_route"),
        (routeAfterApproval, "invalid_approval_route"),
        (routeAfterVerification, "invalid_verification_route"),
    ],
)
def test_deterministic_routers_fail_closed(router, code: str) -> None:
    state = initial_state()
    state["status"] = "created"

    with pytest.raises(GraphContractError) as captured:
        router(state)

    assert captured.value.code == code


def test_missing_or_extra_node_fails_before_compilation() -> None:
    missing = workflow_nodes()
    missing.pop("render_response")
    with pytest.raises(GraphContractError) as captured:
        buildJarvisGraph(
            nodes=missing,
            checkpointer=durable_checkpointer(),
        )
    assert captured.value.code == "node_registry_incompatible"

    extra = workflow_nodes()
    extra["hidden_node"] = NodeSpec(lambda state: {})
    with pytest.raises(GraphContractError) as captured:
        buildJarvisGraph(
            nodes=extra,
            checkpointer=durable_checkpointer(),
        )
    assert captured.value.code == "node_registry_incompatible"


def test_node_version_mismatch_fails_closed_without_invocation() -> None:
    calls: list[str] = []
    nodes = workflow_nodes(calls=calls)
    nodes["create_plan"] = NodeSpec(
        nodes["create_plan"].action,
        contract_version="2.0",
    )

    with pytest.raises(GraphContractError) as captured:
        buildJarvisGraph(
            nodes=nodes,
            checkpointer=durable_checkpointer(),
        )

    assert captured.value.code == "node_contract_incompatible"
    assert calls == []


@pytest.mark.parametrize(
    "checkpointer",
    [
        CheckpointerSpec(saver=InMemorySaver(), durable=False),
        CheckpointerSpec(
            saver=InMemorySaver(),
            durable=True,
            contract_version="2.0",
        ),
    ],
)
def test_non_durable_or_version_mismatched_checkpointer_fails(
    checkpointer: CheckpointerSpec,
) -> None:
    with pytest.raises(GraphContractError) as captured:
        buildJarvisGraph(
            nodes=workflow_nodes(),
            checkpointer=checkpointer,
        )

    assert captured.value.code == "checkpointer_incompatible"


class BadReducerState(TypedDict):
    contract_version: str
    task_id: str
    thread_id: str
    actor_id: str
    device_id: str
    request: dict[str, Any]
    context_refs: list[str]
    intent: dict[str, Any] | None
    plan: dict[str, Any] | None
    policy_decisions: list[dict[str, Any]]
    pending_approval: dict[str, Any] | None
    action_results: Annotated[list[dict[str, Any]], operator.add]
    observations: Annotated[list[dict[str, Any]], operator.add]
    errors: list[dict[str, Any]]
    status: str
    revision_count: int
    final_response: dict[str, Any] | None


def test_incompatible_state_reducer_fails_before_compilation() -> None:
    with pytest.raises(GraphContractError) as captured:
        buildJarvisGraph(
            nodes=workflow_nodes(),
            checkpointer=durable_checkpointer(),
            state_schema=BadReducerState,  # type: ignore[arg-type]
        )

    assert captured.value.code == "state_reducer_incompatible"


@pytest.mark.parametrize(
    "settings",
    [
        GraphBuildSettings(contract_version="2.0"),
        GraphBuildSettings(state_schema_version="2.0"),
        GraphBuildSettings(graph_name=" "),
    ],
)
def test_incompatible_build_settings_fail_closed(
    settings: GraphBuildSettings,
) -> None:
    with pytest.raises(GraphContractError) as captured:
        buildJarvisGraph(
            nodes=workflow_nodes(),
            checkpointer=durable_checkpointer(),
            settings=settings,
        )

    assert captured.value.code == "graph_settings_incompatible"
