"""Canonical, versioned federation permission state; no domain payloads."""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from personal_ai.auth.scope import ApplicationScope
from personal_ai.contracts.context_references import ContextPermissionDependency
from personal_ai.contracts.federation import FederationSelection


class FederationGrantConflict(ValueError):
    """A stale grant lifetime/version or conflicting idempotent intent."""


class FederationGrant(FederationSelection):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["federation-grant-v1"] = "federation-grant-v1"
    owner_id: str = Field(min_length=1, max_length=200)
    acting_user_id: str = Field(min_length=1, max_length=512)
    destination: ApplicationScope
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    expires_at: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime
    source_policy: ContextPermissionDependency
    sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    maximum_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    re_delegation: Literal[False] = False
    state: Literal["active", "revoked"] = "active"
    revocation_id: UUID | None = None

    @model_validator(mode="after")
    def valid_grant(self):
        from personal_ai.applications.contracts import SENSITIVITY_RANK

        if self.source.application_id == self.destination.application_id:
            raise ValueError("federation_requires_distinct_applications")
        if (
            self.source_policy.owner_id != self.owner_id
            or self.source_policy.acting_user_id != self.acting_user_id
            or self.source_policy.source_scope != self.source
            or self.source_policy.purpose != self.purpose
        ):
            raise ValueError("federation_source_policy_binding_invalid")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("federation_fields_not_unique")
        if self.expires_at <= self.created_at or self.updated_at < self.created_at:
            raise ValueError("federation_grant_time_invalid")
        if (self.state == "revoked") != (self.revocation_id is not None):
            raise ValueError("federation_revocation_identity_required")
        if SENSITIVITY_RANK[self.sensitivity] > SENSITIVITY_RANK[self.maximum_sensitivity]:
            raise ValueError("federation_sensitivity_invalid")
        return self

    def current(self, now: datetime) -> bool:
        return self.state == "active" and self.expires_at > now

    def dependency(self) -> ContextPermissionDependency:
        return ContextPermissionDependency(
            permission_id=f"federation_grant:{self.grant_id}",
            version=f"{self.issuance_id}:{self.revision}:{self.epoch}",
            purpose=self.purpose,
            owner_id=self.owner_id,
            acting_user_id=self.acting_user_id,
            source_application_id=self.source.application_id,
            source_workspace_id=self.source.workspace_id,
            destination_application_id=self.destination.application_id,
            destination_workspace_id=self.destination.workspace_id,
        )


class FederationGrantRepository(Protocol):
    def record_access(self, selection, scope, result: str) -> None: ...
    def get(self, owner_id: str, grant_id: UUID) -> FederationGrant | None: ...
    def save(self, grant: FederationGrant, *, expected_revision: int) -> FederationGrant: ...
