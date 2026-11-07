"""Deterministic source closures for current evaluation contracts.

The file identities here contain source and frozen-input bytes only. Runtime
fingerprints and historical replay provenance are recorded separately.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PLANNING_SOURCE_CONTRACT = "planning-source-closure-v1"
OFFLINE_BENCHMARK_SOURCE_CONTRACT = "offline-benchmark-source-closure-v1"
PLANNING_LOCK_GENERATION = 36
OFFLINE_BENCHMARK_SOURCE_GENERATION = 10
PLANNING_LOCK_FILENAME = f"planning-baseline-v{PLANNING_LOCK_GENERATION}.json"
OFFLINE_BENCHMARK_MANIFEST_FILENAME = (
    f"source-manifest-v2-generation-{OFFLINE_BENCHMARK_SOURCE_GENERATION}.json"
)
PLANNING_EVALUATOR_VERSION = "planning-evaluator-v8"
OFFLINE_BENCHMARK_PROTOCOL_FILES = {
    "scoring": "offline_information_scoring.py",
    "contracts": "offline_information_contracts.py",
    "driver": "offline_task_driver.py",
    "runner": "offline_information_handling.py",
    "http": "loopback_synthetic_host.py",
    "audit": "evaluation_effect_audit.py",
}
OFFLINE_BENCHMARK_OPTIONAL_SOURCES = {
    "reading_logbook_client": "examples/reading-logbook/client/src/reading_logbook",
    "reading_logbook_host": "examples/reading-logbook/host/src/reading_logbook_host",
}

# These inputs predate the recursive closure. Keeping them explicit makes a
# deleted required input fail with its path instead of silently shrinking it.
PLANNING_REQUIRED_PATHS = (
    "backend/src/personal_ai/applications/contracts.py",
    "backend/src/personal_ai/applications/registry.py",
    "backend/src/personal_ai/auth/scope.py",
    "backend/src/personal_ai/context/assembler.py",
    "backend/src/personal_ai/context/adapters.py",
    "backend/src/personal_ai/context/authorization.py",
    "backend/src/personal_ai/context/builder.py",
    "backend/src/personal_ai/context/deployment.py",
    "backend/src/personal_ai/context/planner.py",
    "backend/src/personal_ai/context/planning_experiment.py",
    "backend/src/personal_ai/context/providers.py",
    "backend/src/personal_ai/context/runtime.py",
    "backend/src/personal_ai/context/traces.py",
    "backend/src/personal_ai/contracts/context_references.py",
    "backend/src/personal_ai/federation/broker.py",
    "backend/src/personal_ai/federation/contracts.py",
    "backend/src/personal_ai/federation/deployment.py",
    "backend/src/personal_ai/federation/service.py",
    "backend/src/personal_ai/evaluation/context_planner.py",
    "backend/src/personal_ai/evaluation/planning_fixtures.py",
    "backend/src/personal_ai/evaluation/planning_promotion.py",
    "backend/src/personal_ai/evaluation/planning_quality.py",
    "backend/src/personal_ai/evaluation/planning.py",
    "backend/src/personal_ai/evaluation/provider_matrix.py",
    "backend/src/personal_ai/evaluation/provider_matrix_contracts.py",
    "backend/src/personal_ai/settings.py",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/src/personal_ai/evaluation/fixtures/context/context-plan-fixtures.json",
    "backend/src/personal_ai/evaluation/fixtures/context/planning-heldout-v2.json",
)


class SourceContractError(ValueError):
    """A source closure could not be read or normalized safely."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _planning_excluded(relative: str) -> bool:
    path = Path(relative)
    if "__pycache__" in path.parts or path.suffix == ".pyc" or path.name == ".DS_Store":
        return True
    if path.name.startswith("planning-baseline-"):
        return True
    if "evaluation/fixtures/offline_information_handling" in relative.replace("\\", "/"):
        return bool(
            re.fullmatch(
                r"(?:manifest-v[12]|source-manifest-v2-generation-\d+)\.json", path.name
            )
        )
    return False


