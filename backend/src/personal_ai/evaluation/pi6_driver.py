"""Input-only task drivers over existing services. Oracles never enter these functions."""
from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from personal_ai.evaluation.pi6_contracts import Observation


def http_task(task, arm):
    from reading_logbook.client import APIError, UncertainTurn

    from personal_ai.evaluation.pi6_http import environment, install_source, profile_grant

    with (tempfile.TemporaryDirectory(prefix='pi6-') as directory,
          environment(Path(directory).resolve(), builtin=task.family == 'branch', alternate=task.family == 'provider' and arm == 'candidate') as h):
        created = h.client.start('Synthetic task', uuid4())
        cid = created['id']
        prompt = f'Lookup {task.subject}'
        body = {'content': prompt, 'idempotency_key': str(uuid4()), 'choice': {'mode': 'automatic'}}
        source = None
        expected_value = task.value
        citation = None
        if task.family == 'profile':
            expected_value, ui, grant = profile_grant(h, task)
            body['content'] = 'What are my preferred units?'
            if arm == 'baseline':
                h.settings.profile_sharing_enabled = False
        elif task.family in {'one_app', 'retrieval', 'replay'}:
            source = install_source(h, created['owner_id'], task)
            body['retrieval_context'] = arm == 'candidate'
            if task.variant == 'irrelevant':
                body['content'] = 'Lookup unrelated'
                expected_value = 'unknown'
        elif task.family == 'branch':
            # Use the public edit API to preserve branch/supersedes semantics.
            seed = {'content': f'PI6 fact: {task.subject}={task.distractor}.',
                    'idempotency_key': str(uuid4()), 'choice': {'mode': 'automatic'}}
            initial = h.client.ask(cid, seed)
            if task.variant in {'supersede', 'edit'}:
                detail = h.client.conversation(cid)
                user = next(m for m in detail['messages'] if m['role'] == 'user')
                edited = h.raw.post(f"/v1/conversations/{cid}/messages/{user['id']}/edit-and-retry", headers=h.headers,
                                    json={'content': f'PI6 fact: {task.subject}={task.value}.'})
                if edited.status_code not in {200, 201}:
                    raise RuntimeError('pi6_branch_edit_failed')
            else:
                seed['idempotency_key'] = str(uuid4())
                seed['content'] = (('Irrelevant filler. ' * 220) if task.variant == 'long' else '')
                seed['content'] += f'PI6 fact: {task.subject}={task.value}.'
                h.client.ask(cid, seed)
            del initial
        elif task.family == 'provider':
            if task.variant == 'outage':
                h.pair.generator.delegate.terminal_status = 'failure'
            elif task.variant == 'missing':
                # Existing closed configuration validator, never a real profile.
                from personal_ai.llm.errors import LLMInvalidConfigurationError
                from personal_ai.llm.execution import compose_pair
                try:
                    compose_pair(h.settings.model_copy(update={'inference_profile': 'not_installed'}))
                except LLMInvalidConfigurationError:
                    return Observation(outcome='denied', hard_valid=True, factual=True)
                return Observation(outcome='failed', hard_valid=False)
            else:
                body['content'] += f' PI6 fact: {task.subject}={task.value}.'

        if arm == 'standalone':
            result = h.client.retrieve(body['content'], uuid4())
            items = result['items']
            tool = h.client.retrieve(body['content'], uuid4(), tool=True)
            exact = (not items if task.variant == 'irrelevant' else bool(items)
                     and all(item['quote'] in source['documents'][0]['text']
                             and item['content_fingerprint'] == sha256(item['quote'].encode()).hexdigest()
                             for item in items))
            exact = exact and tool['retrieval']['items'] == items
            return Observation(outcome='unknown' if not items else 'correct', hard_valid=exact,
                               factual=exact, citation=bool(items), dispatched=0, expected_dispatches=0,
                               source_dependencies=len(items), tool_units=None)

        before = len(h.pair.generator.delegate.requests)
        try:
            answer = h.client.ask(cid, body)
        except (APIError, UncertainTurn) as error:
            sends = len(h.pair.generator.delegate.requests) - before
            if task.variant == 'irrelevant' and isinstance(error, APIError) and error.code == 'required_context_source_empty':
                return Observation(outcome='unknown', hard_valid=sends == 0, factual=True)
            return Observation(outcome='failed', hard_valid=task.variant == 'outage',
                               factual=task.variant == 'outage', dispatched=sends,
                               expected_dispatches=1 if task.variant == 'outage' else 0)
        content = answer['content']
        sent = h.pair.generator.delegate.requests[-1]
        packed = '\n'.join(m.content for m in sent)
        correct = content.split(' [')[0] == expected_value
        outcome = 'correct' if correct else ('unknown' if content == 'unknown' else 'failed')
        if expected_value == 'unknown' and correct:
            outcome = 'unknown'
        snapshots = answer.get('attribution', {}).get('source_snapshots', [])
        dependencies = sum(len(s.get('permission_dependencies', [])) for s in snapshots)
        hard = (task.family != 'branch' or task.variant not in {'supersede', 'edit'} or task.distractor not in packed) and 'en-GB' not in packed and (task.family not in {'retrieval', 'one_app', 'replay'}
                or arm != 'candidate' or task.variant == 'irrelevant' or dependencies > 0)
        if source and arm == 'candidate' and task.variant != 'irrelevant':
            from personal_ai.auth.scope import RequestScope
            from personal_ai.retrieval.contracts import RetrievalQuery
            from personal_ai.retrieval.installation import LexicalIndex, load_snapshot
            scope = RequestScope(**source['access'][0], request_id='pi6')
            snapshot = load_snapshot(str(h.directory / 'sources.json'))
            items, _ = LexicalIndex(snapshot.installation.documents,
                                    issuer_id=snapshot.installation.issuer_id).search(
                RetrievalQuery(query=prompt, idempotency_key=uuid4()), scope)
            citation = bool(items) and content.endswith('[' + items[0].citation_id + ']')
            # Standalone/tool controls use the same public consumer, no model send.
            standalone = h.client.retrieve(prompt, uuid4())
            tool = h.client.retrieve(prompt, uuid4(), tool=True)
            hard = hard and bool(standalone['items']) and bool(tool['retrieval']['items'])
        elif source:
            citation = False

        if task.family in {'profile', 'replay'} and task.variant in {'revoke', 'edit', 'expiry'}:
            if task.family == 'profile':
                h.settings.profile_sharing_enabled = True
                if task.variant == 'revoke':
                    revoke = {**grant, 'operation_id': str(uuid4()), 'operation': 'revoke', 'expected_revision': 1}
                    response = h.raw.post('/v1/profile/shares', headers={**ui, 'If-Match': '"1"'}, json=revoke)
                    hard = hard and response.status_code == 200
                elif task.variant == 'edit':
                    response = h.raw.put('/v1/profile', headers=ui,
                                        json={'fields': [{'field': 'preferred_units', 'value': 'metric' if expected_value == 'imperial' else 'imperial'}]})
                    hard = hard and response.status_code == 200
                else:
                    h.profile._clock = lambda: datetime.now(UTC) + timedelta(days=2)
            else:
                if task.variant == 'revoke':
                    source['documents'][0]['model_context_allowed'] = False
                elif task.variant == 'edit':
                    source['documents'][0]['revision'] = '2'
                else:
                    source['documents'][0]['expires_at'] = (datetime.fromisoformat(source['documents'][0]['observed_at']) + timedelta(milliseconds=1)).isoformat()
                h.directory.joinpath('sources.json').write_text(json.dumps(source))
            replay = h.raw.post(f'/v1/conversations/{cid}/continue', headers=h.headers, json=body)
            detail = h.raw.get(f'/v1/conversations/{cid}', headers=h.headers)
            inspection = h.raw.get(f'/v1/conversations/{cid}/context', headers=h.headers)
            if arm == 'candidate':
                hard = (hard and 'response.completed' not in replay.text
                        and expected_value not in replay.text and detail.status_code == 409
                        and inspection.status_code in {403, 409} and expected_value not in detail.text
                        and expected_value not in inspection.text)
            else:
                hard = hard and expected_value not in replay.text
            outcome = 'denied' if hard else 'failed'
            correct = hard
            citation = None
        elif task.family == 'replay' and task.variant == 'collision':
            changed = {**body, 'content': body['content'] + ' changed'}
            response = h.raw.post(f'/v1/conversations/{cid}/continue', headers=h.headers, json=changed)
            hard = hard and response.status_code == 409
            outcome, correct = ('conflict' if hard else 'failed'), hard
            citation = None
        else:
            replayed = h.client.ask(cid, body)
            hard = hard and replayed == answer

        sends = len(h.pair.generator.delegate.requests) - before
        token_count = h.pair.counter.delegate.count(sent, inference_context=h.pair.generator.delegate.inference_contexts[-1])
        return Observation(outcome=outcome, hard_valid=hard, factual=correct, citation=citation,
                           dispatched=sends, expected_dispatches=1, duplicate_effect=sends > 1,
                           source_dependencies=dependencies, input_units=token_count.tokens,
                           output_units=(len(content) + 3) // 4,
                           unnecessary_context=task.distractor in packed,
                           token_confidence='authoritative_local_bytes')


