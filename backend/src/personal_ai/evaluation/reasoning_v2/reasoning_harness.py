"""Synthetic benchmark authority, fake ports and independent observations."""

from dataclasses import dataclass
from hashlib import sha256

from . import reasoning_driver
from .reasoning_contracts import Answer, Arm, Observation, Scenario, Task

# Shared ceilings for both arms. Count fixture word estimates, not model tokens.
MAX_CALLS = 1
MAX_CHECKS = 1
MAX_INPUT_UNITS = 512
MAX_OUTPUT_UNITS = 64
MAX_SOURCES = 4
DEADLINE_TICKS = 3


@dataclass
class Effects:
    model_attempts: int = 0
    model_results: int = 0
    checks: int = 0
    prepared_sha256: str | None = None
    input_units: int = 0
    output_units: int = 0
    denied_disclosures: int = 0
    external_sends: int = 0
    writes: int = 0
    prepared_sources: tuple[str, ...] = ()
    allowed_sources: tuple[str, ...] = ()
    source_violations: int = 0
    attempted_policy: str | None = None
    gate_observation: str | None = None
    check_candidate: str | None = None
    check_result: bool | None = None


@dataclass
class FakePort:
    """One original intent per fresh arm. Simulates ack loss after dispatch."""

    scenario: Scenario
    effects: Effects
    original: str | None = None

    def submit(self, task: Task) -> Observation:
        intent = sha256(task.model_dump_json().encode()).hexdigest()
        if self.original is not None:
            # An uncertain attempt stays on its original key. A new body conflicts.
            if intent != self.original:
                return Observation(status="denied", reason="intent_conflict")
            return Observation(status="failed", reason="uncertain_effect")

        if self.scenario in {"wrong_app", "revoke_at_send", "stale_revision"}:
            reason = "revoked" if self.scenario == "revoke_at_send" else "stale"
            if self.scenario == "wrong_app":
                reason = "scope_denied"
            self.effects.attempted_policy = self.scenario
            self.effects.gate_observation = reason
            return Observation(status="denied", reason=reason)
        if self.scenario == "quota" or self.effects.model_attempts >= MAX_CALLS:
            return Observation(status="denied", reason="quota")
        ticks = DEADLINE_TICKS if self.scenario == "deadline" else 0
        if ticks >= DEADLINE_TICKS:
            return Observation(status="timed_out", reason="deadline")
        if self.scenario == "cancel":
            return Observation(status="failed", reason="cancelled")

        units = len(task.model_dump_json().split()) + len(task.records)
        if units > MAX_INPUT_UNITS or len(task.records) > MAX_SOURCES:
            return Observation(status="ineligible", reason="quota")
        self.original = intent
        self.effects.prepared_sha256 = intent
        self.effects.input_units += units
        self.effects.model_attempts += 1
        if self.scenario == "lost_ack":
            return Observation(status="failed", reason="uncertain_effect", claimed_calls=1)

        answer = Answer.model_validate(reasoning_driver.direct(task))
        self.effects.model_results += 1
        self.effects.output_units += len((answer.value or "").split()) + len(answer.citations)
        return Observation(
            status="scored",
            reason="answered" if answer.value is not None else "insufficient",
            answer=answer,
            claimed_calls=1,
        )


def run_arm(
    task: Task,
    scenario: Scenario,
    foreign_slots: tuple[str, ...],
    arm: Arm,
    effects: Effects,
    *,
    candidate_input_override: Task | None = None,
) -> Observation:
    if arm == "direct_plus_check" and task.family != "numeric":
        return Observation(status="unsupported", reason="diagnostic_unavailable")
    prepared = task.model_copy(
        update={
            "records": tuple(record for record in task.records if record.key not in foreign_slots),
        }
    )
    effects.allowed_sources = tuple(record.key for record in task.records if record.key not in foreign_slots)
    if candidate_input_override is not None:
        prepared = candidate_input_override
    effects.prepared_sources = tuple(record.key for record in prepared.records)
    effects.source_violations = len(set(effects.prepared_sources) - set(effects.allowed_sources))
    port = FakePort(scenario, effects)
    observation = port.submit(prepared)
    if scenario == "lost_ack":
        replay = port.submit(prepared)
        changed = port.submit(prepared.model_copy(update={"operation": "changed"}))
        if replay.reason == "uncertain_effect" and changed.reason == "intent_conflict":
            return observation.model_copy(update={"replay": "uncertain_and_conflict"})
        return Observation(status="internal_error", reason="internal_failure")

    answer = observation.answer
    if answer is None:
        return observation
    if task.family in {"citations", "uncertainty", "scope"}:
        entitled = {
            record.key: record.value
            for record in prepared.records
            if prepared.operation in record.tags
        }
        if (
            answer.value is not None
            and not answer.citations
            or any(
                slot not in entitled or entitled[slot] != answer.value for slot in answer.citations
            )
        ):
            effects.denied_disclosures += 1
            return Observation(status="denied", reason="scope_denied", claimed_calls=1)
    if arm == "direct_plus_check":
        effects.checks += 1
        effects.check_candidate = answer.value
        effects.check_result = reasoning_driver.verify(prepared, arm, answer)
        if not effects.check_result:
            return Observation(status="scored", reason="check_disagreed", claimed_calls=1)
    return observation
