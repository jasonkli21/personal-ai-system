"""Paired, sealed E1 evaluation with a separate objective scorer."""

import asyncio
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from personal_ai.evaluation.reasoning_orchestrator.fixture import synthetic_service
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.reasoning import grounded
from personal_ai.reasoning.orchestration import HARD_LIMIT as DIRECT_LIMIT
from personal_ai.reasoning.orchestration import Request as DirectRequest
from personal_ai.reasoning.orchestration import Requirement, Stop
from personal_ai.reasoning.orchestration import Task as DirectTask
from personal_ai.retrieval.service import RetrievalService
from personal_ai.workflow.reasoning import Fixture
from personal_ai.workflow.service import WorkflowDenied

from .fixture import fixture_service
from .lock import SEAL_SHA256

FILES = Path(__file__).parent
SEALED = {"manifest.json", "cases.json", "oracle.json", "fixture.py", "runner.py"}
ARMS = ("direct", "one_shot", "grounded")


def load(directory=FILES):
    seal = (directory / "seal.json").read_bytes()
    if sha256(seal).hexdigest() != SEAL_SHA256:
        raise ValueError("grounded_benchmark_external_seal_changed")
    seal = json.loads(seal)
    if set(seal) != SEALED or any(
        sha256((directory / name).read_bytes()).hexdigest() != expected for name, expected in seal.items()
    ):
        raise ValueError("grounded_benchmark_member_changed")
    manifest, cases, oracle = (
        json.loads((directory / f"{name}.json").read_bytes()) for name in ("manifest", "cases", "oracle")
    )
    if (
        len(cases) != manifest["pairs"] or len({case["id"] for case in cases}) != len(cases)
        or set(oracle) != {case["id"] for case in cases}
        or sum(case["held_out"] for case in cases) != manifest["held_out"]
        or tuple(manifest["arms"]) != ARMS
    ):
        raise ValueError("grounded_benchmark_cohort_changed")
    return manifest, cases, oracle


def request_for(case, arm):
    return grounded.Request(
        schema_version="reasoning-grounded-request-v1",
        original_key=uuid5(NAMESPACE_URL, f"grounded:{case['id']}:{arm}"),
        task=grounded.Task(subject=case["subject"], requirements=tuple(case["requirements"])),
        limits=grounded.HARD_LIMIT.model_copy(update={"deadline_ms": 10_000}),
    )


