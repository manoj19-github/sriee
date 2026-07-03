"""Deterministic plan-policy evaluation for Global ID 120006."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from jarvis.graph.context import REFERENCE_ID_PATTERN, REFERENCE_VERSION_PATTERN
from jarvis.graph.normalize import PRINCIPAL_ID_PATTERN, TASK_ID_PATTERN
from jarvis.graph.plan import (
    CAPABILITY_ID_PATTERN,
    PlanActionDraft,
    PlanDraft,
)


RULE_ID_PATTERN = re.compile(r"^prl_[A-Za-z0-9_-]{8,128}$")
REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
GRANT_ID_PATTERN = re.compile(r"^grt_[A-Za-z0-9_-]{8,128}$")
DECISION_ID_PATTERN = re.compile(r"^pdc_[0-9a-f]{24}$")


class PlanPolicyError(RuntimeError):
    """A content-free policy failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS plan policy evaluation failed: {code}")


class PolicyDecisionKind(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class RiskTier(StrEnum):
    R0 = "r0"
    R1 = "r1"
    R2 = "r2"
    R3 = "r3"
    R4 = "r4"


DECISION_RANK = {
    PolicyDecisionKind.ALLOW: 0,
    PolicyDecisionKind.ASK: 1,
    PolicyDecisionKind.DENY: 2,
}
RISK_RANK = {
    RiskTier.R0: 0,
    RiskTier.R1: 1,
    RiskTier.R2: 2,
    RiskTier.R3: 3,
    RiskTier.R4: 4,
}


class PolicyActionRule(BaseModel):
    """One deterministic capability/version rule from a trusted snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=RULE_ID_PATTERN.pattern)
    capability_id: str = Field(pattern=CAPABILITY_ID_PATTERN.pattern)
    capability_version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    decision: PolicyDecisionKind
    risk_tier: RiskTier
    reason_code: str = Field(pattern=REASON_CODE_PATTERN.pattern)
    grant_reference_id: str | None = Field(
        default=None,
        pattern=GRANT_ID_PATTERN.pattern,
    )

    @model_validator(mode="after")
    def validate_safety_floor(self) -> PolicyActionRule:
        if self.risk_tier is RiskTier.R4 and (
            self.decision is not PolicyDecisionKind.DENY
        ):
            raise ValueError("R4 rules must deny")
        if self.risk_tier is RiskTier.R3 and (
            self.decision is PolicyDecisionKind.ALLOW
            or self.grant_reference_id is not None
        ):
            raise ValueError("R3 rules require fresh approval or denial")
        if (
            self.risk_tier is RiskTier.R2
            and self.decision is PolicyDecisionKind.ALLOW
            and self.grant_reference_id is None
        ):
            raise ValueError("R2 allow requires a scoped grant")
        if (
            self.decision is not PolicyDecisionKind.ALLOW
            and self.grant_reference_id is not None
        ):
            raise ValueError("unused grant reference")
        return self


class PolicyAggregateRule(BaseModel):
    """A combination rule that prevents individually harmless risk splitting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=RULE_ID_PATTERN.pattern)
    capability_ids: tuple[str, ...] = Field(min_length=1, max_length=16)
    minimum_matches: int = Field(ge=2, le=8)
    decision: PolicyDecisionKind
    risk_tier: RiskTier
    reason_code: str = Field(pattern=REASON_CODE_PATTERN.pattern)

    @model_validator(mode="after")
    def validate_aggregate_rule(self) -> PolicyAggregateRule:
        if (
            len(self.capability_ids) != len(set(self.capability_ids))
            or any(
                not CAPABILITY_ID_PATTERN.fullmatch(capability_id)
                for capability_id in self.capability_ids
            )
            or self.decision is PolicyDecisionKind.ALLOW
            or self.risk_tier in {RiskTier.R0, RiskTier.R1}
            or (
                self.risk_tier is RiskTier.R4
                and self.decision is not PolicyDecisionKind.DENY
            )
            or (
                self.risk_tier is RiskTier.R3
                and self.decision is PolicyDecisionKind.ALLOW
            )
        ):
            raise ValueError("invalid aggregate policy rule")
        return self


