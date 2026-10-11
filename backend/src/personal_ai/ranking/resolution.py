"""resolution ranking policy."""

from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
from uuid import UUID

from personal_ai.decisions.contracts import (
    CandidateProposal,
)
from personal_ai.entities.research import (
    CanonicalEntity,
    EntityAlias,
    EntityClaim,
    EntityMatch,
    EvidenceReference,
)
from personal_ai.ranking.claim_verification import (
    CLAIM_VERIFICATION_POLICY_VERSION,
    _claim_value_match,
)
from personal_ai.ranking.normalization import _identifier, normalize_name

RESOLUTION_POLICY_VERSION = "resolve-v2"

IDENTITY_ATTRIBUTES = frozenset(
    {
        "model",
        "sku",
        "catalog_id",
        "product_id",
        "upc",
        "ean",
        "isbn",
        "mpn",
    }
)


def resolve_candidate(
    *,
    decision_id: UUID,
    subject_id: UUID,
    owner_id: str,
    proposal: CandidateProposal,
    proposed_claims: tuple[EntityClaim, ...],
    evidence_refs: tuple[EvidenceReference, ...],
    entities: tuple[CanonicalEntity, ...],
    aliases: tuple[EntityAlias, ...],
    claims_by_entity: dict[UUID, tuple[EntityClaim, ...]],
    new_entity_id: UUID,
    now: datetime,
    threshold: float,
    match_id: UUID,
) -> tuple[EntityMatch, UUID]:
    """Resolve strong identifiers exactly; otherwise abstain or create separately."""
    available = tuple(
        entity
        for entity in entities
        if entity.entity_type == proposal.entity_type
        and entity.status == "active"
        and entity.owner_scope in {f"owner:{owner_id}", "shared"}
    )
    proposed_ids = {
        key.casefold(): _identifier(value) for key, value in proposal.identifiers.items()
    }
    conflicting_identifier_entities = {
        entity.id
        for entity in available
        if any(
            key in {stored_key.casefold() for stored_key in entity.identifiers}
            and value
            != _identifier(
                next(
                    stored_value
                    for stored_key, stored_value in entity.identifiers.items()
                    if stored_key.casefold() == key
                )
            )
            for key, value in proposed_ids.items()
        )
    }
    exact: list[tuple[CanonicalEntity, str]] = []
    for entity in available:
        if entity.id in conflicting_identifier_entities:
            continue
        same = [
            key
            for key, value in proposed_ids.items()
            if key in {k.casefold() for k in entity.identifiers}
            and value
            == _identifier(next(v for k, v in entity.identifiers.items() if k.casefold() == key))
        ]
        if same:
            exact.append((entity, "identifier_exact"))
    if len(exact) == 1:
        entity, feature = exact[0]
        match = EntityMatch(
            id=match_id,
            decision_id=decision_id,
            subject_id=subject_id,
            owner_id=owner_id,
            candidate_entity_id=entity.id,
            candidate_entity_ids=(entity.id,),
            selected_entity_id=entity.id,
            outcome="matched",
            confidence=1.0,
            feature_values={feature: 1.0},
            evidence_ids=tuple(ref.evidence_id for ref in evidence_refs),
            created_at=now,
        )
        return match, entity.id
    if len(exact) > 1:
        ids = tuple(sorted((entity.id for entity, _ in exact), key=str))
        return EntityMatch(
            id=match_id,
            decision_id=decision_id,
            subject_id=subject_id,
            owner_id=owner_id,
            candidate_entity_id=new_entity_id,
            candidate_entity_ids=ids,
            outcome="review",
            confidence=1.0,
            feature_values={"identifier_collision": 1.0},
            evidence_ids=tuple(ref.evidence_id for ref in evidence_refs),
            created_at=now,
        ), new_entity_id

    aliases_by_entity: dict[UUID, list[str]] = {}
    for alias in aliases:
        if alias.owner_id in {owner_id, "*"}:
            aliases_by_entity.setdefault(alias.entity_id, []).append(alias.normalized_alias)
    proposed_name = normalize_name(proposal.canonical_name)
    eligible_proposed = tuple(
        claim
        for claim in proposed_claims
        if claim.attribute.casefold() in IDENTITY_ATTRIBUTES
        and claim.claim_status == "verified"
        and claim.verification_policy_version == CLAIM_VERIFICATION_POLICY_VERSION
        and claim.expires_at > now
    )
    scored: list[tuple[float, CanonicalEntity, dict[str, float]]] = []
    for entity in available:
        if entity.id in conflicting_identifier_entities:
            continue
        name_candidates = [normalize_name(entity.canonical_name)]
        name_candidates.extend(
            normalize_name(alias) for alias in aliases_by_entity.get(entity.id, ())
        )
        similarity = max(
            (SequenceMatcher(None, proposed_name, name).ratio() for name in name_candidates),
            default=0.0,
        )
        stored_claims = tuple(
            claim
            for claim in claims_by_entity.get(entity.id, ())
            if claim.owner_id == owner_id
            and claim.attribute.casefold() in IDENTITY_ATTRIBUTES
            and claim.claim_status == "verified"
            and claim.verification_policy_version == CLAIM_VERIFICATION_POLICY_VERSION
            and claim.expires_at > now
        )
        shared_attributes = sorted(
            {
                left.attribute
                for left in eligible_proposed
                for right in stored_claims
                if left.attribute == right.attribute and _claim_value_match(left, right)
            }
        )
        independent = bool(shared_attributes)
        score = min(1.0, similarity * 0.65 + (0.35 if independent else 0.0))
        features = {"name_similarity": round(similarity, 6)}
        if shared_attributes:
            features["independent_attribute_match"] = 1.0
        if score >= 0.5:
            scored.append((score, entity, features))

    scored.sort(key=lambda item: (-item[0], str(item[1].id)))
    if scored and scored[0][0] >= threshold and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        score, entity, features = scored[0]
        if features.get("independent_attribute_match"):
            match = EntityMatch(
                id=match_id,
                decision_id=decision_id,
                subject_id=subject_id,
                owner_id=owner_id,
                candidate_entity_id=entity.id,
                candidate_entity_ids=(entity.id,),
                selected_entity_id=entity.id,
                outcome="matched",
                confidence=score,
                feature_values=features,
                evidence_ids=tuple(ref.evidence_id for ref in evidence_refs),
                created_at=now,
            )
            return match, entity.id

    if scored:
        top = scored[: min(20, len(scored))]
        best = top[0][0]
        ambiguous = len(top) > 1 and top[1][0] == best
        candidate_ids = tuple(item[1].id for item in top)
        return EntityMatch(
            id=match_id,
            decision_id=decision_id,
            subject_id=subject_id,
            owner_id=owner_id,
            candidate_entity_id=new_entity_id,
            candidate_entity_ids=candidate_ids,
            outcome="review",
            confidence=best,
            feature_values={
                f"candidate_{index}_{key}": value
                for index, (_, _, features) in enumerate(top)
                for key, value in features.items()
            }
            | ({"ambiguous_tie": 1.0} if ambiguous else {})
            | ({"conflicting_identifier": 1.0} if conflicting_identifier_entities else {}),
            evidence_ids=tuple(ref.evidence_id for ref in evidence_refs),
            created_at=now,
        ), new_entity_id

    return EntityMatch(
        id=match_id,
        decision_id=decision_id,
        subject_id=subject_id,
        owner_id=owner_id,
        candidate_entity_id=new_entity_id,
        candidate_entity_ids=(),
        outcome="no_match",
        confidence=0.0,
        feature_values=({"conflicting_identifier": 1.0} if conflicting_identifier_entities else {}),
        evidence_ids=tuple(ref.evidence_id for ref in evidence_refs),
        created_at=now,
    ), new_entity_id