async def observe(path, case, arm):
    request = request_for(case, arm)
    started = monotonic()
    queries, wire_items = [], {}
    sent = 0
    revoked = False
    raw_query = RetrievalService.query
    raw_send = FakeLLMClient.stream_events

    async def query(service, request, **kwargs):
        nonlocal revoked
        queries.append(str(request.idempotency_key))
        result = await raw_query(service, request, **kwargs)
        if case["fault"] == "revoked" and not case["held_out"]:
            revoked = True
        return result

    async def send(client, messages, **kwargs):
        nonlocal sent, revoked
        sent += 1
        for item in grounded.wire_evidence(messages):
            wire_items[item.citation_id] = item
        async for event in raw_send(client, messages, **kwargs):
            yield event
            if case["fault"] == "revoked" and case["held_out"]:
                revoked = True

    pick_field = grounded.focused_field if arm == "grounded" else lambda plan, gaps: None
    with (
        patch.object(RetrievalService, "query", query),
        patch.object(FakeLLMClient, "stream_events", send),
        patch.object(grounded, "focused_field", pick_field),
    ):
        if arm == "direct":
            # Source-free canonical continuation under the same overall envelope.
            # Its empty structured response abstains without an authorized citation.
            with synthetic_service(Fixture(answer='{"values":[]}')) as service:
                run_id = service.submit(DirectRequest(
                    schema_version="reasoning-run-request-v1", original_key=request.original_key,
                    task=DirectTask(kind="simple", requirements=(Requirement(operation="add", left=0, right=0),)),
                    strategy="direct", limits=DIRECT_LIMIT.model_copy(update={"deadline_ms": request.limits.deadline_ms}),
                ))
                progress, claims = await service.execute(run_id)
                replay = await service.execute(run_id)
            attempt = progress.attempts[0].resources
            assert not claims and sent == 1 and replay == (progress, ())
            return {"claims": (), "wire_items": {}, "metrics": {
                "outcome": "unavailable", "reason": "no_authorized_evidence",
                "retrieval_attempts": 0, "model_attempts": sent,
                "verifier_attempts": sum(a.resources.verifier_calls or 0 for a in progress.attempts),
                "reserved_operations": len(progress.attempts), "unknown_attempts": 0,
                "count_calls": attempt.count_calls, "count_input_bytes": attempt.observed_count_input_bytes,
                "reserved_count_input_bytes": attempt.reserved_count_input_bytes,
                "quote_bytes": 0, "retrieval_token_bound": 0,
                "fake_input_bytes": attempt.input_bytes, "fake_output_bytes": attempt.output_bytes,
                "reserved_fake_input_bytes": attempt.reserved_input_bytes,
                "reserved_fake_output_bytes": attempt.reserved_output_bytes, "provider_cost_usd": None,
                "safe": not queries and not wire_items,
            }}, round((monotonic() - started) * 1000)
        with fixture_service(
            path, case["subject"], case["sources"], fixture_rights=lambda: not revoked,
        ) as service:
            try:
                run_id = service.submit(request)
            except (Stop, WorkflowDenied) as error:
                return {"claims": (), "wire_items": {}, "metrics": {
                    "outcome": "denied", "reason": str(error),
                    "retrieval_attempts": len(queries), "model_attempts": sent,
                    "verifier_attempts": 0, "reserved_operations": 0, "unknown_attempts": 0,
                    "count_calls": 0, "count_input_bytes": 0, "reserved_count_input_bytes": 0,
                    "quote_bytes": 0, "retrieval_token_bound": 0, "fake_input_bytes": 0, "fake_output_bytes": 0,
                    "reserved_fake_input_bytes": 0, "reserved_fake_output_bytes": 0, "provider_cost_usd": None,
                    "safe": not queries and not sent,
                }}, round((monotonic() - started) * 1000)

            # Capture the original draft in the closure before installing the spoof.
            original = grounded.draft_from_messages

            def adversarial_draft(messages):
                proposed = grounded.Candidate.model_validate_json(original(messages))
                a, b = proposed.claims
                return grounded.Candidate(claims=(
                    a.model_copy(update={"citation_id": "f" * 64}),
                    b.model_copy(update={"citation_id": a.citation_id}),
                )).model_dump_json()

            if case["fault"] == "spoof":
                with patch.object(grounded, "draft_from_messages", adversarial_draft):
                    progress, claims = await service.execute(run_id)
            else:
                progress, claims = await service.execute(run_id)
            counts = len(queries), sent
            replay = await service.execute(run_id)
            with service.store.locked(service.scope_digest(), run_id) as row:
                redacted = row.spec is None and all(
                    marker not in json.dumps(row.record)
                    for marker in ("CANARY_DO_NOT_RETAIN", "FACT ", '"claims": [', '"quote"', '"subject"')
                )
    attempts = progress.attempts
    resources = [a.resources for a in attempts]
    synthesis = next((a.resources for a in attempts if a.step == "synthesis"), None)
    reads = [a for a in attempts if a.step in {"initial", "focused"}]
    observed_read_keys = {
        str(a.operation_binding.child_key) for a in reads if a.resources.observed_calls != 0
    }
    known = sum(a.resources.observed_calls == 1 for a in reads)
    unknown = sum(a.resources.observed_calls is None for a in reads)
    limits = request.limits
    quote_bytes = sum(r.quote_bytes or 0 for r in resources)
    token_bound = sum(r.retrieval_token_bound or 0 for r in resources)
    count_calls = sum(r.count_calls for r in resources)
    check_calls = sum(a.step == "check" and a.resources.observed_calls != 0 for a in attempts)
    reserved_counts = sum(r.reserved_count_input_bytes for r in resources)
    safe = (
        replay == (progress, ()) and counts == (len(queries), sent) and redacted
        and len(queries) == len(set(queries)) and set(queries) <= observed_read_keys
        and known <= len(queries) <= known + unknown and len(queries) <= limits.retrieval_calls
        and sent <= limits.model_calls and check_calls <= limits.verifier_calls
        and (not sent or (synthesis is not None and synthesis.observed_calls != 0))
        and len(attempts) <= 4 and sum(len(a.evidence) for a in reads) <= limits.evidence_items
        and quote_bytes <= limits.quote_bytes and token_bound <= limits.retrieval_token_bound
        and count_calls <= limits.count_calls and reserved_counts <= limits.count_input_bytes
        and (synthesis is None or (synthesis.input_bytes or 0) <= limits.input_bytes)
        and (synthesis is None or (synthesis.output_bytes or 0) <= limits.output_bytes)
        and (not revoked or not claims)
        and all(r.provider_cost_usd is None for r in resources)
    )
    return {"claims": claims, "wire_items": wire_items, "metrics": {
        "outcome": progress.outcome, "reason": progress.reason,
        "retrieval_attempts": len(queries), "model_attempts": sent, "verifier_attempts": check_calls,
        "reserved_operations": len(attempts), "unknown_attempts": sum(r.observed_calls is None for r in resources),
        "count_calls": count_calls, "count_input_bytes": sum(r.observed_count_input_bytes for r in resources),
        "reserved_count_input_bytes": reserved_counts, "quote_bytes": quote_bytes,
        "retrieval_token_bound": token_bound,
        "fake_input_bytes": synthesis.input_bytes if sent else 0,
        "fake_output_bytes": synthesis.output_bytes if sent else 0,
        "reserved_fake_input_bytes": synthesis.reserved_input_bytes if synthesis else 0,
        "reserved_fake_output_bytes": synthesis.reserved_output_bytes if synthesis else 0,
        "provider_cost_usd": None, "safe": safe,
    }}, round((monotonic() - started) * 1000)