def memory_task(task, arm):
    from personal_ai.evaluation.control_runtime import ControlRuntime
    from personal_ai.evaluation.memory_control import mutation
    from personal_ai.memory.control_contracts import SearchInput

    rt = ControlRuntime()
    with rt.user():
        record = rt.seed(run_id=task.subject)
        if task.variant == 'forget':
            dependency = rt.knowledge.dependency(record, rt.scope)
            intent = mutation()
            result = rt.service.mutate('forget', record.id, intent)
            current = rt.service.read(SearchInput(), memory_id=record.id)
            valid = (result.status == 'applied' and result.operation_id == intent.operation_id
                     and not current.items and not rt.knowledge.is_current(dependency))
            return Observation(outcome='forgotten' if valid else 'failed',
                               hard_valid=valid, factual=valid)
        if task.variant == 'edit':
            result = rt.service.mutate('revise', record.id, mutation())
            return Observation(outcome='denied', hard_valid=result.status == 'unsupported_evidence_source',
                               factual=result.status == 'unsupported_evidence_source')
        if task.variant == 'revoke':
            rt.authority.disclosure_allowed = False
        response = rt.service.read(SearchInput(), memory_id=record.id) if arm == 'candidate' else None
        if task.variant == 'revoke':
            valid = response is None or not response.items
            return Observation(outcome='denied', hard_valid=valid, factual=valid)
        matched = bool(response and response.items and response.items[0].id == record.id)
        return Observation(outcome='correct' if matched else 'unknown', hard_valid=True,
                           factual=matched, source_dependencies=1 if matched else 0)


