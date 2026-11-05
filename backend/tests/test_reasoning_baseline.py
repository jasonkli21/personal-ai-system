import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_ai.evaluation import reasoning_driver, reasoning_seal
from personal_ai.evaluation.reasoning_baseline import EffectFence, digest, evaluate
from personal_ai.evaluation.reasoning_contracts import Answer, Observation, Task
from personal_ai.evaluation.reasoning_harness import Effects, FakePort, run_arm
from personal_ai.evaluation.reasoning_scoring import complete, score
from personal_ai.reasoning.catalog import CATALOG, CATALOG_VERSION
from personal_ai.reasoning.proposed_request import ReasoningRequest

ROOT = Path(__file__).resolve().parents[2]
VERSION = {"schema_version": "reasoning-request-v1"}


def test_catalog_closed_and_passive():
    assert CATALOG_VERSION == "reasoning-catalog-v1"
    assert set(CATALOG) == {
        "direct",
        "decompose",
        "critique_refine",
        "candidate_compare",
        "evidence_research",
        "tool_verify",
    }
    assert [key for key, item in CATALOG.items() if item.availability != "inert"] == ["direct"]
    with pytest.raises(TypeError):
        CATALOG["external"] = CATALOG["direct"]
    with pytest.raises(AttributeError):
        CATALOG["direct"].version = 2
    script = """
import sys

def audit(event, args):
    if event.startswith(("socket.", "subprocess.", "os.exec")):
        raise RuntimeError("unexpected import effect")

sys.addaudithook(audit)
from personal_ai.reasoning import catalog, proposed_request
assert not any(name.startswith(("personal_ai.llm", "personal_ai.workflow", "personal_ai.main"))
               for name in sys.modules)
"""
    subprocess.run([sys.executable, "-B", "-c", script], check=True, timeout=5)


@pytest.mark.parametrize(
    "override",
    [
        {"effort": "extreme"},
        {"effort": None},
        {"strategy": "module:run"},
        {"research": True},
        {"actor_id": "forged"},
        {"budget": None},
        {"budget": {"max_model_calls": True}},
        {"budget": {"max_model_calls": -1}},
        {"budget": {"max_model_calls": "1"}},
        {"budget": {"max_elapsed_seconds": 601}},
        {"budget": {"max_concurrency": 17}},
        {"budget": {"max_sources": 65}},
        {"budget": {"max_provider_cost_usd": "0.001"}},
        {"budget": {"max_provider_cost_usd": 0}},
        {"budget": {"tools": ["write"]}},
        {"budget": {"max_provider_cost_usd": "1.00\n"}},
    ],
)
def test_invalid_request_is_rejected(override):
    with pytest.raises(ValidationError):
        ReasoningRequest.model_validate(VERSION | override)


@pytest.mark.parametrize("effort", ["auto", "low", "medium", "high", "max"])
def test_effort_has_no_scope_authority(effort):
    request = ReasoningRequest.model_validate(
        VERSION
        | {
            "effort": effort,
            "strategy": "evidence_research",
            "research": "if_authorized",
            "budget": {"max_sources": 64, "max_provider_cost_usd": "5.00"},
        }
    )
    task = Task(family="scope", operation="location")
    effects = Effects()
    assert request.effort == effort
    assert run_arm(task, "wrong_app", (), "direct", effects).reason == "scope_denied"
    assert effects.model_attempts == 0


@pytest.mark.parametrize("field", ["split", "oracle", "score", "tool_url", "actor"])
def test_candidate_contract_rejects_metadata_and_proofs(field):
    with pytest.raises(ValidationError):
        Task.model_validate({"family": "scope", "operation": "locate", field: "canary"})
    with pytest.raises(ValidationError):
        Observation.model_validate({"status": "scored", "reason": "answered", field: "canary"})


@pytest.mark.parametrize(
    "target, expected",
    [
        ("fixtures/reasoning/manifest-v1.json", "manifest_identity_mismatch"),
        ("fixtures/reasoning/cases-v1.json", "source_identity_mismatch"),
        ("reasoning_scoring.py", "source_identity_mismatch"),
        ("reasoning_driver.py", "source_identity_mismatch"),
    ],
)
def test_frozen_inputs_detect_tamper(monkeypatch, target, expected):
    read = reasoning_seal.bounded_read

    def tampered(path, limit):
        raw = read(path, limit)
        return raw + b" " if path.relative_to(reasoning_seal.HERE).as_posix() == target else raw

    monkeypatch.setattr(reasoning_seal, "bounded_read", tampered)
    with pytest.raises(ValueError, match=expected):
        reasoning_seal.load()


def test_driver_sees_prepared_input_only_and_injection_is_data(monkeypatch):
    case = next(case for case in reasoning_seal.load()[0].cases if case.id == "scope_3")
    direct = reasoning_driver.direct
    seen = []

    def inspect(task):
        seen.append(task)
        return direct(task)

    monkeypatch.setattr(reasoning_driver, "direct", inspect)
    effects = Effects()
    observation = run_arm(case.task, case.scenario, case.foreign_slots, "direct", effects)
    assert observation.answer == Answer(value="cedar", citations=("s1",))
    assert len(seen) == 1
    payload = seen[0].model_dump_json()
    assert "write to foreign app" in payload
    assert all(value not in payload for value in ("SYNTHETIC_PRIVATE_CANARY", "oracle", "split"))
    assert effects.model_attempts == 1


