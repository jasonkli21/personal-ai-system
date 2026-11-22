"""Test composition for the proposed Health preview wire, with no hosted transport."""

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from typing import Literal
from uuid import UUID

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from personal_ai.auth.application_clients import require_current_client_authority
from personal_ai.auth.scope import current_request_scope
from personal_ai.context.authority import application_plan_source_binding
from personal_ai.context.providers import (
    ContextFieldSensitivity,
    ContextItem,
    ContextOperationSpec,
    ContextPreparationError,
    ContextProviderSpec,
    ContextSelection,
)
from personal_ai.context.runtime import ContextRuntimeContribution
from personal_ai.contracts.context_references import (
    APPLICATION_PLAN_SOURCE_ITEM_PREFIX,
    ApplicationPlanSourceAuthority,
    ApplicationPlanSourceGrant,
    ContextEntityReference,
    ContextPermissionDependency,
    ContextSourceReference,
)
from personal_ai.services.external_turns.application_plan import BoundPlanSource

SCHEMA = "health-context-read-v1"
CATEGORY = "profile_preferences"
PROVIDER = "health.preview_preferences"
FIELDS = ("record",)
MAX_BYTES = 4096
DENIED = "context_no_ai_route"
ORIGIN = "https://health-fixture.invalid"


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def unique(pairs):
    value = dict(pairs)
    if len(pairs) != len(value):
        raise ValueError("duplicate JSON property")
    return value


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Value(Wire):
    type: Literal["text"]
    value: Literal["bullets"]


class Record(Wire):
    kind: Literal["preference"]
    category: Literal["preferences"]
    key: Literal["r5_synthetic_presentation_format"]
    label: Literal["Synthetic presentation format"]
    value: Value


class Payload(Wire):
    record: Record


class ProfilePayload(Payload):
    category: Literal["profile_preferences"]
    object_type: Literal["profile_item"]
    # The typed Health response includes these as null unless omitted by the caller.
    domain: None = None
    notes: None = None
    time: None = None
    interval_end: None = None
    units: None = None
    source_kind: None = None
    confirmation_status: None = None
    quality: None = None
    uncertainty: None = None
    validity: None = None


class FieldSensitivity(Wire):
    field: Literal["record"]
    sensitivity: Literal["restricted"]


class SourceReference(Wire):
    kind: Literal["source", "record"]
    reference_id: str
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class Permission(Wire):
    permission_id: str
    purpose: Literal["personal_ai_context"]
    version: str


class ProfileItem(Wire):
    object_id: UUID
    object_type: Literal["profile_item"]
    object_revision: int = Field(ge=1)
    schema_version: Literal[1]
    source_id: UUID
    source_version: str = Field(min_length=1, max_length=100)
    source_kind: Literal["manual"]
    confirmation_status: Literal["user_confirmed"]
    authority: Literal["authoritative"]
    active_state: Literal["active"]
    observed_at: AwareDatetime
    effective_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    sensitivity: Literal["restricted"]
    field_sensitivity: tuple[FieldSensitivity]
    source_refs: tuple[SourceReference, SourceReference]
    permission_dependencies: tuple[Permission]
    payload: ProfilePayload


class Version(Wire):
    object_id: UUID
    version: str


class Envelope(Wire):
    schema_version: Literal["health-context-read-v1"]
    application_id: Literal["health"]
    workspace_id: None
    operation: Literal["profile", "verify"]
    items: tuple[ProfileItem, ...]
    categories: tuple[()]  # This app contribution has no catalog surface.
    permission_versions: tuple[Version, ...]
    truncated: Literal[False]


@dataclass(frozen=True)
class Selection:
    object_id: UUID
    revision: int

    @property
    def entity(self):
        return ContextEntityReference(
            application_id="health",
            entity_type="profile_item",
            entity_id=str(self.object_id),
        )

    @property
    def dependency(self):
        return f"health_context_read:{CATEGORY}:profile_item:{self.object_id}"

    @property
    def version(self):
        return f"health-object-v1:r{self.revision}:ai1:cross1"

    def request(self, operation):
        return {
            "schema_version": SCHEMA,
            "application_id": "health",
            "workspace_id": None,
            "purpose": "personal_ai_context",
            "operation": operation,
            "category": CATEGORY,
            "entity_refs": [{"object_type": "profile_item", "object_id": str(self.object_id)}],
            "fields": ["record" if operation == "profile" else "permission_version"],
            "max_results": 1,
            "max_bytes": MAX_BYTES,
        }


