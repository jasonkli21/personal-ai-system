"""Locked additive study integrity, retained denominators and honest evidence."""

from personal_ai.evaluation.memory_navigation import run_study, study


def test_study_retains_all_arms_cases_and_safety_negatives_with_repeatable_outcomes():
    manifest = study()
    first, second = run_study(), run_study()
    assert first["semantic_replay_digest"] == second["semantic_replay_digest"]
    assert len(first["rows"]) == manifest["cases"] * len(manifest["arms"]) == 400
    assert not sum(r["violations"] for r in first["rows"])
    assert all(r["result"]["provider_calls"] == 0 for r in first["rows"])
    for arm in ("fixed", "semantic", "hybrid", "hybrid_reranked"):
        assert first["aggregates"][arm]["complete"] == 0
        assert first["aggregates"][arm]["denominator"] == 40
        assert first["aggregates"][arm]["statuses"]["unsupported"] == 33
    assert first["aggregates"]["lexical"]["success"] > first["aggregates"]["no_memory"]["success"]
    assert first["aggregates"]["eligible_full_context"]["complete"] > 0
    assert first["aggregates"]["lexical"]["false_support"] == 0
    assert all(a["model_quality"] == "unmeasured" for a in first["aggregates"].values())
    assert first["paired_vs_no_memory"]["lexical"]["transfer"]["n"] == 4
