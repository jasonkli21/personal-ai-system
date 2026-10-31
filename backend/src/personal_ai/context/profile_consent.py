"""Bounded, explicit profile disclosure consent; no inferred-memory authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.context.profile import GlobalProfile, GlobalProfileFieldRecord, ProfileField
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
)

PURPOSE = "assist_response"
MAX_GRANTS = 32


class ConsentError(ValueError):
    """Safe denial code, never private content or record identifiers."""


class ProfileShareIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    operation: Literal["grant", "revoke"]
    expected_revision: int = Field(ge=0)
    expected_profile_revision: int = Field(ge=1)
    grant_id: UUID
    field: ProfileField
    destination: ApplicationScope
    purpose: Literal["assist_response"] = PURPOSE
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("profile_share_timezone_required")
        return value.astimezone(UTC)

    def digest(self, actor: str) -> str:
        return sha256((actor + "\0" + self.model_dump_json()).encode()).hexdigest()


class ProfileShare(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    grant_id: UUID
    field: ProfileField
    destination: ApplicationScope
    acting_user_id: str = Field(min_length=1, max_length=512)
    purpose: Literal["assist_response"] = PURPOSE
    profile_revision: int = Field(ge=1)
    value_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    issued_at: datetime
    expires_at: datetime
    epoch: Literal[1, 2] = 1
    revoked: bool = False

    @model_validator(mode="after")
    def lifecycle_is_valid(self):
        if (self.issued_at.tzinfo is None or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at <= self.issued_at + timedelta(days=30)
            or self.revoked != (self.epoch == 2)):
            raise ValueError("profile_share_record_invalid")
        return self


class ProfileShareReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    intent_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    grant_id: UUID
    revision: int = Field(ge=1)
    operation: Literal["grant", "revoke"]


class ProfileConsents(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["profile-consents-v1"] = "profile-consents-v1"
    owner_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(default=0, ge=0)
    grants: tuple[ProfileShare, ...] = Field(default=(), max_length=MAX_GRANTS)
    receipts: tuple[ProfileShareReceipt, ...] = Field(default=(), max_length=2 * MAX_GRANTS)
    # Non-authorizing migration archive. Never consulted by readers.
    legacy_sharing: dict[str, list[str]] = Field(default_factory=dict, max_length=4)

    @model_validator(mode="after")
    def ledger_is_valid(self):
        grant_ids = {g.grant_id for g in self.grants}
        if (len(grant_ids) != len(self.grants)
            or len({r.operation_id for r in self.receipts}) != len(self.receipts)
            or len(self.receipts) != self.revision
            or any(r.grant_id not in grant_ids for r in self.receipts)
            or sorted(r.revision for r in self.receipts) != list(range(1, self.revision + 1))):
            raise ValueError("profile_share_ledger_invalid")
        return self


def value_fingerprint(field: GlobalProfileFieldRecord) -> str:
    return sha256(field.model_dump_json().encode()).hexdigest()


def transition_consents(current, profile, actor, intent, now):
    """Pure atomic transition shared by PG and fake. Replays never reapply state."""
    digest = intent.digest(actor)
    for receipt in current.receipts:
        if receipt.operation_id == intent.operation_id:
            if receipt.intent_digest != digest:
                raise ConsentError("profile_share_conflict")
            return current, receipt
    if current.revision != intent.expected_revision:
        raise ConsentError("profile_share_conflict")
    grants = list(current.grants)
    existing = next((g for g in grants if g.grant_id == intent.grant_id), None)
    if intent.operation == "grant":
        field = next((f for f in profile.fields if f.field == intent.field), None)
        if profile.revision != intent.expected_profile_revision or field is None:
            raise ConsentError("profile_share_conflict")
        if existing is not None:
            raise ConsentError("profile_share_conflict")
        if len(grants) >= MAX_GRANTS:
            raise ConsentError("profile_share_capacity")
        if not now < intent.expires_at <= now + timedelta(days=30):
            raise ConsentError("profile_share_expiry_invalid")
        # Replacement is an affirmative new grant, and permanently supersedes
        # older coverage. Revoking the newest must never reveal an older grant.
        grants = [
            grant.model_copy(update={"revoked": True, "epoch": 2})
            if (not grant.revoked and grant.field == intent.field
                and grant.destination == intent.destination and grant.acting_user_id == actor)
            else grant for grant in grants
        ]
        grants.append(ProfileShare(
            grant_id=intent.grant_id, field=intent.field, destination=intent.destination,
            acting_user_id=actor, profile_revision=profile.revision,
            value_fingerprint=value_fingerprint(field), issued_at=now,
            expires_at=intent.expires_at,
        ))
    else:
        # Revoke remains possible after profile edits, expiry or destination loss.
        if existing is None or existing.revoked or (
            existing.acting_user_id != actor
            or existing.field != intent.field or existing.destination != intent.destination
            or existing.profile_revision != intent.expected_profile_revision
            or existing.expires_at != intent.expires_at
        ):
            raise ConsentError("profile_share_conflict")
        grants[grants.index(existing)] = existing.model_copy(update={"revoked": True, "epoch": 2})
    receipt = ProfileShareReceipt(
        operation_id=intent.operation_id, intent_digest=digest, grant_id=intent.grant_id,
        revision=current.revision + 1, operation=intent.operation,
    )
    return current.model_copy(update={
        "revision": current.revision + 1, "grants": tuple(grants),
        "receipts": (*current.receipts, receipt),
    }), receipt


def authorized_fields(profile: GlobalProfile, consents: ProfileConsents, scope, fields, now):
    if (scope.acting_user_id is None or profile.owner_id != scope.owner_id
        or consents.owner_id != scope.owner_id):
        return ()
    destination = ApplicationScope(application_id=scope.application_id, workspace_id=scope.workspace_id)
    by_name = {item.field: item for item in profile.fields}
    output = []
    for name in dict.fromkeys(fields):
        item = by_name.get(name)
        if item is None:
            continue
        for grant in reversed(consents.grants):
            if (
                not grant.revoked and grant.epoch == 1 and grant.field == name
                and grant.destination == destination and grant.acting_user_id == scope.acting_user_id
                and grant.issued_at <= now < grant.expires_at
                and grant.profile_revision == profile.revision
                and grant.value_fingerprint == value_fingerprint(item)
            ):
                output.append((grant, item))
                break
    return tuple(output)


def share_dependency(owner_id: str, grant: ProfileShare):
    source = ApplicationScope()
    return ContextPermissionDependency(
        permission_id=f"global_profile_share:{grant.field}:{grant.destination.application_id}",
        version=sha256(grant.model_dump_json().encode()).hexdigest(), purpose=PURPOSE,
        owner_id=owner_id, acting_user_id=grant.acting_user_id, source_scope=source,
        entity_ref=ContextEntityReference(
            entity_type="global_profile_field", entity_id=str(grant.grant_id),
            application_id=source.application_id,
        ),
        source_revision=str(grant.profile_revision),
        # Same-application scope binding uses source_scope/entity_ref instead.
        source_application_id=(source.application_id if grant.destination.application_id != source.application_id else None),
        destination_application_id=(grant.destination.application_id if grant.destination.application_id != source.application_id else None),
        destination_workspace_id=grant.destination.workspace_id,
    )


def destination_allowed(registry, principal, destination, field):
    """Current installed destination, workspace rights and disclosure policy."""
    from personal_ai.applications.contracts import ApplicationContextRequest
    from personal_ai.context.authorization import authorize_context_selections
    from personal_ai.context.providers import ContextSelection

    if registry is None or principal is None or not principal.authenticated:
        return False
    try:
        registration = registry.registration(destination.application_id)
        definition = registration.definition
        if not any(cap.capability_id == "global_profile" and cap.available and cap.feature_gate is None
                   for cap in registration.context_providers):
            return False
        if (definition.workspace_kind == "required" and destination.workspace_id is None
            or definition.workspace_kind == "unsupported" and destination.workspace_id is not None):
            return False
        if destination.workspace_id is not None and not registry.workspace_authorizer.is_member(
            principal, destination.application_id, destination.workspace_id
        ):
            return False
        scope = RequestScope(
            owner_id=principal.owner_id, acting_user_id=f"{principal.issuer}|{principal.subject}",
            request_id="profile-consent-check", **destination.model_dump(),
        )
        context = ApplicationContextRequest(
            definition=definition, scope=scope,
            context_provider_capabilities=registration.context_providers,
            tool_capabilities=registration.tools,
        )
        authorize_context_selections(context, (ContextSelection(
            provider_id="global_profile", operation="profile", fields=(field,), max_results=1,
        ),))
        return True
    except Exception:  # noqa: BLE001 - unavailable registration/membership/policy denies
        return False


def shared_memory_view_status():
    """No production issuer/source lease: never resolve or return record content."""
    return {"available": False, "reason": "original_source_authority_unavailable"}


class ProfileConsentService:
    """Owner management; identity is bound by the API, never the submitted intent."""

    def __init__(self, repository, registry, principal):
        self.repository, self.registry, self.principal = repository, registry, principal
        self.owner_id = principal.owner_id
        self.actor = f"{principal.issuer}|{principal.subject}"

    def list(self):
        state = self.repository.get_consents(self.owner_id)
        profile = self.repository.get(self.owner_id)
        fields = {f.field: f for f in profile.fields}
        return {
            "revision": state.revision,
            "profile_revision": profile.revision,
            "grants": [
                {**grant.model_dump(mode="json"), "value": (
                    fields[grant.field].value
                    if grant.field in fields and grant.profile_revision == profile.revision
                    and value_fingerprint(fields[grant.field]) == grant.value_fingerprint else None
                )} for grant in state.grants
            ],
            "warning": "Past provider sends cannot be recalled. Profile edits require fresh consent.",
            "shared_memory_view": shared_memory_view_status(),
        }

    def mutate(self, intent):
        # Reconcile before current destination/TTL checks. An old receipt is an
        # observation, not authority to reapply a revoked/expired grant.
        state = self.repository.get_consents(self.owner_id)
        for receipt in state.receipts:
            if receipt.operation_id == intent.operation_id:
                if receipt.intent_digest != intent.digest(self.actor):
                    raise ConsentError("profile_share_conflict")
                return receipt
        if intent.operation == "grant" and not destination_allowed(
            self.registry, self.principal, intent.destination, intent.field
        ):
            raise ConsentError("profile_share_destination_denied")
        return self.repository.mutate_consent(self.owner_id, self.actor, intent)
