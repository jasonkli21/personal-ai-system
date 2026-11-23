"""Closed wire types for the isolated pas-dispatch/1 profile."""

import base64
import json
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

VERSION = "pas-dispatch/1"
MEDIA_TYPE = "application/vnd.pas.dispatch-v1+json"
RECEIPT_HEADER = "x-pas-dispatch-receipt"
ORIGINAL_KEY_HEADER = "x-pas-original-key"


def wire_digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _uuid(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("noncanonical UUID")
    return value


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _signature(value: str) -> str:
    if _b64(base64.urlsafe_b64decode(value + "==")) != value:
        raise ValueError("noncanonical signature")
    return value


Identifier = Annotated[str, Field(min_length=1, max_length=512)]
Digest = Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
Signature = Annotated[str, Field(pattern="^[A-Za-z0-9_-]{86}$"), AfterValidator(_signature)]
WireId = Annotated[str, AfterValidator(_uuid)]
Epoch = Annotated[int, Field(ge=0, le=2**53 - 1)]
Phase = Literal["preview", "confirm", "release", "send", "disclose"]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Destination(WireModel):
    account: Identifier
    connection: Identifier
    endpoint: Literal["loopback-fixture"]
    model: Literal["fake"]
    provider: Literal["fake"]
    revision: Epoch
    runtime: Identifier


class Binding(WireModel):
    actor_issuer: Identifier
    app: Literal["travel", "health"]
    attempt: WireId
    branch: Digest
    client: Identifier
    conversation: WireId
    create_key: WireId
    create_receipt: Digest
    destination: Destination
    epoch: Epoch
    installation: Identifier
    memory: Digest
    original_key: WireId
    owner: Identifier
    policy: Identifier
    preview_receipt: Digest
    root: WireId
    source: Digest
    subject: Identifier
    target: Identifier
    tenant: Identifier
    workspace: Identifier | None


class SignedClaims(WireModel):
    v: Literal["pas-dispatch/1"]
    issuer: Identifier
    audience: Identifier
    kid: Identifier
    binding_sha256: Digest
    expires: Epoch


class PreviewClaims(SignedClaims):
    purpose: Literal["preview"]
    payload_sha256: Digest


class Confirmation(WireModel):
    v: Literal["pas-dispatch/1"]
    confirmation: Digest
    original_key: WireId
    preview_sig: Signature


class ReleaseClaims(SignedClaims):
    purpose: Literal["release"]
    body_sha256: Digest
    payload_sha256: Digest
    root: WireId
    attempt: WireId
    nonce: WireId


class TerminalClaims(SignedClaims):
    purpose: Literal["terminal"]
    root: WireId
    attempt: WireId
    body_sha256: Digest
    message_id: WireId
    result_sha256: Digest


class Current(WireModel):
    binding_sha256: Digest
    phase: Phase
    nonce: WireId
    current: bool
    expires: Epoch


def _ordered(value):
    """RFC 8785 for the profile's JSON subset (no floating-point numbers)."""
    if isinstance(value, dict):
        return {
            key: _ordered(value[key])
            for key in sorted(value, key=lambda item: item.encode("utf-16-be"))
        }
    if isinstance(value, (list, tuple)):
        return [_ordered(item) for item in value]
    if value is None or type(value) in (str, bool):
        return value
    if type(value) is int and -(2**53 - 1) <= value <= 2**53 - 1:
        return value
    raise ValueError("value outside the dispatch JSON profile")


def canonical(value) -> bytes:
    if isinstance(value, WireModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        _ordered(value), ensure_ascii=False, allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")


def _unique_members(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate member")
    return result


def canonical_object(body: bytes) -> dict:
    value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_members)
    if type(value) is not dict or canonical(value) != body:
        raise ValueError("noncanonical dispatch object")
    return value


def parse(body: bytes, model: type[WireModel]):
    return model.model_validate(canonical_object(body))


def sign(key, claims: SignedClaims) -> str:
    return _b64(key.sign(canonical(claims)))


def verify(
    key: Ed25519PublicKey, signature: str, body: bytes, model: type[SignedClaims],
    *, issuer: str, audience: str, kid: str, now: int,
):
    try:
        key.verify(base64.urlsafe_b64decode(_signature(signature) + "=="), body)
    except (InvalidSignature, ValueError):
        raise ValueError("invalid dispatch signature") from None
    claims = parse(body, model)
    if (claims.issuer, claims.audience, claims.kid) != (issuer, audience, kid) or (
        now >= claims.expires
    ):
        raise ValueError("dispatch key scope or expiry mismatch")
    return claims
