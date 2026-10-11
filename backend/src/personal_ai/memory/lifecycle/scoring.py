"""Versioned, bounded memory lifecycle scoring."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from personal_ai.memory.contracts import DerivedMemory, ScoredMemory
from personal_ai.memory.lifecycle.contracts import MemoryLifecycleState


@dataclass(frozen=True)
class ScorePolicy:
    version: str = "score-v1"
    similarity_weight: float = 0.50
    importance_weight: float = 0.15
    recency_weight: float = 0.15
    frequency_weight: float = 0.10
    confidence_weight: float = 0.10
    half_life_days: float = 90

    def __post_init__(self):
        weights = self.weights
        if self.version != "score-v1" or any(
            not math.isfinite(weight) or not 0 <= weight <= 1 for weight in weights
        ):
            raise ValueError("score_policy_invalid")
        if sum(weights) <= 0 or not math.isfinite(self.half_life_days) or self.half_life_days <= 0:
            raise ValueError("score_policy_invalid")

    @property
    def weights(self) -> tuple[float, ...]:
        return (
            self.similarity_weight,
            self.importance_weight,
            self.recency_weight,
            self.frequency_weight,
            self.confidence_weight,
        )

    @property
    def identity(self) -> str:
        payload = json.dumps(
            {
                "version": self.version,
                "weights": self.weights,
                "half_life_days": self.half_life_days,
                "normalization": "positive-weight-sum-v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class MemoryScore:
    memory_id: UUID
    score: float | None
    similarity: float | None
    importance: float | None
    recency: float | None
    frequency: float | None
    confidence: float | None
    policy_version: str
    reason: str | None = None


IMPORTANCE_BY_TYPE = {
    "explicit_correction": 1.0,
    "preference": 0.8,
    "semantic_summary": 0.6,
    "episodic_observation": 0.4,
}


def score_memory(
    candidate: ScoredMemory,
    state: MemoryLifecycleState,
    policy: ScorePolicy,
    *,
    now: datetime,
) -> MemoryScore:
    """Compute the versioned bounded weighted score without reading memory text."""
    memory = candidate.memory
    similarity = float(candidate.similarity)
    if not math.isfinite(similarity):
        return MemoryScore(
            memory.id, None, None, None, None, None, None, policy.version, "similarity_invalid"
        )
    similarity = min(1.0, max(0.0, similarity))
    if state.importance_policy_version not in (None, "score-v1"):
        return MemoryScore(
            memory.id,
            None,
            similarity,
            None,
            None,
            None,
            None,
            policy.version,
            "importance_policy_invalid",
        )
    importance = state.importance
    if importance is None:
        importance = IMPORTANCE_BY_TYPE.get(memory.memory_type)
    if isinstance(memory, DerivedMemory):
        importance = min(importance or 0, memory.importance)
    effective = memory.effective_at
    age_days = max(0.0, (now.astimezone(UTC) - effective.astimezone(UTC)).total_seconds() / 86400)
    recency = 2 ** (-age_days / policy.half_life_days)
    frequency = min(state.retrieval_count / 10, 1.0)
    confidence = memory.confidence
    inputs = (similarity, importance, recency, frequency, confidence)
    if any(
        value is None or not math.isfinite(float(value)) or not 0 <= float(value) <= 1
        for value in inputs
    ):
        return MemoryScore(
            memory.id,
            None,
            similarity,
            importance,
            recency,
            frequency,
            confidence,
            policy.version,
            "score_input_invalid",
        )
    denominator = sum(policy.weights)
    score = (
        sum(value * weight for value, weight in zip(inputs, policy.weights, strict=True))
        / denominator
    )
    return MemoryScore(
        memory.id, score, similarity, importance, recency, frequency, confidence, policy.version
    )
