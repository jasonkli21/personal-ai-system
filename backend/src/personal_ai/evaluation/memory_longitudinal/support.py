"""Pre-outcome arm compatibility derived only from source shape and budgets."""

from functools import lru_cache

from personal_ai.evaluation.memory_navigation import policy, query_for
from personal_ai.memory.research.contracts import ResearchFailure
from personal_ai.memory.research.experiments.contracts import ARMS, digest

from .dataset import load_sources
from .source import LongitudinalAuthority, LongitudinalNavigation

NAVIGATION_ARMS = frozenset(
    {"lexical", "topic_hierarchical", "adaptive", "semantic", "hybrid", "hybrid_reranked"}
)
KNOWLEDGE_ARMS = frozenset({"verified_knowledge", "tool_lookup"})
EMBEDDING_ARMS = frozenset({"semantic", "hybrid", "hybrid_reranked"})
PREEMPTING_EVENTS = frozenset(
    {
        "project_denied",
        "owner",
        "workspace",
        "application",
        "actor",
        "revoke_grant",
        "cancel",
        "timeout",
        "partial",
        "refresh_interrupted",
    }
)
AUTHORITY_CHECKING_ARMS = NAVIGATION_ARMS | frozenset({"no_memory", "fixed", "full_history"})


@lru_cache(maxsize=96)
def _full_context_reason(task_id: str, context_tokens: int, memory_tokens: int) -> str | None:
    """Run the deterministic fit check without reading scoring or task outcomes."""
    task = next(t for t in load_sources().tasks if t.id == task_id)
    source = LongitudinalAuthority(task.id)
    query = query_for(
        {"query": task.query, "scope": task.scope.model_dump(), "project": task.project},
        "eligible_full_context",
        now=source.now(),
    )
    engine = LongitudinalNavigation(source, enabled=True)
    index = engine.index(query)
    selected, _ = engine._selection(query, index)
    try:
        engine.pack(
            query,
            index,
            selected,
            policy(
                global_tokens=context_tokens,
                memory_tokens=(1 if task.fault and task.fault.action == "tight" else memory_tokens),
            ),
        )
    except ResearchFailure as exc:
        if exc.reason == "eligible_full_context_infeasible":
            return exc.reason
        raise
    return None


def support_matrix(tasks, policies, budgets):
    """Return a stable task/arm map; runtime outcomes never affect eligibility."""
    supported = {}
    for task in tasks:
        boundary_preempted = any(
            event.action in PREEMPTING_EVENTS
            for step in task.steps
            if step.phase == "change"
            for event in step.events
        )
        for policy_manifest in policies:
            arm = policy_manifest.arm
            reason = None
            if boundary_preempted and arm in AUTHORITY_CHECKING_ARMS:
                # Source/scope boundary cases remain eligible safety attempts
                # even when the arm cannot represent the task's memory schema.
                reason = None
            elif arm == "fixed":
                reason = "legacy_fixed_cannot_represent_project_facts"
            elif arm == "pending_diagnostic":
                reason = "pending_proposal_not_approved"
            elif arm in KNOWLEDGE_ARMS and task.profile != "canonical_knowledge" or arm in NAVIGATION_ARMS and task.profile != "navigation_fixture":
                reason = "unsupported_record_kind"
            elif arm in EMBEDDING_ARMS:
                reason = "real_embeddings_unavailable"
            elif arm == "full_history" and task.profile == "navigation_fixture":
                reason = _full_context_reason(
                    task.id, budgets.context_tokens, budgets.memory_tokens
                )
            elif arm not in ARMS:
                raise ValueError("support_unknown_arm")
            supported[(task.id, arm)] = reason
    return supported


def support_digest(matrix):
    return digest(
        [
            {"task_id": task_id, "arm": arm, "unsupported_reason": reason}
            for (task_id, arm), reason in sorted(matrix.items())
        ]
    )