class PolicySnapshot(BaseModel):
    """Signed/effective policy projection resolved outside graph state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: str = Field(pattern=r"^pol_[A-Za-z0-9_-]{8,128}$")
    version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    actor_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    device_id: str = Field(pattern=PRINCIPAL_ID_PATTERN.pattern)
    default_decision: PolicyDecisionKind = PolicyDecisionKind.DENY
    default_risk_tier: RiskTier = RiskTier.R4
    action_rules: tuple[PolicyActionRule, ...] = Field(
        default=(),
        max_length=64,
    )
    aggregate_rules: tuple[PolicyAggregateRule, ...] = Field(
        default=(),
        max_length=16,
    )

    @model_validator(mode="after")
    def validate_deny_by_default(self) -> PolicySnapshot:
        action_keys = [
            (rule.capability_id, rule.capability_version)
            for rule in self.action_rules
        ]
        rule_ids = [
            rule.rule_id
            for rule in (*self.action_rules, *self.aggregate_rules)
        ]
        if (
            self.default_decision is not PolicyDecisionKind.DENY
            or self.default_risk_tier is not RiskTier.R4
            or len(action_keys) != len(set(action_keys))
            or len(rule_ids) != len(set(rule_ids))
        ):
            raise ValueError("policy snapshot is not deny-by-default")
        return self


class PolicyDecision(BaseModel):
    """Minimal checkpoint-safe preliminary decision for one exact action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(pattern=DECISION_ID_PATTERN.pattern)
    action_id: str = Field(pattern=r"^act_[0-9a-f]{24}$")
    decision: PolicyDecisionKind
    risk_tier: RiskTier
    reason_codes: tuple[str, ...] = Field(min_length=1, max_length=40)
    policy_reference_id: str = Field(pattern=r"^pol_[A-Za-z0-9_-]{8,128}$")
    policy_version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)
    grant_reference_id: str | None = Field(
        default=None,
        pattern=GRANT_ID_PATTERN.pattern,
    )
    requires_fresh_approval: bool

    @model_validator(mode="after")
    def validate_decision_contract(self) -> PolicyDecision:
        if (
            len(self.reason_codes) != len(set(self.reason_codes))
            or any(
                not REASON_CODE_PATTERN.fullmatch(code)
                for code in self.reason_codes
            )
            or self.requires_fresh_approval
            != (self.decision is PolicyDecisionKind.ASK)
            or (
                self.decision is not PolicyDecisionKind.ALLOW
                and self.grant_reference_id is not None
            )
            or (
                self.risk_tier is RiskTier.R2
                and self.decision is PolicyDecisionKind.ALLOW
                and self.grant_reference_id is None
            )
            or (
                self.risk_tier is RiskTier.R3
                and self.decision is PolicyDecisionKind.ALLOW
            )
            or (
                self.risk_tier is RiskTier.R4
                and self.decision is not PolicyDecisionKind.DENY
            )
        ):
            raise ValueError("invalid policy decision")
        return self


class SecurityRecommendation(BaseModel):
    """Untrusted security-model advice that can only tighten policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str | None = Field(
        default=None,
        pattern=r"^act_[0-9a-f]{24}$",
    )
    decision: PolicyDecisionKind
    risk_tier: RiskTier
    reason_code: str = Field(pattern=REASON_CODE_PATTERN.pattern)


class SecurityAssessment(BaseModel):
    """Bounded result from an optional security analysis specialist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendations: tuple[SecurityRecommendation, ...] = Field(
        default=(),
        max_length=16,
    )


class PolicySnapshotResolver(Protocol):
    async def resolve_policy_snapshot(
        self,
        reference_id: str,
        *,
        actor_id: str,
        device_id: str,
    ) -> PolicySnapshot:
        """Resolve the current authorized deterministic policy snapshot."""


class SecurityPolicyAdvisor(Protocol):
    async def analyze_plan(
        self,
        plan: PlanDraft,
        baseline: tuple[PolicyDecision, ...],
    ) -> SecurityAssessment:
        """Return bounded advice; it has no authority to weaken policy."""


@dataclass(frozen=True, slots=True)
class PlanPolicySettings:
    resolver_timeout_seconds: float = 5.0
    advisor_timeout_seconds: float = 15.0


@dataclass(frozen=True, slots=True)
class PlanPolicyService:
    resolver: PolicySnapshotResolver
    security_advisor: SecurityPolicyAdvisor | None = None
    settings: PlanPolicySettings = PlanPolicySettings()


@dataclass(slots=True)
class _MutableDecision:
    action: PlanActionDraft
    decision: PolicyDecisionKind
    risk_tier: RiskTier
    reason_codes: list[str]
    grant_reference_id: str | None


def _validate_settings(settings: PlanPolicySettings) -> None:
    if (
        settings.resolver_timeout_seconds <= 0
        or settings.resolver_timeout_seconds > 30
        or settings.advisor_timeout_seconds <= 0
        or settings.advisor_timeout_seconds > 60
    ):
        raise PlanPolicyError("plan_policy_settings_incompatible")


