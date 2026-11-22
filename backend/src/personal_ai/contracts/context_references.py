"""Neutral source and grant pointers shared by context and canonical turn records."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator
from pydantic.json_schema import SkipJsonSchema

from personal_ai.auth.scope import ApplicationScope
from personal_ai.contracts.context_categories import ContextSourceClass


class ContextEntityReference(BaseModel):
    """An exact entity reference that keeps its application/workspace scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: str = Field(min_length=1, max_length=200)
    application_id: str = Field(min_length=2, max_length=42)
    workspace_id: str | None = Field(default=None, max_length=100)


class FederationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_provider_id: str = Field(min_length=1, max_length=81)
    source: ApplicationScope
    destination: ApplicationScope
    category: str = Field(min_length=1, max_length=80)
    entities: tuple[ContextEntityReference, ...] = Field(min_length=1, max_length=16)
    grant_id: UUID
    grant_issuance_id: UUID
    grant_revision: int = Field(ge=1)
    grant_epoch: int = Field(ge=1)
    purpose: str = Field(min_length=1, max_length=160)


class ContextSourceReference(BaseModel):
    """A stable pointer to the source record or external observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[
        "record", "source", "conversation_message", "evidence", "url", "tool_invocation"
    ]
    reference_id: str = Field(min_length=1, max_length=512)
    uri: str | None = Field(default=None, max_length=2048)
    fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ContextPermissionDependency(BaseModel):
    """Permission or capability identity required to disclose an item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_scope: ApplicationScope | None = None
    entity_ref: ContextEntityReference | None = None
    source_revision: str | None = Field(default=None, min_length=1, max_length=100)
    permission_id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=160)
    source_application_id: str | None = Field(default=None, min_length=2, max_length=42)
    destination_application_id: str | None = Field(default=None, min_length=2, max_length=42)
    owner_id: str | None = Field(default=None, min_length=1, max_length=200)
    acting_user_id: str | None = Field(default=None, min_length=1, max_length=512)
    source_workspace_id: str | None = Field(default=None, max_length=100)
    destination_workspace_id: str | None = Field(default=None, max_length=100)

    @model_serializer(mode="wrap")
    def omit_absent_additive_bindings(self, handler):
        payload = handler(self)
        for field in ("source_scope", "entity_ref", "source_revision", "owner_id", "acting_user_id",
                      "source_workspace_id", "destination_workspace_id"):
            if payload.get(field) is None:
                payload.pop(field, None)
        return payload

    @model_validator(mode="after")
    def grant_scopes_are_paired(self) -> ContextPermissionDependency:
        if (self.entity_ref is None) != (self.source_revision is None):
            raise ValueError("context_permission_source_revision_incomplete")
        if self.entity_ref is not None and (
            self.source_scope is None
            or self.entity_ref.application_id != self.source_scope.application_id
            or self.entity_ref.workspace_id != self.source_scope.workspace_id
        ):
            raise ValueError("context_permission_source_revision_scope_invalid")
        if (self.source_application_id is None) != (self.destination_application_id is None):
            raise ValueError("context_permission_grant_scopes_incomplete")
        if (
            self.source_application_id is not None
            and self.source_application_id == self.destination_application_id
        ):
            raise ValueError("context_permission_grant_scopes_must_differ")
        return self


class ContextDependencyVersion(BaseModel):
    """Bound, content-free identity for one authority/configuration dependency."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[
        "policy", "provider_spec", "proposal_schema", "permission",
        "federation_grant", "source_revision",
    ]
    reference_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: str | None = Field(default=None, max_length=100)
    dependency_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    revision: int | None = Field(default=None, ge=1)
    epoch: int | None = Field(default=None, ge=1)
    observed_stage: Literal["validation", "retrieval"]

    @model_validator(mode="after")
    def grant_versions_are_complete(self):
        if self.kind == "federation_grant" and (self.revision is None or self.epoch is None):
            raise ValueError("context_dependency_grant_version_incomplete")
        if self.kind != "federation_grant" and (self.revision is not None or self.epoch is not None):
            raise ValueError("context_dependency_revision_outside_grant")
        return self


class ContextAuthorityReference(BaseModel):
    """Durable-safe reference projection; raw IDs and retrieval URIs stay transient."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal[
        "record", "source", "conversation_message", "evidence", "url", "tool_invocation"
    ]
    reference_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="before")
    @classmethod
    def redact_legacy_reference(cls, value):
        # Old canonical snapshots stored raw ContextSourceReference objects. Hydration
        # remains backward-compatible while every subsequent serialization is safe.
        if isinstance(value, ContextSourceReference):
            value = value.model_dump()
        if isinstance(value, dict) and "reference_digest" not in value:
            reference_id = value.get("reference_id")
            kind = value.get("kind")
            if isinstance(reference_id, str) and isinstance(kind, str):
                return {
                    "kind": kind,
                    "reference_digest": hashlib.sha256(
                        f"{kind}\0{reference_id}".encode()
                    ).hexdigest(),
                    "fingerprint": value.get("fingerprint"),
                }
        return value


