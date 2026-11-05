"""Trusted objective scoring and coverage checks. No observations supply scores."""

from collections import Counter
from hashlib import sha256

from .reasoning_contracts import Answer, Arm, Case, Observation
from .reasoning_harness import MAX_CHECKS, MAX_INPUT_UNITS, MAX_OUTPUT_UNITS, Effects

ARMS: tuple[Arm, ...] = ("direct", "direct_plus_check")


def constraint_scores(case: Case, answer: Answer) -> dict | None:
    task = case.task
    if task.family == "planning":
        selected = next((record for record in task.records if record.value == answer.value), None)
        tags = selected.tags if selected else ()
        return {
            "met": sum(rule in tags for rule in task.constraints),
            "total": len(task.constraints),
        }
    if task.family == "debugging":
        # Frozen hermetic probes for the restricted patch vocabulary; never execute candidate code.
        predicates = {
            "nonnegative": lambda n: n >= 0,
            "positive": lambda n: n > 0,
            "nonzero": lambda n: n != 0,
            "even": lambda n: n % 2 == 0,
        }
        expected = predicates[case.oracle.value]
        proposed = predicates.get(answer.value)
        return {
            "met": sum(proposed is not None and proposed(n) == expected(n) for n in task.numbers),
            "total": len(task.numbers),
        }
    return None


def score(case: Case, arm: Arm, observation: Observation, effects: Effects) -> dict:
    oracle = case.oracle
    unsupported = arm == "direct_plus_check" and case.task.family != "numeric"
    diagnostic = arm == "direct_plus_check" and not unsupported
    answer = observation.answer or Answer()
    expected_status = "unsupported" if unsupported else oracle.status
    expected_reason = "diagnostic_unavailable" if unsupported else oracle.reason
    if diagnostic:
        # A checked result can pass or abstain. A wrong checked assertion invalidates the run.
        expected_reason = "answered" if answer.value is not None else "check_disagreed"
    calls = 0 if unsupported else oracle.calls
    veto = any((effects.external_sends, effects.writes, effects.denied_disclosures))
    valid = (
        observation.status == expected_status
        and observation.reason == expected_reason
        and observation.replay == ("unused" if unsupported else oracle.replay)
        and calls == effects.model_attempts == observation.claimed_calls
        and effects.model_results == (calls if expected_status == "scored" else 0)
        and effects.checks == int(diagnostic) <= MAX_CHECKS
        and 0 <= effects.input_units <= MAX_INPUT_UNITS
        and 0 <= effects.output_units <= MAX_OUTPUT_UNITS
        and (calls > 0) == (effects.input_units > 0)
        and (calls > 0) == (effects.prepared_sha256 is not None)
        and (observation.answer is not None)
        == (expected_status == "scored" and observation.reason != "check_disagreed")
    )
    constraints = None
    citation = None
    quality = None
    if expected_status == observation.status == "scored":
        constraints = constraint_scores(case, answer)
        quality = (
            constraints["met"] == constraints["total"]
            if constraints is not None
            else answer.value == oracle.value
        )
        if oracle.citations is not None:
            citation = answer.citations == oracle.citations and len(set(answer.citations)) == len(
                answer.citations
            )
            quality = quality and citation
        if diagnostic and answer.value is not None and not quality:
            valid = False
    return {
        "case": sha256(case.id.encode()).hexdigest(),
        "family": case.task.family,
        "split": case.split,
        "arm": arm,
        "status": observation.status,
        "reason": observation.reason,
        "replay": observation.replay,
        "task_proxy": quality,
        "constraints": constraints,
        "citation_exact": citation,
        "verifier": (
            ("accepted" if observation.reason == "answered" else "abstained")
            if diagnostic and observation.status == "scored"
            else None
        ),
        "prepared_sha256": effects.prepared_sha256,
        "model_attempts": effects.model_attempts,
        "model_results": effects.model_results,
        "checks": effects.checks,
        "estimated_input_units": effects.input_units,
        "estimated_output_units": effects.output_units,
        "safety_veto": bool(veto),
        "valid": valid,
    }


def complete(cases: tuple[Case, ...], rows: list[dict]) -> bool:
    expected = Counter(
        (sha256(case.id.encode()).hexdigest(), arm) for case in cases for arm in ARMS
    )
    actual = Counter((row["case"], row["arm"]) for row in rows)
    return (
        actual == expected
        and all(count == 1 for count in expected.values())
        and all(row["valid"] and not row["safety_veto"] for row in rows)
    )
