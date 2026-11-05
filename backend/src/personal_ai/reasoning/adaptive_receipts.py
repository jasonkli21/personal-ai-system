"""Additive progress format for admitted adaptive plans."""

from typing import Literal

from pydantic import model_validator

from personal_ai.contracts.reasoning_workflow import ReasoningProgress

from .adaptive import COMPARE, SelectionDecisionV1


class AdaptiveProgress(ReasoningProgress):
    schema_version: Literal["reasoning-adaptive-progress-v2"] = "reasoning-adaptive-progress-v2"
    strategy: Literal["candidate_compare"] = "candidate_compare"
    strategy_version: Literal["candidate-compare-objective.v1"] = COMPARE
    selection: Literal["objective_alternative"] = "objective_alternative"
    adaptive_decision: SelectionDecisionV1

    @model_validator(mode="after")
    def canary_identity(self):
        if self.adaptive_decision.mode not in {"local_fixture_canary", "offline_fixture"}:
            raise ValueError("adaptive_progress_invalid")
        return self