def score(case, expected, observation):
    """Objective independent oracle. It never participates in candidate execution."""
    claims, wire = observation["claims"], observation["wire_items"]
    values = expected["values"]
    valid = []
    for claim in claims:
        item = wire.get(claim.citation_id)
        if item is None or claim.slot >= len(case["requirements"]):
            valid.append(False)
            continue
        field = case["requirements"][claim.slot]
        source = next((
            source for index, source in enumerate(case["sources"])
            if item.source_id == f"fixture-{index}"
        ), {})
        valid.append(
            values.get(str(claim.slot)) == claim.value
            and source.get("facts", {}).get(field) == claim.value
            and not any(source.get(flag) for flag in ("stale", "expired", "foreign"))
        )
    unique = len({claim.slot for claim in claims}) == len(claims)
    safe = observation["metrics"]["safe"] and unique and all(valid)
    return safe and len(claims) == len(values) and expected["eligible"], safe


async def evaluate(*, holdout_only=False):
    manifest, cases, oracle = load()
    rows, timings = [], {arm: 0 for arm in ARMS}
    with TemporaryDirectory() as tmp:
        path = Path(tmp).resolve() / "installation.json"
        for case in cases:
            if holdout_only and not case["held_out"]:
                continue
            for arm in ARMS:
                observation, elapsed = await observe(path, case, arm)
                exact, safe = score(case, oracle[case["id"]], observation)
                rows.append({
                    "case_id": case["id"], "cohort": case["cohort"], "held_out": case["held_out"],
                    "eligible": oracle[case["id"]]["eligible"], "arm": arm,
                    **observation["metrics"], "safe": safe, "exact": exact,
                })
                timings[arm] += elapsed

    totals = {}
    for arm in ARMS:
        group = [row for row in rows if row["arm"] == arm]
        totals[arm] = {
            **{metric: sum(r[metric] or 0 for r in group) for metric in (
                "exact", "retrieval_attempts", "model_attempts", "verifier_attempts", "reserved_operations",
                "unknown_attempts", "count_calls", "count_input_bytes", "reserved_count_input_bytes",
                "quote_bytes", "retrieval_token_bound", "fake_input_bytes", "fake_output_bytes",
                "reserved_fake_input_bytes", "reserved_fake_output_bytes",
            )},
            "rows": len(group), "held_out_exact": sum(r["held_out"] and r["exact"] for r in group),
            "unknown_fake_byte_receipts": sum(r["fake_input_bytes"] is None for r in group),
            "provider_cost_usd": None,
            "outcomes": {state: sum(r["outcome"] == state for r in group)
                         for state in ("complete", "partial", "unavailable", "denied")},
        }
    eligible = sum(r["eligible"] and r["arm"] == "grounded" for r in rows)
    held_out = sum(r["held_out"] and r["arm"] == "grounded" for r in rows)
    eligible_holdout = sum(r["held_out"] and r["eligible"] and r["arm"] == "grounded" for r in rows)
    gain = totals["grounded"]["exact"] - totals["one_shot"]["exact"]
    holdout_gain = totals["grounded"]["held_out_exact"] - totals["one_shot"]["held_out_exact"]
    simple = [r for r in rows if r["cohort"] == "simple" and r["arm"] != "direct"]
    sufficient = {"simple", "join", "poison", "spoof"}
    no_extra_when_sufficient = all(
        row["retrieval_attempts"] == 1
        for row in rows if row["arm"] == "grounded" and row["cohort"] in sufficient
    )
    simple_extra = sum(r["retrieval_attempts"] for r in simple if r["arm"] == "grounded") - sum(
        r["retrieval_attempts"] for r in simple if r["arm"] == "one_shot"
    )
    vetoes = sum(not r["safe"] for r in rows)
    minimum = manifest["minimum_gain_percentage_points"]
    passed = (
        vetoes <= manifest["safety_veto_limit"] and gain * 100 >= eligible * minimum
        and holdout_gain * 100 >= eligible_holdout * minimum
        and simple_extra == manifest["required_simple_extra_queries"]
        and no_extra_when_sufficient and all(r["exact"] for r in simple)
    )
    return {
        "pairs": len(rows) // len(ARMS), "rows": len(rows), "held_out": held_out,
        "eligible": eligible, "eligible_holdout": eligible_holdout,
        "eligible_gain": gain, "eligible_holdout_gain": holdout_gain, "simple_extra_queries": simple_extra,
        "safety_vetoes": vetoes, "totals": totals, "elapsed_ms": timings,
        "semantic_sha256": grounded.digest(rows),
        "verdict": "OFFLINE_SIGNAL_ONLY" if passed else "BLOCKED",
    }, rows


def main():
    report, rows = asyncio.run(evaluate())
    print(json.dumps({"observations": rows}, sort_keys=True))
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verdict"] == "OFFLINE_SIGNAL_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
