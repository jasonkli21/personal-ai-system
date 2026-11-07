"""Current source identity coverage and immutable experiment-lock regressions."""

import json
from pathlib import Path

import pytest

from personal_ai.evaluation import planning, source_contracts
from personal_ai.evaluation.offline_information_contracts import PROTOCOL_MANIFEST

ROOT = Path(__file__).resolve().parents[2]


def test_planning_source_closure_is_sorted_broad_and_excludes_only_versioned_locks():
    paths = source_contracts.planning_source_paths(ROOT)
    assert paths == tuple(sorted(paths))
    assert "backend/src/personal_ai/evaluation/source_contracts.py" in paths
    assert "backend/src/personal_ai/evaluation/planning.py" in paths
    assert not any(Path(path).name.startswith("planning-baseline-") for path in paths)
    assert not any(
        path.endswith(f"/source-manifest-v2-generation-{generation}.json") for path in paths for generation in range(2, 11)
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


def test_additive_current_identities_bind_the_final_source_and_preserve_history():
    planning_lock = json.loads(planning.FREEZE_PATH.read_bytes())
    planning_v35 = json.loads(planning.HISTORICAL_V35_FREEZE_PATH.read_bytes())
    planning_entries = source_contracts.planning_source_entries(ROOT)
    assert planning_lock["baseline_lock_version"] == "planning-baseline-lock-v36"
    assert planning_lock["supersedes"] == planning_v35["baseline_lock_version"]
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
        (manifest_path.parent / "source-manifest-v2-generation-9.json").read_bytes()
    )
    hashes, files = source_contracts.offline_benchmark_source_identity(ROOT)
    assert manifest["source_generation"] == 10
    assert manifest["supersedes"] == "source-manifest-v2-generation-9"
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
