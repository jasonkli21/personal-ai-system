"""Bounded federation declarations and non-authoritative selection/provenance."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.auth.scope import ApplicationScope
from personal_ai.contracts.context_references import ContextEntityReference


class FederationExportDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,80}$")
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    sensitivity: Literal["public", "personal", "sensitive", "restricted"]


class FederationSelection(BaseModel):
    """Caller hints; never grant, source membership or revision authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    grant_id: UUID
    issuance_id: UUID
    revision: int = Field(ge=1)
    epoch: int = Field(ge=1)
    source: ApplicationScope
    category: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=160)
    entities: tuple[ContextEntityReference, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def exact_scope(self):
        if len(set(self.entities)) != len(self.entities) or any(
            entity.application_id != self.source.application_id
            or entity.workspace_id != self.source.workspace_id
            for entity in self.entities
        ):
            raise ValueError("federation_entity_scope_invalid")
        return self


class FederationContextChoice(BaseModel):
    """Explicit selected export in any execution lane, subject to shared policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,80}$")
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    federation: FederationSelection

    def context_selection(self):
        from personal_ai.context.providers import ContextSelection

        return ContextSelection(
            provider_id=self.provider_id,
            operation="entity",
            fields=self.fields,
            federation=self.federation,
            required=True,
            max_tokens=2048,
        )
