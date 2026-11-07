"""Read-only current-source verification and explicit additive lock proposals."""

from __future__ import annotations

import argparse
import difflib
import json
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
    previous_path = root / PLANNING_DIRECTORY / f"planning-baseline-v{PLANNING_LOCK_GENERATION - 1}.json"
    previous = _read_json(previous_path, "previous planning lock")
    if lock.get("counter_identity") != previous.get("counter_identity"):
        raise VerificationError(
            "planning lock counter_identity changed without a versioned metric migration"
        )
    required = {
        "baseline_lock_version": f"planning-baseline-lock-v{PLANNING_LOCK_GENERATION}",
        "source_contract_version": PLANNING_SOURCE_CONTRACT,
        "evaluator_version": PLANNING_EVALUATOR_VERSION,
        "runtime_identity_scope": RUNTIME_SCOPE,
    }
    for key, expected in required.items():
        if lock.get(key) != expected:
            raise VerificationError(
                f"planning lock {key}: expected={expected!r}, current={lock.get(key)!r}; "
                "use an additive reviewed lock proposal"
            )
    expected_files = lock.get("source_identity_files")
    if not isinstance(expected_files, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in expected_files.items()
    ):
        raise VerificationError("planning lock source_identity_files is missing or malformed")
    current_files = planning_source_entries(root)
    differences = source_file_differences(expected_files, current_files)
    expected_digest = lock.get("source_identity_digest")
    current_digest = planning_source_digest(current_files, PLANNING_EVALUATOR_VERSION)
    if expected_digest != current_digest:
        differences.insert(
            0,
            f"planning source_identity_digest: expected={expected_digest} current={current_digest}",
        )
    return lock, current_files, differences


def _validate_offline_benchmark(root: Path) -> tuple[dict, dict[str, dict[str, str]], list[str]]:
    path = root / OFFLINE_BENCHMARK_RELATIVE
    manifest = _read_json(path, "offline information handling manifest")
    if manifest.get("schema_version") != 3:
        raise VerificationError("offline information handling manifest uses an unsupported source contract schema")
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
    if (
        manifest.get("source_contract_version") != OFFLINE_BENCHMARK_SOURCE_CONTRACT
        or manifest.get("source_generation") != OFFLINE_BENCHMARK_SOURCE_GENERATION
        or manifest.get("supersedes") != f"source-manifest-v2-generation-{OFFLINE_BENCHMARK_SOURCE_GENERATION - 1}"
        or manifest.get("frozen_before_measurement") is not True
        or manifest.get("suite") != "offline-information-handling-v2"
    ):
        raise VerificationError("offline benchmark active manifest version or source contract is invalid")
    current_hashes, current_files = offline_benchmark_source_identity(root)
    expected_hashes = manifest.get("hashes")
    if not isinstance(expected_hashes, dict):
        raise VerificationError("offline information handling manifest hashes field is malformed")
    differences = []
    for key in sorted(expected_hashes.keys() | current_hashes.keys()):
        before, after = expected_hashes.get(key), current_hashes.get(key)
        if before != after:
            differences.append(f"offline information handling hash {key}: expected={before} current={after}")
    expected_files = manifest.get("source_files")
    if not isinstance(expected_files, dict):
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
    previous_path = root / OFFLINE_BENCHMARK_DIRECTORY / f"source-manifest-v2-generation-{OFFLINE_BENCHMARK_SOURCE_GENERATION - 1}.json"
    previous = _read_json(previous_path, "previous offline information handling manifest")
    cases = _read_json(
        root / "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/cases-v2.json",
        "frozen cases",
    )
    expected_legacy_identity = {key: cases.get(key) for key in ("suite", "rubric")}
    if manifest.get("legacy_corpus_identity") != expected_legacy_identity:
        differences.append("offline benchmark legacy corpus identity does not match frozen case bytes")
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
    planning_lock, planning_files, planning_errors = _validate_planning(root)
    benchmark_manifest, benchmark_files, benchmark_errors = _validate_offline_benchmark(root)
    if planning_lock.get("source_revision") != benchmark_manifest.get("source_revision"):
        planning_errors.append(
            "source revision anchors disagree: "
            f"planning={planning_lock.get('source_revision')} offline benchmark={benchmark_manifest.get('source_revision')}"
        )
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
        "source_revision_binding": (
            "Content identity is the per-file source map and digest; source_revision is the "
            "reviewed ancestry anchor, not a substitute for the content check."
        ),
        "source_change_summary": (
            "Additive current-source closure and field diagnostics; frozen configuration, corpus, "
            "fixture bytes, evaluator behavior, strict replay runtime fingerprint and non-promotion "
            "are carried forward unchanged."
        ),
        "runtime_identity_scope": RUNTIME_SCOPE,
        "supersedes": base["baseline_lock_version"],
        "frozen_at": "2026-11-06",
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
            f"Frozen case bytes and scoring rules remain unchanged. The expected synthetic "
            f"evidence fingerprint and renamed evaluator modules receive new source identities "
            f"in source generation {generation}; earlier measurements do not validate this "
            "generation, "
            "and no new measurements are claimed. Synthetic E1 only; non-promotion."
        ),
        "schema_version": 3,
        "source_contract_version": OFFLINE_BENCHMARK_SOURCE_CONTRACT,
        "source_generation": generation,
        "supersedes": f"source-manifest-v2-generation-{generation - 1}",
        "source_revision": _git_revision(root),
        "source_revision_binding": (
            "Per-file source SHA-256 values and aggregate hashes identify the bytes; the revision "
            "is provenance and an ancestry anchor only. The descriptive-path migration does not "
            "reclassify historical benchmark measurements as evidence for this generation."
        ),
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
        "SOURCE_CONTRACT=PASS "
        f"planning={PLANNING_LOCK_FILENAME} offline_benchmark={OFFLINE_BENCHMARK_MANIFEST_FILENAME} "
        "runtime=not_checked historical_replay=not_run"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
