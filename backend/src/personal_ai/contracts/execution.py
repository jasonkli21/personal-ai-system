"""Provider-neutral request choices for shared conversation continuation."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.routing.contracts import EndpointRef


class ExecutionChoice(BaseModel):
    """Producer-neutral continuation choice. Historical origin never selects a route."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["automatic", "connected_provider", "manual_external"] = "automatic"
    endpoint: EndpointRef | None = None
    connection_id: UUID | None = None
    connection_revision: int | None = Field(default=None, ge=1)
    caller_id: UUID | None = None
    audience: UUID | None = None
    declared_provider: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/ -]{0,199}$"
    )
    declared_model: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/ -]{0,199}$"
    )

    @model_validator(mode="after")
    def valid_choice(self):
        binding = (
            self.endpoint,
            self.connection_id,
            self.connection_revision,
            self.caller_id,
            self.audience,
        )
        if self.mode == "connected_provider" and any(v is None for v in binding):
            raise ValueError("connected_choice_requires_binding")
        if self.mode != "connected_provider" and any(v is not None for v in binding):
            raise ValueError("execution_choice_binding_invalid")
        if self.mode != "manual_external" and (self.declared_provider or self.declared_model):
            raise ValueError("declarations_require_manual_mode")
        return self


class ContinuationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1, max_length=20000)
    idempotency_key: UUID
    choice: ExecutionChoice = Field(default_factory=ExecutionChoice)
    # Optional narrowing. References never authorize or force inclusion.
    candidate_message_ids: tuple[UUID, ...] | None = Field(default=None, max_length=10000)