@dataclass(frozen=True)
class HealthSourceClient:
    # The candidate wire is consumed from a private mock. No live reverse credential exists.
    transport: httpx.MockTransport

    def request(self, selection, operation, *, deadline):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ContextPreparationError(DENIED)
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    trust_env=False,
                    follow_redirects=False,
                ) as client,
                client.stream(
                    "POST",
                    f"{ORIGIN}/source",
                    json=selection.request(operation),
                    timeout=remaining,
                ) as response,
            ):
                response.raise_for_status()
                if response.headers.get("content-type") != "application/json":
                    raise ValueError("wrong media type")
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > MAX_BYTES or monotonic() >= deadline:
                        raise ValueError("source response limit")
                    body.extend(chunk)
            json.loads(body, object_pairs_hook=unique)
            parsed = Envelope.model_validate_json(bytes(body))
            if parsed.operation != operation:
                raise ValueError("wrong operation")
            return parsed
        except (ValueError, RecursionError, httpx.HTTPError):
            raise ContextPreparationError(DENIED) from None

    def read(self, selection, *, deadline):
        profile = self.request(selection, "profile", deadline=deadline)
        if len(profile.items) != 1 or profile.permission_versions:
            raise ContextPreparationError(DENIED)
        item = profile.items[0]
        fingerprint = digest(item.payload.model_dump(mode="json"))
        now = datetime.now(UTC)
        if (
            (item.object_id, item.object_revision) != (selection.object_id, selection.revision)
            or item.source_version != f"health-object-v1:r{selection.revision}:schema-1"
            or {(ref.kind, ref.reference_id, ref.fingerprint) for ref in item.source_refs}
            != {
                ("record", str(item.object_id), fingerprint),
                ("source", str(item.source_id), fingerprint),
            }
            or item.permission_dependencies
            != (
                Permission(
                    permission_id=selection.dependency,
                    version=selection.version,
                    purpose="personal_ai_context",
                ),
            )
            or item.observed_at > now
            or (item.effective_at is not None and item.effective_at > now)
            or (item.expires_at is not None and item.expires_at <= now)
        ):
            raise ContextPreparationError(DENIED)
        verified = self.request(selection, "verify", deadline=deadline)
        if verified.items or verified.permission_versions != (
            Version(object_id=selection.object_id, version=selection.version),
        ):
            raise ContextPreparationError(DENIED)
        return item


