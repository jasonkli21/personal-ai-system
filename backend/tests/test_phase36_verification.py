"""Matrix completeness, evidence attribution and release derivation regressions."""

import ast
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from personal_ai.evaluation.verification import pytest_evidence
from personal_ai.evaluation.verification.__main__ import (
    MATRIX_PATH,
    ROOT,
    render_report,
    source_identity,
    verifier_environment,
)
from personal_ai.evaluation.verification.contracts import (
    ExternalEvidenceManifest,
    ExternalEvidenceReceipt,
    VerificationMatrix,
    VerificationRow,
    execution_status,
    integrated_promotion,
    integrated_threshold_gates,
    merge_external_evidence,
    release_projection,
)


def matrix():
    return VerificationMatrix.model_validate_json(MATRIX_PATH.read_bytes())


def external_receipt(row, *, receipt_id="receipt-1", **updates):
    now = datetime.now(UTC)
    values = {
        "receipt_id": receipt_id,
        "verification_id": row.verification_id,
        "evidence_class": row.evidence_class,
        "status": "passed",
        "authority_ref": row.authority_ref,
        "originating_command": row.command,
        "tested_revision": "a" * 40,
        "matrix_sha256": "b" * 64,
        "source_configuration_sha256": "c" * 64,
        "environment_configuration_sha256": "d" * 64,
        "profile_identities": {"environment": "reviewed-fixture-v1"},
        "artifact_ref": "evidence://reviewed/phase36",
        "artifact_sha256": "e" * 64,
        "recorded_at": now,
        "expires_at": now + timedelta(days=1),
        "operator_provenance": "operator:fixture",
        "reviewer_provenance": "reviewer:fixture",
    }
    return ExternalEvidenceReceipt.model_validate({**values, **updates})


