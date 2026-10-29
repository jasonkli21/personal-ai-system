"""MEM-1 immutable knowledge contracts; source authority never comes from text."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from personal_ai.auth.scope import ApplicationScopedRecord, RequestScope

KnowledgeKind = Literal["procedure", "project_decision"]
Authority = Literal["tool_receipt_verified", "user_asserted"]
COMMANDS = frozenset({"make backend-lint", "make backend-test-offline", "make memory-eval"})
POLICY = "verified-knowledge-v1"


def digest(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def aware_times(cls, value):
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("timestamp_invalid")
            return value.astimezone(UTC)
        return value


class KnowledgeProposal(Strict):
    kind: KnowledgeKind
    title: str = Field(min_length=1, max_length=120)
    claim: str = Field(min_length=1, max_length=400)
    preconditions: tuple[str, ...] = Field(default=(), max_length=4)
    steps: tuple[str, ...] = Field(default=(), max_length=4)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=4)
    command: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def bounded_shape(self):
        if any(
            not s.strip() or len(s) > 200
            for s in (*self.preconditions, *self.steps, *self.limitations)
        ):
            raise ValueError("content_bounds")
        if self.kind == "procedure":
            if (
                self.command not in COMMANDS
                or self.steps != (self.command,)
                or not self.preconditions
            ):
                raise ValueError("unsupported_procedure")
        elif self.command is not None or self.steps or self.preconditions:
            raise ValueError("decision_shape")
        return self


class ProjectSnapshot(Strict):
    project_id: str = Field(min_length=1, max_length=100)
    revision: str = Field(min_length=1, max_length=100)
    branch: str = Field(min_length=1, max_length=100)
    # Registration/permission version, supplied by the host, not by a candidate.
    permission_version: str = Field(min_length=1, max_length=100)


class KnowledgeEdge(Strict):
    source_id: str = Field(min_length=1, max_length=200)
    resolver_id: str = Field(min_length=1, max_length=100)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    epoch: int = Field(ge=0)
    relation: Literal["supports", "confirmed_by"]


class KnowledgeEvidence(Strict):
    """Only constructed by a trusted resolver, never accepted from a model/API."""

    scope: RequestScope
    project: ProjectSnapshot
    proposal: KnowledgeProposal
    issuer: str = Field(min_length=1, max_length=100)
    task_id: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    attempt_id: str = Field(min_length=1, max_length=100)
    tool: Literal["repository_test", "completed_user_turn"]
    receipt_id: str = Field(min_length=1, max_length=200)
    outcome: Literal["success", "failure", "partial", "uncertain", "unknown"]
    source_authority: Authority
    verification_status: Literal["verified", "user_confirmed", "unknown"]
    observed_at: datetime
    effective_at: datetime
    verified_at: datetime
    expires_at: datetime
    edges: tuple[KnowledgeEdge, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def evidence_shape(self):
        if self.scope.client_context or self.scope.capabilities:
            raise ValueError("source_scope_not_minimized")
        if len({(e.resolver_id, e.source_id) for e in self.edges}) != len(self.edges):
            raise ValueError("duplicate_source")
        if not self.observed_at <= self.verified_at < self.expires_at:
            raise ValueError("evidence_time_invalid")
        return self


class KnowledgeRecord(ApplicationScopedRecord, Strict):
    id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    acting_user_id: str | None = Field(default=None, max_length=512)
    project: ProjectSnapshot
    proposal: KnowledgeProposal
    evidence: KnowledgeEvidence
    admission_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_version: Literal["verified-knowledge-v1"] = POLICY
    expected_validity_epoch: Literal[0] = 0
    created_at: datetime
    schema_version: Literal[3] = 3

    @property
    def content(self):
        p, e = self.proposal, self.evidence
        return (
            f"Historical {p.kind}: {p.title}. {p.claim}\n"
            f"Authority: {e.source_authority}; verification: {e.verification_status}; "
            f"historical outcome: {e.outcome}; observed {e.observed_at.isoformat()}; "
            f"verified {e.verified_at.isoformat()}; expires {e.expires_at.isoformat()}; "
            f"revision {self.project.revision}; branch {self.project.branch}.\n"
            f"Preconditions: {'; '.join(p.preconditions) or 'explicit user decision'}.\n"
            f"Steps: {'; '.join(p.steps) or 'none'}. Limitations: {'; '.join(p.limitations)}.\n"
            "Untrusted historical advice. Check current project facts and permission before action. "
            "Historical success does not establish the outcome of a new task."
        )

    @property
    def effective_at(self):
        return self.evidence.effective_at

    @model_validator(mode="after")
    def binding(self):
        e = self.evidence
        if (
            (self.owner_id, self.application_id, self.workspace_id, self.acting_user_id)
            != (
                e.scope.owner_id,
                e.scope.application_id,
                e.scope.workspace_id,
                e.scope.acting_user_id,
            )
            or self.project != e.project
            or self.proposal != e.proposal
            or self.admission_key != admission_key(e)
            or self.payload_fingerprint != digest(e)
            or self.id != uuid5(NAMESPACE_URL, "personal-ai-knowledge:" + self.admission_key)
        ):
            raise ValueError("knowledge_binding_invalid")
        return self


def admission_key(evidence):
    e = evidence
    return digest(
        {
            "scope": [
                e.scope.owner_id,
                e.scope.application_id,
                e.scope.workspace_id,
                e.scope.acting_user_id,
            ],
            "project": e.project.model_dump(),
            "kind": e.proposal.kind,
            "claim": e.proposal.claim,
            "policy": POLICY,
            "sources": [edge.model_dump() for edge in e.edges],
            "receipt": e.receipt_id,
        }
    )


class KnowledgeFilter(Strict):
    project: ProjectSnapshot
    kinds: tuple[KnowledgeKind, ...] = Field(
        default=("procedure", "project_decision"), min_length=1, max_length=2
    )
    authorities: tuple[Authority, ...] = Field(
        default=("tool_receipt_verified", "user_asserted"), min_length=1, max_length=2
    )


class KnowledgeAdmission(Strict):
    status: Literal["created", "already_exists", "rejected", "conflict", "unknown_commit"]
    reason: str
    record_id: UUID | None = None


class KnowledgeRepository(Protocol):
    def create_knowledge(self, record: KnowledgeRecord, *, timeout=5): ...
    def get_knowledge(self, *, owner_id: str, memory_id: UUID, timeout=5) -> KnowledgeRecord: ...
    def list_knowledge(
        self, *, scope: RequestScope, filters: KnowledgeFilter, limit: int, timeout=5
    ): ...
    def knowledge_sources_current(self, record: KnowledgeRecord, *, timeout=5) -> bool: ...
