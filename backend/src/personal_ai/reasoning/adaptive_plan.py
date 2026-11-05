"""Strict additive plan decoder for bounded candidate comparison."""

from typing import Literal

from pydantic import model_validator

from .adaptive import (
    COMPARE,
    FINITE,
    SelectionDecisionV1,
    candidate_steps,
    finite_features,
    finite_reason,
)
from .adaptive_control import SignedEvidence
from .orchestration import Plan, digest


class AdaptivePlan(Plan):
    schema_version: Literal["reasoning-adaptive-run-v2"] = "reasoning-adaptive-run-v2"
    strategy: Literal["candidate_compare"] = "candidate_compare"
    strategy_version: Literal["candidate-compare-objective.v1"] = COMPARE
    selection: Literal["objective_alternative"] = "objective_alternative"
    adaptive_decision: SelectionDecisionV1
    approval: SignedEvidence | None = None
    ablation: Literal["none", "no_features", "no_early_exit", "no_compare"] = "none"

    @model_validator(mode="after")
    def validate_template(self):
        receipt = self.adaptive_decision
        features = finite_features(self)
        steps = candidate_steps()
        if self.ablation == "no_compare":
            steps = steps[:2]
        reason = finite_reason(features)
        if (
            not (reason == "eligible" or self.ablation == "no_features" and reason == "no_marginal_value")
            or self.steps != steps
            or receipt.mode == "shadow"
            or receipt.policy != FINITE.policy
            or receipt.recommendation != "candidate_compare"
            or (receipt.mode == "local_fixture_canary") != (self.approval is not None)
            or self.approval is not None and (
                self.ablation != "none" or not self.binds_approval(self.approval.evidence)
            )
            or receipt.feature_digest != digest(features.model_dump(mode="json"))
            or not self.task.requirements
        ):
            raise ValueError("adaptive_plan_invalid")
        return self

    def binds_approval(self, evidence):
        return (
            self.adaptive_decision.evidence_digest == evidence.identity
            and self.adaptive_decision.build_digest == evidence.build_digest
            and self.adaptive_decision.policy_digest == evidence.policy_digest
            and self.scope_digest == evidence.scope_digest
            and self.endpoint_digest == evidence.endpoint_digest
            and self.task.kind == evidence.family and self.effort == evidence.effort
            and self.limits == evidence.limits
        )


def compile_candidate(baseline, receipt, *, approval=None, ablation="none"):
    return AdaptivePlan.model_validate({
        **baseline.model_dump(exclude={"schema_version", "strategy", "strategy_version", "selection", "steps"}),
        "steps": candidate_steps()[:2] if ablation == "no_compare" else candidate_steps(),
        "adaptive_decision": receipt, "ablation": ablation, "approval": approval,
    })
