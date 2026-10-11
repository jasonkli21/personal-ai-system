"""Compatibility barrel for ranking policies; implementations live by responsibility."""

from personal_ai.ranking.claim_verification import (
    _NUMBER_PATTERN,
    CLAIM_VERIFICATION_POLICY_VERSION,
    _claim_value_match,
    _status,
    attribute_status_for_claims,
    claim_assertion_supported,
    identifier_assertion_supported,
    literal_matches_typed_value,
    literal_supported,
    verified_claims_for_feature,
)
from personal_ai.ranking.constraints import (
    CONSTRAINT_POLICY_VERSION,
    RANKING_POLICY_VERSION,
    _distance_km,
    _matches,
    evaluate_candidates,
)
from personal_ai.ranking.normalization import (
    _identifier,
    normalize_name,
)
from personal_ai.ranking.resolution import (
    IDENTITY_ATTRIBUTES,
    RESOLUTION_POLICY_VERSION,
    resolve_candidate,
)
from personal_ai.ranking.scoring import (
    rank_with_domain_features,
)
from personal_ai.ranking.values import (
    _UNITS,
    _numeric,
    _value_key,
    values_equal,
)

__all__ = [
    "CLAIM_VERIFICATION_POLICY_VERSION",
    "CONSTRAINT_POLICY_VERSION",
    "IDENTITY_ATTRIBUTES",
    "RANKING_POLICY_VERSION",
    "RESOLUTION_POLICY_VERSION",
    "_NUMBER_PATTERN",
    "_UNITS",
    "_claim_value_match",
    "_distance_km",
    "_identifier",
    "_matches",
    "_numeric",
    "_status",
    "_value_key",
    "attribute_status_for_claims",
    "claim_assertion_supported",
    "evaluate_candidates",
    "identifier_assertion_supported",
    "literal_matches_typed_value",
    "literal_supported",
    "normalize_name",
    "rank_with_domain_features",
    "resolve_candidate",
    "values_equal",
    "verified_claims_for_feature",
]
