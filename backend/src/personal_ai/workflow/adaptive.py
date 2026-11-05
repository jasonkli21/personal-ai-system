"""Trusted fixture host integration. WorkflowService retains admission authority."""

import logging
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from time import monotonic, time

from personal_ai.reasoning import adaptive
from personal_ai.reasoning.adaptive_control import LocalPolicyControl
from personal_ai.reasoning.adaptive_plan import compile_candidate

_LOG = logging.getLogger(__name__)


def finite_fixture_binding(task, fixture_digest):
    return adaptive.digest({"task": task.model_dump(mode="json"), "fixture": fixture_digest})


@dataclass(frozen=True, slots=True)
class AdaptiveHost:
    control: LocalPolicyControl
    scope_digest: str
    build_digest: str
    protocol_digest: str
    reviewer_key: bytes | None = None
    finite_fixtures: frozenset[str] = frozenset()

    def has_fixture(self, plan):
        return finite_fixture_binding(plan.task, plan.fixture_digest) in self.finite_fixtures

    @contextmanager
    def pointer(self, scope_digest, policy):
        with ExitStack() as stack:
            try:
                pointer = stack.enter_context(self.control.admission()) if scope_digest == self.scope_digest else None
            except (OSError, ValueError):
                pointer = None
            now = time()
            if pointer is not None and (
                pointer.mode == "disabled" or pointer.policy_digest != policy.identity
                or pointer.build_digest != self.build_digest or not pointer.issued_at <= now < pointer.expires_at
            ):
                pointer = None
            yield pointer

    def select(self, baseline, pointer, endpoint_digest, deadline):
        if pointer is None or not self.has_fixture(baseline):
            return baseline
        reserve = monotonic() + sum(step.timeout_ms for step in adaptive.candidate_steps()) / 1000 < deadline
        features = adaptive.finite_features(baseline, reserve=reserve)
        reason = adaptive.finite_reason(features, direct_pin=baseline.selection == "trusted_direct_pin")
        recommendation = "candidate_compare" if reason == "eligible" else "baseline"
        if pointer.mode == "shadow":
            observe(adaptive.decision(features, adaptive.FINITE, pointer.generation, "baseline", recommendation, reason))
            return baseline
        signed = pointer.approval
        evidence = signed.evidence
        if reason != "eligible" or (
            evidence.scope_digest != self.scope_digest or evidence.protocol_digest != self.protocol_digest
            or evidence.endpoint_digest != endpoint_digest or evidence.family != features.family
            or evidence.effort != features.effort or evidence.limits != baseline.limits
            or not signed.verified(self.reviewer_key, time())
        ):
            return baseline
        receipt = adaptive.decision(
            features, adaptive.FINITE, pointer.generation, "baseline", recommendation, reason, approval=evidence,
        )
        return compile_candidate(baseline, receipt, approval=signed)

    def authorizes(self, plan, scope_digest):
        signed = plan.approval
        if signed is None or self.scope_digest != scope_digest or not self.has_fixture(plan):
            return False
        evidence = signed.evidence
        now = time()
        return (
            evidence.build_digest == self.build_digest and evidence.protocol_digest == self.protocol_digest
            and evidence.issued_at <= now < evidence.expires_at + plan.deadline_ms / 1000
            # The admitted run may finish across the approval's expiry within its pinned deadline.
            and signed.verified(self.reviewer_key, evidence.issued_at)
        )

    def grounded_shadow(self, plan, gaps, can_focus, scope_digest):
        with self.pointer(scope_digest, adaptive.GROUNDED) as pointer:
            if pointer is None or pointer.mode != "shadow":
                return
            gap_count = sum(gap is not None for gap in gaps)
            uncertain = any(gap in {"conflict", "verification_inconclusive"} for gap in gaps)
            freshness = (
                "uncertain" if uncertain else "stale" if "stale_or_expired" in gaps else
                "missing" if gap_count else "usable"
            )
            features = adaptive.ReasoningFeaturesV1(
                profile="grounded_local_fixture", family="fact_slots", requirements=len(gaps),
                ambiguity="conflicting" if uncertain else "missing" if gap_count else "resolved",
                verifier="fixture-fact-citation.v1", source="authorized_public_fixture", gaps=gap_count,
                freshness=freshness,
                effort=plan.effort, alternative_fits=can_focus,
            )
            if not gap_count:
                reason = "coverage_complete"
            elif uncertain:
                reason = "coverage_uncertain"
            elif not can_focus:
                reason = "insufficient_reserve"
            elif gap_count == 1 and adaptive.GROUNDED.worthwhile:
                reason = "focused_gap"
            else:
                reason = "no_marginal_value"
            observe(adaptive.decision(
                features, adaptive.GROUNDED, pointer.generation,
                "focused" if can_focus else "one_shot",
                "focused" if reason == "focused_gap" else "one_shot", reason,
            ))


def observe(receipt):
    # No scope, task identifier, candidate output, source content or scoring facts.
    _LOG.info("adaptive_shadow %s", receipt.model_dump_json(exclude_none=True))
