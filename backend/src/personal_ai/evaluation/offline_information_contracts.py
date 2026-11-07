"""Closed offline information handling v2 inputs and content-free observations."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import importlib.util
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.evaluation.source_contracts import (
    OFFLINE_BENCHMARK_MANIFEST_FILENAME,
    OFFLINE_BENCHMARK_PROTOCOL_FILES,
    OFFLINE_BENCHMARK_SOURCE_CONTRACT,
    source_file_differences,
)

PACKAGE = importlib.resources.files("personal_ai.evaluation")
FAMILIES = ("one_app", "profile", "memory", "branch", "research", "retrieval", "provider", "replay")
SOURCE_BYTE_LIMIT = 8192
MEMORY_COMMANDS = ("make backend-lint", "make backend-test-offline", "make memory-eval")
V2_PROTOCOL_FILES = OFFLINE_BENCHMARK_PROTOCOL_FILES
PROTOCOL_MANIFEST = OFFLINE_BENCHMARK_MANIFEST_FILENAME
OPTIONAL_PACKAGES = {
    "reading_logbook_client": ("reading_logbook", "reading-logbook-client"),
    "reading_logbook_host": ("reading_logbook_host", "reading-logbook-host"),
}


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Task(Closed):
    family: Literal[
        "one_app", "profile", "memory", "branch", "research", "retrieval", "provider", "replay"
    ]
    variant: Literal[
        "current",
        "irrelevant",
        "revoke",
        "edit",
        "forget",
        "recall",
        "collision",
        "expiry",
        "conflict",
        "outage",
        "alternate",
        "missing",
        "supersede",
        "long",
    ]
    subject: str = Field(pattern=r"^[a-z]{4,16}$")
    value: str = Field(pattern=r"^[a-z]{3,16}$")
    distractor: str = Field(pattern=r"^[a-z]{3,16}$")
    prompt_style: Literal["lookup", "describe", "recorded", "pair"] = "lookup"


class Oracle(Closed):
    baseline: Literal[
        "correct", "unknown", "denied", "completed", "forgotten", "conflict", "failed"
    ]
    candidate: Literal[
        "correct", "unknown", "denied", "completed", "forgotten", "conflict", "failed"
    ]
    forbidden_actions: tuple[
        Literal["external_send", "write_tool", "duplicate_effect", "stale_disclosure"], ...
    ]
    citation_required: bool


class Case(Closed):
    case_id: str = Field(pattern=r"^P6(?:V2)?-[A-H][1-4]$")
    lineage: str = Field(pattern=r"^[a-z]{4,30}$")
    source_configuration: str = Field(pattern=r"^[a-z]{4,30}$")
    split: Literal["calibration", "heldout"]
    operation: Literal["one_turn", "transition"]
    rights_event: Literal["none", "revoke", "edit", "expire"]
    provenance: Literal["authored_synthetic_v1", "authored_synthetic_v2"]
    task: Task
    oracle: Oracle


class Corpus(Closed):
    suite: Literal["pi6-offline-v1", "pi6-offline-v2"]
    rubric: Literal["pi6-rubric-v1", "pi6-rubric-v2"]
    seed: Literal[61, 62]
    input_cap: Literal[32768]
    output_cap: Literal[256]
    deadline_seconds: Literal[5]
    source_bytes: Literal[8192]
    cases: tuple[Case, ...] = Field(min_length=32, max_length=32)

    @model_validator(mode="after")
    def groups(self):
        if len({c.case_id for c in self.cases}) != 32:
            raise ValueError("duplicate_case")
        for attr in ("lineage", "source_configuration"):
            groups = {}
            for c in self.cases:
                groups.setdefault(getattr(c, attr), set()).add(c.split)
            if any(len(s) != 1 for s in groups.values()):
                raise ValueError("group_split_leakage")
        for family in FAMILIES:
            cases = [c for c in self.cases if c.task.family == family]
            if len(cases) != 4 or sum(c.split == "heldout" for c in cases) != 2:
                raise ValueError("family_split")
            if len({c.lineage for c in cases}) < 2 or {c.operation for c in cases} != {
                "one_turn",
                "transition",
            }:
                raise ValueError("family_variants")
        expected_suite = "pi6-offline-v2" if self.seed == 62 else "pi6-offline-v1"
        expected_rubric = "pi6-rubric-v2" if self.seed == 62 else "pi6-rubric-v1"
        expected_case_prefix = "P6V2" if self.seed == 62 else "P6"
        if self.suite != expected_suite or self.rubric != expected_rubric:
            raise ValueError("suite_version_mismatch")
        if any(not case.case_id.startswith(f"{expected_case_prefix}-") for case in self.cases):
            raise ValueError("case_id_version_mismatch")
        if any(
            c.provenance
            != ("authored_synthetic_v2" if self.seed == 62 else "authored_synthetic_v1")
            for c in self.cases
        ):
            raise ValueError("fixture_provenance_mismatch")
        if self.seed == 62 and len({case.task.prompt_style for case in self.cases}) < 3:
            raise ValueError("v2_prompt_diversity")
        return self


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def memory_command(value: str) -> str:
    return MEMORY_COMMANDS[sum(value.encode("ascii")) % len(MEMORY_COMMANDS)]


def _package_tree_digest(package_name: str, *, exclude: tuple[str, ...] = ()) -> str | None:
    spec = importlib.util.find_spec(package_name)
    if spec is None or not spec.submodule_search_locations:
        return None
    root = Path(next(iter(spec.submodule_search_locations))).resolve()
    entries = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if (
            path.is_file()
            and path.suffix in {".py", ".json"}
            and "__pycache__" not in path.parts
            and relative not in exclude
            and not (
                package_name == "personal_ai"
                and relative.startswith("evaluation/fixtures/offline_information_handling/")
                and (
                    re.fullmatch(
                        r"evaluation/fixtures/offline_information_handling/manifest-v[12]\.json",
                        relative,
                    )
                    or re.fullmatch(
                        r"evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-\d+\.json",
                        relative,
                    )
                )
            )
        ):
            entries.append((relative, sha(path.read_bytes())))
    return sha(canonical(entries).encode())


def _package_tree_entries(package_name: str) -> dict[str, str] | None:
    spec = importlib.util.find_spec(package_name)
    if spec is None or not spec.submodule_search_locations:
        return None
    root = Path(next(iter(spec.submodule_search_locations))).resolve()
    entries = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if (
            not path.is_file()
            or path.suffix not in {".py", ".json"}
            or "__pycache__" in path.parts
        ):
            continue
        if (
            package_name == "personal_ai"
            and relative.startswith("evaluation/fixtures/offline_information_handling/")
            and (
                re.fullmatch(
                    r"evaluation/fixtures/offline_information_handling/manifest-v[12]\.json",
                    relative,
                )
                or re.fullmatch(
                    r"evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-\d+\.json",
                    relative,
                )
            )
        ):
            continue
        entries[relative] = sha(path.read_bytes())
    return entries


def current_protocol_hashes() -> tuple[dict[str, str], tuple[str, ...]]:
    hashes = {}
    for key, name in V2_PROTOCOL_FILES.items():
        hashes[key] = sha(PACKAGE.joinpath(name).read_bytes())
    hashes["core_runtime"] = _package_tree_digest("personal_ai")
    missing = []
    for key, (module, distribution) in OPTIONAL_PACKAGES.items():
        digest = _package_tree_digest(module)
        if digest is None:
            missing.append(distribution)
        else:
            hashes[key] = digest
    return hashes, tuple(missing)


def _read_manifest(name: str) -> dict:
    value = json.loads(PACKAGE.joinpath("fixtures", "offline_information_handling", name).read_bytes())
    legacy = {"suite", "hashes", "preregistration", "frozen_before_measurement"}
    versioned = legacy | {
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
    if value.get("schema_version") == 3:
        valid_shape = set(value) == versioned
        valid_contract = (
            value.get("source_contract_version") == OFFLINE_BENCHMARK_SOURCE_CONTRACT
            and type(value.get("source_generation")) is int
            and value.get("source_generation") >= 10
            and value.get("supersedes")
            == f"source-manifest-v2-generation-{value.get('source_generation') - 1}"
            and isinstance(value.get("source_revision"), str)
            and bool(value.get("source_revision_binding"))
            and isinstance(value.get("changed_protocols"), list)
            and isinstance(value.get("source_files"), dict)
            and isinstance(value.get("legacy_corpus_identity"), dict)
            and value.get("suite") == "offline-information-handling-v2"
        )
    else:
        valid_shape = set(value) == legacy
        valid_contract = True
    if not valid_shape or not valid_contract or value["frozen_before_measurement"] is not True:
        raise ValueError("manifest_invalid")
    return value


def load_historical_v1() -> tuple[Corpus, dict]:
    """Read preserved v1 cases; do not treat the v1 manifest as a current protocol."""
    raw = PACKAGE.joinpath("fixtures", "offline_information_handling", "cases-v1.json").read_bytes()
    manifest = _read_manifest("manifest-v1.json")
    corpus = Corpus.model_validate_json(raw)
    if corpus.suite != manifest["suite"] or manifest["hashes"].get("cases") != sha(raw):
        raise ValueError("historical_v1_fixture_identity_mismatch")
    return corpus, manifest


def load_corpus() -> tuple[Corpus, dict]:
    """Load v2 and bind all locally available protocol and consumer sources."""
    raw = PACKAGE.joinpath("fixtures", "offline_information_handling", "cases-v2.json").read_bytes()
    manifest = _read_manifest(PROTOCOL_MANIFEST)
    current, missing = current_protocol_hashes()
    corpus = Corpus.model_validate_json(raw)
    if (
        manifest.get("suite") != "offline-information-handling-v2"
        or manifest.get("legacy_corpus_identity")
        != {"suite": corpus.suite, "rubric": corpus.rubric}
        or manifest["hashes"].get("cases") != sha(raw)
    ):
        raise ValueError("frozen_identity_mismatch")
    if any(manifest["hashes"].get(key) != value for key, value in current.items()):
        raise ValueError("frozen_protocol_mismatch")
    required = {"cases"} | set(V2_PROTOCOL_FILES) | set(OPTIONAL_PACKAGES) | {"core_runtime"}
    if set(manifest["hashes"]) != required:
        raise ValueError("frozen_manifest_shape_mismatch")
    if manifest.get("schema_version") == 3:
        for key, module in {
            "core_runtime": "personal_ai",
            "reading_logbook_client": "reading_logbook",
            "reading_logbook_host": "reading_logbook_host",
        }.items():
            actual = _package_tree_entries(module)
            if actual is None:
                continue
            expected = manifest["source_files"].get(key)
            if not isinstance(expected, dict):
                raise ValueError(f"frozen_source_files_missing:{key}")  # noqa: TRY004
            differences = source_file_differences(expected, actual, limit=1)
            if differences:
                raise ValueError(f"frozen_source_file_mismatch:{key}:{differences[0]}")
    if not manifest["preregistration"]:
        raise ValueError("frozen_identity_mismatch")
    return corpus, {**manifest, "missing_dependencies": list(missing)}


class Observation(Closed):
    outcome: Literal["correct", "unknown", "denied", "completed", "forgotten", "conflict", "failed"]
    hard_valid: bool
    factual: bool | None = None
    citation: bool | None = None
    evidence_type: Literal[
        "answer_value",
        "no_evidence",
        "explicit_denial",
        "forget_receipt",
        "unsupported_mutation",
        "idempotency_conflict",
        "provider_rejection",
        "provider_failure",
        "retrieval_provenance",
        "research_support",
        "none",
    ] = "none"
    operation_status: (
        Literal[
            "found",
            "no_match",
            "completed",
            "applied",
            "forbidden_or_not_found",
            "unsupported_evidence_source",
            "conflict",
            "provider_missing",
            "provider_failed",
        ]
        | None
    ) = None
    answer_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    evidence_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_dependencies: int | None = Field(default=None, ge=0, le=64)
    input_units: int | None = Field(default=None, ge=0)
    output_units: int | None = Field(default=None, ge=0)
    tool_units: int | None = Field(default=None, ge=0, le=64)
    unnecessary_context: bool | None = None
    token_confidence: Literal["authoritative_local_bytes", "estimated", "unknown"] = "unknown"
    status: Literal[
        "measured", "blocked_capability", "denied_policy", "not_applicable", "unmeasured"
    ] = "measured"
    ineligibility: (
        Literal["missing_optional_host", "outside_task_scope", "suite_deadline"] | None
    ) = None
    error: Literal[
        "none",
        "offline_failure",
        "budget_exceeded",
        "operation_timeout",
        "native_fence_missing",
        "network_attempt",
        "worker_crash",
    ] = "none"
