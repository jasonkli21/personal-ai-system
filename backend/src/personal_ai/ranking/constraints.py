"""constraints ranking policy."""

from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from uuid import UUID, uuid5

from personal_ai.decisions.contracts import (
    CandidateEvaluation,
    Constraint,
    ConstraintOutcome,
    FeatureScore,
    Preference,
)
from personal_ai.entities.research import (
    AvailabilityValue,
    CanonicalEntity,
    DateValue,
    DateWindowValue,
    EntityClaim,
    EntityMatch,
    LocationValue,
    TypedValue,
)
from personal_ai.ranking.claim_verification import (
    CLAIM_VERIFICATION_POLICY_VERSION,
    _status,
)
from personal_ai.ranking.normalization import normalize_name
from personal_ai.ranking.values import _numeric, values_equal

CONSTRAINT_POLICY_VERSION = "constraint-v1"

RANKING_POLICY_VERSION = "rank-v1"


def _distance_km(left: LocationValue, right: LocationValue) -> float:
    lat1, lat2 = radians(left.latitude), radians(right.latitude)
    d_lat = lat2 - lat1
    d_lon = radians(right.longitude - left.longitude)
    value = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(value))


def _matches(actual: TypedValue, constraint: Constraint) -> tuple[bool | None, str]:
    op = constraint.operator
    expected = constraint.value
    if op in {"maximum", "minimum", "range"}:
        if isinstance(actual, DateValue) and isinstance(expected, DateValue):
            if op == "maximum":
                passed = actual.value <= expected.value
                return passed, "within_maximum" if passed else "over_maximum"
            if op == "minimum":
                passed = actual.value >= expected.value
                return passed, "within_minimum" if passed else "under_minimum"
            upper = constraint.upper_value
            if not isinstance(upper, DateValue):
                return None, "incompatible_range_units"
            passed = expected.value <= actual.value <= upper.value
            return passed, "inside_range" if passed else "outside_range"
        actual_numeric = _numeric(actual)
        expected_numeric = _numeric(expected) if expected is not None else None
        if actual_numeric is None or expected_numeric is None:
            return None, "unsupported_unit_or_currency"
        if actual_numeric[1] != expected_numeric[1]:
            return None, "incompatible_unit_or_currency"
        actual_number = actual_numeric[0]
        if op == "maximum":
            return actual_number <= expected_numeric[
                0
            ], "within_maximum" if actual_number <= expected_numeric[0] else "over_maximum"
        if op == "minimum":
            return actual_number >= expected_numeric[
                0
            ], "within_minimum" if actual_number >= expected_numeric[0] else "under_minimum"
        upper = _numeric(constraint.upper_value) if constraint.upper_value else None
        if upper is None or upper[1] != expected_numeric[1]:
            return None, "incompatible_range_units"
        passed = expected_numeric[0] <= actual_number <= upper[0]
        return passed, "inside_range" if passed else "outside_range"
    if op == "exact":
        same = values_equal(actual, expected)
        return (
            same,
            "exact_match"
            if same is True
            else "value_mismatch"
            if same is False
            else "incompatible_value",
        )
    if op == "set":
        results = [values_equal(actual, allowed) for allowed in constraint.allowed_values]
        if any(result is True for result in results):
            return True, "set_match"
        if all(result is False for result in results):
            return False, "not_in_set"
        return None, "incompatible_set_value"
    if op == "geospatial":
        if not isinstance(actual, LocationValue) or not isinstance(expected, LocationValue):
            return None, "location_unknown"
        distance = _distance_km(actual, expected)
        passed = distance <= (constraint.radius_km or 0)
        return passed, "inside_radius" if passed else "outside_radius"
    if op == "date_window":
        if not isinstance(actual, DateWindowValue) or not isinstance(expected, DateWindowValue):
            return None, "date_window_unknown"
        passed = actual.start <= expected.start and actual.end >= expected.end
        return passed, "covers_date_window" if passed else "does_not_cover_date_window"
    if op == "availability":
        if not isinstance(actual, AvailabilityValue) or not isinstance(expected, AvailabilityValue):
            return None, "availability_unknown"
        passed = actual.value == expected.value and actual.value != "unknown"
        return passed, "availability_matches" if passed else "availability_mismatch"
    return None, "unsupported_constraint"


