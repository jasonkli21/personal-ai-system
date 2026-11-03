"""PI-6 bounded offline runner. Raw text exists only within individual drivers."""
from __future__ import annotations

import argparse
import io
import json
import logging
import platform
import statistics
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from pathlib import Path
from time import perf_counter, process_time

from personal_ai.evaluation.pi6_contracts import Observation, Task, canonical, load_corpus
from personal_ai.evaluation.pi6_scoring import aggregate, score

ROOT = Path(__file__).resolve().parents[4]


def runtime_identity():
    files = sorted((ROOT / 'backend/src/personal_ai').rglob('*.py'))
    files += [ROOT / 'backend/uv.lock', ROOT / 'backend/pyproject.toml']
    return sha256(canonical([(str(p.relative_to(ROOT)), sha256(p.read_bytes()).hexdigest())
                             for p in files]).encode()).hexdigest()


def safe_dispatch(task, arm, driver=None):
    # Suppress third-party exception/log text, including startup errors. Never emit
    # exception strings. This sink is ephemeral and never serialized or returned.
    from personal_ai.evaluation.pi6_driver import dispatch

    started, cpu = perf_counter(), process_time()
    prior = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            observation = (driver or dispatch)(task, arm)
        observation = Observation.model_validate(observation)
    except Exception:  # noqa: BLE001 - content-free fail-closed evaluation observation
        observation = Observation(outcome='failed', hard_valid=False, error='offline_failure')
    finally:
        logging.disable(prior)
    return observation, round((perf_counter() - started) * 1000, 3), round((process_time() - cpu) * 1000, 3)


def evaluate(*, emit=None):
    corpus, manifest = load_corpus()
    started = perf_counter()
    # Warmup deliberately outside corpus, split, denominator and source configuration.
    warmup = Task(family='provider', variant='current', subject='warmup', value='ready', distractor='absent')
    warmed, _, _ = safe_dispatch(warmup, 'baseline')
    if warmed.error != 'none' or not warmed.hard_valid:
        raise RuntimeError('pi6_warmup_failed')
    rows = []
    for index, case in enumerate(corpus.cases):
        arms = ('baseline', 'candidate') if (index + corpus.seed) % 2 else ('candidate', 'baseline')
        if case.task.family == 'retrieval':
            arms = (*arms, 'standalone')
        for arm in arms:
            if perf_counter() - started > 120:
                raise RuntimeError('pi6_suite_deadline')
            observation, wall, cpu = safe_dispatch(case.task, arm)
            if ((observation.input_units is not None and observation.input_units > corpus.input_cap)
                    or (observation.output_units is not None and observation.output_units > corpus.output_cap)):
                observation = observation.model_copy(update={'hard_valid': False, 'error': 'budget_exceeded'})
            # All fields are code-owned enums, opaque digests or numeric measurements.
            row = {'case_digest': sha256(case.case_id.encode()).hexdigest(),
                   'source_digest': sha256(canonical(case.task.model_dump()).encode()).hexdigest(),
                   'family': case.task.family, 'split': case.split, 'arm': arm,
                   'order': len(rows), 'authority': 'synthetic_exact_scope',
                   'owner_class': 'synthetic', 'actor_class': 'verified_synthetic',
                   'application_class': 'unrelated_http_consumer' if case.task.family not in {'memory', 'research'} else 'local_service',
                   'workspace_class': 'isolated_synthetic', 'rights_epoch_class': 'local_revision_one',
                   'output_token_confidence': 'estimated' if observation.output_units is not None else 'unknown',
                   'provider': ('offline_fake_alt' if case.task.family == 'provider' and arm == 'candidate' else 'offline_fake') if case.task.family not in {'memory','research'} else 'synthetic_only',
                   'model': ('offline_fake_alt-v1' if case.task.family == 'provider' and arm == 'candidate' else 'offline_fake-v1') if case.task.family not in {'memory','research'} else 'not_applicable',
                   'token_counter': 'pi3-local-json-bytes-v1' if observation.token_confidence == 'authoritative_local_bytes' else observation.token_confidence,
                   'serializer': 'pi3-local-json-bytes-v1' if case.task.family not in {'memory','research'} else 'not_applicable',
                   'observation': observation.model_dump(mode='json'),
                   'score': score(case, 'candidate' if arm == 'standalone' else arm, observation), 'wall_ms': wall, 'cpu_ms': cpu,
                   'latency_class': 'local_synthetic', 'cost': {'synthetic_usd': 0,
                       'real_usd': None, 'upper_bound_usd': None, 'estimated_usd': None,
                       'confidence': 'synthetic_only'},
                   'quota': {'reservation': None, 'settlement': None, 'status': 'unmeasured'},
                   'cancellation': 'not_applicable', 'unknown_outcome': False}
            rows.append(row)
            if emit:
                # Copy prevents retention hooks from mutating the canonical result.
                emit(json.loads(canonical(row)))
    elapsed = sorted(r['wall_ms'] for r in rows)
    return {'suite': corpus.suite, 'rubric': corpus.rubric, 'seed': corpus.seed,
            'evidence_class': 'offline_scripted_service_proxy', 'fixture_hashes': manifest['hashes'],
            'runtime_sha256': runtime_identity(), 'runtime': platform.python_version(),
            'os': platform.system(), 'architecture': platform.machine(),
            'commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
            'dirty': bool(subprocess.check_output(['git','status','--porcelain'], cwd=ROOT)),
            'rows': rows, 'analysis': aggregate(rows),
            'latency': {'class': 'local_synthetic', 'n': len(elapsed),
                        'p50_ms': statistics.median(elapsed),
                        'p95_ms': elapsed[int(.95 * (len(elapsed) - 1))]},
            'ineligible': [
                {'arm': 'external_source_to_model', 'status': 'blocked_capability', 'reason': 'distributed_authority_absent'},
                {'arm': 'live_provider_quality', 'status': 'unmeasured', 'reason': 'no_live_authorization'},
                {'arm': 'paid_or_arbitrary_tool', 'status': 'denied_policy', 'reason': 'outside_offline_scope'},
                {'arm': 'memory_on_nonmemory_tasks', 'status': 'not_applicable', 'reason': 'task_has_no_durable_memory'},
            ],
            'pi5_completion': 'blocked_unverified', 'pi6_production_promotion': 'no_go'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Refuse ordinary invocation; the launcher proves the native fence and passes
    # a process-local capability through a builtin, not user/environment strings.
    if not getattr(sys, '_pi6_native_fenced', False):
        raise SystemExit('PI6 requires backend/scripts/pi6_checks.py native launcher')
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical(result) + '\n')
    print(canonical({'suite': result['suite'], 'rows': len(result['rows']), 'analysis': result['analysis']}))
    return 1 if result['analysis']['safety_veto'] or any(r['observation']['error'] != 'none' for r in result['rows']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
