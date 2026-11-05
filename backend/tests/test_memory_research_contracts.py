"""Untrusted portable research input, custody and bounded denominator contracts."""

import json
from hashlib import sha256

import pytest
from pydantic import ValidationError

from personal_ai.evaluation.memory_longitudinal.dataset import (
    ChallengeSubmission,
    inspect_challenge,
    load_sources,
    parse_sources,
    source_bytes,
)
from personal_ai.memory.research.experiments.artifacts import (
    PACKAGE_MEMBERS,
    checked_json,
    immutable_write,
    validate_grid,
    verify_package,
    verify_sources,
)
from personal_ai.memory.research.experiments.contracts import (
    AttemptReceipt,
    ResourceCounters,
    SourceHash,
    canonical,
    digest,
)


def receipt(**updates):
    data = {
        "run_sha256": "0" * 64,
        "task_id": "task-one",
        "arm": "lexical",
        "repetition": 0,
        "seed": 719,
        "time_step": 2,
        "session": "session-b",
        "original_intent": "1" * 64,
        "status": "complete",
        "reason": "observed",
        "source_epoch": 1,
        "permission_epoch": 1,
    }
    return AttemptReceipt(**(data | updates))


@pytest.mark.parametrize(
    "updates",
    [
        {"version": "unknown"},
        {"extra": "secret"},
        {"source_epoch": 0},
        {"run_sha256": "invalid"},
        {"time_step": 100},
        {"arm": "promote-live"},
        {"observed_action": "self-attested"},
        {"consumed": ("source-one",)},
        {"selected": ("source-one",), "packed": ("source-two",)},
        {"status": "denied", "terminal_state_sha256": "2" * 64},
        {"reason": "private text with spaces"},
        {"session": "x" * 101},
    ],
)
def test_attempt_rejects_unsupported_schema_bounds_and_false_success(updates):
    with pytest.raises(ValidationError):
        receipt(**updates)


@pytest.mark.parametrize(
    "values",
    [
        {"provider_calls": 1},
        {"actual_tokens": 12},
        {"billed_cost": 0},
        {"fixture_token_estimate": 4097},
        {"index_bytes": 262145},
        {"elapsed_ms": float("nan")},
        {"elapsed_ms": float("inf")},
        {"tool_calls": 5},
    ],
)
def test_resources_never_invent_model_observations_or_exceed_bounds(values):
    with pytest.raises(ValidationError):
        ResourceCounters(**values)


def test_canonical_identity_ignores_key_order_and_rejects_nonfinite_values():
    assert canonical({"b": 1, "a": 2}) == canonical({"a": 2, "b": 1})
    assert digest({"b": 1}) != digest({"b": 2})
    with pytest.raises(ValueError):
        canonical({"b": float("nan")})


def test_local_artifact_creation_is_immutable_and_content_checked(tmp_path):
    path = tmp_path / "receipt.json"
    expected = immutable_write(path, b'{"value":1}')
    assert expected == immutable_write(path, b'{"value":1}')
    with pytest.raises(ValueError, match="conflict"):
        immutable_write(path, b'{"value":2}')
    path.write_text('{"value":1,"value":2}')
    with pytest.raises(ValueError, match="duplicate_json_key"):
        checked_json(path)
    with pytest.raises(ValueError, match="capacity"):
        immutable_write(tmp_path / "large", b" " * 16777217)


def test_package_does_not_read_untrusted_paths_or_accept_tampered_members(tmp_path):
    immutable_write(tmp_path / "run.json", b"{}")
    index = {"version": "memory-replay-package-v1", "files": {"../secret": "0" * 64}}
    (tmp_path / "package.json").write_bytes(canonical(index))
    with pytest.raises(ValueError, match="package_capacity"):
        verify_package(tmp_path)
    index["files"] = {"run.json": "0" * 64}
    (tmp_path / "package.json").write_bytes(canonical(index))
    with pytest.raises(ValueError, match="package_capacity"):
        verify_package(tmp_path)


