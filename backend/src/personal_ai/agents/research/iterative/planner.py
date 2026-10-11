"""Deterministic gap priorities and bounded follow-up proposals."""

from __future__ import annotations

from uuid import UUID

from personal_ai.agents.research.iterative.contracts import (
    EvidenceGap,
    EvidenceGapClass,
    FollowupProposal,
    IterativeResearchRequest,
)


class FollowupPlanner:
    """Return a bounded template action for one validated, named evidence gap."""

    def propose(
        self,
        request: IterativeResearchRequest,
        gap: EvidenceGap,
        candidates: dict[UUID, str],
        domains: tuple[str, ...],
    ) -> FollowupProposal | None:
        template = {
            EvidenceGapClass.REQUIRED_FACT_MISSING: "required_fact",
            EvidenceGapClass.EVIDENCE_STALE: "current_source",
            EvidenceGapClass.SOURCE_CONFLICT: "independent_confirmation",
            EvidenceGapClass.IDENTITY_AMBIGUITY: "identity_model",
            EvidenceGapClass.CANDIDATE_COVERAGE: "candidate_source",
        }.get(gap.gap_class)
        if template is None:
            return None
        return FollowupProposal(
            gap_id=gap.id,
            template=template,
            target_id=gap.target_id,
            attribute=gap.attribute,
            allowed_domains=domains,
        )


GAP_PRIORITY = {
    EvidenceGapClass.REQUIRED_FACT_MISSING: 0,
    EvidenceGapClass.EVIDENCE_STALE: 1,
    EvidenceGapClass.SOURCE_CONFLICT: 2,
    EvidenceGapClass.IDENTITY_AMBIGUITY: 3,
    EvidenceGapClass.CANDIDATE_COVERAGE: 4,
    EvidenceGapClass.CITATION_SUPPORT: 5,
    EvidenceGapClass.INITIAL_COVERAGE: 6,
}
