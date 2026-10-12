import json
from types import SimpleNamespace

from personal_ai.evaluation.planning_quality import measure_planning_answer
from personal_ai.evaluation.provider_matrix import load_provider_matrix_configuration


def _assembled(fixture, available_sources):
    items = []
    source_items = []
    for index, source_id in enumerate(available_sources):
        provider_id = f"synthetic.source-{index:02d}"
        item_id = f"item-{index:02d}"
        items.append(SimpleNamespace(provider_id=provider_id, item_id=item_id, injected=True))
        source_items.append(SimpleNamespace(
            provider_id=provider_id,
            item_id=item_id,
            source_refs=(SimpleNamespace(reference_id=source_id),),
        ))
    return SimpleNamespace(
        manifest=SimpleNamespace(actual_build=True, items=tuple(items)),
        source_items=tuple(source_items),
        messages=(SimpleNamespace(role="user", content="Synthetic assembled evidence."),),
    )


def test_phase22_scorer_measures_only_sources_injected_by_planned_context():
    fixtures, _task, _scoring = load_provider_matrix_configuration()
    fixture = fixtures[0]
    output = json.dumps(fixture.reference_output)
    bindings = {source_id: source_id for source_id in fixture.source_ids}
    identity = {
        "strategy_version": "deterministic-context-planner-v1",
        "configuration_digest": "a" * 64,
        "provider_id": "synthetic.provider",
        "model_id": "synthetic.model",
        "evaluation_evidence_identity": "evaluation-run:synthetic:case-1",
        "tested_revision": "abcdef0123456789",
        "counter_identity": "phase13-envelope-byte-estimate-v1",
    }

    complete = measure_planning_answer(
        _assembled(fixture, fixture.source_ids), fixture, output,
        source_bindings=bindings, **identity,
    )
    partial = measure_planning_answer(
        _assembled(fixture, fixture.source_ids[:-1]), fixture, output,
        source_bindings=bindings, **identity,
    )

    assert complete.supported_answer_rate == 1
    assert partial.supported_answer_rate < complete.supported_answer_rate
    assert complete.evidence_identity != partial.evidence_identity
    assert all(source_id not in complete.model_dump_json() for source_id in fixture.source_ids)


def test_quality_evidence_binds_provider_model_and_evaluation_identity():
    fixtures, _task, _scoring = load_provider_matrix_configuration()
    fixture = fixtures[0]
    kwargs = {
        "source_bindings": {source_id: source_id for source_id in fixture.source_ids},
        "strategy_version": "deterministic-context-planner-v1",
        "configuration_digest": "a" * 64,
        "provider_id": "synthetic.provider",
        "model_id": "synthetic.model",
        "evaluation_evidence_identity": "evaluation-run:synthetic:case-1",
        "tested_revision": "abcdef0123456789",
        "counter_identity": "phase13-envelope-byte-estimate-v1",
    }
    assembled = _assembled(fixture, fixture.source_ids)
    output = json.dumps(fixture.reference_output)
    first = measure_planning_answer(assembled, fixture, output, **kwargs)
    second = measure_planning_answer(
        assembled,
        fixture,
        output,
        **{**kwargs, "model_id": "synthetic.model-v2"},
    )
    assert first.evidence_identity != second.evidence_identity
