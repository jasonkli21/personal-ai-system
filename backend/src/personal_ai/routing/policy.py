"""Hard routing compatibility and source-narrowing rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .decision_models import _CONFIDENCE_RANK, _SENSITIVITY_RANK

if TYPE_CHECKING:
    from .decision_models import RoutingDecision


def reselection_requirements_preserved(parent, child) -> bool:
    """Return true when child routing facts preserve or tighten root policy."""

    def narrower(parent_value, child_value):
        return parent_value is None or (child_value is not None and child_value <= parent_value)

    if (
        child.execution_mode != parent.execution_mode
        or child.automatic != parent.automatic
        or _SENSITIVITY_RANK[child.sensitivity] < _SENSITIVITY_RANK[parent.sensitivity]
        or not parent.required_capabilities.issubset(child.required_capabilities)
        or not narrower(parent.input_tokens, child.input_tokens)
        or not narrower(parent.output_tokens, child.output_tokens)
        or not narrower(parent.search_query_chars, child.search_query_chars)
        or not narrower(parent.search_results, child.search_results)
        or (
            parent.embedding_dimensions is not None
            and child.embedding_dimensions != parent.embedding_dimensions
        )
        or (
            parent.structured_schema_id is not None
            and child.structured_schema_id != parent.structured_schema_id
        )
    ):
        return False
    if parent.count is not None:
        if child.count is None:
            return False
        if (
            _CONFIDENCE_RANK[child.count.minimum_confidence]
            < _CONFIDENCE_RANK[parent.count.minimum_confidence]
        ):
            return False
        if (
            parent.count.structured_schema_id is not None
            and child.count.structured_schema_id != parent.count.structured_schema_id
        ):
            return False
    return True


def sources_allowed(decision: RoutingDecision, sources: tuple[str, ...]) -> bool:
    return sources == decision.request.source_reference_sha256s or (
        decision.task.allow_source_narrowing
        and set(sources).issubset(decision.request.source_reference_sha256s)
    )
