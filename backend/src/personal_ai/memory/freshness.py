"""Shared freshness classification and relevance scoring for memory records."""

from datetime import UTC


def freshness(record):
    return {
        "preference": "stable",
        "episodic_observation": "episodic",
        "semantic_summary": "episodic",
        "explicit_correction": "volatile",
    }[record.memory_type]


def freshness_recency(record, *, now, default_half_life_days):
    """Stable facts do not decay; corrections decay quickly but remain history."""
    classification = freshness(record)
    if classification == "stable":
        return 1.0
    half_life = min(default_half_life_days, 7.0) if classification == "volatile" else default_half_life_days
    age_days = max(
        0.0,
        (now.astimezone(UTC) - record.effective_at.astimezone(UTC)).total_seconds() / 86400,
    )
    return 2 ** (-age_days / half_life)
