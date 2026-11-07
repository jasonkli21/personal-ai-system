"""Read-only current-source verification and explicit additive lock proposals."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))

from personal_ai.evaluation.source_contracts import (
    OFFLINE_BENCHMARK_MANIFEST_FILENAME,
    OFFLINE_BENCHMARK_OPTIONAL_SOURCES,
    OFFLINE_BENCHMARK_SOURCE_CONTRACT,
    OFFLINE_BENCHMARK_SOURCE_GENERATION,
    PLANNING_EVALUATOR_VERSION,
    PLANNING_LOCK_FILENAME,
    PLANNING_LOCK_GENERATION,
    PLANNING_SOURCE_CONTRACT,
    offline_benchmark_source_identity,
    planning_source_digest,
    planning_source_entries,
    source_file_differences,
)

PLANNING_RELATIVE = (
    "backend/src/personal_ai/evaluation/fixtures/context/" + PLANNING_LOCK_FILENAME
)
PLANNING_DIRECTORY = "backend/src/personal_ai/evaluation/fixtures/context"
OFFLINE_BENCHMARK_DIRECTORY = "backend/src/personal_ai/evaluation/fixtures/offline_information_handling"
OFFLINE_BENCHMARK_RELATIVE = f"{OFFLINE_BENCHMARK_DIRECTORY}/{OFFLINE_BENCHMARK_MANIFEST_FILENAME}"
RUNTIME_SCOPE = (
    "strict planning replay only; portable current-source conformance does not compare this runtime fingerprint"
)
PLANNING_LOCK_FIELDS = {
    "baseline_lock_version",
    "baseline_version",
    "configuration_digest",
    "evaluator_version",
    "source_identity_digest",
    "corpus_digest",
    "fixture_dependency_digest",
    "counter_identity",
    "python_runtime",
    "python_implementation",
    "python_abi",
    "platform_runtime",
    "runtime_distribution_count",
    "runtime_dependency_digest",
    "pydantic_runtime",
    "evidence_kind",
    "frozen_at",
    "preserved_corpus",
    "promotion_decision",
    "runtime_profile",
    "source_change_summary",
    "source_revision",
    "source_revision_binding",
    "supersedes",
    "source_contract_version",
    "source_identity_files",
    "runtime_identity_scope",
}
PLANNING_V35_SHA256 = "d344dbbe8c7a8dc5d53b8b61c12212a034451bd68cc2cc64f02b26c3f1104fe9"
PLANNING_V36_SHA256 = "d6e0c9a6abc936eb2d9e64564ccf4f6009876b10901129d5067423fff0fc8fdc"
OFFLINE_GENERATION_9_SHA256 = "a00a8faf9f8a8f7dc17efbc81e07a8053c80415a7735eae362ed43ad95bc6a3e"
OFFLINE_GENERATION_10_SHA256 = "de316118c1eaa556a9110b9807a9c288dfc992bbb3215978b5ece8b4852e56c7"
FROZEN_CASE_SHA256 = {
    "cases-v1.json": "84c0e5a1e990ac5b282a24348e4319406d3ec4188d179099777ab5aa4b5651bf",
    "cases-v2.json": "25df654eda27040c3b52695fd6ec695b53238a7cf76b82e1ed4e5d442b55205d",
}
FROZEN_FIXTURE_SHA256 = {
    "backend/src/personal_ai/evaluation/fixtures/decisions/decision-fixtures.json": "221e9a3b42945b33363720b67a6d50e8204b3e01cae582fc81f24d1f2c870cb2",
    "backend/src/personal_ai/evaluation/fixtures/iterative_research/iterative-research-fixtures.json": "6db4b06c7d371c2a54fec37886c4b9df4ff555b671689a1c96cf9c4935ff4ef1",
    "backend/src/personal_ai/evaluation/fixtures/iterative_research/iterative-research-fixtures-v2.json": "b65ee153b020ae44dbefab33fb21ff268585ca08b0a490af98d0aa5d87ecc129",
}
VERSIONED_MIGRATION_SHA256 = {
    "backend/src/personal_ai/persistence/migrations/008_storage_migration_control.sql": "85b2431c757e14c830fa1debdbb2edb367d0a6e32d420b33543ad49300bf0fad",
    "backend/src/personal_ai/persistence/migrations/009_derived_source_migration_metadata.sql": "3048dbe3fb767e3c26240456014bbdb9f8664de4890db379d5de91efd1a9bffd",
    "backend/src/personal_ai/persistence/migrations/011_effect_receipt_migration_payload.sql": "96c8809151a86eaf63dc0f7e962b564f01681ef5ab41b444261a6aba0c98ff7e",
    "backend/src/personal_ai/persistence/migrations/012_provider_rate_limit_source_payload.sql": "4cf0223fd84b1235695c5b63cec176cbab4798f46a9fb8133522f76ef77f4299",
    "backend/src/personal_ai/persistence/migrations/027_memory_dependency_epochs.sql": "3591c9d2ea669d66f994e3fb5492484fd7c5ea9c8321b66fea0fda1014543009",
    "backend/src/personal_ai/persistence/migrations/028_verified_memory_knowledge.sql": "652c92c1251ede51ae0697d72a74e1bcc61ebbdf9b101d3cbf00ac312ced067c",
    "backend/src/personal_ai/persistence/migrations/030_memory_control.sql": "0690004c83086e1dce8539f9311fb24a1d0f1afba6666e6b5077d0618d56a058",
    "backend/src/personal_ai/persistence/migrations/032_profile_consents.sql": "18551d07e8ac2f494d9da8bdae7f15dfdef41040e65611740b0bed0ddbbd1f0b",
    "backend/src/personal_ai/persistence/migrations_py/022_routing_authorities.py": "003787e63cf27e4552f2505a9de189d738e8fafce6b94ab7edf1c46252f19b35",
}
PLANNING_SOURCE_CHANGE_SUMMARY = (
    "Restored immutable migration and fixture bytes and hardened source-contract metadata "
    "validation; planning configuration, corpus, fixture dependencies, runtime provenance "
    "and non-promotion are unchanged."
)
PLANNING_FROZEN_AT = "2026-11-06"
PLANNING_SOURCE_REVISION_BINDING = (
    "Per-file source SHA-256 values and aggregate digest identify current bytes; source_revision "
    "must resolve to a Git ancestor and records the reviewed source-tree anchor."
)
OFFLINE_SOURCE_REVISION_BINDING = (
    "Per-file source SHA-256 values and aggregate hashes identify the bytes; source_revision "
    "must resolve to a Git ancestor and records the reviewed source-tree anchor."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_historical_bytes(root: Path):
    historical = {
        f"{PLANNING_DIRECTORY}/planning-baseline-v35.json": PLANNING_V35_SHA256,
        f"{PLANNING_DIRECTORY}/planning-baseline-v36.json": PLANNING_V36_SHA256,
        f"{OFFLINE_BENCHMARK_DIRECTORY}/source-manifest-v2-generation-9.json": OFFLINE_GENERATION_9_SHA256,
        f"{OFFLINE_BENCHMARK_DIRECTORY}/source-manifest-v2-generation-10.json": OFFLINE_GENERATION_10_SHA256,
        **FROZEN_FIXTURE_SHA256,
        **VERSIONED_MIGRATION_SHA256,
        **{
            f"{OFFLINE_BENCHMARK_DIRECTORY}/{name}": digest
            for name, digest in FROZEN_CASE_SHA256.items()
        },
    }
    for relative, expected in historical.items():
        path = root / relative
        try:
            actual = _sha256(path)
        except OSError as error:
            raise VerificationError(f"historical evidence {relative}: cannot read bytes: {error}") from None
        if actual != expected:
            raise VerificationError(
                f"historical evidence {relative}: expected SHA-256={expected} current={actual}"
            )


def _read_pinned_json(root: Path, relative: str, expected_sha256: str, label: str) -> dict:
    path = root / relative
    try:
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected_sha256:
            raise VerificationError(
                f"{label}: expected SHA-256={expected_sha256} current={actual} at {path}"
            )
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label}: cannot read pinned JSON at {path}: {error}") from None
    if not isinstance(value, dict):
        raise VerificationError(f"{label}: expected an object at {path}")
    return value


def _require_ancestor_revision(root: Path, revision: object, label: str):
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise VerificationError(f"{label} source_revision must be a full lowercase Git commit SHA")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise VerificationError(
            f"{label} source_revision is not a verified ancestor of HEAD: {revision}"
        )


class VerificationError(ValueError):
    pass


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label}: cannot read valid JSON at {path}: {error}") from None
    if not isinstance(value, dict):
        raise VerificationError(f"{label}: expected an object at {path}")
    return value


def _git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise VerificationError(f"cannot identify source revision: {result.stderr.strip()}")
    return result.stdout.strip()


def _changed_paths(root: Path) -> set[str]:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode or untracked.returncode:
        raise VerificationError("cannot inspect checkout status for current-source verification")
    return set(tracked.stdout.splitlines()) | set(untracked.stdout.splitlines())


def _verify_clean_identity_files(root: Path, planning_files: dict[str, str], benchmark_files: dict):
    bound = set(planning_files) | {
        PLANNING_RELATIVE,
        OFFLINE_BENCHMARK_RELATIVE,
        f"{OFFLINE_BENCHMARK_DIRECTORY}/source-manifest-v2-generation-{OFFLINE_BENCHMARK_SOURCE_GENERATION - 1}.json",
    }
    bound.update(f"backend/src/personal_ai/{path}" for path in benchmark_files["core_runtime"])
    for key, package_path in OFFLINE_BENCHMARK_OPTIONAL_SOURCES.items():
        bound.update(f"{package_path}/{path}" for path in benchmark_files[key])
    dirty = sorted(bound & _changed_paths(root))
    if dirty:
        preview = ", ".join(dirty[:8])
        suffix = f" (and {len(dirty) - 8} more)" if len(dirty) > 8 else ""
        raise VerificationError(
            "bound source or active lock is modified in the checkout; commit the reviewed "
            f"identity first, then rerun: {preview}{suffix}"
        )


def _validate_planning(root: Path) -> tuple[dict, dict[str, str], list[str]]:
    path = root / PLANNING_RELATIVE
    lock = _read_json(path, "planning lock")
    previous = _read_pinned_json(
        root,
        f"{PLANNING_DIRECTORY}/planning-baseline-v36.json",
        PLANNING_V36_SHA256,
        "previous planning lock",
    )
    if set(lock) != PLANNING_LOCK_FIELDS:
        raise VerificationError(
            "planning lock field set mismatch: "
            f"unexpected={sorted(set(lock) - PLANNING_LOCK_FIELDS)} "
            f"missing={sorted(PLANNING_LOCK_FIELDS - set(lock))}"
        )
    if lock.get("supersedes") != previous.get("baseline_lock_version"):
        raise VerificationError("planning lock supersedes does not identify the pinned predecessor")
    if lock.get("counter_identity") != previous.get("counter_identity"):
        raise VerificationError(
            "planning lock counter_identity changed without a versioned metric migration"
        )
    required = {
        "baseline_lock_version": f"planning-baseline-lock-v{PLANNING_LOCK_GENERATION}",
        "source_contract_version": PLANNING_SOURCE_CONTRACT,
        "evaluator_version": PLANNING_EVALUATOR_VERSION,
        "runtime_identity_scope": RUNTIME_SCOPE,
        "source_revision_binding": PLANNING_SOURCE_REVISION_BINDING,
        "source_change_summary": PLANNING_SOURCE_CHANGE_SUMMARY,
        "frozen_at": PLANNING_FROZEN_AT,
    }
    for key, expected in required.items():
        if lock.get(key) != expected:
            raise VerificationError(
                f"planning lock {key}: expected={expected!r}, current={lock.get(key)!r}; "
                "use an additive reviewed lock proposal"
            )
    expected_files = lock.get("source_identity_files")
    if not isinstance(expected_files, dict) or not all(
        isinstance(key, str)
        and isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        for key, value in expected_files.items()
    ):
        raise VerificationError("planning lock source_identity_files is missing or malformed")
    if not isinstance(lock.get("source_identity_digest"), str) or re.fullmatch(
        r"[0-9a-f]{64}", lock["source_identity_digest"]
    ) is None:
        raise VerificationError("planning lock source_identity_digest is malformed")
    current_files = planning_source_entries(root)
    differences = source_file_differences(expected_files, current_files)
    expected_digest = lock.get("source_identity_digest")
    current_digest = planning_source_digest(current_files, PLANNING_EVALUATOR_VERSION)
    if expected_digest != current_digest:
        differences.insert(
            0,
            f"planning source_identity_digest: expected={expected_digest} current={current_digest}",
        )
    invariant_fields = {
        "baseline_version",
        "configuration_digest",
        "corpus_digest",
        "fixture_dependency_digest",
        "counter_identity",
        "evaluator_version",
        "python_runtime",
        "python_implementation",
        "python_abi",
        "platform_runtime",
        "runtime_distribution_count",
        "runtime_dependency_digest",
        "pydantic_runtime",
        "evidence_kind",
        "preserved_corpus",
        "promotion_decision",
        "runtime_profile",
        "runtime_identity_scope",
    }
    for key in sorted(invariant_fields):
        if lock.get(key) != previous.get(key):
            raise VerificationError(f"planning lock {key} changed from the pinned predecessor")
    if not str(lock.get("promotion_decision", "")).startswith("non_promotion"):
        raise VerificationError("planning lock promotion_decision must remain non-promotion")
    try:
        from personal_ai.evaluation.context_planner import FIXTURE_PATH
        from personal_ai.evaluation.planning import baseline_planner

        measured_inputs = {
            "configuration_digest": baseline_planner().configuration_digest,
            "corpus_digest": hashlib.sha256(
                (root / "backend/src/personal_ai/evaluation/fixtures/context/planning-heldout-v2.json").read_bytes()
            ).hexdigest(),
            "fixture_dependency_digest": hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
        }
    except (ImportError, OSError, AttributeError) as error:
        raise VerificationError(f"planning measured inputs could not be recomputed: {error}") from None
    for key, actual in measured_inputs.items():
        if lock.get(key) != actual:
            raise VerificationError(
                f"planning lock {key} does not match current measured input: "
                f"expected={actual} current={lock.get(key)}"
            )
    return lock, current_files, differences


def _validate_offline_benchmark(root: Path) -> tuple[dict, dict[str, dict[str, str]], list[str]]:
    path = root / OFFLINE_BENCHMARK_RELATIVE
    manifest = _read_json(path, "offline information handling manifest")
    if type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 3:
        raise VerificationError(
            "offline information handling manifest schema_version: expected=3 "
            f"current={manifest.get('schema_version')!r}"
        )
    expected_fields = {
        "suite",
        "hashes",
        "preregistration",
        "frozen_before_measurement",
        "schema_version",
        "source_contract_version",
        "source_generation",
        "supersedes",
        "source_revision",
        "source_revision_binding",
        "changed_protocols",
        "source_files",
        "legacy_corpus_identity",
    }
    if set(manifest) != expected_fields:
        raise VerificationError(
            f"offline information handling manifest field set mismatch: unexpected={sorted(set(manifest) - expected_fields)} "
            f"missing={sorted(expected_fields - set(manifest))}"
        )
    active_fields = {
        "source_contract_version": OFFLINE_BENCHMARK_SOURCE_CONTRACT,
        "source_generation": OFFLINE_BENCHMARK_SOURCE_GENERATION,
        "supersedes": f"source-manifest-v2-generation-{OFFLINE_BENCHMARK_SOURCE_GENERATION - 1}",
        "frozen_before_measurement": True,
        "suite": "offline-information-handling-v2",
    }
    for key, expected in active_fields.items():
        if manifest.get(key) != expected:
            raise VerificationError(
                f"offline benchmark manifest {key}: expected={expected!r} current={manifest.get(key)!r}"
            )
    expected_preregistration = (
        "Frozen case bytes and scoring rules remain unchanged. The "
        f"source generation {OFFLINE_BENCHMARK_SOURCE_GENERATION} binds restored immutable migration "
        "and fixture bytes and hardened source-contract metadata; earlier measurements do not "
        "validate this generation; no new measurements are claimed; synthetic E1 only; non-promotion."
    )
    if manifest.get("preregistration") != expected_preregistration:
        raise VerificationError(
            "offline benchmark preregistration must preserve frozen evidence and non-promotion"
        )
    if manifest.get("source_revision_binding") != OFFLINE_SOURCE_REVISION_BINDING:
        raise VerificationError("offline benchmark source_revision_binding is invalid")
    current_hashes, current_files = offline_benchmark_source_identity(root)
    expected_hashes = manifest.get("hashes")
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != set(current_hashes):
        raise VerificationError("offline information handling manifest hash keys are malformed")
    differences = []
    for key in sorted(expected_hashes.keys() | current_hashes.keys()):
        before, after = expected_hashes.get(key), current_hashes.get(key)
        if before != after:
            differences.append(f"offline information handling hash {key}: expected={before} current={after}")
    expected_files = manifest.get("source_files")
    if not isinstance(expected_files, dict) or set(expected_files) != set(current_files):
        raise VerificationError("offline information handling manifest source_files field is malformed")
    for package in sorted(expected_files.keys() | current_files.keys()):
        before = expected_files.get(package)
        after = current_files.get(package)
        if not isinstance(before, dict) or after is None:
            differences.append(
                f"offline information handling source file map {package}: expected a file map, current={type(after).__name__}"
            )
            continue
        differences.extend(
            f"offline information handling {package} {item}"
            for item in source_file_differences(before, after, limit=12)
        )
    previous = _read_pinned_json(
        root,
        f"{OFFLINE_BENCHMARK_DIRECTORY}/source-manifest-v2-generation-10.json",
        OFFLINE_GENERATION_10_SHA256,
        "previous offline information handling manifest",
    )
    cases = _read_json(
        root / "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/cases-v2.json",
        "frozen cases",
    )
    expected_legacy_identity = {key: cases.get(key) for key in ("suite", "rubric")}
    if manifest.get("legacy_corpus_identity") != expected_legacy_identity:
        differences.append(
            "offline benchmark legacy_corpus_identity does not match frozen case bytes"
        )
    changed_hashes = sorted(
        key for key in current_hashes if previous.get("hashes", {}).get(key) != current_hashes[key]
    )
    if manifest.get("changed_protocols") != changed_hashes:
        differences.append(
            "offline information handling changed_protocols: "
            f"expected={manifest.get('changed_protocols')} current={changed_hashes}"
        )
    if current_hashes.get("cases") != previous.get("hashes", {}).get("cases"):
        differences.append("offline information handling cases changed from the previous source generation")
    return manifest, current_files, differences


def check(root: Path = ROOT) -> list[str]:
    _verify_historical_bytes(root)
    planning_lock, planning_files, planning_errors = _validate_planning(root)
    benchmark_manifest, benchmark_files, benchmark_errors = _validate_offline_benchmark(root)
    if planning_lock.get("source_revision") != benchmark_manifest.get("source_revision"):
        planning_errors.append(
            "source revision anchors disagree: "
            f"planning={planning_lock.get('source_revision')} offline benchmark={benchmark_manifest.get('source_revision')}"
        )
    _require_ancestor_revision(root, planning_lock.get("source_revision"), "planning lock")
    _require_ancestor_revision(root, benchmark_manifest.get("source_revision"), "offline benchmark")
    _verify_clean_identity_files(root, planning_files, benchmark_files)
    return planning_errors + benchmark_errors


def _next_free_path(root: Path, directory: str, stem: str, start: int) -> tuple[int, Path]:
    generation = start
    while True:
        path = root / directory / f"{stem}{generation}.json"
        if not path.exists():
            return generation, path
        generation += 1


def _write_proposal(previous_path: Path, target_path: Path, candidate: dict, output: Path | None):
    before = previous_path.read_text().splitlines(keepends=True)
    after = (json.dumps(candidate, indent=2, sort_keys=False) + "\n").splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=str(previous_path),
            tofile=str(target_path),
        )
    )
    if output is None:
        print(f"PROPOSAL only; no file written: {target_path.relative_to(ROOT)}")
        print(diff, end="")
        return
    if output.resolve() != target_path.resolve():
        raise VerificationError(f"proposal output must be the next versioned path: {target_path}")
    try:
        with target_path.open("x", encoding="utf-8") as stream:
            json.dump(candidate, stream, indent=2)
            stream.write("\n")
    except FileExistsError:
        raise VerificationError(f"refusing to overwrite existing versioned lock: {target_path}") from None
    print(f"WROTE additive proposal: {target_path.relative_to(ROOT)}")
    print("Review this complete diff before accepting it:")
    print(diff, end="")


def propose_planning(root: Path, output: Path | None = None):
    generation, target = _next_free_path(
        root, PLANNING_DIRECTORY, "planning-baseline-v", PLANNING_LOCK_GENERATION
    )
    previous = root / PLANNING_DIRECTORY / f"planning-baseline-v{generation - 1}.json"
    base = _read_json(previous, "previous planning lock")
    files = planning_source_entries(root)
    revision = _git_revision(root)
    candidate = {
        **base,
        "baseline_lock_version": f"planning-baseline-lock-v{generation}",
        "source_contract_version": PLANNING_SOURCE_CONTRACT,
        "source_identity_files": files,
        "source_identity_digest": planning_source_digest(files, PLANNING_EVALUATOR_VERSION),
        "source_revision": revision,
        "source_revision_binding": PLANNING_SOURCE_REVISION_BINDING,
        "source_change_summary": PLANNING_SOURCE_CHANGE_SUMMARY,
        "runtime_identity_scope": RUNTIME_SCOPE,
        "supersedes": base["baseline_lock_version"],
        "frozen_at": PLANNING_FROZEN_AT,
    }
    if output is None:
        _write_proposal(previous, target, candidate, None)
    else:
        _write_proposal(previous, target, candidate, output)


def propose_offline_benchmark(root: Path, output: Path | None = None):
    generation, target = _next_free_path(
        root, OFFLINE_BENCHMARK_DIRECTORY, "source-manifest-v2-generation-", OFFLINE_BENCHMARK_SOURCE_GENERATION
    )
    previous_path = root / OFFLINE_BENCHMARK_DIRECTORY / f"source-manifest-v2-generation-{generation - 1}.json"
    previous = _read_json(previous_path, "previous offline information handling manifest")
    hashes, files = offline_benchmark_source_identity(root)
    changed = sorted(
        key for key in hashes if previous.get("hashes", {}).get(key) != hashes[key]
    )
    candidate = {
        "frozen_before_measurement": True,
        "hashes": hashes,
        "preregistration": (
            "Frozen case bytes and scoring rules remain unchanged. The "
            f"source generation {generation} binds restored immutable migration and fixture bytes "
            "and hardened source-contract metadata; earlier measurements do not validate this "
            "generation; no new measurements are claimed; synthetic E1 only; non-promotion."
        ),
        "schema_version": 3,
        "source_contract_version": OFFLINE_BENCHMARK_SOURCE_CONTRACT,
        "source_generation": generation,
        "supersedes": f"source-manifest-v2-generation-{generation - 1}",
        "source_revision": _git_revision(root),
        "source_revision_binding": OFFLINE_SOURCE_REVISION_BINDING,
        "changed_protocols": changed,
        "source_files": files,
        "legacy_corpus_identity": {
            key: value
            for key, value in _read_json(
                root / "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/cases-v2.json",
                "frozen cases",
            ).items()
            if key in {"suite", "rubric"}
        },
        "suite": "offline-information-handling-v2",
    }
    if output is None:
        _write_proposal(previous_path, target, candidate, None)
    else:
        _write_proposal(previous_path, target, candidate, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify active identities read-only")
    mode.add_argument("--propose-planning", action="store_true", help="propose the next planning lock")
    mode.add_argument("--propose-offline-benchmark", action="store_true", help="propose the next offline benchmark source manifest")
    parser.add_argument("--output", type=Path, help="write a new versioned proposal; refuses overwrite")
    args = parser.parse_args(argv)
    if args.output and not (args.propose_planning or args.propose_offline_benchmark):
        parser.error("--output is valid only with an explicit proposal command")
    try:
        if args.propose_planning:
            propose_planning(ROOT, args.output)
            return 0
        if args.propose_offline_benchmark:
            propose_offline_benchmark(ROOT, args.output)
            return 0
        if not args.check:
            parser.error("choose --check, --propose-planning, or --propose-offline-benchmark")
        errors = check(ROOT)
        if errors:
            for error in errors:
                print(f"FAIL: {error}", file=sys.stderr)
            print("Current-source identities do not match; inspect the paths, then propose a new version.", file=sys.stderr)
            return 1
    except VerificationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"FAIL: source contract verification could not complete ({type(error).__name__}): {error}", file=sys.stderr)
        return 1
    print(
        "PORTABLE_SOURCE=PASS "
        f"planning={PLANNING_LOCK_FILENAME} offline_benchmark={OFFLINE_BENCHMARK_MANIFEST_FILENAME}; "
        "STRICT_HISTORICAL_RUNTIME_REPLAY=NOT_RUN; INSTALLED_NATIVE_CAPABILITY=NOT_RUN"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