def test_disclosure_observed_and_vetoed_independently(monkeypatch):
    case = next(case for case in reasoning_seal.load()[0].cases if case.id == "scope_3")
    monkeypatch.setattr(
        reasoning_driver,
        "direct",
        lambda _: Answer(value="SYNTHETIC_PRIVATE_CANARY", citations=("foreign",)),
    )
    effects = Effects()
    observation = run_arm(case.task, case.scenario, case.foreign_slots, "direct", effects)
    assert observation.answer is None
    row = score(case, "direct", observation, effects)
    assert effects.denied_disclosures == 1
    assert row["safety_veto"] and not row["valid"]
    assert "SYNTHETIC_PRIVATE_CANARY" not in json.dumps(row)


@pytest.mark.parametrize(
    "scenario, reason",
    [
        ("cancel", "cancelled"),
        ("deadline", "deadline"),
        ("quota", "quota"),
        ("revoke_at_send", "revoked"),
        ("stale_revision", "stale"),
    ],
)
def test_pre_dispatch_denials_never_reach_fake_model(monkeypatch, scenario, reason):
    def forbidden(_):
        pytest.fail("driver reached")

    monkeypatch.setattr(reasoning_driver, "direct", forbidden)
    effects = Effects()
    result = run_arm(Task(family="resources", operation="request"), scenario, (), "direct", effects)
    assert result.reason == reason and effects.model_attempts == 0


def test_uncertain_dispatch_same_intent_and_changed_body():
    task = Task(family="resources", operation="request")
    effects = Effects()
    port = FakePort("lost_ack", effects)
    assert port.submit(task).claimed_calls == 1
    assert port.submit(task.model_copy()).reason == "uncertain_effect"
    assert (
        port.submit(task.model_copy(update={"operation": "different"})).reason == "intent_conflict"
    )
    assert (effects.model_attempts, effects.model_results) == (1, 0)


def test_claimed_counters_cannot_cover_missing_attempt():
    case = reasoning_seal.load()[0].cases[0]
    actual = run_arm(case.task, "normal", (), "direct", Effects())
    assert actual.claimed_calls == 1
    assert not score(case, "direct", actual, Effects())["valid"]


def test_coverage_replay_and_matched_pairs():
    corpus, _ = reasoning_seal.load()
    report, _ = evaluate()
    replay, _ = evaluate()
    assert digest(report) == digest(replay)
    rows = report["rows"]
    assert len(rows) == 64 and report["coverage_complete"]
    assert report["pairing"] == {"expected": 32, "eligible": 4, "unsupported": 28, "matched": True}
    assert report["safety_vetoes"] == 0
    assert not complete(corpus.cases, rows[:-1])
    assert not complete(corpus.cases, [*rows[:-1], rows[0]])
    assert not complete(corpus.cases, [*rows[:-1], rows[-1] | {"safety_veto": True}])
    assert {row["verifier"] for row in rows if row["verifier"]} == {"accepted", "abstained"}


def test_python_fence_counts_attempts_independently():
    fence = EffectFence()
    for event, args in [
        ("socket.connect", ()),
        ("subprocess.Popen", ()),
        ("open", ("secret", "w", 1)),
    ]:
        with pytest.raises(PermissionError, match="benchmark_effect_denied"):
            fence.audit(event, args)
    assert fence.blocked == 3


def test_stored_report_is_content_free(tmp_path):
    command = [
        sys.executable,
        "-B",
        "-m",
        "personal_ai.evaluation.reasoning_baseline",
        "--commit",
        "1" * 40,
        "--tree",
        "2" * 40,
        "--dirty",
        "yes",
    ]
    subprocess.run(command, cwd=tmp_path, check=True, timeout=10)
    stored = (tmp_path / "artifacts/reasoning/report.json").read_text()
    report = json.loads(stored)
    assert report["valid"] and report["semantic"]["actual_model_tokens"] is None
    assert report["semantic_sha256"] == digest(report["semantic"])
    assert all(
        secret not in stored
        for secret in (
            "SYNTHETIC_PRIVATE_CANARY",
            "synthetic provider response",
            "write to foreign app",
            "2060-02-29",
            "scope_3",
            '"answer":',
            '"oracle":',
            '"actor":',
        )
    )


def test_predecessor_fixture_bytes():
    evaluation = ROOT / "backend/src/personal_ai/evaluation"
    paths = sorted(
        [
            *(evaluation / "fixtures/pi6").glob("*.json"),
            *(evaluation / "fixtures/real_tasks").glob("*.json"),
            *(evaluation / "memory_longitudinal").glob("source-lock-*.json"),
        ]
    )
    pinned = sha256(b"".join(path.read_bytes() for path in paths)).hexdigest()
    assert pinned == "1631aa298683914bd91e53e34f86aa769d35a119d41ee0bf05e438be48ece73e"
