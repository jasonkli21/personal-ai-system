"""Closed portable representation of explicit owner-set profile fields."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from personal_ai.context.profile import GlobalProfile, GlobalProfileFieldRecord

MAX_PORTABLE_BYTES = 8192
DOWNLOAD_WARNING = "Downloaded copies leave Personal AI and cannot be recalled."


class PortableProfileField(GlobalProfileFieldRecord):
    # A portable field carries its observation, never an active sharing dependency.
    shared_with_applications: tuple[()] = ()
    set_by: Literal["user"]

    @field_validator("set_at", mode="before")
    @classmethod
    def observed_as_text(cls, value):
        if not isinstance(value, str) or not 20 <= len(value) <= 40:
            raise ValueError("portable_observation_invalid")
        return value


class PortableProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["personal-ai-memory-export/v1"]
    origin: Literal["personal_ai"]
    owner_id: str = Field(min_length=1, max_length=200, pattern=r"^[!-~]+$")
    application_id: Literal["personal_ai"]
    workspace_id: None
    project_id: None
    kind: Literal["explicit_profile"]
    source: Literal["owner-global-profile"]
    revision: int = Field(strict=True, ge=0, le=2**63 - 1)
    created_at: str = Field(min_length=20, max_length=40)
    expires_at: None
    embedding: None
    restriction: Literal["owner_copy_only"]
    complete: StrictBool
    fields: tuple[PortableProfileField, ...] = Field(max_length=4)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_observations(self):
        created = datetime.fromisoformat(self.created_at)
        names = [item.field for item in self.fields]
        if (
            not self.complete
            or created.utcoffset() is None
            or any(item.set_at > created for item in self.fields)
            or names != sorted(set(names))
            or (self.revision == 0 and names)
        ):
            raise ValueError("portable_observation_invalid")
        return self


class PreviewItem(BaseModel):
    field: str
    disposition: Literal["duplicate", "conflict", "quarantine"]
    reason: Literal[
        "already_current", "revision_conflict", "foreign_scope", "source_authority_unproven"
    ]


class ImportPreview(BaseModel):
    items: tuple[PreviewItem, ...]
    commit_available: Literal[False] = False
    reason: Literal["source_authority_unavailable"] = "source_authority_unavailable"


def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def export_profile(profile: GlobalProfile, now: datetime) -> bytes:
    payload = {
        "format": "personal-ai-memory-export/v1",
        "origin": "personal_ai",
        "owner_id": profile.owner_id,
        "application_id": "personal_ai",
        "workspace_id": None,
        "project_id": None,
        "kind": "explicit_profile",
        "source": "owner-global-profile",
        "revision": profile.revision,
        "created_at": now.astimezone(UTC).isoformat(),
        "expires_at": None,
        "embedding": None,
        "restriction": "owner_copy_only",
        "complete": True,
        "fields": [
            item.model_dump(mode="json", exclude={"shared_with_applications"})
            for item in sorted(profile.fields, key=lambda item: item.field)
        ],
    }
    manifest = {**payload, "digest": digest(payload)}
    PortableProfile.model_validate(manifest)
    result = canonical_json(manifest)
    if len(result) > MAX_PORTABLE_BYTES:
        raise ValueError("portable_export_too_large")
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def parse_portable_profile(raw: bytes) -> PortableProfile:
    if not 0 < len(raw) <= MAX_PORTABLE_BYTES:
        raise ValueError("portable_size_invalid")
    payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    manifest = PortableProfile.model_validate(payload)
    unsigned = {key: value for key, value in payload.items() if key != "digest"}
    if not hmac.compare_digest(manifest.digest, digest(unsigned)):
        raise ValueError("portable_digest_invalid")
    return manifest


def preview_profile(manifest: PortableProfile, current: GlobalProfile) -> ImportPreview:
    values = {item.field: item for item in current.fields}
    items = []
    for item in manifest.fields:
        if manifest.owner_id != current.owner_id:
            disposition, reason = "quarantine", "foreign_scope"
        elif manifest.revision != current.revision:
            disposition, reason = "conflict", "revision_conflict"
        elif (
            (record := values.get(item.field)) is not None
            and item.value == record.value
            and item.set_at == record.set_at
        ):
            disposition, reason = "duplicate", "already_current"
        else:
            disposition, reason = "quarantine", "source_authority_unproven"
        items.append(PreviewItem(field=item.field, disposition=disposition, reason=reason))
    return ImportPreview(items=tuple(items))