def test_package_requires_exact_indexed_members_and_rejects_unindexed_files(tmp_path):
    members = {name: name.encode() for name in PACKAGE_MEMBERS}
    for name, payload in members.items():
        immutable_write(tmp_path / name, payload)
    inventory = {name: sha256(payload).hexdigest() for name, payload in members.items()}
    index_path = tmp_path / "package.json"
    index_path.write_bytes(
        canonical({"version": "memory-replay-package-v1", "files": inventory})
    )
    assert set(verify_package(tmp_path)["files"]) == PACKAGE_MEMBERS

    omitted = dict(inventory)
    omitted.pop("faults.json")
    index_path.write_bytes(
        canonical({"version": "memory-replay-package-v1", "files": omitted})
    )
    with pytest.raises(ValueError, match="package_capacity"):
        verify_package(tmp_path)

    index_path.write_bytes(
        canonical({"version": "memory-replay-package-v1", "files": inventory})
    )
    (tmp_path / "unindexed.json").write_text("{}")
    with pytest.raises(ValueError, match="package_inventory_mismatch"):
        verify_package(tmp_path)


@pytest.mark.parametrize("path", ["/etc/secret", "../../secret", "source/../secret", "x\nsecret"])
def test_source_references_cannot_escape_repository(path):
    with pytest.raises(ValidationError):
        SourceHash(path=path, sha256="0" * 64)


def test_challenge_import_validates_bytes_and_cannot_self_certify_independence():
    payload = source_bytes()
    manifest = {
        "source_sha256": sha256(payload).hexdigest(),
        "scorer_sha256": "0" * 64,
        "custodian": "external-custodian",
        "parent_dataset": "1" * 64,
    }
    assert len(inspect_challenge(manifest, payload).tasks) == 48
    with pytest.raises(ValidationError):
        ChallengeSubmission(**(manifest | {"independent_acceptance": True}))
    with pytest.raises(ValueError, match="identity"):
        inspect_challenge(manifest, payload + b" ")


def test_source_schema_and_hidden_gold_injection_are_rejected_even_with_fresh_hash():
    data = json.loads(source_bytes())
    data["tasks"][0]["expected_action"] = "leak-canary"
    payload = canonical(data)
    with pytest.raises(ValidationError):
        parse_sources(payload, sha256(payload).hexdigest())


def test_all_cases_have_separate_sessions_and_immutable_task_manifests():
    corpus = load_sources()
    assert len(corpus.tasks) == 48
    assert all(len(t.steps) >= 3 and len({s.session for s in t.steps}) >= 2 for t in corpus.tasks)
    assert (
        sum(
            any(s.events for s in t.steps) or len(t.records) > 1 or t.fault is not None
            for t in corpus.tasks
        )
        >= 16
    )
    for task in corpus.tasks:
        manifest = task.manifest()
        assert (
            not {"expected_action", "expected_status", "family", "split"}
            & type(manifest).model_fields.keys()
        )
        assert digest(manifest) == digest(task.manifest())


def test_complete_grid_requires_every_step_and_repetition_without_duplicates(research_run):
    run, rows, _, _ = research_run
    tasks = load_sources().tasks
    assert validate_grid(run, rows, tasks) == rows
    with pytest.raises(ValueError, match="grid_incomplete"):
        validate_grid(run, rows[:-1], tasks)
    with pytest.raises(ValueError, match="duplicate"):
        validate_grid(run, (*rows, rows[0]), tasks)
    changed = rows[0].model_copy(update={"run_sha256": "0" * 64})
    with pytest.raises(ValueError, match="binding"):
        validate_grid(run, (changed, *rows[1:]), tasks)


def test_changed_source_is_not_accepted_as_current_evidence(research_run, tmp_path):
    run, _, _, _ = research_run
    with pytest.raises((ValueError, FileNotFoundError)):
        verify_sources(run, tmp_path)


pytest_plugins = ("tests.memory_research_support",)


