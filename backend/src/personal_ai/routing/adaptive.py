"""Pure bounded preference experiment behind RoutingStrategy; shadow-only rollout."""

from datetime import datetime, timedelta
from time import perf_counter_ns, thread_time_ns
from typing import Literal

from pydantic import Field, model_validator

from personal_ai.routing.decision_models import (
    RoutingShadowObservation,
    StrategyRef,
    _aware,
    _FrozenModel,
)
from personal_ai.routing.features import FEATURE_SCHEMA, coverage_identity, digest, extract_features
from personal_ai.routing.strategy import QuotaAwareDeterministicStrategy, implementation_sha256_for


class AdaptiveArtifact(_FrozenModel):
    schema_version: Literal[1] = 1
    strategy_id: Literal["bounded-capacity-rule"] = "bounded-capacity-rule"
    strategy_version: Literal["1"] = "1"
    feature_schema: str = Field(default=FEATURE_SCHEMA, max_length=100)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline: StrategyRef = QuotaAwareDeterministicStrategy.ref
    baseline_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_sha256s: tuple[str, ...] = Field(min_length=1, max_length=128)
    measured_at: datetime
    fresh_until: datetime
    maximum_quality_drop: float = Field(default=0.02, ge=0, le=0.02)
    maximum_input_bucket: int = Field(default=11, ge=0, le=21)
    maximum_latency_us: int = Field(default=5000, ge=1, le=5000)
    # This is a transparent rule, not a calibrated probability model.
    calibration: Literal["unavailable-rule-margin-only"] = "unavailable-rule-margin-only"
    rollout: Literal["shadow"] = "shadow"

    @model_validator(mode="after")
    def validate_artifact(self):
        _aware(self.measured_at)
        _aware(self.fresh_until)
        if not self.measured_at < self.fresh_until <= self.measured_at + timedelta(days=30):
            raise ValueError("adaptive_artifact_freshness_invalid")
        if len(set(self.coverage_sha256s)) != len(self.coverage_sha256s) or any(
            len(x) != 64 or any(c not in "0123456789abcdef" for c in x)
            for x in self.coverage_sha256s
        ):
            raise ValueError("adaptive_coverage_invalid")
        if len(self.model_dump_json().encode()) > 16384:
            raise ValueError("adaptive_metadata_too_large")
        return self

    @property
    def sha256(self):
        return digest(self)

    @property
    def ref(self):
        return StrategyRef(
            strategy_id=self.strategy_id,
            semantic_version=self.strategy_version,
            artifact_id=f"sha256:{self.sha256}",
        )


class BoundedCapacityStrategy:
    """Strategy 1: conserve free capacity for small tasks within a quality tolerance.

    No learned quality estimates, network/model call, history query or exploration.
    Unknown capacity/quality and ties abstain. Policy remains with the router.
    """

    def __init__(self, artifact: AdaptiveArtifact):
        self.artifact = AdaptiveArtifact.model_validate(artifact.model_dump())
        self.ref = self.artifact.ref

    def propose(self, view):
        baseline = QuotaAwareDeterministicStrategy().select(view)
        artifact = self.artifact
        reason = None
        if view.feature_context is None or view.observed_at is None:
            reason = "decision-features-unavailable"
        elif (
            artifact.feature_schema != FEATURE_SCHEMA
            or view.feature_context.schema_version != FEATURE_SCHEMA
        ):
            reason = "feature-schema-incompatible"
        elif not artifact.measured_at <= view.observed_at < artifact.fresh_until:
            reason = "artifact-stale"
        elif artifact.baseline != QuotaAwareDeterministicStrategy.ref or (
            artifact.baseline_implementation_sha256
            != implementation_sha256_for(QuotaAwareDeterministicStrategy())
        ):
            reason = "baseline-incompatible"
        elif artifact.strategy_implementation_sha256 != rule_implementation_sha256():
            reason = "strategy-implementation-incompatible"
        elif any(c.endpoint_configuration_sha256 is None for c in view.candidates):
            reason = "endpoint-configuration-unavailable"
        elif coverage_identity(view) not in artifact.coverage_sha256s:
            reason = "out-of-coverage"
        elif view.feature_context.input_token_bucket is None:
            reason = "input-count-unavailable"
        elif view.feature_context.input_token_bucket > artifact.maximum_input_bucket:
            reason = "complexity-abstention"
        if reason:
            return baseline, reason
        features = extract_features(view)
        if not features or any(
            f["quality"] is None or f["remaining_send_bucket"] is None for f in features
        ):
            return baseline, "supported-signals-missing"
        best_quality = max(f["quality"] for f in features)
        covered = [
            f for f in features if f["quality"] + artifact.maximum_quality_drop >= best_quality
        ]
        covered.sort(key=lambda f: (-f["remaining_send_bucket"], f["deterministic_rank"]))
        winner = covered[0]
        current = next(f for f in features if f["deterministic_rank"] == 0)
        if (
            winner["deterministic_rank"] == 0
            or winner["remaining_send_bucket"] <= current["remaining_send_bucket"]
        ):
            return baseline, "no-supported-resource-margin"
        endpoint_id = winner["endpoint"]["endpoint_profile_id"]
        ranking = sorted(baseline, key=lambda r: r.endpoint.endpoint_profile_id != endpoint_id)
        # Scores encode the final preference order; retain a stable bounded code.
        return tuple(
            r.model_copy(update={"score": len(ranking) - i, "reason_code": "bounded-capacity-rule"})
            for i, r in enumerate(ranking)
        ), None

    def select(self, view):
        # A shadow artifact grants no rollout authority, including when an
        # internal caller injects this strategy without the configured wrapper.
        # Preference proposals are consumed only by offline/shadow observation.
        return QuotaAwareDeterministicStrategy().select(view)


