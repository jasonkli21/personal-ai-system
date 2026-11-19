"""Strict wire contract for the private, synthetic source composition."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

SCHEMA = "app-context-v1"
MAX_MESSAGE = 8192
MAX_STRING = 2048
Kind = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
Operation = Literal["describe", "search", "fetch"]
Sensitivity = Literal["public", "personal", "sensitive", "restricted"]
OpaqueID = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")]
AppID = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Positive = Annotated[int, Field(ge=1, le=2**53 - 1)]
Code = Literal[
    "invalid_request", "unauthenticated", "unavailable", "stale_dependency",
    "limit_exceeded", "rate_limited", "source_unavailable",
]


class ProtocolError(Exception):
    def __init__(self, code: Code):
        self.code = code
        super().__init__(code)


def encode(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    try:
        return json.dumps(
            value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode()
    except (ValueError, TypeError, RecursionError) as error:
        raise ProtocolError("invalid_request") from error


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def screen(raw):
    if len(raw) > MAX_MESSAGE:
        raise ProtocolError("limit_exceeded")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_number(_):
    raise ValueError("unsupported JSON number")


def decode(raw):
    screen(raw)
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
            parse_constant=_reject_number, parse_float=_reject_number,
        )
        if type(value) is not dict:
            raise ValueError("object required")
        # A JSON surrogate escape may decode successfully but cannot round-trip to UTF-8.
        encode(value)
        return value
    except (ValueError, RecursionError) as error:
        raise ProtocolError("invalid_request") from error


def checked(model, value):
    try:
        return model.model_validate(value)
    except ValidationError as error:
        raise ProtocolError("invalid_request") from error


def utf8_bound(value, limit):
    if len(value.encode()) > limit:
        raise ProtocolError("limit_exceeded")


def _utc(value):
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", value
    ):
        raise ValueError("UTC RFC 3339 timestamp required")
    return datetime.fromisoformat(value).astimezone(UTC)


WireTime = Annotated[datetime, BeforeValidator(_utc)]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Binding(Message):
    schema_version: Literal["app-context-v1"] = SCHEMA
    application_id: AppID
    installation_id: OpaqueID
    origin: Annotated[str, Field(pattern=r"^https://[a-z][a-z0-9.-]+\.invalid$")]
    service_identity: OpaqueID
    projection_schema_id: OpaqueID
    max_sensitivity: Sensitivity
    max_ttl_seconds: Annotated[int, Field(ge=1, le=300)]


class Install(Binding):
    schema_version: Literal["app-context-v1"]
    operation: Literal["install"]


class Update(Binding):
    schema_version: Literal["app-context-v1"]
    operation: Literal["update"]
    expected_revision: OpaqueID


class Disable(Message):
    schema_version: Literal["app-context-v1"]
    operation: Literal["disable"]
    installation_id: OpaqueID
    expected_revision: OpaqueID


class Scoped(Message):
    schema_version: Literal["app-context-v1"]
    source_id: OpaqueID
    application_id: AppID
    workspace_id: OpaqueID


class Describe(Scoped):
    operation: Literal["describe"]


class Search(Scoped):
    operation: Literal["search"]
    record_kind: Kind
    query: str
    limit: Annotated[int, Field(ge=1, le=10)]
    cursor: Digest | None = None


class Fetch(Scoped):
    operation: Literal["fetch"]
    record_ref: OpaqueID
    source_revision: OpaqueID


REQUESTS = {"describe": Describe, "search": Search, "fetch": Fetch}


class Claims(Message):
    iss: OpaqueID
    aud: OpaqueID
    sub: OpaqueID
    owner_id: OpaqueID
    acting_user_id: OpaqueID | None
    application_id: AppID
    workspace_id: OpaqueID
    source_id: OpaqueID
    installation_epoch: Positive
    kind_allowlist: list[Kind] = Field(min_length=1, max_length=2)
    field_allowlist: list[OpaqueID] = Field(min_length=1, max_length=2)
    purpose: OpaqueID
    recipient: OpaqueID
    operation: Operation
    request_digest: Digest
    nonce: OpaqueID
    grant_id: OpaqueID
    grant_epoch: Positive
    iat: Positive
    exp: Positive
    kid: OpaqueID


class FieldDescription(Message):
    name: OpaqueID
    type: Literal["string", "integer"]
    sensitivity: Sensitivity


class KindDescription(Message):
    name: Kind
    fields: list[FieldDescription] = Field(min_length=1, max_length=2)


class Description(Message):
    schema_version: Literal["app-context-v1"]
    source_id: OpaqueID
    installation_revision: OpaqueID
    installation_epoch: Positive
    operations: list[Operation] = Field(max_length=2)
    kinds: list[KindDescription] = Field(min_length=1, max_length=2)
    max_page_size: Literal[10]
    max_record_bytes: Literal[8192]
    max_ttl_seconds: Annotated[int, Field(ge=1, le=300)]


class Hit(Message):
    record_ref: OpaqueID
    source_revision: OpaqueID
    record_kind: Kind
    effective_at: WireTime
    title: str


class Page(Scoped):
    record_kind: Kind
    watermark: OpaqueID
    items: list[Hit] = Field(max_length=10)
    next_cursor: Digest | None


class Projection(Scoped):
    record_ref: OpaqueID
    source_revision: OpaqueID
    record_kind: Kind
    watermark: OpaqueID
    observed_at: WireTime
    effective_at: WireTime
    expires_at: WireTime
    sensitivity: Sensitivity
    content_projection: dict[OpaqueID, str | int] = Field(min_length=1, max_length=2)


class ErrorDetail(Message):
    code: Code
    request_id: OpaqueID


class ErrorEnvelope(Message):
    schema_version: Literal["app-context-v1"]
    error: ErrorDetail
