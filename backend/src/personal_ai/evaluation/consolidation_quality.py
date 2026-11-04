"""Scripted fresh-consumer quality and optional canonical local inference pilot."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from importlib.resources import files
from time import perf_counter

from personal_ai.context.builder import ContextBuilder, ContextBuildItem, ContextBuildPolicy
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.llm.client import ChatMessage
from personal_ai.memory.consolidation.contracts import (
    BACKFILL_GENERATION,
    V2_SOURCE_V1_POLICY_GENERATION,
)
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
CHALLENGE_MANIFEST_SHA256 = "b50bd0253f316c318f700ec1e31d60522391f3323c68afc9e84d9dab624c1169"


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
    repo = OfflineProposalRepository(source, generation=V2_SOURCE_V1_POLICY_GENERATION)
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


def eligible_source_cards(source, scope):
    """Exact current fixture records, with source identity retained for attribution."""
    key = source._scope(scope)
    return [
        {
            "source_id": record.source_id,
            "source_fingerprint": digest(record),
            "revision": record.revision,
            "epoch": record.epoch,
            "evidence": record.evidence,
            "command": record.fact.command,
            "outcome": record.fact.outcome,
            "fact_revision": record.fact.revision,
        }
        for record in source._streams[key][: source._published[key]]
        if source.current(record, scope)
    ]


LOCAL_PILOT_ARMS = (
    "no_consolidation",
    "deterministic_pending",
    "eligible_source_context",
)


def local_pilot_status(rows):
    """Do not call incomplete or unaccounted attempts a measured pilot."""
    by_arm = {row.get("pilot_arm"): row for row in rows}
    if len(rows) != len(LOCAL_PILOT_ARMS) or set(by_arm) != set(LOCAL_PILOT_ARMS):
        return "blocked", "arm_coverage_incomplete"
    for arm in LOCAL_PILOT_ARMS:
        row = by_arm[arm]
        if row.get("status") != "completed" or row.get("completed") is not True:
            return "blocked", "attempt_incomplete"
        if row.get("forbidden_output") is True:
            return "blocked", "safety_failure"
        if (
            type(row.get("input_tokens")) is not int
            or type(row.get("output_tokens")) is not int
            or row.get("usage_confidence") not in {"reported", "estimated"}
        ):
            return "blocked", "usage_unverified"
    return "measured_pilot", None


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
    if (
        type(query) is not dict
        or set(query) != {"command", "revision"}
        or type(query.get("command")) is not str
        or type(query.get("revision")) is not str
        or query["command"]
        not in {"make backend-lint", "make backend-test-offline", "make memory-eval"}
    ):
        return {"status": "abstain", "outcome": None}
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


def load_challenge_manifest():
    """Load an additive, author-visible regression manifest without relabeling it E5."""
    data = (
        files("personal_ai.evaluation")
        .joinpath("fixtures/memory/offline-consolidation-challenges-v1.json")
        .read_bytes()
    )
    if len(data) > 65536 or sha256(data).hexdigest() != CHALLENGE_MANIFEST_SHA256:
        raise RuntimeError("consolidation_challenge_manifest_identity_mismatch")
    manifest = json.loads(data)
    if (
        manifest.get("schema_version") != "offline-consolidation-challenges-v1"
        or manifest.get("classification") != "synthetic"
        or manifest.get("author_visible") is not True
        or manifest.get("independent_holdout") is not False
        or len(manifest.get("cases", ())) != 4
    ):
        raise RuntimeError("consolidation_challenge_manifest_invalid")
    return manifest


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
    """Matched synthetic source arms via canonical chat assembly and accounting."""
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
    expected_query = task["expected"]
    actual = consume(pack(cards), scope.key, task["query"])
    if actual != expected_query:
        return {"status": "blocked", "reason": "synthetic_candidate_failed"}
    prompt = (
        f"Report the synthetic outcome for {task['query']['command']} at "
        f"{task['query']['revision']}. Do not execute anything."
    )
    eligible = eligible_source_cards(_source, scope)
    pending_text = "Untrusted pending synthetic proposals: " + json.dumps(cards, sort_keys=True)
    eligible_text = "Untrusted eligible synthetic source records: " + json.dumps(
        eligible, sort_keys=True
    )
    no_source_text = "No eligible memory or source context is available."
    case_base = {
        "id": session,
        "family": "synthetic_consolidation_pilot",
        "split": "development",
        "distractor": "No additional synthetic evidence is eligible.",
        "prompt": prompt,
        "required": [task["expected"]["outcome"], task["query"]["revision"]],
        "forbidden": ["SECRET_CANARY"],
        "require_scope_denial": False,
    }
    # This fixture fact type has no representation in canonical schema-3 fixed
    # memory, so the fixed-memory comparator is an explicit unsupported row.
    unsupported = {
        "pilot_arm": "current_fixed_memory",
        "status": "unsupported",
        "reason": "fixture_facts_not_representable_in_canonical_fixed_memory",
        "completed": False,
        "rubric_pass": None,
    }
    pair = compose_pair(settings, usage)
    rows = []
    for pilot_arm, source_text, selected_arm in (
        ("no_consolidation", no_source_text, "direct"),
        ("deterministic_pending", pending_text, "selected"),
        ("eligible_source_context", eligible_text, "selected"),
    ):
        case = {
            **case_base,
            "source": source_text,
        }
        row = await run_case(settings, pair, case, selected_arm, uuid4())
        row["pilot_arm"] = pilot_arm
        rows.append(row)
    status, reason = local_pilot_status(rows)
    resource_rows = [
        {
            "pilot_arm": row["pilot_arm"],
            "input_tokens": row.get("input_tokens"),
            "output_tokens": row.get("output_tokens"),
            "usage_confidence": row.get("usage_confidence"),
            "elapsed_ms": row.get("elapsed_ms"),
            "provider_cost_usd": None,
            "cost_class": "LOCAL_NO_CHARGE",
        }
        for row in rows
    ]
    return {
        "status": status,
        "reason": reason,
        "evidence_tier": "E2_attempt",
        "comparator_contract": {
            "attempted_arms": LOCAL_PILOT_ARMS,
            "unsupported_arms": (unsupported,),
            "same_model_and_context_budget": True,
            "same_output_and_deadline_bounds": True,
            "fixed_memory_comparator": "unsupported",
        },
        "model_identity": {
            "provider_id": pair.generator.identity.provider_id,
            "model_id": pair.generator.identity.model_id,
            "serializer_id": pair.generator.identity.serializer_id,
        },
        "resource_policy": {
            "context_tokens": settings.max_context_tokens,
            "response_tokens": settings.max_response_tokens,
            "deadline_seconds": settings.request_timeout_seconds,
            "hardware": "not_recorded",
        },
        "rows": [*rows, unsupported],
        "task_result_rubric": {
            "completed_trials": sum(row.get("completed") is True for row in rows),
            "passes": sum(row.get("rubric_pass") is True for row in rows),
            "denominator": len(rows),
        },
        "resources": resource_rows,
        "corpus_sha256": ADVERSARIAL_CORPUS_SHA256,
        "hosted_fallback": False,
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
