"""Adversarial PI-6 contracts, scoring, split, privacy and I/O boundary probes."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_ai.evaluation.pi6 import safe_dispatch
from personal_ai.evaluation.pi6_contracts import (
    DIRECTORY,
    Case,
    Corpus,
    Observation,
    Task,
    load_corpus,
)
from personal_ai.evaluation.pi6_scoring import aggregate, score


def test_frozen_corpus_and_lineage_splits():
    corpus, manifest = load_corpus()
    assert len(corpus.cases) == 32 and manifest['frozen_before_measurement']
    assert len({c.lineage for c in corpus.cases}) == 32


@pytest.mark.parametrize('mutation', ['duplicate', 'leakage', 'extra', 'url', 'code', 'budget'])
def test_untrusted_corpus_rejects(mutation):
    raw = json.loads((DIRECTORY / 'cases-v1.json').read_text())
    if mutation == 'duplicate':
        raw['cases'][1]['case_id'] = raw['cases'][0]['case_id']
    elif mutation == 'leakage':
        raw['cases'][2]['lineage'] = raw['cases'][0]['lineage']
    elif mutation == 'extra':
        raw['import'] = 'os:system'
    elif mutation == 'url':
        raw['cases'][0]['task']['subject'] = 'http://127.0.0.1/secret'
    elif mutation == 'code':
        raw['cases'][0]['oracle']['scorer'] = "__import__('os').system('echo unsafe')"
    else:
        raw['input_cap'] = 999999999
    with pytest.raises(ValidationError):
        Corpus.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize('payload', ['../private', '/etc/passwd', 'https://example.org', 'os:system', 'x\nsecret'])
def test_manifest_task_cannot_supply_path_url_import(payload):
    with pytest.raises(ValidationError):
        Task(family='one_app', variant='current', subject=payload, value='cobalt', distractor='violet')


def test_manifest_hash_and_schema_tamper(monkeypatch):
    original = Path.read_bytes
    def tamper(path):
        raw = original(path)
        return raw.replace(b'cobalt', b'cobolt', 1) if path.name == 'cases-v1.json' else raw
    monkeypatch.setattr(Path, 'read_bytes', tamper)
    with pytest.raises(ValueError, match='frozen_identity_mismatch'):
        load_corpus()


@pytest.mark.parametrize('change', [
    {'outcome': 'correct', 'factual': False},
    {'hard_valid': False}, {'duplicate_effect': True}, {'dispatched': 2},
    {'citation': False}, {'status': 'unmeasured'}, {'error': 'offline_failure'},
])
def test_schema_valid_false_or_unsafe_answers_fail(change):
    case = next(c for c in load_corpus()[0].cases if c.task.family == 'retrieval' and c.task.variant == 'current')
    observation = Observation(outcome='correct', hard_valid=True, factual=True, citation=True)
    result = score(case, 'candidate', observation.model_copy(update=change))
    assert not result['success']


def test_veto_survives_high_average_and_unmatched_excluded():
    case = load_corpus()[0].cases[0]
    good = Observation(outcome='correct', hard_valid=True, factual=True)
    bad = good.model_copy(update={'hard_valid': False})
    rows = [{'family': 'one_app', 'split': 'heldout', 'case_digest': str(i), 'arm': arm,
             'observation': (bad if i == 9 else good).model_dump(),
             'score': score(case, arm, bad if i == 9 else good)}
            for i in range(10) for arm in ('baseline','candidate')]
    rows.append({**rows[0], 'case_digest': 'unmatched'})
    analysis = aggregate(rows)
    assert analysis['safety_veto'] and analysis['promotion'] == 'not_promoted'
    assert analysis['families']['one_app']['matched'] == 10
    assert analysis['families']['memory']['risk_difference'] is None


def test_exception_and_print_content_never_retained(capsys):
    secret = 'PI6_RAW_TASK_SECRET_NEVER_PERSIST'
    task = Task(family='one_app', variant='current', subject='amber', value='cobalt', distractor='violet')
    def leaking(task, arm):
        print(secret)
        raise RuntimeError(secret)
    observation, wall, cpu = safe_dispatch(task, 'baseline', driver=leaking)
    assert secret not in observation.model_dump_json()
    assert secret not in str(capsys.readouterr())
    assert observation.error == 'offline_failure' and not observation.hard_valid
    assert wall >= 0 and cpu >= 0


def test_observation_rejects_raw_fields_and_unknown_is_not_zero():
    with pytest.raises(ValidationError):
        Observation(outcome='correct', hard_valid=True, answer='raw private answer')
    row = Observation(outcome='unknown', hard_valid=True)
    assert row.input_units is None and row.output_units is None


def test_driver_has_no_oracle_input():
    assert 'oracle' not in Task.model_fields
    assert 'oracle' in Case.model_fields


@pytest.mark.loopback_http
@pytest.mark.parametrize('change', ['owner', 'actor', 'app', 'workspace', 'expired', 'unauthenticated'])
def test_signed_http_foreign_scope_is_opaque(tmp_path, change):
    from uuid import uuid4

    from personal_ai.evaluation.pi6_http import environment

    with environment(tmp_path) as h:
        created = h.client.start('Synthetic', uuid4())
        headers = dict(h.headers)
        if change == 'owner':
            headers['X-Owner-ID'] = 'forged'
        elif change == 'actor':
            headers['X-Acting-User-ID'] = 'forged'
        elif change == 'app':
            headers['X-Application-ID'] = 'personal_ai'
        elif change == 'workspace':
            headers['X-Workspace-ID'] = 'foreign'
        elif change == 'expired':
            headers['Authorization'] = 'Bearer ' + h.token(exp=1)
        else:
            headers.pop('Authorization')
        response = h.raw.get(f"/v1/conversations/{created['id']}", headers=headers)
        assert response.status_code in {401, 403, 404}
        assert 'Synthetic' not in response.text and not h.pair.generator.delegate.requests


@pytest.mark.loopback_http
@pytest.mark.parametrize('operation', ['external', 'unregistered_tool', 'schema', 'source_path'])
def test_disabled_external_and_tool_payloads_cannot_dispatch(tmp_path, operation):
    from uuid import uuid4

    from personal_ai.evaluation.pi6_http import environment

    with environment(tmp_path) as h:
        body = {'query': 'Synthetic', 'idempotency_key': str(uuid4())}
        path = '/v1/retrieval/query'
        if operation == 'external':
            body['sources'] = ['external']
        elif operation == 'unregistered_tool':
            path = '/v1/tools/memory.forget/invoke'
        elif operation == 'schema':
            body['schema_version'] = 'evil-v9'
        else:
            body['path'] = '/private/secret'
        response = h.raw.post(path, headers=h.headers, json=body)
        assert not h.pair.generator.delegate.requests
        assert response.status_code in {200, 403, 404, 422}
        if response.status_code == 200:
            assert not response.json()['items']


def test_emit_receives_only_safe_copy(monkeypatch):
    # A representative one-case pilot uses the exact row builder and emitter;
    # corpus validation remains exercised separately against all 32 frozen cases.
    from types import SimpleNamespace

    from personal_ai.evaluation import pi6

    corpus, manifest = load_corpus()
    one = SimpleNamespace(cases=(corpus.cases[0],), seed=61, suite=corpus.suite,
                          rubric=corpus.rubric, input_cap=32768, output_cap=256)
    monkeypatch.setattr(pi6, 'load_corpus', lambda: (one, manifest))
    monkeypatch.setattr(pi6, 'safe_dispatch', lambda *a: (Observation(outcome='correct', hard_valid=True), 1., 1.))
    emitted = []
    def emit(row):
        emitted.append(json.dumps(row))
        row['observation']['outcome'] = 'changed_by_sink'
    result = pi6.evaluate(emit=emit)
    assert all(r['observation']['outcome'] == 'correct' for r in result['rows'])
    raw = ''.join(emitted)
    assert not any(word in raw for word in ['Authorization', 'prompt', 'answer', 'cobalt', 'amber', 'pi6-synthetic'])


@pytest.mark.loopback_http
def test_calibration_empty_required_source_is_unknown_without_dispatch():
    from personal_ai.evaluation.pi6_driver import dispatch
    case = next(c for c in load_corpus()[0].cases if c.split == 'calibration' and c.task.variant == 'irrelevant')
    result = dispatch(case.task, 'candidate')
    assert result.outcome == 'unknown' and result.hard_valid and result.dispatched == 0



def test_forget_failure_and_unavailable_read_cannot_score_success(monkeypatch):
    from personal_ai.evaluation.pi6_driver import memory_task
    from personal_ai.memory.control_contracts import OperationResult, ReadResult
    from personal_ai.memory.control_service import MemoryControlService

    monkeypatch.setattr(MemoryControlService, 'mutate', lambda *a: OperationResult(
        status='temporarily_unavailable', reason='synthetic_failure'))
    monkeypatch.setattr(MemoryControlService, 'read', lambda *a, **k: ReadResult(
        status='temporarily_unavailable'))
    task = Task(family='memory', variant='forget', subject='amber', value='cobalt', distractor='violet')
    result = memory_task(task, 'candidate')
    assert result.outcome == 'failed' and not result.hard_valid and not result.factual