def planning_source_paths(repository_root: Path) -> tuple[str, ...]:
    root = repository_root.resolve()
    package = root / "backend/src/personal_ai"
    if not package.is_dir():
        raise SourceContractError("missing source root: backend/src/personal_ai")
    paths = set(PLANNING_REQUIRED_PATHS)
    for path in package.rglob("*"):
        if path.is_symlink():
            raise SourceContractError(
                f"source closure contains unsupported symlink: {path.relative_to(root).as_posix()}"
            )
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if not _planning_excluded(relative):
                paths.add(relative)
    return tuple(sorted(paths))


def planning_source_entries(
    repository_root: Path, *, paths: tuple[str, ...] | None = None
) -> dict[str, str]:
    root = repository_root.resolve()
    entries = {}
    for relative in paths if paths is not None else planning_source_paths(root):
        path = root / relative
        try:
            entries[relative] = sha(path.read_bytes())
        except OSError as error:
            raise SourceContractError(f"cannot read required source {relative}: {error}") from None
    return entries


def planning_source_digest(entries: dict[str, str], evaluator_version: str) -> str:
    identity = {**entries, "evaluator_version": evaluator_version}
    return sha(canonical(identity).encode())


def package_tree_entries(repository_root: Path, package_path: str) -> dict[str, str]:
    root = repository_root.resolve()
    package = root / package_path
    if not package.is_dir():
        raise SourceContractError(f"missing package source root: {package_path}")
    entries = {}
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise SourceContractError(
                f"package source contains unsupported symlink: {path.relative_to(root).as_posix()}"
            )
        relative = path.relative_to(package).as_posix()
        if (
            not path.is_file()
            or path.suffix not in {".py", ".json"}
            or "__pycache__" in path.parts
        ):
            continue
        if (
            package_path.endswith("backend/src/personal_ai")
            and path.parent.name == "offline_information_handling"
            and re.fullmatch(
                r"(?:manifest-v[12]|source-manifest-v2-generation-\d+)\.json", path.name
            )
        ):
            continue
        try:
            entries[relative] = sha(path.read_bytes())
        except OSError as error:
            raise SourceContractError(
                f"cannot read package source {path.relative_to(root).as_posix()}: {error}"
            ) from None
    return entries


def package_tree_digest(entries: dict[str, str]) -> str:
    return sha(canonical(sorted(entries.items())).encode())


def offline_benchmark_source_identity(
    repository_root: Path,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    root = repository_root.resolve()
    package = "backend/src/personal_ai"
    evaluation = root / package / "evaluation"
    hashes = {
        key: sha((evaluation / path).read_bytes())
        for key, path in OFFLINE_BENCHMARK_PROTOCOL_FILES.items()
    }
    cases_path = evaluation / "fixtures/offline_information_handling/cases-v2.json"
    hashes["cases"] = sha(cases_path.read_bytes())
    files = {"core_runtime": package_tree_entries(root, package)}
    hashes["core_runtime"] = package_tree_digest(files["core_runtime"])
    for key, package_path in OFFLINE_BENCHMARK_OPTIONAL_SOURCES.items():
        files[key] = package_tree_entries(root, package_path)
        hashes[key] = package_tree_digest(files[key])
    return hashes, files


def source_file_differences(
    expected: dict[str, str], current: dict[str, str], *, limit: int = 12
) -> list[str]:
    differences = []
    for relative in sorted(expected.keys() | current.keys()):
        before = expected.get(relative)
        after = current.get(relative)
        if before == after:
            continue
        if before is None:
            differences.append(f"unexpected source {relative}: current={after}")
        elif after is None:
            differences.append(f"missing source {relative}: expected={before}")
        else:
            differences.append(f"changed source {relative}: expected={before} current={after}")
        if len(differences) >= limit:
            remaining = sum(
                expected.get(path) != current.get(path)
                for path in sorted(expected.keys() | current.keys())
                if path > relative
            )
            if remaining:
                differences.append(f"... and {remaining} more source path difference(s)")
            break
    return differences