class ShadowRoutingStrategy:
    """Composition of the same strategy seam. Visible ranking stays deterministic."""

    def __init__(self, adaptive):
        self.baseline = QuotaAwareDeterministicStrategy()
        self.adaptive = adaptive
        # Replay and P19 producer identity describe the visible baseline, not shadow.
        self.ref = self.baseline.ref
        self.tie_break_version = self.baseline.tie_break_version
        self.dependencies = self.baseline.dependencies
        self.implementation_sha256 = self.baseline.implementation_sha256
        self.artifact_sha256 = adaptive.artifact.sha256
        self.artifact_metadata_json = adaptive.artifact.model_dump_json()

    def select(self, view):
        return self.baseline.select(view)

    def observe(self, view, ranking):
        if not ranking:
            return None
        started, cpu_started = perf_counter_ns(), thread_time_ns()
        reason = None
        coverage = coverage_identity(view)
        try:
            proposal, reason = self.adaptive.propose(view)
            if (
                len(proposal) != len(ranking)
                or len({r.endpoint for r in proposal}) != len(ranking)
                or {r.endpoint for r in proposal} != {r.endpoint for r in ranking}
            ):
                raise ValueError("adaptive_ranking_invalid")
        except Exception:  # noqa: BLE001 - safe code, never exception/prompt text
            proposal, reason = ranking, "strategy-unavailable"
        elapsed = max(0, (perf_counter_ns() - started) // 1000)
        cpu = max(0, (thread_time_ns() - cpu_started) // 1000)
        if elapsed > self.adaptive.artifact.maximum_latency_us:
            proposal, reason = ranking, "strategy-overhead-exceeded"
        return RoutingShadowObservation(
            strategy=self.adaptive.ref,
            artifact_sha256=self.artifact_sha256,
            artifact_metadata_json=self.artifact_metadata_json,
            coverage_sha256=coverage,
            candidate_endpoints=tuple(c.endpoint for c in view.candidates),
            deterministic_choice=ranking[0].endpoint,
            ranking=proposal,
            agreement=proposal[0].endpoint == ranking[0].endpoint,
            abstention_reason=reason,
            latency_us=elapsed,
            cpu_us=cpu,
        )


def configured_routing_strategy(settings):
    """Default-off rollback and explicit registration; unknown implementations fail closed."""
    if not settings.routing_shadow_enabled:
        return QuotaAwareDeterministicStrategy()
    artifact = AdaptiveArtifact.model_validate(settings.routing_shadow_artifact)
    return ShadowRoutingStrategy(ADAPTIVE_STRATEGIES[artifact.strategy_id](artifact))


ADAPTIVE_STRATEGIES = {"bounded-capacity-rule": BoundedCapacityStrategy}


def rule_implementation_sha256():
    from personal_ai.routing.features import token_bucket
    from personal_ai.routing.strategy import _implementation_sha256

    return _implementation_sha256(
        BoundedCapacityStrategy.propose, BoundedCapacityStrategy.select,
        extract_features, coverage_identity, digest, token_bucket
    )
