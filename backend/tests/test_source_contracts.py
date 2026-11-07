"""Current source identity coverage and immutable experiment-lock regressions."""

import importlib.util
import json
from pathlib import Path

import pytest

from personal_ai.evaluation import planning, source_contracts
from personal_ai.evaluation.offline_information_contracts import PROTOCOL_MANIFEST

ROOT = Path(__file__).resolve().parents[2]
SOURCE_CHECK_SPEC = importlib.util.spec_from_file_location(
    "source_contract_check", ROOT / "backend/scripts/source_contract_check.py"
)
source_contract_check = importlib.util.module_from_spec(SOURCE_CHECK_SPEC)
SOURCE_CHECK_SPEC.loader.exec_module(source_contract_check)


def test_planning_source_closure_is_sorted_broad_and_excludes_only_versioned_locks():
    paths = source_contracts.planning_source_paths(ROOT)
    assert paths == tuple(sorted(paths))
    assert "backend/src/personal_ai/evaluation/source_contracts.py" in paths
    assert "backend/src/personal_ai/evaluation/planning.py" in paths
    assert not any(Path(path).name.startswith("planning-baseline-") for path in paths)
    assert not any(
        path.endswith(f"/source-manifest-v2-generation-{generation}.json")
        for path in paths
        for generation in range(2, 12)
    )
    assert f"backend/src/personal_ai/evaluation/fixtures/offline_information_handling/{PROTOCOL_MANIFEST}" not in paths


def test_package_closure_reports_mutated_scorer_corpus_and_missing_source(tmp_path):
    package = tmp_path / "backend/src/personal_ai"
    fixture = package / "evaluation/fixtures/offline_information_handling"
    fixture.mkdir(parents=True)
    scorer = package / "evaluation/offline_information_scoring.py"
    cases = fixture / "cases-v2.json"
    historical = fixture / "source-manifest-v2-generation-9.json"
    scorer.write_text("score-v1")
    cases.write_text("cases-v1")
    historical.write_text("old-seal")

    expected = source_contracts.package_tree_entries(tmp_path, "backend/src/personal_ai")
    historical.write_text("tampered historical seal")
    unchanged = source_contracts.package_tree_entries(tmp_path, "backend/src/personal_ai")
    assert unchanged == expected

    scorer.write_text("score-v2")
    cases.write_text("cases-v2")
    changed = source_contracts.package_tree_entries(tmp_path, "backend/src/personal_ai")
    differences = source_contracts.source_file_differences(expected, changed)
    assert any("offline_information_scoring.py" in item for item in differences)
    assert any("cases-v2.json" in item for item in differences)

    scorer.unlink()
    missing = source_contracts.package_tree_entries(tmp_path, "backend/src/personal_ai")
    assert any("missing source evaluation/offline_information_scoring.py" in item for item in source_contracts.source_file_differences(changed, missing))


def test_planning_closure_fails_with_path_for_missing_required_input(tmp_path, monkeypatch):
    (tmp_path / "backend/src/personal_ai").mkdir(parents=True)
    monkeypatch.setattr(source_contracts, "PLANNING_REQUIRED_PATHS", ("backend/required.py",))
    with pytest.raises(source_contracts.SourceContractError, match="backend/required.py"):
        source_contracts.planning_source_entries(tmp_path)


def test_source_file_comparison_distinguishes_changed_missing_and_unexpected_paths():
    differences = source_contracts.source_file_differences(
        {"changed.py": "a", "missing.py": "b"},
        {"changed.py": "c", "unexpected.py": "d"},
    )
    assert differences == [
        "changed source changed.py: expected=a current=c",
        "missing source missing.py: expected=b",
        "unexpected source unexpected.py: current=d",
    ]


def test_planning_v35_and_offline_information_handling_generation_nine_are_immutable():
    planning_v35 = planning.HISTORICAL_V35_FREEZE_PATH.read_bytes()
    offline_information_handling_generation_nine = (
        ROOT / "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-9.json"
    ).read_bytes()
    assert source_contracts.sha(planning_v35) == (
        "d344dbbe8c7a8dc5d53b8b61c12212a034451bd68cc2cc64f02b26c3f1104fe9"
    )
    assert source_contracts.sha(offline_information_handling_generation_nine) == (
        "a00a8faf9f8a8f7dc17efbc81e07a8053c80415a7735eae362ed43ad95bc6a3e"
    )
    assert json.loads(planning_v35)["promotion_decision"].startswith("non_promotion")

    planning_v36 = ROOT / "backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v36.json"
    offline_generation_ten = (
        ROOT / "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-10.json"
    )
    assert source_contracts.sha(planning_v36.read_bytes()) == (
        source_contract_check.PLANNING_V36_SHA256
    )
    assert source_contracts.sha(offline_generation_ten.read_bytes()) == (
        source_contract_check.OFFLINE_GENERATION_10_SHA256
    )


