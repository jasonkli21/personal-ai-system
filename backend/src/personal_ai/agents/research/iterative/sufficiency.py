"""Evidence conflict and question normalization checks for iterative runs."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID, uuid5

from personal_ai.agents.research.contracts import ResearchSession
from personal_ai.agents.research.iterative.contracts import (
    EvidenceGap,
    EvidenceGapClass,
    IterationRecord,
    ResearchRun,
)
from personal_ai.agents.research.iterative.planner import GAP_PRIORITY


def _normalized_query(query: str) -> str:
    return " ".join(query.casefold().split())


def _evidence_conflicts(session: ResearchSession, now: datetime) -> tuple[UUID, ...]:
    evidence = [item for item in session.evidence if item.expires_at > now]
    conflicting_ids: set[UUID] = set()
    for index, first in enumerate(evidence):
        first_words = set(re.findall(r"\w+", first.passage.casefold()))
        first_numbers = set(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?", first.passage))
        first_negated = bool(
            re.search(r"\b(no|not|never|without|cannot|can't)\b", first.passage, re.IGNORECASE)
        )
        for second in evidence[index + 1 :]:
            second_words = set(re.findall(r"\w+", second.passage.casefold()))
            union = first_words | second_words
            overlap = len(first_words & second_words) / max(1, len(union))
            if overlap < 0.7:
                continue
            second_numbers = set(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?", second.passage))
            second_negated = bool(
                re.search(r"\b(no|not|never|without|cannot|can't)\b", second.passage, re.IGNORECASE)
            )
            if first_numbers != second_numbers or first_negated != second_negated:
                conflicting_ids.update((first.id, second.id))
    # Store one immutable conflict finding per assessment with all participating
    # evidence IDs. This keeps the bounded run record small as the evidence set
    # grows while preserving the complete provenance for review.
    return tuple(sorted(conflicting_ids, key=str))


def _relevant_evidence(question: str, evidence):
    ignored = {
        "what", "which", "when", "where", "does", "with", "from", "that", "this",
        "have", "about", "show", "find", "tell", "give", "for", "the", "and", "are",
        "is", "of", "to", "in", "on", "a", "an", "current",
    }
    words = {
        word
        for word in re.findall(r"[a-z0-9]+", question.casefold())
        if len(word) > 1 and word not in ignored
    }
    if len(words) < 2:
        return ()
    aliases = {
        "schedule": {"schedule", "open", "opens", "opening", "hours", "time", "times"},
        "hours": {"hours", "open", "opens", "opening", "time", "times"},
        "current": {"current", "today", "latest", "updated", "new"},
        "price": {"price", "cost", "costs", "priced", "retails", "usd", "eur", "gbp"},
        "availability": {"available", "availability", "in-stock", "stock"},
    }
    groups = [aliases.get(word, {word}) for word in sorted(words)]
    return tuple(
        item
        for item in evidence
        if all(group & set(re.findall(r"[a-z0-9]+", item.passage.casefold())) for group in groups)
    )


def _gap(
    run: ResearchRun,
    iteration: IterationRecord,
    gap_class: EvidenceGapClass,
    target_id: UUID | None,
    attribute: str | None,
    evidence_ids,
    required: bool,
    reason: str,
    *,
    constraint_id: UUID | None = None,
) -> EvidenceGap:
    semantic_key = f"{gap_class}:{target_id}:{constraint_id}:{attribute}:"
    assessment_id = uuid5(run.id, f"assessment:{len(run.assessments)}")
    identity = f"{assessment_id}:{semantic_key}"
    return EvidenceGap(
        id=uuid5(run.id, identity),
        run_id=run.id,
        assessment_id=assessment_id,
        iteration_id=iteration.id,
        semantic_key=semantic_key,
        gap_class=gap_class,
        target_id=target_id,
        constraint_id=constraint_id,
        attribute=attribute,
        evidence_ids=tuple(sorted(set(evidence_ids), key=str)),
        required=required,
        status="open",
        reason_code=reason,
    )


def _merge_gaps(run: ResearchRun, fresh) -> tuple[EvidenceGap, ...]:
    fresh_keys = {item.semantic_key for item in fresh}
    open_indexes: dict[str, list[int]] = {}
    for index, item in enumerate(run.gaps):
        if item.status == "open":
            open_indexes.setdefault(item.semantic_key, []).append(index)
    old = list(run.gaps)
    for semantic_key, indexes in open_indexes.items():
        if semantic_key not in fresh_keys:
            for index in indexes:
                old[index] = old[index].model_copy(update={"status": "resolved"})
    seen = set()
    additions = []
    for item in fresh:
        if item.semantic_key in seen:
            continue
        seen.add(item.semantic_key)
        additions.append(item)
    return (*old, *additions)


def _select_gap(gaps) -> EvidenceGap | None:
    open_gaps = [item for item in gaps if item.status == "open" and item.required]
    if not open_gaps:
        open_gaps = [item for item in gaps if item.status == "open"]
    return (
        min(open_gaps, key=lambda item: (GAP_PRIORITY[item.gap_class], item.semantic_key))
        if open_gaps
        else None
    )
