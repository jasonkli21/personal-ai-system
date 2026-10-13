"""Bounded decision-time routing features and exact compatibility identities."""

import hashlib
import json

from personal_ai.routing.decision_models import RoutingFeatureContext, StrategyView

FEATURE_SCHEMA = "routing-features-v1"


def digest(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def token_bucket(tokens: int | None) -> int | None:
    return tokens.bit_length() if tokens is not None else None


def feature_context_for(application_id, task, request) -> RoutingFeatureContext:
    return RoutingFeatureContext(
        application_id=application_id,
        task_id=task.task_id,
        task_profile_id=task.profile_id,
        task_profile_version=task.profile_version,
        # Full routing configuration, including quota/cascade preferences.
        task_configuration_sha256=digest(task),
        requirements_sha256=digest(request.requirements),
        policy_sha256=digest(request.policy_version),
        input_token_bucket=token_bucket(request.requirements.input_tokens),
        output_token_bucket=token_bucket(request.requirements.output_tokens),
    )


def coverage_identity(view: StrategyView) -> str:
    """Changing any endpoint/account/tier/count/quality/config fact demotes evidence.

    Dynamic health/quota snapshots are features, not static coverage authority.
    Exact candidate composition is deliberately conservative for this experiment.
    """
    return digest(
        {
            "context": view.feature_context.model_dump(mode="json")
            if view.feature_context
            else None,
            "endpoints": sorted(
                (
                    c.endpoint.endpoint_profile_id,
                    c.endpoint.profile_version,
                    c.endpoint_configuration_sha256,
                    c.quality_identity_sha256,
                )
                for c in view.candidates
            ),
        }
    )


def extract_features(view: StrategyView) -> tuple[dict, ...]:
    """Explicit allowlist; replay never reads prompt/context/domain payloads."""
    from personal_ai.routing.strategy import QuotaAwareDeterministicStrategy

    ranks = {r.endpoint: i for i, r in enumerate(QuotaAwareDeterministicStrategy().select(view))}
    buckets = {b.bucket_id: b for b in view.quota_buckets}
    rows = []
    for candidate in view.candidates:
        sends = []
        for edge in candidate.quota_requirements:
            bucket = buckets[edge.bucket_id]
            if edge.reservation_units == 0:
                continue
            if bucket.remaining_units is None or edge.reservation_units is None:
                sends.append(None)
            else:
                sends.append(bucket.remaining_units // edge.reservation_units)
        capacity = min(sends) if sends and all(x is not None for x in sends) else None
        rows.append(
            {
                "endpoint": candidate.endpoint.model_dump(mode="json"),
                "quality": candidate.quality_score,
                "health": candidate.health_status,
                "remaining_send_bucket": token_bucket(capacity) if capacity is not None else None,
                "deterministic_rank": ranks[candidate.endpoint],
            }
        )
    return tuple(rows)
