"""Versioned strategy descriptions without executable references."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

CATALOG_VERSION = "reasoning-catalog-v1"


@dataclass(frozen=True, slots=True)
class Strategy:
    purpose: str
    capabilities: tuple[str, ...]
    evidence: str
    verifier: str
    shape: str
    max_nodes: int
    stage: str
    effect: Literal["read_only", "proposal_only"]
    eligibility: str
    availability: Literal["offline_comparator", "inert"] = "inert"
    version: int = 1


CATALOG = MappingProxyType(
    {
        "direct": Strategy(
            "One answer from prepared context",
            ("answer",),
            "prepared context",
            "task oracle where available",
            "one answer",
            1,
            "direct_answer",
            "read_only",
            "within the shared context and inference ceilings",
            "offline_comparator",
        ),
        "decompose": Strategy(
            "Split independent requirements",
            ("answer",),
            "task constraints",
            "constraint checks",
            "plan → at most three subproblems → synthesis",
            5,
            "decomposition",
            "read_only",
            "bounded independent subproblems and reserved synthesis",
        ),
        "critique_refine": Strategy(
            "Correct a concrete defect",
            ("answer",),
            "draft and requirements",
            "independent defect predicate",
            "draft → critique → one revision",
            3,
            "critique_and_revision",
            "read_only",
            "testable defect and one revision within cap",
        ),
        "candidate_compare": Strategy(
            "Compare alternatives by a shared rubric",
            ("answer",),
            "task and frozen rubric",
            "objective ranking or explicit tie",
            "at most two proposals → compare → synthesis",
            4,
            "candidate_comparison",
            "proposal_only",
            "shared rubric and matched candidate budgets",
        ),
        "evidence_research": Strategy(
            "Resolve a factual dependency",
            ("answer", "scoped_source_read"),
            "current source grants",
            "claim-to-revision checks",
            "plan → at most two reads → synthesis",
            4,
            "evidence_research",
            "read_only",
            "authorized current scope and final disclosure recheck",
        ),
        "tool_verify": Strategy(
            "Check a bounded proposal",
            ("answer", "scoped_verifier"),
            "input and verifier version",
            "deterministic registered verifier",
            "propose → one check → synthesis",
            3,
            "tool_verification",
            "proposal_only",
            "allowlisted read-only verifier with a typed result",
        ),
    }
)
