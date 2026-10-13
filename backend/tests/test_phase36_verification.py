"""Matrix completeness, evidence attribution and release derivation regressions."""

import ast
import importlib.util
import json
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
)
from personal_ai.evaluation.verification.contracts import (
    VerificationMatrix,
    VerificationRow,
    execution_status,
    integrated_promotion,
    release_projection,
)


def matrix():
    return VerificationMatrix.model_validate_json(MATRIX_PATH.read_bytes())


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
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    before = source_identity(tmp_path)
    (tmp_path / "backend/src/new.py").write_text("changed")
    assert source_identity(tmp_path) != before
    unchanged = source_identity(tmp_path)
    (tmp_path / "receipts.json").write_text("generated")
    assert source_identity(tmp_path) == unchanged


def test_aggregate_resource_gate_is_measured_and_live_gates_stay_unverified():
    thresholds = matrix().thresholds
    result = integrated_promotion([], thresholds)
    assert result["gates"]["synthetic_aggregate_resource_saving"]["status"] == "unverified"
    for saving, expected in ((0.016, "failed"), (0.10, "passed")):
        result = integrated_promotion(
            [{"kind": "combined-implemented-paths-v1", "aggregate_saving_fraction": saving}],
            thresholds,
        )
        assert result["gates"]["synthetic_aggregate_resource_saving"]["status"] == expected
        assert result["gates"]["supported_live_answer_quality"]["status"] == "unverified"
        assert result["decision"] == "not_promoted" and not result["promoted_coverage"]


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
