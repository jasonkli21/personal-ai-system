"""MEM-2 content-only inputs and bounded disclosure contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt, field_validator, model_validator

from personal_ai.contracts.context_references import ContextPermissionDependency
from personal_ai.memory.knowledge import KnowledgeKind, ProjectSnapshot, Strict


class SearchInput(Strict):
    query: str = Field(default="", max_length=200)
    kind: KnowledgeKind | None = None
    limit: int = Field(default=8, ge=1, le=8, strict=True)


class FetchInput(Strict):
    memory_id: UUID


class ProposalInput(Strict):
    kind: KnowledgeKind
    title: str = Field(min_length=1, max_length=120)
    claim: str = Field(min_length=1, max_length=400)
    limitations: tuple[str, ...] = Field(default=(), max_length=4)

    @property
    def preconditions(self):
        return ()

    @property
    def steps(self):
        return ()


class MutationInput(Strict):
    operation_id: UUID
    expected_version: StrictInt = Field(ge=0)
    confirm: Literal[True]

    @field_validator("confirm", mode="before")
    @classmethod
    def explicit_intent(cls, value):
        if value is not True:
            raise ValueError("explicit_user_intent_required")
        return value


class ReviewInput(MutationInput):
    decision: Literal["reviewed", "rejected"]


class ControlIntent(Strict):
    """Internal only: actor and evidence are never supplied by a caller."""

    operation_id: UUID
    action: Literal["propose", "reviewed", "rejected", "forget"]
    target_id: UUID | None = None
    expected_version: int = Field(default=0, ge=0)
    proposal: ProposalInput | None = None
    actor: Literal["agent_proposal", "verified_user"]

    @model_validator(mode="after")
    def operation_shape(self):
        if self.action == "propose":
            if (
                self.actor != "agent_proposal"
                or self.proposal is None
                or self.target_id is not None
                or self.expected_version != 0
            ):
                raise ValueError("proposal_intent_invalid")
        elif self.actor != "verified_user" or self.target_id is None or self.proposal is not None:
            raise ValueError("user_intent_invalid")
        return self


class PendingProposal(Strict):
    id: UUID
    project: ProjectSnapshot
    content: ProposalInput | None
    status: Literal["pending", "reviewed", "rejected", "expired"] = "pending"
    version: int = 0
    created_at: datetime
    expires_at: datetime
    origin: Literal["agent_proposal"] = "agent_proposal"


class OperationResult(Strict):
    status: Literal[
        "proposed_for_review",
        "reviewed",
        "rejected",
        "applied",
        "conflict",
        "expired",
        "unknown_commit",
        "temporarily_unavailable",
        "forbidden_or_not_found",
        "disabled",
        "unsupported_evidence_source",
        "limit_exceeded",
        "stale_evidence",
        "cancelled",
    ]
    reason: str = Field(max_length=100)
    operation_id: UUID | None = None
    target_id: UUID | None = None
    version: int | None = None
    replayed: bool = False


class OperationReceipt(Strict):
    operation_id: UUID
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    actor: Literal["agent_proposal", "verified_user"]
    action: Literal["propose", "reviewed", "rejected", "forget"]
    target_id: UUID | None
    expected_version: int
    result: OperationResult
    created_at: datetime
    expires_at: datetime


class MemoryView(Strict):
    application_id: str
    workspace_id: str | None
    id: UUID
    kind: KnowledgeKind
    title: str
    historical_content: str = Field(max_length=8192)
    project: ProjectSnapshot
    authority: str
    verification: str
    observed_at: datetime
    expires_at: datetime
    permission_dependencies: tuple[ContextPermissionDependency, ...] = Field(
        min_length=1, max_length=1
    )
    state_version: int
    validity_epoch: int
    source_ids: tuple[str, ...] = Field(max_length=8)


class ReadResult(Strict):
    status: Literal[
        "found",
        "forbidden_or_not_found",
        "limit_exceeded",
        "temporarily_unavailable",
        "disabled",
        "cancelled",
    ]
    items: tuple[MemoryView, ...] = Field(default=(), max_length=8)
    topics: tuple[str, ...] = Field(default=(), max_length=8)
    proposals: tuple[PendingProposal, ...] = Field(default=(), max_length=32)
    truncated: bool = False