def _validate_state(
    state: Mapping[str, Any],
) -> tuple[str, str, str, str, PlanDraft]:
    if (
        state.get("status") != "planning"
        or state.get("plan") is None
        or state.get("policy_decisions") != []
    ):
        raise PlanPolicyError("plan_policy_state_invalid")
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
        raise PlanPolicyError("plan_policy_identity_invalid")
    raw_refs = state.get("context_refs")
    if (
        not isinstance(raw_refs, list)
        or any(
            not isinstance(reference_id, str)
            or not REFERENCE_ID_PATTERN.fullmatch(reference_id)
            for reference_id in raw_refs
        )
        or len(raw_refs) != len(set(raw_refs))
    ):
        raise PlanPolicyError("plan_policy_context_invalid")
    policy_refs = [
        reference_id
        for reference_id in raw_refs
        if reference_id.startswith("pol_")
    ]
    if len(policy_refs) != 1:
        raise PlanPolicyError("plan_policy_context_invalid")
    try:
        plan = PlanDraft.model_validate(state["plan"])
    except (ValidationError, TypeError, ValueError):
        raise PlanPolicyError("plan_policy_plan_invalid") from None
    if plan.schema_version != "1.0" or not plan.actions:
        raise PlanPolicyError("plan_policy_plan_invalid")
    return task_id, actor_id, device_id, policy_refs[0], plan


def _validate_snapshot(
    value: object,
    *,
    reference_id: str,
    actor_id: str,
    device_id: str,
) -> PolicySnapshot:
    if not isinstance(value, PolicySnapshot):
        raise PlanPolicyError("policy_snapshot_invalid")
    try:
        snapshot = PolicySnapshot.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise PlanPolicyError("policy_snapshot_invalid") from None
    if (
        snapshot.reference_id != reference_id
        or snapshot.actor_id != actor_id
        or snapshot.device_id != device_id
    ):
        raise PlanPolicyError("policy_snapshot_invalid")
    return snapshot


def _apply_safety_floor(
    decision: PolicyDecisionKind,
    risk_tier: RiskTier,
    grant_reference_id: str | None,
) -> PolicyDecisionKind:
    if risk_tier is RiskTier.R4:
        return PolicyDecisionKind.DENY
    if (
        risk_tier is RiskTier.R3
        and decision is PolicyDecisionKind.ALLOW
    ):
        return PolicyDecisionKind.ASK
    if (
        risk_tier is RiskTier.R2
        and decision is PolicyDecisionKind.ALLOW
        and grant_reference_id is None
    ):
        return PolicyDecisionKind.ASK
    return decision


def _tighten(
    current: _MutableDecision,
    *,
    decision: PolicyDecisionKind,
    risk_tier: RiskTier,
    reason_code: str,
) -> None:
    if RISK_RANK[risk_tier] > RISK_RANK[current.risk_tier]:
        current.risk_tier = risk_tier
    if DECISION_RANK[decision] > DECISION_RANK[current.decision]:
        current.decision = decision
        current.grant_reference_id = None
    current.decision = _apply_safety_floor(
        current.decision,
        current.risk_tier,
        current.grant_reference_id,
    )
    if current.decision is not PolicyDecisionKind.ALLOW:
        current.grant_reference_id = None
    if reason_code not in current.reason_codes:
        current.reason_codes.append(reason_code)


def _baseline_decisions(
    plan: PlanDraft,
    snapshot: PolicySnapshot,
) -> dict[str, _MutableDecision]:
    rules = {
        (rule.capability_id, rule.capability_version): rule
        for rule in snapshot.action_rules
    }
    decisions: dict[str, _MutableDecision] = {}
    for action in plan.actions:
        rule = rules.get(
            (action.capability_id, action.capability_version)
        )
        if rule is None:
            decision = _MutableDecision(
                action=action,
                decision=snapshot.default_decision,
                risk_tier=snapshot.default_risk_tier,
                reason_codes=["policy_default_deny"],
                grant_reference_id=None,
            )
        else:
            decision = _MutableDecision(
                action=action,
                decision=rule.decision,
                risk_tier=rule.risk_tier,
                reason_codes=[rule.reason_code],
                grant_reference_id=rule.grant_reference_id,
            )
        decisions[action.action_id] = decision
    return decisions


def _apply_aggregate_rules(
    decisions: Mapping[str, _MutableDecision],
    snapshot: PolicySnapshot,
) -> None:
    for rule in sorted(
        snapshot.aggregate_rules,
        key=lambda item: item.rule_id,
    ):
        matched = [
            decision
            for decision in decisions.values()
            if decision.action.capability_id in rule.capability_ids
        ]
        if len(matched) < rule.minimum_matches:
            continue
        for decision in matched:
            _tighten(
                decision,
                decision=rule.decision,
                risk_tier=rule.risk_tier,
                reason_code=rule.reason_code,
            )


