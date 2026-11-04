"""Sealed source-only task package; scorer payloads have a separate loader."""

from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from typing import Literal

from pydantic import Field, model_validator

from personal_ai.memory.research.contracts import ResearchRecord, ResearchScope
from personal_ai.memory.research.experiments.artifacts import parse_json
from personal_ai.memory.research.experiments.contracts import (
    Digest,
    Identity,
    Record,
    TaskManifest,
    digest,
)

SOURCE_SHA256 = "da7ccb44d7cf6076d33d4a14dfda04b2f907d5bb529fe05ee177bfc1abae8d6c"
SCORER_SHA256 = "69a3f4d91335ec3f72e9b8e5188b1cc221d7c5bd26bb72aaabff746fdf2dffeb"
FIXTURE_DIR = files("personal_ai.evaluation").joinpath("fixtures/memory")


class Mutation(Record):
    action: Literal[
        "revision",
        "project_denied",
        "forget",
        "owner",
        "workspace",
        "application",
        "actor",
        "forget_restore",
        "regrant",
        "advance",
        "revoke_grant",
        "tight",
        "cancel",
        "timeout",
        "partial",
        "stale",
        "refresh_interrupted",
    ]
    target: Identity


class Fault(Mutation):
    stage: Literal["budget", "ranked", "packed", "consume"]


class Step(Record):
    session: Identity
    offset: int = Field(ge=0, le=3)
    phase: Literal["learn", "change", "task_b"]
    events: tuple[Mutation, ...] = Field(max_length=4)


class SourceTask(Record):
    id: Identity
    subject: Identity
    scope: ResearchScope
    project: Literal["repo-alpha"]
    query: str = Field(min_length=1, max_length=2048)
    records: tuple[ResearchRecord, ...] = Field(min_length=1, max_length=100)
    profile: Literal["canonical_knowledge", "navigation_fixture"]
    steps: tuple[Step, ...] = Field(min_length=3, max_length=4)
    fault: Fault | None
    current_hint: str | None = Field(max_length=200)
    current_action: str | None = Field(max_length=200)
    retry: bool
    evidence_outcome: Literal["success", "forged", "unknown"]

    @model_validator(mode="after")
    def trajectory(self):
        if (
            tuple(s.offset for s in self.steps) != tuple(range(len(self.steps)))
            or len({s.session for s in self.steps}) < 2
            or tuple(s.phase for s in self.steps[:3]) != ("learn", "change", "task_b")
            or len({r.id for r in self.records}) != len(self.records)
        ):
            raise ValueError("trajectory_invalid")
        return self

    def manifest(self):
        return TaskManifest(
            task_id=self.id,
            subject=self.subject,
            workspace=self.scope.workspace_id,
            actor=self.scope.acting_user_id,
            sessions=tuple(s.session for s in self.steps),
            temporal_order=tuple(s.offset for s in self.steps),
            permission_timeline_sha256=digest([s.model_dump() for s in self.steps]),
            source_timeline_sha256=digest([r.model_dump(mode="json") for r in self.records]),
            scorer_reference=SCORER_SHA256,
        )


class SourceCorpus(Record):
    # The complete corpus has its own byte bound, beyond an individual record.
    version: Literal["memory-longitudinal-sources-v1"]
    tasks: tuple[SourceTask, ...] = Field(min_length=48, max_length=96)

    @model_validator(mode="after")
    def unique(self):
        if len({t.id for t in self.tasks}) != len(self.tasks):
            raise ValueError("duplicate_task")
        return self

    @model_validator(mode="after")
    def bounded(self):
        # Override the per-record 64 KiB limit for this bounded aggregate only.
        if len(self.model_dump_json().encode()) > 262144:
            raise ValueError("corpus_capacity")
        return self


def source_bytes():
    return FIXTURE_DIR.joinpath("memory-longitudinal-sources-v1.json").read_bytes()


@lru_cache(maxsize=2)
def parse_sources(payload: bytes, expected_digest: str):
    if len(payload) > 262144 or sha256(payload).hexdigest() != expected_digest:
        raise ValueError("source_identity_or_capacity")
    corpus = SourceCorpus.model_validate(parse_json(payload, limit=262144))
    for task in corpus.tasks:
        task.manifest()
    return corpus


def load_sources():
    return parse_sources(source_bytes(), SOURCE_SHA256)


class ChallengeSubmission(Record):
    version: Literal["memory-longitudinal-challenge-v1"] = "memory-longitudinal-challenge-v1"
    source_sha256: Digest
    scorer_sha256: Digest
    custodian: Identity
    parent_dataset: Digest
    author_visibility: Literal["author_visible"] = "author_visible"
    independent_acceptance: Literal[False] = False


class ChallengeCorpus(SourceCorpus):
    tasks: tuple[SourceTask, ...] = Field(min_length=12, max_length=96)


def inspect_challenge(submission, payload: bytes):
    """Validate an untrusted submission; never installs it as a trusted source."""
    submission = ChallengeSubmission.model_validate(submission)
    if len(payload) > 262144 or sha256(payload).hexdigest() != submission.source_sha256:
        raise ValueError("challenge_identity_or_capacity")
    return ChallengeCorpus.model_validate(parse_json(payload, limit=262144))