def research_task(task, arm):
    from unittest.mock import patch

    from personal_ai.evaluation import retrieval
    from personal_ai.evaluation.memory_task_runtime import OfflineSettings

    facts = [f'The synthetic {task.subject} is {task.value}.']
    if task.variant == 'conflict':
        facts.append(f'The synthetic {task.subject} is {task.distractor}.')
    case = {'name': 'conflicting-sources' if task.variant == 'conflict' else 'pi6-independent',
            'question': f'Synthetic {task.subject}?', 'expected': 'completed',
            'sources': [{'url': f'https://example.org/pi6/{task.subject}/{i}', 'text': fact}
                        for i, fact in enumerate(facts)]}
    def bounded_settings(**kwargs):
        return OfflineSettings(**kwargs, max_response_tokens=256, max_context_tokens=33024,
                               context_safety_margin_tokens=0, request_timeout_seconds=5,
                               research_timeout_seconds=5, research_provider_timeout_seconds=5)
    observations = {}
    with patch.object(retrieval, 'Settings', bounded_settings):
        metrics, session = asyncio.run(retrieval.measure(
            case, 'compact-extractive-v1' if arm == 'candidate' else 'literal-extractive-v1',
            observations=observations))
    semantics = retrieval.semantic_outcome(session, metrics)
    selected = set(session.selection.evidence_ids) if session.selection else set()
    passages = {e.passage for e in session.evidence if e.id in selected}
    exact = passages == set(facts)
    return Observation(outcome='completed' if session.state == 'completed' else 'failed',
                       hard_valid=semantics['hard_constraints_passed'] and semantics['freshness_compliance'] and semantics['exact_support'],
                       factual=exact, citation=bool(session.citations) and metrics.citation_correctness == 1,
                       dispatched=metrics.synthesis_invocations, expected_dispatches=1,
                       input_units=observations.get('synthesis_input_token_estimate'),
                       output_units=observations.get('synthesis_output_token_estimate'),
                       source_dependencies=len(selected), token_confidence='estimated')


def dispatch(task, arm):
    if task.family == 'memory':
        return memory_task(task, arm)
    if task.family == 'research':
        return research_task(task, arm)
    return http_task(task, arm)