@dataclass(frozen=True)
class HealthSource:
    client: HealthSourceClient
    installed: Callable
    grant: Callable
    binding: object = None
    permission_namespaces = ("health_context_read:",)

    spec = ContextProviderSpec(
        provider_id=PROVIDER,
        source_class="domain_current",
        source_version=SCHEMA,
        operations=(
            ContextOperationSpec(
                operation="current",
                allowed_fields=FIELDS,
                accepts_entity_refs=True,
                maximum_results=1,
                maximum_bytes=MAX_BYTES,
                maximum_timeout_seconds=2,
            ),
        ),
        maximum_items_per_call=1,
    )

    @classmethod
    def selection(cls, target_id, selected):
        return BoundPlanSource(
            target_id,
            ContextSelection(
                provider_id=PROVIDER,
                operation="current",
                fields=FIELDS,
                entity_refs=(selected.entity,),
                max_results=1,
                max_bytes=MAX_BYTES,
                max_tokens=1536,
                timeout_seconds=2,
                required=True,
            ),
        )

    def contribution(self):
        return ContextRuntimeContribution(
            provider_factories={PROVIDER: self},
            permission_revalidators=(self,),
        )

    def _selected(self, binding, scope):
        if (
            binding is None
            or scope is None
            or binding != application_plan_source_binding.get()
            or (scope.application_id, scope.workspace_id) != ("health", None)
            or (binding.owner_id, f"{binding.human_issuer}|{binding.human_subject}")
            != (scope.owner_id, scope.acting_user_id)
        ):
            raise ContextPreparationError(DENIED)
        require_current_client_authority()
        selected = self.installed(binding)
        if selected is None:
            raise ContextPreparationError(DENIED)
        return selected

    def create(self, inputs):
        binding = application_plan_source_binding.get()
        self._selected(binding, inputs.scope)
        pending = inputs.pending_message
        if pending is None or pending.conversation_id != binding.conversation_id:
            raise ContextPreparationError(DENIED)
        return replace(self, binding=binding)

    def validate_selection(self, selection, inputs):
        installed = self._selected(self.binding, inputs.scope)
        if selection != self.selection(self.binding.target_id, installed).selection:
            raise ContextPreparationError(DENIED)

    def _fetch(self, binding, scope, deadline):
        selection = self._selected(binding, scope)
        recipients = (
            ("source-read", binding.target_id),
            ("runtime-handoff", binding.runtime_recipient),
            ("inference-disclosure", binding.model_recipient),
        )
        grants = tuple(self.grant(binding, purpose) for purpose, _ in recipients)
        if any(
            not isinstance(grant, ApplicationPlanSourceGrant)
            or (grant.binding, grant.purpose, grant.recipient, grant.fields)
            != (binding, purpose, recipient, FIELDS)
            or grant.expires_at <= datetime.now(UTC)
            for grant, (purpose, recipient) in zip(grants, recipients, strict=True)
        ):
            raise ContextPreparationError(DENIED)
        item = self.client.read(selection, deadline=deadline)
        payload = Payload(record=item.payload.record)
        # The wire hash authenticates the Health envelope. PAS hashes its one-field projection.
        fingerprint = digest(payload.model_dump(mode="json"))
        source_id = str(item.source_id)
        revision = str(item.object_revision)
        authority = ApplicationPlanSourceAuthority(
            binding=binding,
            fields=FIELDS,
            source_id=source_id,
            item_id=APPLICATION_PLAN_SOURCE_ITEM_PREFIX + str(item.object_id),
            source_version=revision,
            source_fingerprint=fingerprint,
            source_sensitivity="restricted",
            field_sensitivities=(("record", "restricted"),),
            observed_at=item.observed_at,
            grants=grants,
        )
        return ContextItem(
            source_class="domain_current",
            provider_id=PROVIDER,
            source_id=source_id,
            item_id=authority.item_id,
            source_version=revision,
            owner_id=binding.owner_id,
            application_id="health",
            authority=item.authority,
            observed_at=item.observed_at,
            effective_at=item.effective_at,
            expires_at=item.expires_at,
            sensitivity=item.sensitivity,
            entity_refs=(selection.entity,),
            source_refs=(
                ContextSourceReference(
                    kind="record",
                    reference_id=str(item.object_id),
                    fingerprint=fingerprint,
                ),
            ),
            permission_dependencies=(
                ContextPermissionDependency(
                    source_scope=binding.scope,
                    entity_ref=selection.entity,
                    source_revision=revision,
                    purpose="personal_ai_context",
                    permission_id=selection.dependency,
                    version=selection.version,
                    owner_id=binding.owner_id,
                    acting_user_id=scope.acting_user_id,
                ),
            ),
            field_sensitivity=(ContextFieldSensitivity(field="record", sensitivity="restricted"),),
            payload=payload,
            selected_operation="current",
            application_plan_authority=authority,
        )

    def fetch(self, selection, scope, *, deadline):
        return (self._fetch(self.binding, scope, deadline),)

    def supports(self, _dependency):
        return False

    def supports_application_plan_source(self, snapshot):
        return snapshot.provider_id == PROVIDER

    def is_application_plan_source_current(self, snapshot):
        if not self.supports_application_plan_source(snapshot):
            return False
        live = self._fetch(
            application_plan_source_binding.get(), current_request_scope(), monotonic() + 0.75
        )
        return live.authority_snapshot() == snapshot
