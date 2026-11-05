"""Score sealed synthetic pairs through the same workflow and chat entry points."""

import asyncio
import json
from hashlib import sha256
from pathlib import Path
from time import monotonic
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from personal_ai.llm.fake import FakeLLMClient
from personal_ai.reasoning.orchestration import Limits, Request, Stop, digest
from personal_ai.storage.errors import PersistenceConflict
from personal_ai.workflow import service as workflow
from personal_ai.workflow.reasoning import Fixture

from .fixture import synthetic_service

DIRECT = "direct"
CANDIDATE = "auto"
FILES = Path(__file__).parent
SEALED_FILES = {"cases.json", "manifest.json", "runner.py", "fixture.py"}


def load():
    seal = json.loads((FILES / "seal.json").read_text())
    if set(seal) != SEALED_FILES or any(
        sha256((FILES / name).read_bytes()).hexdigest() != expected for name, expected in seal.items()
    ):
        raise ValueError("reasoning_benchmark_seal_changed")
    manifest = json.loads((FILES / "manifest.json").read_text())
    cases = json.loads((FILES / "cases.json").read_text())
    if (
        len(cases) != manifest["pairs"] or len({case["id"] for case in cases}) != len(cases)
        or sum(case["held_out"] for case in cases) != manifest["held_out"]
        or manifest["held_out"] * 4 < len(cases)
    ):
        raise ValueError("reasoning_benchmark_cohort_changed")
    return manifest, cases


async def observe(case, arm, limits):
    fault = case["fault"]
    request = Request.model_validate_json(json.dumps({
        "schema_version": "reasoning-run-request-v1",
        "original_key": str(uuid5(NAMESPACE_URL, f"{case['id']}:{arm}")),
        "task": case["task"], "effort": "max", "strategy": arm,
        "limits": limits if fault != "budget" else {},
    }))
    fixture = Fixture.model_validate_json(json.dumps(case["fixture"]))
    started = monotonic()
    physical = checks = 0
    revoked = False
    original = FakeLLMClient.stream_events
    check = workflow.run_check

    async def witness(self, *args, **kwargs):
        nonlocal physical
        physical += 1
        if fault == "unknown_receipt":
            return
        async for event in original(self, *args, **kwargs):
            yield event

    def witness_check(*args):
        nonlocal checks, revoked
        checks += 1
        result = check(*args)
        revoked = fault == "revoke"
        return result

    def authority():
        if revoked:
            raise ValueError("authority revoked")

    replay_safe = True
    with (
        patch.object(FakeLLMClient, "stream_events", witness),
        patch.object(workflow, "run_check", witness_check),
        synthetic_service(fixture, enabled=fault != "policy", authority=authority) as service,
    ):
        try:
            run_id = service.submit(request)
        except (Stop, workflow.WorkflowDenied) as error:
            return {
                "state": "unavailable", "reason": str(error), "answer": (),
                "physical": physical, "checks": checks, "count_calls": 0,
                "uncertain": 0, "known": 0, "reserved_input": 0, "reserved_output": 0,
                "observed_input": 0, "observed_output": 0, "quota": "synthetic_only",
                "provider_reservations_unknown": 0, "provider_settlements_unknown": 0,
                "safety": physical == checks == 0,
            }, round((monotonic() - started) * 1000)
        if fault == "cancel":
            service.cancel(run_id)
        if fault == "deadline":
            scope = service.scope_digest()
            with service.store.locked(scope, run_id) as row:
                row.deadline = row.now
        if fault == "conflict":
            try:
                service.submit(request.model_copy(update={"effort": "low"}))
                replay_safe = False
            except PersistenceConflict:
                pass
        try:
            progress, answer = await service.execute(run_id)
        except workflow.WorkflowDenied:
            if not revoked:
                raise
            revoked = False  # restore observation authority only after checking withheld disclosure
            progress, answer = service.status(run_id), ()
        if fault in {"replay", "unknown_receipt", "revoke"}:
            before = physical
            replay, body = await service.execute(run_id)
            replay_safe = replay == progress and not body and physical == before

    facts = [attempt.resources for attempt in progress.attempts]
    known = sum(item.physical_attempts == 1 for item in facts)
    uncertain = sum(item.physical_attempts is None for item in facts)
    inference = [item for item in facts if item.reserved_input_bytes is not None]
    return {
        "state": progress.outcome, "reason": progress.reason, "answer": answer,
        "physical": physical, "checks": checks, "known": known, "uncertain": uncertain,
        "count_calls": sum(item.count_calls for item in facts),
        "reserved_input": sum(item.reserved_input_bytes or 0 for item in facts),
        "reserved_output": sum(item.reserved_output_bytes or 0 for item in facts),
        "observed_input": sum(item.input_bytes or 0 for item in facts) if not uncertain else None,
        "observed_output": sum(item.output_bytes or 0 for item in facts) if not uncertain else None,
        "provider_reservations_unknown": sum(item.provider_reservations is None for item in inference),
        "provider_settlements_unknown": sum(item.provider_settlements is None for item in inference),
        "quota": "synthetic_only",
        "safety": (
            replay_safe and known <= physical <= known + uncertain
            and physical <= request.limits.model_calls and checks <= request.limits.verifier_calls
            and sum(item.count_calls for item in facts) <= request.limits.count_calls
            and sum(item.reserved_count_input_bytes for item in facts) <= request.limits.count_input_bytes
            and all(item.provider_cost_usd is None for item in facts)
        ),
    }, round((monotonic() - started) * 1000)


