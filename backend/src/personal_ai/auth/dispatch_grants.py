"""Pinned asymmetric proofs for a user-controlled execution boundary.

Signing is consumed only by the gated shared turn service after authorization and
branch/source rechecks. No HTTP issuer is composed; signatures do not replace policy.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.llm.external import PreparedExecution


class LocalChatScope(BaseModel):
    """Issuer assertion for a foreground, source-free turn in the standalone PAS app."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    application_id: Literal["personal_ai"] = "personal_ai"
    operation: Literal["foreground_source_free_chat"] = "foreground_source_free_chat"
    owner_id: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=512)
    workspace_id: str | None

    def matches_package(self, package: PreparedExecution) -> bool:
        return (self.application_id, self.owner_id, self.workspace_id) == (
            package.application_id, package.owner_id, package.workspace_id,
        )


class ApplicationPlanScope(BaseModel):
    """Exact app pairing, with an opaque binding to locally held registration facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    application_id: str = Field(min_length=2, max_length=42)
    owner_id: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=512)
    workspace_id: str | None
    client_namespace: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_id: UUID
    registration_binding: str = Field(pattern=r"^[a-f0-9]{64}$")
    local_recipient: str = Field(min_length=1, max_length=160)
    model_recipient: str = Field(min_length=1, max_length=160)

    def matches_package(self, package: PreparedExecution) -> bool:
        return (self.application_id, self.owner_id, self.workspace_id) == (
            package.application_id, package.owner_id, package.workspace_id,
        )


class ApplicationPlanDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    operation: Literal["foreground_application_plan"] = "foreground_application_plan"
    scope: ApplicationPlanScope
    attempt_id: UUID
    intent_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DispatchGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1, 2] = 1
    issuer: str = Field(min_length=1, max_length=200)
    key_id: str = Field(min_length=1, max_length=100)
    audience: UUID
    caller_id: UUID
    grant_id: UUID
    package_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    connection_id: UUID
    provider_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    policy_version: str = Field(min_length=1, max_length=200)
    effective_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    issued_at: int = Field(strict=True, ge=0)
    expires_at: int = Field(strict=True, ge=0)
    local_chat: LocalChatScope | None = Field(default=None, exclude_if=lambda value: value is None)
    routing_root: UUID | None = Field(default=None, exclude_if=lambda value: value is None)
    application_plan: ApplicationPlanDispatch | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def bind_version(self):
        if (self.schema_version == 2) != (self.application_plan is not None) or (
            self.application_plan is not None and (
                self.local_chat is not None or self.routing_root is None
                or self.audience != self.application_plan.scope.runtime_id
            )
        ):
            raise ValueError("dispatch_grant_invalid")
        return self

    def canonical(self) -> bytes:
        return (
            f"personal-ai-dispatch-v{self.schema_version}\0".encode()
            + json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        )


class SignedDispatchGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claims: DispatchGrant
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{86}$")


class InvalidDispatchGrant(ValueError):
    def __init__(self):
        super().__init__("dispatch_grant_invalid")


class DispatchGrantVerifier:
    def __init__(self, *, issuer: str, keys: dict[str, Ed25519PublicKey], audience: UUID):
        self.issuer, self.keys, self.audience = issuer, dict(keys), audience

    def verify(
        self,
        proof: SignedDispatchGrant,
        package: PreparedExecution,
        *,
        caller_id: UUID,
        now: int,
    ) -> DispatchGrant:
        try:
            package = PreparedExecution.model_validate(package.model_dump())
        except (ValueError, AttributeError, TypeError):
            raise InvalidDispatchGrant() from None
        claims = self.verify_claims(proof, caller_id=caller_id, now=now)
        if (
            claims.package_hash != package.fingerprint
            or claims.connection_id != package.connection_id
            or claims.provider_id != package.provider_id
            or claims.model_id != package.model_id
            or claims.policy_version != package.policy_version
            or claims.effective_sensitivity != package.effective_sensitivity
        ):
            raise InvalidDispatchGrant()
        return claims

    def verify_claims(self, proof, *, caller_id, now) -> DispatchGrant:
        """Authenticate the content-free envelope before the recipient receives a package."""
        try:
            proof = SignedDispatchGrant.model_validate(proof.model_dump())
        except (ValueError, AttributeError, TypeError):
            raise InvalidDispatchGrant() from None
        claims = proof.claims
        key = self.keys.get(claims.key_id)
        if (
            key is None
            or claims.issuer != self.issuer
            or claims.audience != self.audience
            or claims.caller_id != caller_id
            or not claims.issued_at <= now < claims.expires_at
            or not 0 < claims.expires_at - claims.issued_at <= 120
        ):
            raise InvalidDispatchGrant()
        try:
            signature = base64.urlsafe_b64decode(proof.signature + "==")
            # Reject noncanonical base64 encodings too.
            if base64.urlsafe_b64encode(signature).decode().rstrip("=") != proof.signature:
                raise InvalidDispatchGrant()
            key.verify(signature, claims.canonical())
        except (InvalidSignature, ValueError):
            raise InvalidDispatchGrant() from None
        return claims


class DispatchGrantSigner:
    """Server-only signer. The orchestration service supplies already checked claims."""

    def __init__(self, *, issuer: str, key_id: str, key: Ed25519PrivateKey):
        self.issuer, self.key_id, self._key = issuer, key_id, key

    def sign(
        self,
        package: PreparedExecution,
        *,
        caller_id: UUID,
        audience: UUID,
        now: datetime,
        expires_at: datetime,
        local_chat: LocalChatScope | None = None,
        routing_root: UUID | None = None,
        application_plan: ApplicationPlanDispatch | None = None,
    ) -> SignedDispatchGrant:
        if (
            now.tzinfo is None
            or expires_at.tzinfo is None
            or not 0 < (expires_at - now).total_seconds() <= 120
            or (routing_root is not None and local_chat is None and application_plan is None)
            or (application_plan is not None and (
                local_chat is not None
                or routing_root is None
                or application_plan.scope.runtime_id != audience
                or not application_plan.scope.matches_package(package)
            ))
        ):
            raise InvalidDispatchGrant()
        claims = DispatchGrant(
            schema_version=2 if application_plan is not None else 1,
            issuer=self.issuer,
            key_id=self.key_id,
            audience=audience,
            caller_id=caller_id,
            grant_id=uuid4(),
            package_hash=package.fingerprint,
            connection_id=package.connection_id,
            provider_id=package.provider_id,
            model_id=package.model_id,
            policy_version=package.policy_version,
            effective_sensitivity=package.effective_sensitivity,
            issued_at=int(now.timestamp()),
            expires_at=int(expires_at.timestamp()),
            local_chat=local_chat,
            routing_root=routing_root,
            application_plan=application_plan,
        )
        return SignedDispatchGrant(
            claims=claims,
            signature=base64.urlsafe_b64encode(self._key.sign(claims.canonical()))
            .decode()
            .rstrip("="),
        )
