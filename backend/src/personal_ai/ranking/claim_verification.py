"""claim verification ranking policy."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from personal_ai.decisions.contracts import (
    AttributeStatus,
)
from personal_ai.entities.research import (
    AvailabilityValue,
    BooleanValue,
    DateTimeValue,
    DateValue,
    DateWindowValue,
    EntityClaim,
    LocationValue,
    MoneyValue,
    NumberValue,
    QuantityValue,
    TextValue,
    TypedValue,
)
from personal_ai.ranking.normalization import normalize_name
from personal_ai.ranking.values import _value_key, values_equal

CLAIM_VERIFICATION_POLICY_VERSION = "claim-verification-v2"

_NUMBER_PATTERN = r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"


def literal_supported(original_value: str, passage: str) -> bool:
    """Conservatively accept only values literally present in attributed text."""
    normalize = lambda text: " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    needle = normalize(original_value)
    haystack = normalize(passage)
    if not needle:
        return False
    start = 0
    while (position := haystack.find(needle, start)) >= 0:
        end = position + len(needle)
        left_ok = not needle[0].isalnum() or position == 0 or not haystack[position - 1].isalnum()
        right_ok = not needle[-1].isalnum() or end == len(haystack) or not haystack[end].isalnum()
        if left_ok and right_ok:
            return True
        start = position + 1
    return False


def claim_assertion_supported(
    subject: str, attribute: str, original_value: str, typed_value: TypedValue, passage: str
) -> bool:
    """Require a literal value in a simple, subject-bound, affirmative assertion.

    This intentionally handles only explicit single-sentence forms (plus a narrow
    adjacent ``Its color is ...`` form). It is not a semantic entailment check.
    """
    if not normalize_name(subject) or not literal_matches_typed_value(original_value, typed_value):
        return False
    value_pattern = re.escape(unicodedata.normalize("NFKC", original_value).strip())
    subject_pattern = r"\s+".join(
        re.escape(part) for part in unicodedata.normalize("NFKC", subject).split()
    )
    subject_prefix = rf"^\s*(?:the\s+)?{subject_pattern}(?:\s+catalog\s+\S+)?\s+"
    # A complete assertion cannot borrow a value or omit a trailing qualifier.
    boundary = r"\s*[.!?;]?\s*$"
    if attribute.casefold() == "price":
        predicates = r"(?:costs?|price\s+is|is\s+priced\s+at|is\s+listed\s+for)"
        assertion_pattern = subject_prefix + predicates + rf"\s+{value_pattern}{boundary}"
    else:
        attribute_pattern = re.escape(attribute.replace("_", " "))
        assertion_pattern = (
            subject_prefix
            + rf"(?:{attribute_pattern}\s+(?:is|are|:|=)|is\s+{attribute_pattern})"
            + rf"\s+{value_pattern}{boundary}"
        )
        if attribute == "availability" and isinstance(typed_value, AvailabilityValue):
            assertion_pattern = (
                rf"(?:{assertion_pattern}|{subject_prefix}is\s+{value_pattern}{boundary})"
            )

    sentences = re.split(r"(?<=[.!?;])\s+", passage)
    for index, sentence in enumerate(sentences):
        sentence = unicodedata.normalize("NFKC", sentence)
        if re.search(r"\b(if|unless|whether|might|may|could|would)\b", sentence, re.IGNORECASE):
            continue
        if re.search(assertion_pattern, sentence, re.IGNORECASE):
            return True
        if index == 0 or attribute.casefold() == "price":
            continue
        current = unicodedata.normalize("NFKC", sentence)
        if not re.match(r"\s*(?:its|the item['’]s)\b", current, re.IGNORECASE):
            continue
        previous = unicodedata.normalize("NFKC", sentences[index - 1])
        # Anaphora is accepted only after one simple, explicit subject assertion.
        prior_assertion = re.fullmatch(
            subject_prefix + rf"(?:costs?|price\s+is|is\s+priced\s+at)\s+"
            rf"(?:[$€£]\s*)?{_NUMBER_PATTERN}\s+[A-Z]{{3}}{boundary}",
            previous,
            re.IGNORECASE,
        )
        if prior_assertion is None or re.search(
            r"\b(and|or|but|while|whereas|versus|if|unless)\b", previous, re.IGNORECASE
        ):
            continue
        pronoun_pattern = (
            rf"^\s*(?:its|the item['’]s)\s+{re.escape(attribute.replace('_', ' '))}"
            rf"\s+(?:is|are|:|=)\s+{value_pattern}{boundary}"
        )
        if re.search(pronoun_pattern, current, re.IGNORECASE):
            return True
    return False


def identifier_assertion_supported(subject: str, key: str, value: str, passage: str) -> bool:
    """Bind an identity literal to its subject instead of borrowing nearby IDs."""
    if not value.strip() or len(value) > 500:
        return False
    aliases = {
        "osm": ("openstreetmap_identifier", "osm"),
        "offer_id": ("offer_identifier", "offer_id"),
        "upc": ("upc", "barcode", "product_variant"),
        "ean": ("ean", "barcode", "product_variant"),
        "catalog": ("catalog", "catalog_id"),
    }.get(key.casefold(), (key,))
    if any(
        claim_assertion_supported(subject, attribute, value, TextValue(value=value), passage)
        for attribute in aliases
    ):
        return True
    if key.casefold() != "catalog":
        return False
    # Existing sources may put the catalog ID in the explicit subject heading:
    # "Widget catalog SKU-1 costs ...". Require that immediate association.
    subject_pattern = r"\s+".join(re.escape(part) for part in subject.split())
    identifier_pattern = re.escape(value.strip())
    heading = rf"^\s*(?:the\s+)?{subject_pattern}\s+catalog\s+{identifier_pattern}\s+"
    return any(
        re.match(heading, sentence, re.IGNORECASE)
        for sentence in re.split(r"(?<=[.!?;])\s+", passage)
    )


def literal_matches_typed_value(original_value: str, value: TypedValue) -> bool:
    """Validate a proposed typed value against a conservatively parsed source literal."""
    literal = unicodedata.normalize("NFKC", original_value).strip()
    normalized = " ".join(literal.casefold().split())
    semantic_literal = literal.rstrip(" .,:;")
    normalized_semantic = " ".join(semantic_literal.casefold().split())

    if isinstance(value, TextValue):
        target = " ".join(unicodedata.normalize("NFKC", value.value).casefold().split())
        return normalized == target
    if isinstance(value, AvailabilityValue):
        return normalized_semantic == value.value
    if isinstance(value, BooleanValue):
        return normalized_semantic in ({"true", "yes"} if value.value else {"false", "no"})

    numbers = re.findall(rf"(?<![\w.]){_NUMBER_PATTERN}(?![\w.])", literal)
    if isinstance(value, NumberValue):
        if len(numbers) != 1:
            return False
        try:
            return Decimal(numbers[0].replace(",", "")) == value.value
        except InvalidOperation:
            return False

    if isinstance(value, MoneyValue):
        if len(numbers) != 1:
            return False
        codes = re.findall(r"(?<![A-Z])([A-Z]{3})(?![A-Z])", literal.upper())
        # Currency symbols are accepted only when they uniquely identify the
        # currency; dollar and yen symbols deliberately remain ambiguous.
        symbol_currency = {"€": "EUR", "£": "GBP"}.get(literal[:1])
        if value.currency not in codes and symbol_currency != value.currency:
            return False
        try:
            return Decimal(numbers[0].replace(",", "")) == value.amount
        except InvalidOperation:
            return False

    if isinstance(value, QuantityValue):
        if len(numbers) != 1:
            return False
        unit_match = re.search(r"([A-Za-z]+)\s*$", semantic_literal)
        if unit_match is None:
            return False
        try:
            parsed = QuantityValue(
                amount=Decimal(numbers[0].replace(",", "")),
                unit=unit_match.group(1),
            )
        except (InvalidOperation, ValidationError):
            return False
        return values_equal(parsed, value) is True

    if isinstance(value, DateValue):
        try:
            return date.fromisoformat(semantic_literal) == value.value
        except ValueError:
            return False

    if isinstance(value, DateTimeValue):
        try:
            parsed = datetime.fromisoformat(semantic_literal)
        except ValueError:
            return False
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return False
        return parsed.astimezone(UTC) == value.value

    if isinstance(value, DateWindowValue):
        match = re.fullmatch(
            r"\s*(\d{4}-\d{2}-\d{2})\s*(?:to|through|–|—)\s*(\d{4}-\d{2}-\d{2})\s*",
            semantic_literal,
            flags=re.IGNORECASE,
        )
        if match is None:
            return False
        try:
            return (
                date.fromisoformat(match.group(1)) == value.start
                and date.fromisoformat(match.group(2)) == value.end
            )
        except ValueError:
            return False

    if isinstance(value, LocationValue):
        match = re.fullmatch(
            r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*",
            semantic_literal,
        )
        if match is None:
            return False
        return round(float(match.group(1)), 7) == round(value.latitude, 7) and round(
            float(match.group(2)), 7
        ) == round(value.longitude, 7)

    return False


def _claim_value_match(left: EntityClaim, right: EntityClaim) -> bool:
    result = values_equal(left.typed_value, right.typed_value)
    return result is True and left.scope == right.scope


def _status(
    attribute: str,
    scope: str | None,
    claims: tuple[EntityClaim, ...],
    now: datetime,
) -> AttributeStatus:
    relevant = tuple(
        claim
        for claim in claims
        if claim.attribute == attribute and (scope is None or claim.scope == scope)
    )
    active = tuple(
        claim for claim in relevant if claim.expires_at > now and claim.claim_status != "retracted"
    )
    verified = tuple(
        claim
        for claim in active
        if claim.claim_status == "verified"
        and claim.verification_policy_version == CLAIM_VERIFICATION_POLICY_VERSION
    )
    unverified = tuple(
        claim
        for claim in active
        if claim.claim_status == "unverified"
        or claim.verification_policy_version != CLAIM_VERIFICATION_POLICY_VERSION
    )
    shown_claims = active or relevant
    claim_ids = tuple(sorted((claim.id for claim in shown_claims), key=str))
    evidence_ids = tuple(
        sorted({ref.evidence_id for claim in shown_claims for ref in claim.evidence_refs}, key=str)
    )
    if verified:
        keys = {_value_key(claim.typed_value) for claim in verified}
        if None in keys or len(keys) > 1:
            status, reason = "conflicting", "fresh_claim_conflict"
        elif unverified and any(
            values_equal(unverified_claim.typed_value, verified[0].typed_value) is not True
            for unverified_claim in unverified
        ):
            status, reason = "conflicting", "verified_unverified_disagreement"
        else:
            status, reason = "verified", "fresh_attributed_claim"
    elif unverified:
        status, reason = "unverified", "source_value_not_validated"
    elif relevant:
        status, reason = "stale", "all_claims_expired_or_retracted"
    else:
        status, reason = "missing", "no_claim"
    return AttributeStatus(
        attribute=attribute,
        scope=scope,
        status=status,
        claim_ids=claim_ids,
        evidence_ids=evidence_ids,
        reason=reason,
    )


def attribute_status_for_claims(
    attribute: str,
    scope: str | None,
    claims: tuple[EntityClaim, ...],
    now: datetime,
) -> AttributeStatus:
    """Return the shared freshness/conflict status used by constraints and features."""
    return _status(attribute, scope, claims, now)


def verified_claims_for_feature(
    claims: tuple[EntityClaim, ...],
    attribute: str,
    now: datetime,
    *,
    evaluation=None,
    scope: str | None = None,
) -> tuple[AttributeStatus, tuple[EntityClaim, ...]]:
    """Select only claims admitted by the shared status policy for one feature.

    An omitted scope is inferred only when the candidate has one scope for the
    attribute. Multiple scopes are incomparable for a domain feature and are
    therefore omitted even if their values happen to match.
    """
    matching = tuple(item for item in claims if item.attribute == attribute)
    scopes = {item.scope for item in matching}
    if scope is None:
        if len(scopes) > 1:
            return attribute_status_for_claims(attribute, None, matching, now), ()
        scope = next(iter(scopes)) if scopes else None

    statuses = getattr(evaluation, "attribute_statuses", ()) if evaluation is not None else ()
    status = next(
        (item for item in statuses if item.attribute == attribute and item.scope == scope),
        None,
    )
    if status is None:
        status = attribute_status_for_claims(attribute, scope, matching, now)
    if status.status != "verified":
        return status, ()

    selected = tuple(
        sorted(
            (
                item
                for item in matching
                if item.scope == scope
                and item.id in status.claim_ids
                and item.claim_status == "verified"
                and item.verification_policy_version == CLAIM_VERIFICATION_POLICY_VERSION
                and item.expires_at > now
            ),
            key=lambda item: str(item.id),
        )
    )
    return status, selected
