"""Frozen author-visible structural comparisons; never real-model utility."""

import json
from datetime import UTC, datetime
from time import perf_counter

from personal_ai.memory.consolidation.repository import OfflineProposalRepository
from personal_ai.memory.consolidation.sources import CORPUS_SHA256, FrozenFixtureSource, load_corpus

EVALUATION_TIME = datetime(2026, 11, 3, 13, tzinfo=UTC)


def oracle_kinds(records, source):
    """Full eligible source upper bound, independent of extractor/candidate text."""
    eligible = [
        r for r in records if source.current(r, r.scope) and r.evidence != "observed_completion"
    ]
    corrections = [r for r in eligible if r.evidence == "user_correction"]
    eligible = corrections or eligible
    outcomes = {r.fact.outcome for r in eligible}
    if len(outcomes) > 1:
        return ["conflict"]
    return ["procedure" if "passed" in outcomes else "lesson"] if outcomes else []


def evaluate():
    started = perf_counter()
    corpus = load_corpus()
    source = FrozenFixtureSource(clock=lambda: EVALUATION_TIME)
    repository = OfflineProposalRepository(source)
    scores = {
        arm: {"development": 0, "reserved_author_visible": 0}
        for arm in corpus["preregistration"]["arms"]
    }
    denominators = {"development": 0, "reserved_author_visible": 0}
    for task in corpus["tasks"]:
        scope = next(s for s in source.scopes if s.session == task["session"])
        records = [r for r in corpus["records"] if r["scope"]["session"] == scope.session]
        source.publish(scope, len(records))
        cursor = 0
        while page := source.page(scope, cursor):
            lease = repository.claim(scope, "evaluation")
            receipt = repository.commit(lease, page)
            cursor = receipt.cursor
        first = source.page(scope, 0).records[0]
        fixed = (
            ["procedure" if first.fact.outcome == "passed" else "lesson"]
            if first.evidence != "observed_completion"
            else []
        )
        # Expectations are used ONLY here by the scorer, never by the extractor.
        arms = {
            "no_consolidation": [],
            "fixed_first_assertion": fixed,
            "deterministic_pending": sorted(p.kind for p in repository.pending(scope)),
            "eligible_source_oracle": oracle_kinds(tuple(source._streams[scope.key]), source),
        }
        denominators[task["split"]] += 1
        for arm, kinds in arms.items():
            scores[arm][task["split"]] += kinds == task["expected_kinds"]
    return {
        "schema_version": "offline-consolidation-evaluation-v1",
        "evidence_tier": "E1",
        "corpus_sha256": CORPUS_SHA256,
        "reserved_independent": False,
        "metric": "exact_pending_shape_scripted_only",
        "scores": scores,
        "denominators": denominators,
        "resources": repository.diagnostics(),
        "elapsed_seconds": round(perf_counter() - started, 6),
        "model_utility": "unverified",
        "production_promotable": False,
    }


def main():
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    # A bounded structural regression gate, never a promotion decision.
    return 0 if result["scores"]["deterministic_pending"] == result["denominators"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
