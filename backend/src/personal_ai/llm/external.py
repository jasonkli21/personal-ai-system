"""Bounded prepared execution value, not context preparation or turn persistence."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.auth.scope import ApplicationScope
from personal_ai.entities.conversation import MAX_MESSAGE_CONTENT_CHARS
from personal_ai.llm.client import ChatMessage, InferenceContext
from personal_ai.routing.contracts import EndpointRef


class ExecutionProfileIdentity(BaseModel):
    """The exact shared Phase 18 profile identity selected for local execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    endpoint: EndpointRef
    endpoint_id: str = Field(min_length=1, max_length=200)
    deployment_id: str = Field(min_length=1, max_length=200)
    serializer_id: str = Field(min_length=1, max_length=200)
    runtime_id: str = Field(min_length=1, max_length=200)


CHATGPT_PLAN_PROFILE = ExecutionProfileIdentity(
    endpoint=EndpointRef(endpoint_profile_id="openai_chatgpt_plan:responses", profile_version=1),
    endpoint_id="openai-responses-v1",
    deployment_id="api.openai.com-v1",
    serializer_id="siwc-responses-text-v1",
    runtime_id="chatgpt-responses-httpx-v1",
)


class PreparedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: Literal["system", "developer", "user", "assistant"]
    content: str = Field(min_length=1, max_length=131072)


class PreparedExecution(ApplicationScope):
    """Must originate from shared authorized assembly; browser labels are advisory.

    A signed hash binds ALL fields, including scope/branch/source versions and limits.
    This is not a new canonical prepared-turn repository.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[3] = 3
    owner_id: str = Field(min_length=1, max_length=200)
    conversation_id: UUID
    reservation_id: UUID
    branch_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_authority_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
    execution_profile: ExecutionProfileIdentity
    connection_id: UUID
    connection_revision: int = Field(ge=1, strict=True)
    messages: tuple[PreparedMessage, ...] = Field(min_length=1, max_length=256)
    effective_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    maximum_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    policy_version: str = Field(min_length=1, max_length=200)
    max_output_bytes: int = Field(ge=1, le=262144, strict=True)
    max_output_chars: int = Field(
        default=MAX_MESSAGE_CONTENT_CHARS,
        ge=1,
        le=MAX_MESSAGE_CONTENT_CHARS,
        strict=True,
    )
    timeout_seconds: int = Field(ge=1, le=120, strict=True)

    @model_validator(mode="after")
    def bounded_authorized(self):
        self.inference_context()
        if len(self.canonical()) > 262144:
            raise ValueError("external_request_too_large")
        return self

    def canonical(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()

    @property
    def dispatch_identity(self) -> str:
        # Proof IDs can be reissued; this scoped reservation cannot be sent twice.
        return hashlib.sha256(
            json.dumps(
                [
                    self.owner_id,
                    self.application_id,
                    self.workspace_id,
                    str(self.conversation_id),
                    str(self.reservation_id),
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def inference_context(self) -> InferenceContext:
        return InferenceContext(
            self.effective_sensitivity,
            self.maximum_sensitivity,
            self.policy_version,
        )

    def chat_messages(self) -> tuple[ChatMessage, ...]:
        return tuple(ChatMessage(message.role, message.content) for message in self.messages)
