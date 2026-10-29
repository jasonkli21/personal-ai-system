"""Content-causal companion: the deterministic consumer sees packed text only."""

from hashlib import sha256
from inspect import signature

from personal_ai.evaluation import memory_knowledge_consumer as evaluation


def test_content_causal_suite_has_sixteen_frozen_paired_sessions_and_no_model_claim():
    corpus = evaluation.load_corpus()
    assert len(corpus.pairs) == 16
    assert len({pair.pair_id for pair in corpus.pairs}) == 16
    assert corpus.review_status == "author_reviewed_independent_review_pending"
    assert corpus.evidence_class == "hermetic_packed_context_consumer_causal_proxy"
    assert set(signature(evaluation.consume_packed_context).parameters) == {"messages", "tools"}
    assert (
        sha256(evaluation.FIXTURE.read_bytes()).hexdigest()
        == "ff94f67f8889f13887128003d21e5f1b89078e806c12a1d148c4ac7d1d347066"
    )

    first = evaluation.evaluate(corpus)
    second = evaluation.evaluate(corpus)
    assert evaluation.semantic(first) == evaluation.semantic(second)
    metrics = evaluation._paired_metrics(first)
    assert metrics["arms"]["none"]["task_passed"] == 0
    assert metrics["arms"]["knowledge"]["task_passed"] == 16
    assert metrics["arms"]["history"]["task_passed"] == 16
    assert metrics["arms"]["knowledge"]["selected"] == 16
    assert metrics["arms"]["knowledge"]["packed"] == 16
    assert metrics["arms"]["knowledge"]["consumed"] == 16
    assert metrics["knowledge_paired"]["none"]["intersection"] == 16
    assert metrics["knowledge_paired"]["none"]["wins"] == 16
    assert metrics["knowledge_paired"]["none"]["regressions"] == 0
    assert metrics["knowledge_paired"]["history"]["intersection"] == 16
    assert metrics["knowledge_paired"]["history"]["ties"] == 16
    assert all(not row["invariant_violations"] for row in first)

    fixed_rows = [row for row in first if row["arm"] == "fixed"]
    assert len(fixed_rows) == 16
    assert all(row["applicability"] == "unsupported" for row in fixed_rows)
    assert all(row["session_a"] != row["session_b"] for row in first if row["arm"] != "fixed")


def test_consumer_outcome_tracks_visible_content_and_authority_changes():
    rows = evaluation.evaluate(evaluation.load_corpus())
    by_key = {(row["case_id"], row["arm"], row["variant"]): row for row in rows}

    positive = by_key[("workflow-swap", "knowledge", "positive")]
    swapped = by_key[("workflow-swap", "knowledge", "swap")]
    assert positive["target_outcome"]["command"] == "make memory-eval"
    assert swapped["target_outcome"]["command"] == "make backend-lint"
    assert swapped["target_outcome"]["command"] != positive["expected_action"]

    corpus = evaluation.load_corpus()
    for case_id in ("workflow-drop", "workflow-redact", "workflow-poison"):
        pair = next(pair for pair in corpus.pairs if pair.pair_id == case_id)
        controlled = by_key[(case_id, "knowledge", pair.control)]
        assert controlled["target_outcome"] is None
        assert controlled["applicability"] == "adverse_control"

    for pair in corpus.pairs:
        if pair.control in {
            "source_revoked",
            "stale_project",
            "grant_revoked",
            "actor_changed",
            "forged_receipt",
            "expired",
            "unconfirmed_turn",
        }:
            controlled = by_key[(pair.pair_id, "knowledge", pair.control)]
            assert controlled["target_outcome"] is None
        if pair.control == "duplicate_effect":
            controlled = by_key[(pair.pair_id, "knowledge", pair.control)]
            assert controlled["target_outcome"]["command"] == pair.action
            assert controlled["target_effect_count"] == 1