def test_every_boundary_has_executable_evidence_or_an_original_blocker():
    program = matrix()
    assert len(program.rows) >= 40
    assert {r.status for r in program.rows} == {"unverified", "blocked"}
    assert all((ROOT / r.authority_ref).is_file() for r in program.rows)
    for row in program.rows:
        for ref in row.test_refs:
            path, *names = ref.split("::")
            file = ROOT / "backend" / path
            assert file.is_file(), ref
            if names:
                functions = {
                    n.name
                    for n in ast.walk(ast.parse(file.read_text()))
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                assert names[0] in functions, ref
    for field, update in (
        ("rows", [r.model_dump() for r in program.rows] + [program.rows[0].model_dump()]),
        ("normative_boundaries", [*program.normative_boundaries, "uncovered"]),
    ):
        with pytest.raises(ValidationError):
            VerificationMatrix.model_validate({**program.model_dump(), field: update})


@pytest.mark.parametrize(
    "cases,expected",
    [
        ([], "unverified"),
        ([{"nodeid": "tests/x.py::test_x[a]", "status": "passed"}], "passed"),
        (
            [
                {"nodeid": "tests/x.py::test_x[a]", "status": "passed"},
                {"nodeid": "tests/x.py::test_x[b]", "status": "unverified"},
            ],
            "unverified",
        ),
        (
            [
                {"nodeid": "tests/x.py::test_x[a]", "status": "failed"},
                {"nodeid": "tests/x.py::test_x[b]", "status": "unverified"},
            ],
            "failed",
        ),
        ([{"nodeid": "tests/x.py::test_xyz", "status": "passed"}], "unverified"),
    ],
)
def test_status_attribution_is_exact_and_skips_are_not_passes(cases, expected):
    assert execution_status(("tests/x.py::test_x",), cases) == expected
    assert execution_status(("tests/x.py::test_x", "tests/missing.py"), cases) != "passed"


def test_pass_requires_revision_configuration_and_evidence_and_na_requires_rationale():
    row = matrix().rows[0].model_dump()
    with pytest.raises(ValidationError, match="pass_requires_bound_evidence"):
        VerificationRow.model_validate({**row, "status": "passed"})
    with pytest.raises(ValidationError):
        VerificationRow.model_validate({**row, "status": "not-applicable", "rationale": ""})
    with pytest.raises(ValidationError):
        VerificationRow.model_validate({**row, "test_refs": ["tests/../unsafe.py"]})


def test_teardown_failure_skips_and_incomplete_collection_remain_visible(monkeypatch, tmp_path):
    # Isolate the collector under test from the active program's pytest hooks.
    spec = importlib.util.spec_from_file_location("isolated_receipts", pytest_evidence.__file__)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    output = tmp_path / "receipt.json"
    monkeypatch.setenv("PHASE36_RECEIPTS", str(output))
    collector.pytest_collection_finish(
        SimpleNamespace(
            items=[
                SimpleNamespace(nodeid="tests/x.py::test_x"),
                SimpleNamespace(nodeid="tests/x.py::test_missing"),
            ]
        )
    )

    def report(when, *, failed=False, skipped=False, passed=False):
        return SimpleNamespace(
            nodeid="tests/x.py::test_x",
            when=when,
            failed=failed,
            skipped=skipped,
            passed=passed,
            user_properties=[],
        )

    collector.pytest_runtest_logreport(report("call", passed=True))
    collector.pytest_runtest_logreport(report("teardown", failed=True))
    collector.pytest_sessionfinish(None, 1)
    cases = json.loads(output.read_text())["cases"]
    assert execution_status(("tests/x.py",), cases) == "failed"
    collector._cases.clear()
    collector.pytest_runtest_logreport(report("setup", skipped=True))
    assert collector._cases["tests/x.py::test_x"]["status"] == "unverified"


def test_release_and_blockers_are_derived_without_external_evidence_inference():
    program = matrix()
    rows = tuple(
        r.model_copy(
            update={
                "status": "passed",
                "evidence_ref": "receipts.json",
                "tested_revision": "synthetic-revision",
                "configuration_sha256": "a" * 64,
            }
        )
        if r.evidence_class == "offline"
        else r
        for r in program.rows
    )
    release = release_projection(rows)
    assert not release["release_ready"]
    assert release["capabilities"]["routing"]["release_status"] == "unavailable"
    assert any(
        b["evidence_class"] == "live" for b in release["capabilities"]["routing"]["blockers"]
    )
    report = {
        "tested_revision": "synthetic-revision",
        "configuration_sha256": "a" * 64,
        "matrix_sha256": "b" * 64,
        "recorded_at": "2026-10-12",
        "strategy_coverage": program.strategy_coverage,
        "thresholds": program.thresholds,
        "rows": [r.model_dump() for r in rows],
        "measurements": [],
        "release": release,
        "verification_environment": verifier_environment(),
    }
    assert render_report(report) == render_report(json.loads(json.dumps(report)))
    assert "unverified" in render_report(report) and "Release ready: **false**" in render_report(
        report
    )
    # Known critical local failure cannot be hidden by enabling/disabling a product gate.
    failed = rows[0].model_copy(update={"status": "failed"})
    assert (
        release_projection((failed,))["capabilities"][failed.capability]["blockers"][0]["severity"]
        == "critical"
    )


def test_source_identity_binds_new_and_dirty_code_but_not_generated_evidence(tmp_path):
    for relative in (
        "Makefile",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "frontend/package.json",
        "frontend/pnpm-lock.yaml",
        "backend/src/new.py",
        "infrastructure/aws/templates/identity.yaml",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    before = source_identity(tmp_path)
    (tmp_path / "backend/src/new.py").write_text("changed")
    assert source_identity(tmp_path) != before
    unchanged = source_identity(tmp_path)
    template = tmp_path / "infrastructure/aws/templates/identity.yaml"
    template.write_text("changed infrastructure input")
    assert source_identity(tmp_path) != unchanged
    unchanged = source_identity(tmp_path)
    generated = tmp_path / "docs/personal-ai-chapter-2/phase-36/receipts.json"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text("generated")
    assert source_identity(tmp_path) == unchanged


def test_aggregate_resource_gate_is_measured_and_live_gates_stay_unverified():
    thresholds = matrix().thresholds
    result = integrated_promotion([], thresholds)
    assert result["gates"]["minimum_aggregate_resource_saving_fraction"]["status"] == "unverified"
    for saving, expected in ((0.016, "failed"), (0.10, "passed")):
        result = integrated_promotion(
            [{"kind": "combined-implemented-paths-v1", "aggregate_saving_fraction": saving}],
            thresholds,
        )
        assert result["gates"]["minimum_aggregate_resource_saving_fraction"]["status"] == expected
        assert result["gates"]["minimum_supported_quality_delta"]["status"] == "unverified"
        assert result["decision"] == "not_promoted" and not result["promoted_coverage"]


def test_every_integrated_threshold_has_a_gate_and_latency_is_compared_by_variant():
    thresholds = matrix().thresholds
    assert set(integrated_threshold_gates([], thresholds)) == set(thresholds)
    result = integrated_threshold_gates(
        [
            {
                "kind": "combined-implemented-paths-v1",
                "aggregate_saving_fraction": 0.10,
                "rows": [
                    {"variant": "baseline", "latency_ms": 10},
                    {"variant": "baseline", "latency_ms": 20},
                    {
                        "variant": "combined",
                        "latency_ms": 11,
                        "assembled_token_estimate": 100,
                        "post_builder_exact_support": 1.0,
                        "post_builder_authority_confusion": 0,
                        "logical_calls": {"search": 2},
                    },
                    {
                        "variant": "combined",
                        "latency_ms": 25,
                        "assembled_token_estimate": 120,
                        "post_builder_exact_support": 1.0,
                        "post_builder_authority_confusion": 0,
                        "logical_calls": {"search": 3},
                    },
                ],
            },
            {
                "kind": "bounded-soak-v1",
                "iterations": thresholds["soak_iterations"],
                "revoked_cached_memory_selected": 0,
                "samples": [
                    {"derived_views_created": 2, "maintenance_jobs_created": 3},
                    {"derived_views_created": 4, "maintenance_jobs_created": 5},
                ],
            },
        ],
        thresholds,
    )
    assert result["maximum_pipeline_p95_latency_increase_ms"]["observed"] == 5
    assert result["maximum_pipeline_p95_latency_increase_ms"]["status"] == "failed"
    assert result["minimum_exact_support"]["status"] == "passed"
    assert result["maximum_maintenance_jobs_per_soak_turn"]["status"] == "failed"
    assert result["minimum_mutation_correctness"]["status"] == "unverified"


def test_external_receipts_are_bound_fail_closed_and_supersession_is_auditable():
    program = matrix()
    row = next(item for item in program.rows if item.verification_id == "P36-IDENTITY")
    receipt = external_receipt(row)
    manifest = ExternalEvidenceManifest(matrix_sha256="b" * 64, receipts=(receipt,))
    updated, audit = merge_external_evidence(
        program.rows,
        manifest,
        tested_revision="a" * 40,
        source_configuration_sha256="c" * 64,
        matrix_sha256="b" * 64,
    )
    passed = next(item for item in updated if item.verification_id == row.verification_id)
    assert passed.status == "passed" and audit["accepted"] == ["receipt-1"]
    assert passed.evidence_ref.startswith("external-evidence.json#receipt_id=receipt-1")

    for bad_receipt, revision, configuration, expected_reason in (
        (receipt, "f" * 40, "c" * 64, "tested_revision_mismatch"),
        (receipt, "a" * 40, "f" * 64, "source_configuration_mismatch"),
        (
            receipt.model_copy(update={"evidence_class": "cloud"}),
            "a" * 40,
            "c" * 64,
            "evidence_class_mismatch",
        ),
        (
            receipt.model_copy(
                update={
                    "recorded_at": datetime.now(UTC) - timedelta(days=31),
                    "expires_at": datetime.now(UTC) + timedelta(days=1),
                }
            ),
            "a" * 40,
            "c" * 64,
            "receipt_stale_or_future",
        ),
    ):
        candidate = ExternalEvidenceManifest(matrix_sha256="b" * 64, receipts=(bad_receipt,))
        unchanged, audit = merge_external_evidence(
            program.rows,
            candidate,
            tested_revision=revision,
            source_configuration_sha256=configuration,
            matrix_sha256="b" * 64,
        )
        assert (
            next(item for item in unchanged if item.verification_id == row.verification_id).status
            == "unverified"
        )
        assert audit["rejected"][0]["reason"] == expected_reason

    failed_receipt = receipt.model_copy(update={"status": "failed"})
    failed, _ = merge_external_evidence(
        program.rows,
        ExternalEvidenceManifest(matrix_sha256="b" * 64, receipts=(failed_receipt,)),
        tested_revision="a" * 40,
        source_configuration_sha256="c" * 64,
        matrix_sha256="b" * 64,
    )
    assert (
        next(item for item in failed if item.verification_id == row.verification_id).status
        == "failed"
    )
    unchanged, _ = merge_external_evidence(
        program.rows,
        None,
        tested_revision="a" * 40,
        source_configuration_sha256="c" * 64,
        matrix_sha256="b" * 64,
    )
    assert unchanged == program.rows

    superseding = external_receipt(row, receipt_id="receipt-2", supersedes_receipt_id="receipt-1")
    merged, audit = merge_external_evidence(
        program.rows,
        ExternalEvidenceManifest(matrix_sha256="b" * 64, receipts=(receipt, superseding)),
        tested_revision="a" * 40,
        source_configuration_sha256="c" * 64,
        matrix_sha256="b" * 64,
    )
    assert audit["accepted"] == ["receipt-2"]
    assert (
        "receipt-2"
        in next(item for item in merged if item.verification_id == row.verification_id).evidence_ref
    )
    with pytest.raises(ValidationError, match="external_receipt_replay_or_duplicate_id"):
        ExternalEvidenceManifest(matrix_sha256="b" * 64, receipts=(receipt, receipt))


def test_external_receipt_manifest_is_merged_into_the_generated_report(monkeypatch, tmp_path):
    from personal_ai.evaluation.verification import __main__ as runner

    program = matrix()
    row = next(item for item in program.rows if item.verification_id == "P36-IDENTITY")
    matrix_digest = sha256(MATRIX_PATH.read_bytes()).hexdigest()
    receipt = external_receipt(
        row, matrix_sha256=matrix_digest, source_configuration_sha256="c" * 64
    )
    evidence_path = tmp_path / "operator-evidence.json"
    evidence_path.write_text(
        json.dumps(
            ExternalEvidenceManifest(matrix_sha256=matrix_digest, receipts=(receipt,)).model_dump(
                mode="json"
            )
        )
    )

    def execute(command, **kwargs):
        if command[0] == "git":
            return SimpleNamespace(stdout="a" * 40 + "\n")
        Path(kwargs["env"]["PHASE36_RECEIPTS"]).write_text(
            json.dumps({"exit_code": 0, "cases": []})
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", execute)
    monkeypatch.setattr(runner, "source_identity", lambda: "c" * 64)
    assert runner.run(tmp_path / "out", evidence_path) == 0
    report = json.loads((tmp_path / "out/matrix-results.json").read_text())
    assert (
        next(r for r in report["rows"] if r["verification_id"] == "P36-IDENTITY")["status"]
        == "passed"
    )
    assert report["external_receipt_validation"]["accepted"] == ["receipt-1"]
    assert (tmp_path / "out/external-evidence.json").is_file()


def test_phase36_human_summaries_use_offline_terminology_and_defer_exact_soak_counts():
    root = ROOT
    implementation = (root / "docs/personal-ai-chapter-2/phase-36/implementation-report.md").read_text()
    current = (root / "docs/current-state.md").read_text()
    assert "24 offline rows passed" in implementation
    assert "24 passed offline rows" in current
    assert "24 passed local rows" not in current
    assert "59 views" not in implementation and "91 jobs" not in implementation
    assert "exact final counts are recorded only in the generated" in implementation


def test_runner_never_executes_external_refs_and_reports_incomplete_batch(monkeypatch, tmp_path):
    from personal_ai.evaluation.verification import __main__ as runner

    commands = []

    def execute(command, **kwargs):
        commands.append(command)
        if command[0] == "git":
            return SimpleNamespace(stdout="fixture-head\n")
        Path(kwargs["env"]["PHASE36_RECEIPTS"]).write_text(
            json.dumps(
                {
                    "exit_code": 2,
                    "cases": [],
                }
            )
        )
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(runner.subprocess, "run", execute)
    monkeypatch.setattr(runner, "source_identity", lambda: "a" * 64)
    assert runner.run(tmp_path) == 1
    expected = {
        ref for row in matrix().rows if row.evidence_class == "offline" for ref in row.test_refs
    }
    assert set(commands[1][-len(expected) :]) == expected
    report = json.loads((tmp_path / "matrix-results.json").read_text())
    assert not any(r["status"] == "passed" for r in report["rows"])
    assert json.loads((tmp_path / "blockers.json").read_text()) == report["release"]
    assert (tmp_path / "release-report.md").read_text() == render_report(report)
