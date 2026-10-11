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
from pydantic import BaseModel, ConfigDict, Field

from personal_ai.llm.external import PreparedExecution


class DispatchGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
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

    def canonical(self) -> bytes:
        return (
            b"personal-ai-dispatch-v1\0"
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
            proof = SignedDispatchGrant.model_validate(proof.model_dump())
            package = PreparedExecution.model_validate(package.model_dump())
        except (ValueError, AttributeError, TypeError):
            raise InvalidDispatchGrant() from None
        claims = proof.claims
        key = self.keys.get(claims.key_id)
        if (
            key is None
            or claims.issuer != self.issuer
            or claims.audience != self.audience
            or claims.caller_id != caller_id
            or claims.package_hash != package.fingerprint
            or claims.connection_id != package.connection_id
            or claims.provider_id != package.provider_id
            or claims.model_id != package.model_id
            or claims.policy_version != package.policy_version
            or claims.effective_sensitivity != package.effective_sensitivity
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
    ) -> SignedDispatchGrant:
        if (
            now.tzinfo is None
            or expires_at.tzinfo is None
            or not 0 < (expires_at - now).total_seconds() <= 120
        ):
            raise InvalidDispatchGrant()
        claims = DispatchGrant(
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
        )
        return SignedDispatchGrant(
            claims=claims,
            signature=base64.urlsafe_b64encode(self._key.sign(claims.canonical()))
            .decode()
            .rstrip("="),
        )