def test_additive_current_identities_bind_the_final_source_and_preserve_history():
    planning_lock = json.loads(planning.FREEZE_PATH.read_bytes())
    planning_v36 = json.loads(
        (ROOT / "backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v36.json").read_bytes()
    )
    planning_entries = source_contracts.planning_source_entries(ROOT)
    assert planning_lock["baseline_lock_version"] == "planning-baseline-lock-v37"
    assert planning_lock["supersedes"] == planning_v36["baseline_lock_version"]
    assert planning_lock["source_contract_version"] == "planning-source-closure-v1"
    assert planning_lock["source_identity_files"] == planning_entries
    assert planning_lock["source_identity_digest"] == source_contracts.planning_source_digest(
        planning_entries, planning.PLANNING_EVALUATOR_VERSION
    )
    assert planning_lock["promotion_decision"].startswith("non_promotion")

    manifest_path = (
        ROOT
        / "backend/src/personal_ai/evaluation/fixtures/offline_information_handling"
        / PROTOCOL_MANIFEST
    )
    manifest = json.loads(manifest_path.read_bytes())
    previous = json.loads(
        (manifest_path.parent / "source-manifest-v2-generation-10.json").read_bytes()
    )
    hashes, files = source_contracts.offline_benchmark_source_identity(ROOT)
    assert manifest["source_generation"] == 11
    assert manifest["supersedes"] == "source-manifest-v2-generation-10"
    assert manifest["source_files"] == files
    assert manifest["hashes"] == hashes
    assert manifest["legacy_corpus_identity"] == {
        key: json.loads((manifest_path.parent / "cases-v2.json").read_bytes())[key]
        for key in ("suite", "rubric")
    }
    assert manifest["hashes"]["cases"] == previous["hashes"]["cases"]
    assert manifest["changed_protocols"] == sorted(
        key for key, digest in hashes.items() if previous["hashes"].get(key) != digest
    )
    assert "earlier measurements do not validate this generation" in manifest["preregistration"]


