"""scoring ranking policy."""

from __future__ import annotations

from uuid import UUID

from personal_ai.decisions.contracts import (
    CandidateEvaluation,
    FeatureScore,
)
from personal_ai.entities.research import (
    CanonicalEntity,
)
from personal_ai.ranking.normalization import normalize_name


def rank_with_domain_features(
    evaluations: tuple[CandidateEvaluation, ...],
    entities: tuple[CanonicalEntity, ...],
    features_by_entity: dict[UUID, tuple[FeatureScore, ...]],
    fallback_state: str,
) -> tuple[tuple[CandidateEvaluation, ...], str, UUID | None]:
    """Apply registered domain features after the shared eligibility filter.

    Phase 6 eligibility and exclusion outcomes are preserved. The shared stage
    combines its preference score with a domain feature score at equal weight,
    then applies the same stable name/entity tie breakers as rank-v1.
    """
    names = {entity.id: normalize_name(entity.canonical_name) for entity in entities}
    combined: dict[UUID, CandidateEvaluation] = {}
    for evaluation in evaluations:
        extra = features_by_entity.get(evaluation.entity_id, ()) if evaluation.eligibility else ()
        features = (*evaluation.feature_values, *extra)
        base_score = evaluation.score
        domain_values = [item for item in extra if item.value is not None and item.weight > 0]
        domain_weight = sum(item.weight for item in domain_values)
        domain_score = (
            sum(item.value * item.weight for item in domain_values) / domain_weight
            if domain_weight > 0
            else None
        )
        if base_score is None:
            score = domain_score
        elif domain_score is None:
            score = base_score
        else:
            score = 0.5 * base_score + 0.5 * domain_score
        combined[evaluation.entity_id] = evaluation.model_copy(
            update={"feature_values": features, "score": score, "rank": None}
        )

    eligible = [item for item in combined.values() if item.eligibility]
    eligible.sort(
        key=lambda item: (
            item.score is None,
            -(item.score if item.score is not None else 0),
            names.get(item.entity_id, ""),
            str(item.entity_id),
        )
    )
    ranked_ids = [item.entity_id for item in eligible if item.score is not None]
    ranked = {
        entity_id: combined[entity_id].model_copy(update={"rank": index + 1})
        for index, entity_id in enumerate(ranked_ids)
    }
    combined.update(ranked)
    selected = ranked_ids[0] if ranked_ids else None
    if selected is not None:
        state = "recommended"
    elif eligible:
        state = "eligible_unranked"
    else:
        # Keep the core distinction between research-needed and no-match.
        state = fallback_state
    return tuple(combined[item.entity_id] for item in evaluations), state, selected