def _stable_decision_id(
    task_id: str,
    snapshot: PolicySnapshot,
    decision: _MutableDecision,
) -> str:
    payload = json.dumps(
        {
            "task_id": task_id,
            "action_id": decision.action.action_id,
            "decision": decision.decision.value,
            "risk_tier": decision.risk_tier.value,
            "reason_codes": sorted(decision.reason_codes),
            "policy_reference_id": snapshot.reference_id,
            "policy_version": snapshot.version,
            "grant_reference_id": decision.grant_reference_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "pdc_" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def _project_decisions(
    task_id: str,
    plan: PlanDraft,
    snapshot: PolicySnapshot,
    decisions: Mapping[str, _MutableDecision],
) -> tuple[PolicyDecision, ...]:
    return tuple(
        PolicyDecision(
            decision_id=_stable_decision_id(
                task_id,
                snapshot,
                decisions[action.action_id],
            ),
            action_id=action.action_id,
            decision=decisions[action.action_id].decision,
            risk_tier=decisions[action.action_id].risk_tier,
            reason_codes=tuple(
                sorted(decisions[action.action_id].reason_codes)
            ),
            policy_reference_id=snapshot.reference_id,
            policy_version=snapshot.version,
            grant_reference_id=(
                decisions[action.action_id].grant_reference_id
            ),
            requires_fresh_approval=(
                decisions[action.action_id].decision
                is PolicyDecisionKind.ASK
            ),
        )
        for action in plan.actions
    )


def _validate_assessment(
    value: object,
    action_ids: set[str],
) -> SecurityAssessment:
    if not isinstance(value, SecurityAssessment):
        raise PlanPolicyError("policy_security_assessment_invalid")
    try:
        assessment = SecurityAssessment.model_validate(
            value.model_dump(mode="json")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise PlanPolicyError("policy_security_assessment_invalid") from None
    if any(
        recommendation.action_id is not None
        and recommendation.action_id not in action_ids
        for recommendation in assessment.recommendations
    ):
        raise PlanPolicyError("policy_security_assessment_invalid")
    return assessment


def _apply_security_assessment(
    decisions: Mapping[str, _MutableDecision],
    assessment: SecurityAssessment,
) -> None:
    recommendations = sorted(
        assessment.recommendations,
        key=lambda item: (
            item.action_id or "",
            item.reason_code,
            item.decision.value,
            item.risk_tier.value,
        ),
    )
    for recommendation in recommendations:
        targets = (
            tuple(decisions.values())
            if recommendation.action_id is None
            else (decisions[recommendation.action_id],)
        )
        for target in targets:
            if (
                DECISION_RANK[recommendation.decision]
                <= DECISION_RANK[target.decision]
                and RISK_RANK[recommendation.risk_tier]
                <= RISK_RANK[target.risk_tier]
            ):
                continue
            _tighten(
                target,
                decision=recommendation.decision,
                risk_tier=recommendation.risk_tier,
                reason_code=recommendation.reason_code,
            )


def _workflow_status(
    decisions: tuple[PolicyDecision, ...],
) -> str:
    if any(
        decision.decision is PolicyDecisionKind.DENY
        for decision in decisions
    ):
        return "denied"
    if any(
        decision.decision is PolicyDecisionKind.ASK
        for decision in decisions
    ):
        return "awaiting_approval"
    return "executing"


async def evaluatePlanPolicy(
    state: Mapping[str, Any],
    *,
    service: PlanPolicyService,
) -> dict[str, Any]:
    """Evaluate every validated action under deterministic policy."""

    settings = service.settings
    _validate_settings(settings)
    task_id, actor_id, device_id, policy_ref, plan = _validate_state(state)
    try:
        raw_snapshot = await asyncio.wait_for(
            service.resolver.resolve_policy_snapshot(
                policy_ref,
                actor_id=actor_id,
                device_id=device_id,
            ),
            timeout=settings.resolver_timeout_seconds,
        )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise PlanPolicyError("policy_snapshot_unavailable") from None
    except Exception:
        raise PlanPolicyError("policy_snapshot_unavailable") from None
    snapshot = _validate_snapshot(
        raw_snapshot,
        reference_id=policy_ref,
        actor_id=actor_id,
        device_id=device_id,
    )
    decisions = _baseline_decisions(plan, snapshot)
    _apply_aggregate_rules(decisions, snapshot)

    baseline = _project_decisions(
        task_id,
        plan,
        snapshot,
        decisions,
    )
    if service.security_advisor is not None:
        try:
            raw_assessment = await asyncio.wait_for(
                service.security_advisor.analyze_plan(plan, baseline),
                timeout=settings.advisor_timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise PlanPolicyError(
                "policy_security_analysis_unavailable"
            ) from None
        except Exception:
            raise PlanPolicyError(
                "policy_security_analysis_unavailable"
            ) from None
        assessment = _validate_assessment(
            raw_assessment,
            set(decisions),
        )
        _apply_security_assessment(decisions, assessment)

    projected = _project_decisions(
        task_id,
        plan,
        snapshot,
        decisions,
    )
    return {
        "policy_decisions": [
            decision.model_dump(mode="json")
            for decision in projected
        ],
        "status": _workflow_status(projected),
    }
