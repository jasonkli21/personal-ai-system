import subprocess
import sys
from pathlib import Path

from personal_ai.evaluation.reasoning_v2 import reasoning_driver, reasoning_seal
from personal_ai.evaluation.reasoning_v2.reasoning_baseline import evaluate
from personal_ai.evaluation.reasoning_v2.reasoning_contracts import Answer, Task
from personal_ai.evaluation.reasoning_v2.reasoning_harness import Effects, run_arm
from personal_ai.evaluation.reasoning_v2.reasoning_scoring import score

ROOT = Path(__file__).resolve().parents[2]


def test_foreign_prepared_source_is_vetoed_even_with_correct_answer(monkeypatch):
    case = next(c for c in reasoning_seal.load()[0].cases if c.id == "scope_3")
    observed = []

    def responder(task):
        observed.extend(record.key for record in task.records)
        return Answer(value="cedar", citations=("s1",))

    monkeypatch.setattr(reasoning_driver, "direct", responder)
    effects = Effects()
    observation = run_arm(
        case.task, case.scenario, case.foreign_slots, "direct", effects,
        candidate_input_override=case.task,
    )
    row = score(case, "direct", observation, effects)
    assert observation.answer is not None and observation.answer.value == "cedar"
    assert set(case.foreign_slots).intersection(observed)
    assert effects.source_violations > 0
    assert row["safety_veto"] and not row["valid"]
    assert "SYNTHETIC_PRIVATE_CANARY" not in str(row)


def test_denial_without_source_operation_is_not_policy_evidence():
    case = next(c for c in reasoning_seal.load()[0].cases if c.scenario == "wrong_app")
    empty = case.model_copy(update={"task": Task(family="scope", operation="location")})
    effects = Effects()
    observation = run_arm(empty.task, empty.scenario, empty.foreign_slots, "direct", effects)
    assert not score(empty, "direct", observation, effects)["valid"]


def test_witnessed_denial_requires_matching_gate_receipt():
    corpus, _ = reasoning_seal.load()
    cases = [c for c in corpus.cases if c.scenario in {"wrong_app", "revoke_at_send", "stale_revision"}]
    assert {c.scenario for c in cases} == {"wrong_app", "revoke_at_send", "stale_revision"}
    for case in cases:
        effects = Effects()
        observation = run_arm(case.task, case.scenario, case.foreign_slots, "direct", effects)
        assert score(case, "direct", observation, effects)["valid"]
        effects.gate_observation = None
        assert not score(case, "direct", observation, effects)["valid"]


def test_always_rejecting_and_accepting_checkers_fail_integrity(monkeypatch):
    monkeypatch.setattr(reasoning_driver, "verify", lambda *_: False)
    rejected, _ = evaluate()
    assert not rejected["coverage_complete"]
    monkeypatch.setattr(reasoning_driver, "verify", lambda *_: True)
    accepted, _ = evaluate()
    assert not accepted["coverage_complete"]


def test_v2_seal_and_v1_fixture_are_distinct():
    corpus, _ = reasoning_seal.load()
    assert corpus.version == "reasoning-offline-v2"
    assert (ROOT / "backend/src/personal_ai/evaluation/fixtures/reasoning/cases-v1.json").exists()


def test_provenance_rejects_forged_checkout_ids():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
    for supplied_commit, supplied_tree in (("1" * 40, tree), (commit, "2" * 40)):
        command = [
            sys.executable, "-B", "-m", "personal_ai.evaluation.reasoning_v2.reasoning_baseline",
            "--commit", supplied_commit, "--tree", supplied_tree, "--dirty", "no",
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
        assert result.returncode != 0
        assert "provenance_mismatch" in result.stderr


def test_provenance_rejects_dirty_state_spoof():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
    relevant_dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--", "backend/src/personal_ai/evaluation/reasoning_v2"],
        cwd=ROOT, text=True,
    ).strip())
    spoofed_dirty = "no" if relevant_dirty else "yes"
    command = [
        sys.executable, "-B", "-m", "personal_ai.evaluation.reasoning_v2.reasoning_baseline",
        "--commit", commit, "--tree", tree, "--dirty", spoofed_dirty,
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode != 0
    assert "dirty_state_mismatch" in result.stderr