class ApplicationPlanSourceBinding(BaseModel):
    """The verified private conversation and its registered preview destination."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lane: Literal["user_owned_plan"] = "user_owned_plan"
    target_id: str = Field(min_length=1, max_length=200)
    conversation_id: UUID
    scope: ApplicationScope
    owner_id: str = Field(min_length=1, max_length=200)
    human_issuer: str = Field(min_length=1, max_length=256)
    human_subject: str = Field(min_length=1, max_length=255)
    client_namespace: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_recipient: str = Field(min_length=1, max_length=160)
    model_recipient: str = Field(min_length=1, max_length=160)
    target_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


PlanSourceGrantPurpose = Literal["source-read", "runtime-handoff", "inference-disclosure"]
APPLICATION_PLAN_SOURCE_ITEM_PREFIX = "application-plan-source:"
SourceSensitivity = Literal["public", "personal", "sensitive", "restricted", "unknown"]


class ApplicationPlanSourceGrant(BaseModel):
    """One independently revocable grant for the exact bound projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding: ApplicationPlanSourceBinding
    purpose: PlanSourceGrantPurpose
    recipient: str = Field(min_length=1, max_length=200)
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    version: str = Field(min_length=1, max_length=100)
    expires_at: datetime

    @model_validator(mode="after")
    def aware_expiry(self):
        if self.expires_at.utcoffset() is None:
            raise ValueError("timestamp_requires_timezone")
        return self


class ApplicationPlanSourceAuthority(BaseModel):
    """Private authority retained separately from an unchanged domain projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding: ApplicationPlanSourceBinding
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    source_id: str = Field(min_length=1, max_length=200)
    item_id: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=100)
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sensitivity: SourceSensitivity
    field_sensitivities: tuple[tuple[str, SourceSensitivity], ...] = Field(min_length=1, max_length=32)
    observed_at: datetime
    grants: tuple[ApplicationPlanSourceGrant, ApplicationPlanSourceGrant, ApplicationPlanSourceGrant]

    @model_validator(mode="after")
    def exact_grants(self):
        if self.observed_at.utcoffset() is None:
            raise ValueError("timestamp_requires_timezone")
        recipients = {
            "source-read": self.binding.target_id,
            "runtime-handoff": self.binding.runtime_recipient,
            "inference-disclosure": self.binding.model_recipient,
        }
        if (
            len(set(self.fields)) != len(self.fields)
            or {name for name, _label in self.field_sensitivities} != set(self.fields)
            or len(self.field_sensitivities) != len(self.fields)
            or not self.item_id.startswith(APPLICATION_PLAN_SOURCE_ITEM_PREFIX)
        ) or {
            grant.purpose: grant.recipient for grant in self.grants
        } != recipients or any(
            grant.binding != self.binding or grant.fields != self.fields for grant in self.grants
        ):
            raise ValueError("application_plan_source_grants_invalid")
        return self

    @property
    def expires_at(self) -> datetime:
        return min(grant.expires_at for grant in self.grants)


class ContextSourceSnapshot(BaseModel):
    """Payload-free frozen identity for final authority rechecks, not a source store."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    federation: FederationProvenance | None = None
    # Internal persistence can round-trip this authority. Public response schemas
    # only describe snapshots that may be released from the ordinary API.
    application_plan_authority: SkipJsonSchema[ApplicationPlanSourceAuthority | None] = None
    provider_id: str = Field(min_length=1, max_length=81)
    source_id: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=100)
    item_id: str = Field(min_length=1, max_length=200)
    source_classes: tuple[ContextSourceClass, ...] = Field(default=(), max_length=9)
    owner_id: str = Field(min_length=1, max_length=200)
    application_id: str = Field(min_length=2, max_length=42)
    workspace_id: str | None = Field(default=None, max_length=100)
    operation: Literal["profile", "current", "entity", "history", "search"] | None = None
    content_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_refs: tuple[ContextAuthorityReference, ...] = Field(default=(), max_length=200)
    permission_dependencies: tuple[ContextPermissionDependency, ...] = Field(
        default=(), max_length=16
    )
    expires_at: datetime | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_snapshot_shape(self, handler):
        payload = handler(self)
        for field in ("federation", "application_plan_authority"):
            if getattr(self, field) is None:
                payload.pop(field, None)
        return payload

    @model_validator(mode="after")
    def source_classes_are_unique(self) -> ContextSourceSnapshot:
        if len(set(self.source_classes)) != len(self.source_classes):
            raise ValueError("context_source_classes_must_be_unique")
        return self

    @model_validator(mode="after")
    def aware_expiry(self) -> ContextSourceSnapshot:
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("timestamp_requires_timezone")
        return self