def test_twelve_challenge_slots_can_be_validated_without_installing_source_authority():
    data = json.loads(source_bytes())
    data["tasks"] = data["tasks"][-12:]
    payload = canonical(data)
    submission = {
        "source_sha256": sha256(payload).hexdigest(),
        "scorer_sha256": "0" * 64,
        "custodian": "external-author",
        "parent_dataset": "1" * 64,
    }
    assert len(inspect_challenge(submission, payload).tasks) == 12
    with pytest.raises(ValueError, match="duplicate_json_key"):
        payload = b'{"version":"x","version":"y","tasks":[]}'
        inspect_challenge(submission | {"source_sha256": sha256(payload).hexdigest()}, payload)


def test_protocol_only_model_metadata_cannot_be_dispatched_by_research_run(research_run):
    from personal_ai.memory.research.experiments.contracts import ModelManifest, RunManifest

    protocol = ModelManifest(
        mode="protocol_only",
        provider="local-model",
        model="unmeasured",
        endpoint="http://127.0.0.1:8000",
        capability="not_observed",
        cost_profile="not_observed",
        seed=1,
        configuration_sha256="0" * 64,
    )
    run, _, _, _ = research_run
    with pytest.raises(ValidationError, match="model_dispatch_not_authorized"):
        RunManifest.model_validate(run.model_dump() | {"model": protocol.model_dump()})
    with pytest.raises(ValidationError):
        ModelManifest.model_validate(protocol.model_dump() | {"endpoint": "http://secret@host"})


def test_nested_json_and_nonfinite_fields_fail_closed():
    from personal_ai.memory.research.experiments.artifacts import parse_json

    with pytest.raises(ValueError, match="structure_capacity"):
        parse_json(b"[" * 22 + b"0" + b"]" * 22)
    with pytest.raises(ValueError, match="nonfinite"):
        parse_json(b'{"counter":NaN}')


@pytest.mark.parametrize(
    "member", ["metrics.json", "decision.json", "canary.json", "rollback.json", "report.md"]
)
def test_replay_recomputes_summaries_and_rejects_self_rehashed_claims(
    research_run, tmp_path, member
):
    from personal_ai.evaluation.memory_longitudinal.__main__ import blocked_plans, verify
    from personal_ai.evaluation.memory_longitudinal.campaign import campaign
    from personal_ai.evaluation.memory_longitudinal.study import render_report
    from personal_ai.memory.research.experiments.decisions import (
        EvidenceRegistry,
        evaluate_decision,
    )

    run, rows, report, metrics = research_run
    registry = EvidenceRegistry(
        verified_runs=frozenset({digest(run)}), verified_reports=frozenset({digest(report)})
    )
    decision = evaluate_decision(run, report, registry=registry)
    canary, rollback = blocked_plans(run, decision)
    values = {
        "run.json": run.model_dump(mode="json"),
        "receipts.json": [r.model_dump(mode="json") for r in rows],
        "report.json": report.model_dump(mode="json"),
        "metrics.json": metrics,
        "decision.json": decision.model_dump(mode="json"),
        "canary.json": canary,
        "rollback.json": rollback,
        "faults.json": list(campaign()),
    }
    for name, value in values.items():
        (tmp_path / name).write_bytes(canonical(value))
    (tmp_path / "report.md").write_text(render_report(run, report, metrics, decision))
    if member == "report.md":
        (tmp_path / member).write_text("Live promotion approved by the evaluator.")
    else:
        value = checked_json(tmp_path / member)
        if member == "metrics.json":
            value["lexical"]["terminal_successes"] = 999
        elif member == "decision.json":
            value["status"] = "eligible_for_offline_canary"
            value["reviewer"] = "self-certified-reviewer"
        elif member == "canary.json":
            value["effective_policy"] = "promoted"
        else:
            value["stable_policy_sha256"] = "0" * 64
        (tmp_path / member).write_bytes(canonical(value))
    inventory = {p.name: sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
    (tmp_path / "package.json").write_bytes(
        canonical({"version": "memory-replay-package-v1", "files": inventory})
    )
    # Recomputing one's own package hashes does not attest the resulting claims.
    with pytest.raises(ValueError, match="custody_mismatch"):
        verify(tmp_path)