def evaluate_candidates(
    *,
    decision_id: UUID,
    entities: tuple[CanonicalEntity, ...],
    claims_by_entity: dict[UUID, tuple[EntityClaim, ...]],
    constraints: tuple[Constraint, ...],
    preferences: tuple[Preference, ...],
    now: datetime,
    preference_weight: float,
    score_enabled: bool = True,
    identity_matches=(),
):
    """Filter first, then score only eligible candidates with a stable tie-break."""

    draft = []
    unknown_required = False
    identity_by_entity: dict[UUID, list[EntityMatch]] = {}
    for match in identity_matches:
        identity_by_entity.setdefault(match.candidate_entity_id, []).append(match)
    for entity in entities:
        claims = claims_by_entity.get(entity.id, ())
        relevant = {(item.attribute, item.scope) for item in constraints} | {
            (item.attribute, item.scope) for item in preferences
        }
        statuses = tuple(
            _status(attribute, scope, claims, now)
            for attribute, scope in sorted(relevant, key=lambda item: (item[0], item[1] or ""))
        )
        status_lookup = {(item.attribute, item.scope): item for item in statuses}
        outcomes: list[ConstraintOutcome] = []
        exclusions: list[str] = []
        candidate_matches = identity_by_entity.get(entity.id, [])
        identity_outcome = (
            "review"
            if any(match.outcome == "review" for match in candidate_matches)
            else "matched"
            if any(match.outcome == "matched" for match in candidate_matches)
            else "no_match"
        )
        identity_confidence = max((match.confidence for match in candidate_matches), default=0.0)
        identity_candidate_ids = tuple(
            sorted(
                {
                    candidate_id
                    for match in candidate_matches
                    for candidate_id in match.candidate_entity_ids
                },
                key=str,
            )
        )
        if identity_outcome == "review":
            exclusions.append("identity_ambiguous")
            unknown_required = True
        elif any(
            match.feature_values.get("identity_evidence_missing") for match in candidate_matches
        ):
            exclusions.append("identity_evidence_missing")
            unknown_required = True
        verified_claims = tuple(
            claim
            for claim in claims
            if claim.claim_status == "verified"
            and claim.verification_policy_version == CLAIM_VERIFICATION_POLICY_VERSION
            and claim.expires_at > now
        )
        if not verified_claims:
            exclusions.append("candidate_no_current_evidence")
            unknown_required = True
        for constraint in constraints:
            status = status_lookup[(constraint.attribute, constraint.scope)]
            if status.status != "verified":
                outcome = "unknown"
                reason = status.status
                if constraint.required or constraint.missing_policy == "fail_closed":
                    exclusions.append(f"required_{constraint.attribute}_{status.status}")
                    unknown_required = True
            else:
                claim = next(
                    candidate_claim
                    for candidate_claim in claims
                    if candidate_claim.id in status.claim_ids
                    and candidate_claim.claim_status == "verified"
                    and candidate_claim.verification_policy_version
                    == CLAIM_VERIFICATION_POLICY_VERSION
                    and candidate_claim.expires_at > now
                )
                passed, reason = _matches(claim.typed_value, constraint)
                if passed is None:
                    outcome = "unknown"
                    if constraint.required or constraint.missing_policy == "fail_closed":
                        exclusions.append(f"required_{constraint.attribute}_{reason}")
                        unknown_required = True
                elif passed:
                    outcome = "pass"
                else:
                    outcome = "fail"
                    if constraint.required:
                        exclusions.append(f"constraint_{constraint.attribute}_{reason}")
            outcomes.append(
                ConstraintOutcome(
                    constraint_id=constraint.id,
                    attribute=constraint.attribute,
                    outcome=outcome,
                    reason=reason,
                    claim_ids=status.claim_ids,
                    evidence_ids=status.evidence_ids,
                )
            )
        draft.append(
            {
                "entity": entity,
                "identity_outcome": identity_outcome,
                "identity_confidence": identity_confidence,
                "identity_candidate_ids": identity_candidate_ids,
                "claims": claims,
                "statuses": statuses,
                "outcomes": tuple(outcomes),
                "exclusions": tuple(sorted(set(exclusions))),
                "eligible": not exclusions,
            }
        )

    eligible = [item for item in draft if item["eligible"]]
    if score_enabled:
        for item in eligible:
            feature_values = []
            weighted_total = 0.0
            weight_total = 0.0
            status_lookup = {
                (status.attribute, status.scope): status for status in item["statuses"]
            }
            for preference in preferences:
                status = status_lookup.get((preference.attribute, preference.scope))
                if status is None or status.status != "verified":
                    value = None
                    evidence_ids = status.evidence_ids if status else ()
                    treatment = "omit"
                else:
                    claim = next(
                        candidate_claim
                        for candidate_claim in item["claims"]
                        if candidate_claim.id in status.claim_ids
                        and candidate_claim.claim_status == "verified"
                        and candidate_claim.verification_policy_version
                        == CLAIM_VERIFICATION_POLICY_VERSION
                        and candidate_claim.expires_at > now
                    )
                    match = values_equal(claim.typed_value, preference.target)
                    value = float(match) if match is not None else None
                    evidence_ids = status.evidence_ids
                    treatment = "omit" if match is None else "zero"
                feature_weight = preference.weight * preference_weight
                feature_values.append(
                    FeatureScore(
                        name=f"preference:{preference.attribute}",
                        value=value,
                        weight=feature_weight,
                        evidence_ids=evidence_ids,
                        missing_treatment=treatment,
                    )
                )
                if value is not None and feature_weight > 0:
                    weighted_total += value * feature_weight
                    weight_total += feature_weight
            item["features"] = tuple(feature_values)
            item["score"] = (weighted_total / weight_total) if weight_total else 0.0
    else:
        for item in eligible:
            item["features"] = ()
            item["score"] = None

    if score_enabled:
        eligible.sort(
            key=lambda item: (
                -(item["score"] or 0),
                normalize_name(item["entity"].canonical_name),
                str(item["entity"].id),
            )
        )
    else:
        eligible.sort(
            key=lambda item: (normalize_name(item["entity"].canonical_name), str(item["entity"].id))
        )

    ranks = (
        {item["entity"].id: index + 1 for index, item in enumerate(eligible)}
        if score_enabled
        else {}
    )
    results = tuple(
        CandidateEvaluation(
            id=uuid5(decision_id, f"candidate-evaluation:{item['entity'].id}"),
            decision_id=decision_id,
            entity_id=item["entity"].id,
            identity_outcome=item["identity_outcome"],
            identity_confidence=item["identity_confidence"],
            identity_candidate_entity_ids=item["identity_candidate_ids"],
            claim_ids=tuple(sorted((claim.id for claim in item["claims"]), key=str)),
            eligibility=item["eligible"],
            attribute_statuses=item["statuses"],
            constraint_outcomes=item["outcomes"],
            feature_values=item.get("features", ()),
            score=item.get("score"),
            rank=ranks.get(item["entity"].id),
            exclusion_reasons=item["exclusions"],
        )
        for item in draft
    )
    has_unknown = any(
        not item["eligible"] and any(outcome.outcome == "unknown" for outcome in item["outcomes"])
        for item in draft
    )
    if eligible:
        state = "recommended" if score_enabled else "eligible_unranked"
        selected = eligible[0]["entity"].id if score_enabled else None
    elif has_unknown or unknown_required:
        state, selected = "research_needed", None
    else:
        state, selected = "no_verified_match", None
    return results, state, selected
