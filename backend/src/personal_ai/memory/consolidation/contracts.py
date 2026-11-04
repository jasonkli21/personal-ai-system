"""Closed, bounded offline contracts. Source text cannot confer authority."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from personal_ai.memory.knowledge import Strict, digest

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,63}$")]
ActorIdentifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:|/-]{0,127}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Counter = Annotated[int, Field(strict=True, ge=0, le=1024)]
Command = Literal["make backend-lint", "make backend-test-offline", "make memory-eval"]
GENERATION = "synthetic-source-v1:bounded-extractor-v1:pending-policy-v1"
BACKFILL_GENERATION = "synthetic-source-v2:bounded-extractor-v2:pending-policy-v2"
Generation = Literal[GENERATION, BACKFILL_GENERATION]
PAGE_SIZE = 4
MAX_SOURCES = 128
MAX_PROPOSALS = 64
MAX_RECEIPTS = 64
MAX_CLAIMS = 32
MAX_BYTES = 16384


class ConsolidationScope(Strict):
    owner: Identifier
    application: Identifier
    workspace: Identifier | None
    project: Identifier
    actor: ActorIdentifier | None
    client: Identifier
    purpose: Literal["offline_synthetic_consolidation"]
    session: Identifier

    @property
    def key(self):
        return digest(self)


class FixtureFact(Strict):
    command: Command
    outcome: Literal["passed", "failed"]
    revision: Identifier


class SourceEnvelope(Strict):
    schema_version: Literal["consolidation-source-v1"] = "consolidation-source-v1"
    scope: ConsolidationScope
    source_id: Identifier
    sequence: Annotated[int, Field(strict=True, ge=1, le=MAX_SOURCES)]
    issuer: Literal["frozen-synthetic-issuer-v1"]
    classification: Literal["synthetic"]
    revision: Annotated[int, Field(strict=True, ge=1, le=1024)]
    epoch: Annotated[int, Field(strict=True, ge=1, le=1024)]
    observed_at: datetime
    expires_at: datetime
    evidence: Literal["fixture_independent_check", "observed_completion", "user_correction"]
    fact: FixtureFact
    supersedes: Identifier | None = None

    @model_validator(mode="after")
    def bounds(self):
        if not 0 < (self.expires_at - self.observed_at).total_seconds() <= 30 * 86400:
            raise ValueError("source_time_bounds")
        if len(self.model_dump_json().encode()) > 2048:
            raise ValueError("source_byte_bounds")
        return self


class EvidenceEdge(Strict):
    source_id: Identifier
    fingerprint: Hash
    revision: Annotated[int, Field(strict=True, ge=1, le=1024)]
    epoch: Annotated[int, Field(strict=True, ge=1, le=1024)]


def edge(source):
    return EvidenceEdge(
        source_id=source.source_id,
        fingerprint=digest(source),
        revision=source.revision,
        epoch=source.epoch,
    )


class DerivedProposal(Strict):
    """Closed facts only; no accept/promote operation exists in this component."""

    schema_version: Literal["offline-proposal-v1"] = "offline-proposal-v1"
    scope: ConsolidationScope
    kind: Literal["procedure", "lesson", "conflict"]
    fact: FixtureFact
    authority: Literal["fixture_checked", "user_asserted", "unresolved"]
    edges: tuple[EvidenceEdge, ...] = Field(min_length=1, max_length=2)
    status: Literal["pending"] = "pending"
    verification: Literal["synthetic_only_not_task_success"] = "synthetic_only_not_task_success"
    generation: Generation = GENERATION

    @property
    def key(self):
        return digest(self)

    @property
    def assertion_key(self):
        # Equal surface assertions do not merge provenance or unrelated scopes.
        return digest([self.scope.key, self.kind, self.fact.model_dump(), self.authority])


class SourcePage(Strict):
    scope: ConsolidationScope
    generation: Generation = GENERATION
    after: Counter
    records: tuple[SourceEnvelope, ...] = Field(min_length=1, max_length=PAGE_SIZE)

    @model_validator(mode="after")
    def ordered(self):
        if any(
            s.scope != self.scope or s.sequence != self.after + i + 1
            for i, s in enumerate(self.records)
        ):
            raise ValueError("source_page_order")
        if len(self.model_dump_json().encode()) > MAX_BYTES:
            raise ValueError("page_byte_bounds")
        return self

    @property
    def original_key(self):
        # Lease ownership is deliberately excluded for lost-ACK reconciliation.
        return digest([self.scope.key, self.generation, self.after, self.records[-1].sequence])


class Lease(Strict):
    scope_key: Hash
    worker: Identifier
    fence: Counter
    cursor: Counter
    expires_at: datetime
    generation: Generation = GENERATION


class BatchReceipt(Strict):
    original_key: Hash
    payload_digest: Hash
    cursor: Counter
    proposal_count: Counter
    reasons: tuple[
        Literal[
            "proposed",
            "duplicate",
            "unsupported_observation",
            "source_ineligible",
            "user_correction_wins",
            "conflict",
            "superseded",
        ],
        ...,
    ] = Field(max_length=PAGE_SIZE)


class ConsolidationDenied(ValueError):
    """Content-free closed failure surface, including for hostile inputs."""

    def __init__(self):
        super().__init__("offline_consolidation_denied")


def checked(value, contract):
    """Revalidate even unsafe model copies, without serializing hostile warnings.

    Pydantic's model_copy can add unknown __dict__ keys that model_dump silently
    drops; reject these before normal serialization instead of normalizing them.
    """

    remaining = 1024

    def inspect(item, depth=0):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 8:
            raise ConsolidationDenied()
        if isinstance(item, BaseModel):
            if type(item) not in (
                ConsolidationScope,
                FixtureFact,
                SourceEnvelope,
                EvidenceEdge,
                DerivedProposal,
                SourcePage,
                Lease,
            ):
                raise ConsolidationDenied()
            if set(item.__dict__) != set(type(item).model_fields) or item.__pydantic_extra__:
                raise ConsolidationDenied()
            for field in type(item).model_fields:
                inspect(getattr(item, field), depth + 1)
        elif isinstance(item, tuple):
            if len(item) > MAX_SOURCES:
                raise ConsolidationDenied()
            for member in item:
                inspect(member, depth + 1)
        elif isinstance(item, str):
            if len(item) > MAX_BYTES or len(item.encode()) > MAX_BYTES:
                raise ConsolidationDenied()
        elif item is not None and type(item) not in (int, datetime):
            raise ConsolidationDenied()

    try:
        if type(value) is not contract:
            raise ConsolidationDenied()
        inspect(value)
        return contract.model_validate(value.model_dump(warnings=False))
    except (AttributeError, TypeError, ValueError):
        raise ConsolidationDenied() from None