@pytest.mark.parametrize(
    ("surface", "field", "mutated_value", "expected_error"),
    [
        ("planning", "promotion_decision", "PROMOTED", "promotion_decision"),
        ("planning", "configuration_digest", "0" * 64, "configuration_digest"),
        ("planning", "corpus_digest", "0" * 64, "corpus_digest"),
        ("planning", "fixture_dependency_digest", "0" * 64, "fixture_dependency_digest"),
        ("planning", "python_runtime", "0.0", "python_runtime"),
        ("planning", "python_abi", "forged-abi", "python_abi"),
        ("planning", "platform_runtime", "forged-platform", "platform_runtime"),
        ("planning", "runtime_dependency_digest", "0" * 64, "runtime_dependency_digest"),
        ("planning", "pydantic_runtime", "0.0", "pydantic_runtime"),
        ("planning", "evidence_kind", "provider_validated", "evidence_kind"),
        ("planning", "preserved_corpus", "changed cases", "preserved_corpus"),
        ("planning", "runtime_profile", "all providers", "runtime_profile"),
        ("planning", "frozen_at", "2026-11-07", "frozen_at"),
        ("planning", "evaluator_version", "forged-evaluator", "evaluator_version"),
        ("planning", "runtime_identity_scope", "portable replay only", "runtime_identity_scope"),
        ("planning", "source_revision_binding", "no ancestry check", "source_revision_binding"),
        ("planning", "source_change_summary", "promoted", "source_change_summary"),
        ("planning", "source_identity_digest", "0" * 64, "source_identity_digest"),
        ("planning", "source_identity_files", "unknown-map-key", "unknown-map-key"),
        ("planning", "supersedes", "planning-baseline-lock-v34", "supersedes"),
        ("planning", "source_revision", None, "source_revision"),
        ("offline", "preregistration", "production validated", "preregistration"),
        ("offline", "schema_version", 4, "schema_version"),
        ("offline", "source_generation", 10, "source_generation"),
        ("offline", "supersedes", "source-manifest-v2-generation-9", "supersedes"),
        ("offline", "frozen_before_measurement", False, "frozen_before_measurement"),
        ("offline", "suite", "arbitrary-suite", "suite"),
        ("offline", "source_revision_binding", "unverified revision", "source_revision_binding"),
        ("offline", "legacy_corpus_identity", {"suite": "x", "rubric": "y"}, "legacy_corpus_identity"),
        ("offline", "hashes", "unknown-map-key", "offline information handling manifest hash keys"),
        ("offline", "source_files", "unknown-map-key", "source_files"),
        ("offline", "changed_protocols", [], "changed_protocols"),
    ],
)
def test_source_contract_rejects_current_metadata_tampering(
    surface, field, mutated_value, expected_error, monkeypatch
):
    original_read = source_contract_check._read_json

    def injected_read(path, label):
        value = original_read(path, label)
        is_planning = path.name == "planning-baseline-v37.json"
        is_offline = path.name == "source-manifest-v2-generation-11.json"
        if (surface == "planning" and is_planning) or (surface == "offline" and is_offline):
            value = json.loads(json.dumps(value))
            if field == "source_identity_files":
                value[field][mutated_value] = "0" * 64
            elif field == "source_files":
                value[field][mutated_value] = {}
            elif field == "hashes":
                value[field][mutated_value] = "0" * 64
            else:
                value[field] = mutated_value
        return value

    if field == "source_revision":
        def inject_both_anchors(path, label):
            value = original_read(path, label)
            if path.name in {
                "planning-baseline-v37.json",
                "source-manifest-v2-generation-11.json",
            }:
                value = json.loads(json.dumps(value))
                value["source_revision"] = "f" * 40
            return value

        monkeypatch.setattr(source_contract_check, "_read_json", inject_both_anchors)
    else:
        monkeypatch.setattr(source_contract_check, "_read_json", injected_read)
    monkeypatch.setattr(source_contract_check, "_verify_clean_identity_files", lambda *args: None)

    try:
        errors = source_contract_check.check(ROOT)
    except source_contract_check.VerificationError as error:
        errors = [str(error)]
    assert any(expected_error in error for error in errors), errors


def test_source_contract_rejects_mutated_pinned_predecessor_bytes(tmp_path):
    pins = {
        f"{source_contract_check.PLANNING_DIRECTORY}/planning-baseline-v36.json": source_contract_check.PLANNING_V36_SHA256,
        f"{source_contract_check.OFFLINE_BENCHMARK_DIRECTORY}/source-manifest-v2-generation-10.json": source_contract_check.OFFLINE_GENERATION_10_SHA256,
        f"{source_contract_check.OFFLINE_BENCHMARK_DIRECTORY}/source-manifest-v2-generation-9.json": source_contract_check.OFFLINE_GENERATION_9_SHA256,
    }
    pins.update(
        {
            f"{source_contract_check.OFFLINE_BENCHMARK_DIRECTORY}/{name}": digest
            for name, digest in source_contract_check.FROZEN_CASE_SHA256.items()
        }
    )
    pins.update(source_contract_check.FROZEN_FIXTURE_SHA256)
    pins.update(source_contract_check.VERSIONED_MIGRATION_SHA256)
    pins[f"{source_contract_check.PLANNING_DIRECTORY}/planning-baseline-v35.json"] = (
        source_contract_check.PLANNING_V35_SHA256
    )
    for index, target in enumerate(pins):
        fixture_root = tmp_path / f"case-{index}"
        for relative in pins:
            source = ROOT / relative
            path = fixture_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read_bytes())
        path = fixture_root / target
        path.write_bytes(path.read_bytes() + b" ")
        with pytest.raises(source_contract_check.VerificationError, match="SHA-256"):
            source_contract_check._verify_historical_bytes(fixture_root)


def test_portable_source_contract_ignores_host_runtime_fingerprint(monkeypatch):
    monkeypatch.setattr(planning.platform, "python_version", lambda: "3.12.14")
    monkeypatch.setattr(planning.platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(planning.platform, "platform", lambda: "Linux-6.12-x86_64")
    monkeypatch.setattr(source_contract_check, "_verify_clean_identity_files", lambda *args: None)

    assert source_contract_check.check(ROOT) == []
