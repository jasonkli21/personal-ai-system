"""Neutral source and grant pointers shared by context and canonical turn records."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContextEntityReference(BaseModel):
    """An exact entity reference that keeps its application/workspace scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: str = Field(min_length=1, max_length=200)
    application_id: str = Field(min_length=2, max_length=42)
    workspace_id: str | None = Field(default=None, max_length=100)


class ContextSourceReference(BaseModel):
    """A stable pointer to the source record or external observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["record", "conversation_message", "evidence", "url", "tool_invocation"]
    reference_id: str = Field(min_length=1, max_length=512)
    uri: str | None = Field(default=None, max_length=2048)
    fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ContextPermissionDependency(BaseModel):
    """Permission or capability identity required to disclose an item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    permission_id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=160)
    source_application_id: str | None = Field(default=None, min_length=2, max_length=42)
    destination_application_id: str | None = Field(default=None, min_length=2, max_length=42)

    @model_validator(mode="after")
    def grant_scopes_are_paired(self) -> ContextPermissionDependency:
        if (self.source_application_id is None) != (self.destination_application_id is None):
            raise ValueError("context_permission_grant_scopes_incomplete")
        if (
            self.source_application_id is not None
            and self.source_application_id == self.destination_application_id
        ):
            raise ValueError("context_permission_grant_scopes_must_differ")
        return self


class ContextSourceSnapshot(BaseModel):
    """Payload-free frozen identity for final authority rechecks, not a source store."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider_id: str = Field(min_length=1, max_length=81)
    source_id: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=100)
    item_id: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=200)
    application_id: str = Field(min_length=2, max_length=42)
    workspace_id: str | None = Field(default=None, max_length=100)
    operation: Literal["profile", "current", "entity", "history", "search"] | None = None
    content_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_refs: tuple[ContextSourceReference, ...] = Field(default=(), max_length=200)
    permission_dependencies: tuple[ContextPermissionDependency, ...] = Field(
        default=(), max_length=16
    )
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def aware_expiry(self) -> ContextSourceSnapshot:
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("timestamp_requires_timezone")
        return self
