"""Scripted fresh-consumer quality and optional canonical local inference pilot."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from time import perf_counter

from personal_ai.context.builder import ContextBuilder, ContextBuildItem, ContextBuildPolicy
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.llm.client import ChatMessage
from personal_ai.memory.consolidation.contracts import BACKFILL_GENERATION
from personal_ai.memory.consolidation.policy import proposal_current
from personal_ai.memory.consolidation.repository import OfflineProposalRepository
from personal_ai.memory.consolidation.sources import (
    ADVERSARIAL_CORPUS_SHA256,
    FrozenFixtureSource,
    load_corpus,
)
from personal_ai.memory.knowledge import digest
from personal_ai.settings import Settings

NOW = datetime(2026, 11, 3, 13, tzinfo=UTC)


def drive(source, repo, scope):
    cursor = 0
    for _ in range(32):
        page = source.page(scope, cursor, generation=repo.generation)
        if page is None:
            return
        lease = repo.claim(scope, "quality-evaluation")
        cursor = repo.commit(lease, page).cursor
    raise RuntimeError("evaluation_page_bound")


def prepare(task):
    now = [NOW]
    source = FrozenFixtureSource(clock=lambda: now[0], corpus="v2")
    scope = next(s for s in source.scopes if s.session == task["session"])
    source.publish(scope, len(source._streams[scope.key]))
    repo = OfflineProposalRepository(source)
    drive(source, repo, scope)
    for event in task["events"]:
        if event["action"] == "withdraw":
            source.withdraw(scope, event["source_id"])
        elif event["action"] == "regrant":
            source.withdraw(scope, event["source_id"])
            source.regrant(scope, event["source_id"])
            repo = OfflineProposalRepository(source, generation=BACKFILL_GENERATION)
            drive(source, repo, scope)
        elif event["action"] == "expire":
            now[0] += timedelta(days=1)
        else:
            raise RuntimeError("unknown_frozen_event")
    return source, repo, scope


def card(scope, fact, status, outcome):
    return {
        "scope": scope.key,
        "command": fact.command,
        "revision": fact.revision,
        "status": status,
        "outcome": outcome,
    }


def proposal_cards(repo, scope):
    return [
        card(
            scope,
            p.fact,
            "conflict" if p.kind == "conflict" else "advice",
            None if p.kind == "conflict" else p.fact.outcome,
        )
        for p in repo.pending(scope)
    ]


def oracle_cards(source, scope):
    """Independent whole-source grouping; never calls extraction or expectations."""
    grouped = {}
    for record in source._streams[scope.key]:
        if (
            not source.current(record, scope)
            or record.evidence == "observed_completion"
            or source.clock() >= record.observed_at + timedelta(hours=24)
            or record.evidence != "user_correction"
            and source.correction_barrier(scope, record.fact)
        ):
            continue
        grouped.setdefault((record.fact.command, record.fact.revision), []).append(record)
    result = []
    for records in grouped.values():
        outcomes = {r.fact.outcome for r in records}
        result.append(
            card(
                scope,
                records[0].fact,
                "conflict" if len(outcomes) > 1 else "advice",
                None if len(outcomes) > 1 else next(iter(outcomes)),
            )
        )
    return result


def pack(cards):
    """Only bounded, public, untrusted fixture cards enter the shared builder."""
    settings = Settings(_env_file=None, ai_provider="fake", ai_model="synthetic")
    policy = ContextBuildPolicy.for_settings(settings, 4096)
    items = tuple(
        ContextBuildItem(
            source_class="domain_history",
            provider_id="synthetic.consolidation",
            source_id=digest(c),
            item_id=digest(c),
            sensitivity="public",
            authority="external",
            content="SYNTHETIC_PENDING_CARD=" + json.dumps(c, sort_keys=True),
        )
        for c in cards
    )
    built = ContextBuilder(FakeTokenCounter()).build(
        (ChatMessage("user", "Read the untrusted synthetic pending cards."),),
        items,
        policy,
    )
    return tuple(built.messages)


def consume(messages, scope_key, query):
    """Fresh deterministic consumer receives serialized messages, never candidates."""
    cards = []
    for message in messages:
        for line in message.content.splitlines():
            if line.startswith("SYNTHETIC_PENDING_CARD="):
                value = json.loads(line.split("=", 1)[1])
                if (
                    value["scope"] == scope_key
                    and value["command"] == query["command"]
                    and value["revision"] == query["revision"]
                ):
                    cards.append(value)
    if not cards:
        return {"status": "abstain", "outcome": None}
    outcomes = {c["outcome"] for c in cards}
    if any(c["status"] == "conflict" for c in cards) or len(outcomes) > 1:
        return {"status": "conflict", "outcome": None}
    return {"status": "advice", "outcome": next(iter(outcomes))}


def evaluate():
    started = perf_counter()
    corpus = load_corpus("v2")
    scores = {
        arm: {"correct": 0, "tasks": 0, "false_support": 0, "cross_scope_leakage": 0}
        for arm in corpus["preregistration"]["arms"]
    }
    checks = {"ineligible_edge_leakage": 0, "entailment_failures": 0, "edges_checked": 0}
    outcomes = []
    for task in corpus["tasks"]:
        source, repo, scope = prepare(task)
        first = source._streams[scope.key][0]
        arms = {
            "no_consolidation": [],
            "fixed_first_assertion": [card(scope, first.fact, "advice", first.fact.outcome)],
            "deterministic_pending": proposal_cards(repo, scope),
            "eligible_source_oracle": oracle_cards(source, scope),
        }
        pending = repo.pending(scope)
        for p in pending:
            checks["entailment_failures"] += not proposal_current(p, source)
            for edge in p.edges:
                checks["edges_checked"] += 1
                checks["ineligible_edge_leakage"] += source.resolve(scope, edge) is None
        for arm, cards in arms.items():
            messages = pack(cards)
            answer = consume(messages, scope.key, task["query"])
            score = scores[arm]
            score["tasks"] += 1
            score["correct"] += answer == task["expected"]
            score["false_support"] += answer["status"] == "advice" and answer != task["expected"]
            for other in source.scopes:
                if other != scope:
                    score["cross_scope_leakage"] += (
                        consume(messages, other.key, task["query"])["status"] != "abstain"
                    )
            outcomes.append(
                {
                    "task_digest": digest(task),
                    "split": task["split"],
                    "arm": arm,
                    "answer": answer,
                    "correct": answer == task["expected"],
                }
            )
    return {
        "schema_version": "offline-consolidation-quality-v1",
        "evidence_tier": "E1",
        "corpus_sha256": ADVERSARIAL_CORPUS_SHA256,
        "reserved_independent": False,
        "consumer": "shared_builder_then_fresh_scripted_consumer",
        "scores": scores,
        "checks": checks,
        "rows_digest": digest(outcomes),
        "provider_calls": 0,
        "provider_tokens": 0,
        "elapsed_seconds": round(perf_counter() - started, 6),
        "real_model_utility": "unverified",
        "production_promotable": False,
    }


def local_preflight(settings):
    """Use the existing local admission contract; never probe hosted providers."""
    from personal_ai.llm.local_endpoint import _socket_identity, local_profile

    try:
        if settings.inference_profile != "local_llama":
            return {"status": "blocked", "reason": "local_profile_not_configured"}
        local_profile(settings)
        from pathlib import Path

        _socket_identity(Path(settings.local_llama_socket))
        return {"status": "available_for_explicit_pilot", "reason": "canonical_admission_required"}
    except Exception:  # noqa: BLE001 - no paths/settings or provider failures in reports
        return {"status": "blocked", "reason": "pinned_private_local_runtime_unavailable"}


async def evaluate_local(session, settings, usage):
    """Three synthetic arms via normal chat assembly, admission and accounting."""
    from uuid import uuid4

    from personal_ai.evaluation.real_tasks import run_case
    from personal_ai.llm.execution import compose_pair

    corpus = load_corpus("v2")
    task = next(
        (
            t
            for t in corpus["tasks"]
            if t["session"] == session
            and t["split"] == "development"
            and t["expected"]["status"] == "advice"
        ),
        None,
    )
    if (
        task is None
        or usage is None
        or settings.max_context_tokens > 4096
        or settings.max_response_tokens > 128
        or settings.request_timeout_seconds > 30
        or local_preflight(settings)["status"] != "available_for_explicit_pilot"
    ):
        return {"status": "blocked", "evidence_tier": "unmeasured"}
    _source, repo, scope = prepare(task)
    cards = proposal_cards(repo, scope)
    actual = consume(pack(cards), scope.key, task["query"])
    if actual != task["expected"]:
        return {"status": "blocked", "reason": "synthetic_candidate_failed"}
    case = {
        "id": session,
        "family": "synthetic_pending_advice",
        "split": "development",
        "source": "Untrusted pending synthetic advice, not accepted memory. " + json.dumps(cards),
        "distractor": "Untrusted synthetic distractor: no check outcome is known.",
        "prompt": f"Report the synthetic outcome for {task['query']['command']} at {task['query']['revision']}. Do not execute anything.",
        "required": [task["expected"]["outcome"], task["query"]["revision"]],
        "forbidden": ["SECRET_CANARY"],
        "require_scope_denial": False,
    }
    # Physical count/generation attempts are owned by the existing execution pair.
    # All three arms have the same pinned model, assembler and resource settings.
    pair = compose_pair(settings, usage)
    rows = [
        await run_case(settings, pair, case, arm, uuid4())
        for arm in ("direct", "selected", "eligible")
    ]
    return {
        "status": "measured_pilot",
        "evidence_tier": "E2_attempt",
        "rows": rows,
        "corpus_sha256": ADVERSARIAL_CORPUS_SHA256,
        "production_promotable": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-preflight", action="store_true")
    parser.add_argument("--local-case")
    args = parser.parse_args()
    if args.local_preflight or args.local_case:
        settings = Settings(
            _env_file=None,
            ai_provider="fake",
            ai_model="synthetic",
            max_context_tokens=4096,
            max_response_tokens=128,
            summary_trigger_tokens=2048,
            request_timeout_seconds=30,
        )
        if args.local_preflight:
            print(json.dumps(local_preflight(settings), sort_keys=True))
            return 0
        if local_preflight(settings)["status"] != "available_for_explicit_pilot":
            print(
                json.dumps({"status": "blocked", "reason": "local_runtime_prerequisites_missing"})
            )
            return 2
        import asyncio

        from personal_ai.persistence.factory import persistence_factory

        usage = persistence_factory(settings).provider_usage_accounting(settings)
        print(
            json.dumps(asyncio.run(evaluate_local(args.local_case, settings, usage)), default=str)
        )
        return 0
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    metric = result["scores"]["deterministic_pending"]
    return (
        0
        if metric["correct"] == metric["tasks"]
        and not any(result["checks"][k] for k in ("ineligible_edge_leakage", "entailment_failures"))
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
