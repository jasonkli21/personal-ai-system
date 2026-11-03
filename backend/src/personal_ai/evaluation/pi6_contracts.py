"""Closed PI-6 v2 inputs and content-free observations."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import importlib.util
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PACKAGE = importlib.resources.files("personal_ai.evaluation")
FAMILIES = ("one_app", "profile", "memory", "branch", "research", "retrieval", "provider", "replay")
SOURCE_BYTE_LIMIT = 8192
MEMORY_COMMANDS = ("make backend-lint", "make backend-test-offline", "make memory-eval")
V2_PROTOCOL_FILES = {
    "scoring": "pi6_scoring.py",
    "contracts": "pi6_contracts.py",
    "driver": "pi6_driver.py",
    "runner": "pi6.py",
    "http": "pi6_http.py",
    "audit": "pi6_audit.py",
}
PROTOCOL_MANIFEST = "manifest-v2-source-2.json"
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
        expected = "pi6-offline-v2" if self.seed == 62 else "pi6-offline-v1"
        expected_rubric = "pi6-rubric-v2" if self.seed == 62 else "pi6-rubric-v1"
        if self.suite != expected or self.rubric != expected_rubric:
            raise ValueError("suite_version_mismatch")
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
        ):
            entries.append((relative, sha(path.read_bytes())))
    return sha(canonical(entries).encode())


def current_protocol_hashes() -> tuple[dict[str, str], tuple[str, ...]]:
    hashes = {}
    for key, name in V2_PROTOCOL_FILES.items():
        hashes[key] = sha(PACKAGE.joinpath(name).read_bytes())
    hashes["core_runtime"] = _package_tree_digest(
        "personal_ai", exclude=(
            "evaluation/fixtures/pi6/manifest-v2.json",
            f"evaluation/fixtures/pi6/{PROTOCOL_MANIFEST}",
        ),
    )
    missing = []
    for key, (module, distribution) in OPTIONAL_PACKAGES.items():
        digest = _package_tree_digest(module)
        if digest is None:
            missing.append(distribution)
        else:
            hashes[key] = digest
    return hashes, tuple(missing)


def _read_manifest(name: str) -> dict:
    value = json.loads(PACKAGE.joinpath("fixtures", "pi6", name).read_bytes())
    expected = {"suite", "hashes", "preregistration", "frozen_before_measurement"}
    if set(value) != expected or value["frozen_before_measurement"] is not True:
        raise ValueError("manifest_invalid")
    return value


def load_historical_v1() -> tuple[Corpus, dict]:
    """Read preserved v1 cases; do not treat the v1 manifest as a current protocol."""
    raw = PACKAGE.joinpath("fixtures", "pi6", "cases-v1.json").read_bytes()
    manifest = _read_manifest("manifest-v1.json")
    if manifest["suite"] != "pi6-offline-v1" or manifest["hashes"].get("cases") != sha(raw):
        raise ValueError("historical_v1_fixture_identity_mismatch")
    return Corpus.model_validate_json(raw), manifest


def load_corpus() -> tuple[Corpus, dict]:
    """Load v2 and bind all locally available protocol and consumer sources."""
    raw = PACKAGE.joinpath("fixtures", "pi6", "cases-v2.json").read_bytes()
    manifest = _read_manifest(PROTOCOL_MANIFEST)
    current, missing = current_protocol_hashes()
    if manifest["suite"] != "pi6-offline-v2" or manifest["hashes"].get("cases") != sha(raw):
        raise ValueError("frozen_identity_mismatch")
    if any(manifest["hashes"].get(key) != value for key, value in current.items()):
        raise ValueError("frozen_protocol_mismatch")
    required = {"cases"} | set(V2_PROTOCOL_FILES) | set(OPTIONAL_PACKAGES) | {"core_runtime"}
    if set(manifest["hashes"]) != required:
        raise ValueError("frozen_manifest_shape_mismatch")
    corpus = Corpus.model_validate_json(raw)
    if corpus.suite != manifest["suite"] or not manifest["preregistration"]:
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