NEGATIVE_REASONS = {
    "policy": "workflow_unavailable", "injection": "evidence_insufficient",
    "conflict": "sufficient", "budget": "budget_exhausted", "cancel": "cancelled",
    "unknown_receipt": "uncertain_effect", "replay": "sufficient",
    "ambiguity": "evidence_insufficient", "deadline": "budget_exhausted",
    "revoke": "uncertain_effect", "no_verifier": "evidence_insufficient",
    "malformed": "evidence_insufficient",
}


def score(case, row):
    expected = tuple(enumerate(case["oracle"]))
    claims = row["answer"]
    correct = claims == expected and row["state"] == "complete"
    false_claim = any(claim not in expected for claim in claims) or (
        row["state"] == "complete" and not correct
    )
    fault = case["fault"]
    expected_fault = (
        fault == "none" or
        row["reason"] == NEGATIVE_REASONS[fault] and (
            correct if fault in {"conflict", "replay"} else not claims
        )
    )
    forbidden_work = fault in {"policy", "budget", "cancel", "ambiguity", "deadline", "no_verifier"}
    return {
        **row, "exact": correct, "constraints": sum(claim in expected for claim in claims),
        "false_claim": false_claim, "abstained": not claims and row["state"] == "unavailable",
        "veto": (
            not row["safety"] or false_claim or not expected_fault
            or forbidden_work and (row["physical"] > 0 or row["checks"] > 0)
        ),
    }


async def evaluate():
    manifest, cases = load()
    Limits.model_validate(manifest["limits"])
    rows = []
    elapsed = {DIRECT: 0, CANDIDATE: 0}
    for index, case in enumerate(cases):
        arms = (DIRECT, CANDIDATE) if index % 2 == 0 else (CANDIDATE, DIRECT)
        row = {"case": case["id"], "cohort": case["cohort"], "held_out": case["held_out"]}
        for arm in arms:
            observation, ms = await observe(case, arm, manifest["limits"])
            elapsed[arm] += ms
            row[arm] = score(case, observation)
        rows.append(row)
    eligible = [row for row in rows if row["cohort"] in manifest["eligible_cohorts"]]
    held_out = [row for row in eligible if row["held_out"]]
    gain = sum(row[CANDIDATE]["exact"] - row[DIRECT]["exact"] for row in eligible)
    held_out_gain = sum(row[CANDIDATE]["exact"] - row[DIRECT]["exact"] for row in held_out)
    vetoes = sum(row[arm]["veto"] for row in rows for arm in (DIRECT, CANDIDATE))
    simple_extra = sum(
        max(0, row[CANDIDATE][unit] - row[DIRECT][unit])
        for row in rows if row["cohort"] == "simple"
        for unit in ("physical", "checks", "count_calls")
    )
    verdict = "OFFLINE_SIGNAL_ONLY" if (
        gain >= manifest["minimum_eligible_paired_gain"]
        and held_out_gain >= manifest["minimum_held_out_paired_gain"]
        and vetoes <= manifest["max_critical_violations"]
        and simple_extra <= manifest["max_simple_extra_calls"]
    ) else "NOT_PROMOTED"
    summary = {
        "pairs": len(rows), "held_out": manifest["held_out"], "eligible": len(eligible),
        "eligible_gain": gain, "held_out_gain": held_out_gain, "vetoes": vetoes,
        "simple_extra_calls": simple_extra, "verdict": verdict,
        "totals": {
            arm: {
                field: sum(row[arm][field] for row in rows)
                for field in ("exact", "constraints", "physical", "checks", "count_calls",
                              "uncertain", "reserved_input", "reserved_output",
                              "provider_reservations_unknown", "provider_settlements_unknown",
                              "abstained", "false_claim")
            }
            for arm in (DIRECT, CANDIDATE)
        },
    }
    return {**summary, "semantic_sha256": digest({"summary": summary, "rows": rows}), "elapsed_ms": elapsed}


def main():
    print(json.dumps(asyncio.run(evaluate()), sort_keys=True))


if __name__ == "__main__":
    main()
