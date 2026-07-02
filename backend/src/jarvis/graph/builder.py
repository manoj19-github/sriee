"""Pure, versioned LangGraph construction for Global ID 120000."""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal, get_args, get_origin, get_type_hints

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from jarvis.graph.state import JarvisState


GRAPH_CONTRACT_VERSION = "1.0"
STATE_SCHEMA_VERSION = "1.0"

REQUIRED_NODE_NAMES = (
    "normalize_request",
    "load_context",
    "classify_intent",
    "create_plan",
    "validate_plan",
    "evaluate_policy",
    "pause_for_approval",
    "resume_approval",
    "dispatch_action",
    "collect_action_result",
    "verify_outcome",
    "revise_plan",
    "render_response",
)

APPEND_REDUCER_FIELDS = frozenset(
    {"action_results", "observations", "errors"}
)

TERMINAL_STATUSES = frozenset(
    {
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
        "denied",
        "expired",
    }
)


class GraphContractError(RuntimeError):
    """A sanitized graph composition failure safe for startup diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS graph construction failed: {code}")


@dataclass(frozen=True, slots=True)
class GraphBuildSettings:
    """Versions and non-secret compile settings for one graph definition."""

    contract_version: str = GRAPH_CONTRACT_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION
    graph_name: str = "jarvis-core-v1"
    debug: bool = False


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """One version-bound node callable supplied by its owning function."""

    action: Callable[..., Any]
    contract_version: str = GRAPH_CONTRACT_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class CheckpointerSpec:
    """Trusted composition-root assertion around a configured saver."""

    saver: BaseCheckpointSaver[Any]
    durable: bool
    contract_version: str = GRAPH_CONTRACT_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION


PolicyRoute = Literal[
    "pause_for_approval",
    "dispatch_action",
    "render_response",
]
ApprovalRoute = Literal["dispatch_action", "render_response"]
VerificationRoute = Literal["revise_plan", "render_response"]


def routeAfterPolicy(state: JarvisState) -> PolicyRoute:
    """Route only from the policy node's explicit workflow status."""

    status = state["status"]
    if status == "awaiting_approval":
        return "pause_for_approval"
    if status == "executing":
        return "dispatch_action"
    if status == "denied":
        return "render_response"
    raise GraphContractError("invalid_policy_route")


def routeAfterApproval(state: JarvisState) -> ApprovalRoute:
    """Route an exact approval outcome without consulting a model."""

    status = state["status"]
    if status == "executing":
        return "dispatch_action"
    if status in {"denied", "expired"}:
        return "render_response"
    raise GraphContractError("invalid_approval_route")


def routeAfterVerification(state: JarvisState) -> VerificationRoute:
    """Route recoverable work to one revision or terminal work to response."""

    status = state["status"]
    if status == "planning":
        return "revise_plan"
    if status in TERMINAL_STATUSES:
        return "render_response"
    raise GraphContractError("invalid_verification_route")


def _validate_settings(settings: GraphBuildSettings) -> None:
    if (
        settings.contract_version != GRAPH_CONTRACT_VERSION
        or settings.state_schema_version != STATE_SCHEMA_VERSION
        or not settings.graph_name.strip()
        or len(settings.graph_name) > 64
    ):
        raise GraphContractError("graph_settings_incompatible")


def _validate_state_schema(state_schema: type[JarvisState]) -> None:
    try:
        actual_hints = get_type_hints(state_schema, include_extras=True)
        expected_hints = get_type_hints(JarvisState, include_extras=True)
    except (NameError, TypeError):
        raise GraphContractError("state_schema_incompatible") from None

    if set(actual_hints) != set(expected_hints) or set(
        getattr(state_schema, "__required_keys__", ())
    ) != set(expected_hints):
        raise GraphContractError("state_schema_incompatible")

    for field_name, expected_annotation in expected_hints.items():
        annotation = actual_hints[field_name]
        if field_name in APPEND_REDUCER_FIELDS:
            expected_value_type = get_args(expected_annotation)[0]
            if (
                get_origin(annotation) is not Annotated
                or get_args(annotation)[0] != expected_value_type
                or operator.add not in get_args(annotation)[1:]
            ):
                raise GraphContractError("state_reducer_incompatible")
        elif annotation != expected_annotation:
            raise GraphContractError("state_schema_incompatible")


def _validate_nodes(
    nodes: Mapping[str, NodeSpec],
    settings: GraphBuildSettings,
) -> None:
    if set(nodes) != set(REQUIRED_NODE_NAMES):
        raise GraphContractError("node_registry_incompatible")
    for name in REQUIRED_NODE_NAMES:
        spec = nodes[name]
        if (
            not isinstance(spec, NodeSpec)
            or not callable(spec.action)
            or spec.contract_version != settings.contract_version
            or spec.state_schema_version != settings.state_schema_version
        ):
            raise GraphContractError("node_contract_incompatible")


def _validate_checkpointer(
    checkpointer: CheckpointerSpec,
    settings: GraphBuildSettings,
) -> None:
    if (
        not isinstance(checkpointer, CheckpointerSpec)
        or not isinstance(checkpointer.saver, BaseCheckpointSaver)
        or checkpointer.durable is not True
        or checkpointer.contract_version != settings.contract_version
        or checkpointer.state_schema_version != settings.state_schema_version
    ):
        raise GraphContractError("checkpointer_incompatible")


def buildJarvisGraph(
    *,
    nodes: Mapping[str, NodeSpec],
    checkpointer: CheckpointerSpec,
    settings: GraphBuildSettings | None = None,
    state_schema: type[JarvisState] = JarvisState,
) -> CompiledStateGraph[JarvisState, Any, JarvisState, JarvisState]:
    """Validate and compile the fixed JARVIS workflow without invoking a node."""

    selected_settings = settings or GraphBuildSettings()
    _validate_settings(selected_settings)
    _validate_state_schema(state_schema)
    _validate_nodes(nodes, selected_settings)
    _validate_checkpointer(checkpointer, selected_settings)

    builder = StateGraph(state_schema)
    for name in REQUIRED_NODE_NAMES:
        builder.add_node(name, nodes[name].action)

    builder.add_edge(START, "normalize_request")
    builder.add_edge("normalize_request", "load_context")
    builder.add_edge("load_context", "classify_intent")
    builder.add_edge("classify_intent", "create_plan")
    builder.add_edge("create_plan", "validate_plan")
    builder.add_edge("validate_plan", "evaluate_policy")
    builder.add_conditional_edges(
        "evaluate_policy",
        routeAfterPolicy,
        {
            "pause_for_approval": "pause_for_approval",
            "dispatch_action": "dispatch_action",
            "render_response": "render_response",
        },
    )
    builder.add_edge("pause_for_approval", "resume_approval")
    builder.add_conditional_edges(
        "resume_approval",
        routeAfterApproval,
        {
            "dispatch_action": "dispatch_action",
            "render_response": "render_response",
        },
    )
    builder.add_edge("dispatch_action", "collect_action_result")
    builder.add_edge("collect_action_result", "verify_outcome")
    builder.add_conditional_edges(
        "verify_outcome",
        routeAfterVerification,
        {
            "revise_plan": "revise_plan",
            "render_response": "render_response",
        },
    )
    builder.add_edge("revise_plan", "validate_plan")
    builder.add_edge("render_response", END)

    try:
        return builder.compile(
            checkpointer=checkpointer.saver,
            debug=selected_settings.debug,
            name=selected_settings.graph_name,
        )
    except Exception:
        raise GraphContractError("graph_compile_failed") from None
