"""Conversation-bound Travel projection for an explicitly isolated PAS preview."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field

from personal_ai.auth.application_clients import (
    external_conversation_namespace,
    require_current_client_authority,
)
from personal_ai.auth.delegation import delegated_user_assertion
from personal_ai.auth.scope import RequestScope, current_request_scope, current_verified_principal
from personal_ai.context.authority import application_plan_source_binding
from personal_ai.context.providers import (
    ContextItem,
    ContextOperationSpec,
    ContextPreparationError,
    ContextProviderError,
    ContextProviderInputs,
    ContextProviderSpec,
    ContextSelection,
)
from personal_ai.context.runtime import ContextRuntimeContribution
from personal_ai.contracts.context_references import (
    APPLICATION_PLAN_SOURCE_ITEM_PREFIX,
    ApplicationPlanSourceAuthority,
    ApplicationPlanSourceBinding,
    ApplicationPlanSourceGrant,
    ContextAuthorityReference,
    ContextPermissionDependency,
    ContextSourceReference,
    ContextSourceSnapshot,
    PlanSourceGrantPurpose,
)
from personal_ai.services.external_turns.application_plan import BoundPlanSource

from .travel import TRAVEL_CONTEXT_PROVIDER_ID, TRAVEL_CONTEXT_SCHEMA, TravelContextReadResponse

SOURCE_PATH = "/internal/personal-ai/plan-source"
SOURCE_MAX_BYTES = 4096
CURRENT_FIELDS = ("trip_title", "trip_revision")
VERIFY_FIELDS = ("trip_revision",)
PERMISSION_PURPOSE = "confirm current owner access and Travel source revision before disclosure"
DENIED = "context_source_authority_changed"


class PlanSourceGrantReader(Protocol):
    def __call__(
        self,
        binding: ApplicationPlanSourceBinding,
        *,
        purpose: PlanSourceGrantPurpose,
        recipient: str,
        fields: tuple[str, ...],
        deadline: float,
    ) -> ApplicationPlanSourceGrant | None: ...


class _TripRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    trip_revision: int = Field(ge=0, le=9_999_999_999)


class _TripProjection(_TripRevision):
    trip_title: str = Field(min_length=1, max_length=200)


def _unique_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("duplicate property")
    return value


def _projection_fingerprint(payload):
    return sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _request_matches(binding: ApplicationPlanSourceBinding, scope: RequestScope | None) -> bool:
    principal = current_verified_principal()
    return (
        principal is not None
        and principal.authenticated
        and principal.owner_id == binding.owner_id
        and (principal.issuer, principal.subject) == (binding.human_issuer, binding.human_subject)
        and scope is not None
        and scope.owner_id == binding.owner_id
        and scope.acting_user_id == f"{principal.issuer}|{principal.subject}"
        and (scope.application_id, scope.workspace_id)
        == (binding.scope.application_id, binding.scope.workspace_id)
        and external_conversation_namespace() == binding.client_namespace
    )


class TravelPlanSourceClient:
    """One bounded signed call over the isolated host's supplied HTTP transport."""

    def __init__(
        self,
        *,
        base_url: str,
        audience: str,
        issuer: str,
        key_id: str,
        signing_key: Ed25519PrivateKey,
        service_token: Callable[..., str],
        transport: httpx.BaseTransport,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or transport is None
        ):
            raise ValueError("travel_plan_source_endpoint_invalid")
        self._base_url = base_url.rstrip("/")
        self._audience = audience
        self._issuer = issuer
        self._key_id = key_id
        self._signing_key = signing_key
        self._service_token = service_token
        self._transport = transport

    def read(self, binding: ApplicationPlanSourceBinding, *, expected_revision: str | None, deadline: float):
        if not _request_matches(binding, current_request_scope()):
            raise ContextPreparationError(DENIED)
        require_current_client_authority()
        body = {
            "schema_version": "travel-private-plan-source-v1",
            "purpose": "personal_ai_context",
            "destination_application_id": "travel",
            "workspace_id": None,
            "lane": binding.lane,
            "target_id": binding.target_id,
            "client_namespace": binding.client_namespace,
            "conversation_id": str(binding.conversation_id),
            "operation": "current" if expected_revision is None else "verify",
        }
        if expected_revision is not None:
            body["expected_source_version"] = expected_revision
        try:
            if monotonic() >= deadline:
                raise TimeoutError
            assertion = delegated_user_assertion(
                principal=current_verified_principal(),
                request_body=body,
                private_key=self._signing_key,
                issuer=self._issuer,
                audience=self._audience,
                key_id=self._key_id,
            )
            token = self._service_token(audience=self._audience, deadline=deadline)
            if not token or len(token) > 8192 or any(char.isspace() for char in token):
                raise ValueError("travel_plan_source_service_identity_invalid")
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError
            with (
                httpx.Client(
                    transport=self._transport, timeout=remaining,
                    follow_redirects=False, trust_env=False,
                ) as client,
                client.stream(
                    "POST", self._base_url + SOURCE_PATH, json=body,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-User-Delegation": assertion,
                        "Accept-Encoding": "identity",
                    },
                ) as response,
            ):
                if (
                    response.status_code != 200
                    or response.headers.get("content-type", "").strip().lower() != "application/json"
                    or response.headers.get("content-encoding", "identity").lower() != "identity"
                ):
                    raise ValueError("travel_plan_source_response_invalid")
                encoded = bytearray()
                for chunk in response.iter_bytes():
                    if len(encoded) + len(chunk) > SOURCE_MAX_BYTES or monotonic() >= deadline:
                        raise ValueError("travel_plan_source_response_invalid")
                    encoded.extend(chunk)
            raw = json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_object)
            if (
                not isinstance(raw, dict)
                or set(raw) != set(TravelContextReadResponse.model_fields)
                or raw["complete"] is not True
            ):
                raise ValueError("travel_plan_source_response_invalid")
            parsed = TravelContextReadResponse.model_validate(raw)
            if (
                parsed.schema_version != TRAVEL_CONTEXT_SCHEMA
                or parsed.application_id != "travel"
                or parsed.authoritative_empty_entities
                or parsed.continuation is not None
                or len(parsed.items) != 1
            ):
                raise ValueError("travel_plan_source_response_invalid")
            record = parsed.items[0]
            payload, fields = (
                (_TripProjection.model_validate(record.payload), CURRENT_FIELDS)
                if expected_revision is None
                else (_TripRevision.model_validate(record.payload), VERIFY_FIELDS)
            )
            entity = str(UUID(record.entity_id))
            opaque = sha256(f"trip\0{entity}".encode()).hexdigest()
            if (
                record.entity_type != "trip"
                or record.entity_id != entity
                or record.source_id != f"travel:{opaque}"
                or not re.fullmatch(r"0|[1-9][0-9]{0,9}", record.source_version)
                or record.source_version != str(payload.trip_revision)
                or (expected_revision is not None and record.source_version != expected_revision)
                or record.authority != "authoritative"
                or record.observed_at is None
                or record.observed_at.utcoffset() is None
                or record.effective_at is not None
                or record.expires_at is not None
                or record.sensitivity != "sensitive"
                or record.selection_binding is not None
                or len(record.field_sensitivity) != len(fields)
                or {(label.field, label.sensitivity) for label in record.field_sensitivity}
                != {(field, "sensitive") for field in fields}
                or record.source_refs != (ContextSourceReference(
                    kind="record", reference_id=f"travel-record:{opaque}",
                    fingerprint=_projection_fingerprint(record.payload),
                ),)
                or record.permission_dependencies != (ContextPermissionDependency(
                    permission_id=f"travel_context_read:{entity}", version=record.source_version,
                    purpose=PERMISSION_PURPOSE,
                ),)
                or monotonic() >= deadline
            ):
                raise ValueError("travel_plan_source_record_invalid")
            return record, payload
        except (httpx.HTTPError, OSError, TimeoutError, ValueError, TypeError, RecursionError):
            raise ContextProviderError("travel_plan_source_unavailable") from None


@dataclass(frozen=True)
class TravelPlanSource:
    """One private contribution with separate PAS read, runtime and model grants."""

    client: TravelPlanSourceClient
    read_grant: PlanSourceGrantReader
    runtime_grant: PlanSourceGrantReader
    model_grant: PlanSourceGrantReader
    binding: ApplicationPlanSourceBinding | None = None

    spec = ContextProviderSpec(
        provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
        source_class="domain_current",
        source_version=TRAVEL_CONTEXT_SCHEMA,
        operations=(
            ContextOperationSpec(
                operation="current", allowed_fields=CURRENT_FIELDS,
                maximum_results=1, maximum_bytes=SOURCE_MAX_BYTES, maximum_timeout_seconds=2,
            ),
        ),
        maximum_items_per_call=1,
    )
    permission_namespaces = ("travel-private-plan-source:",)

    @classmethod
    def selection(cls, target_id: str, *, max_tokens: int) -> BoundPlanSource:
        return BoundPlanSource(target_id, ContextSelection(
            provider_id=cls.spec.provider_id, operation="current", fields=CURRENT_FIELDS,
            max_results=1, max_bytes=SOURCE_MAX_BYTES, max_tokens=max_tokens,
            timeout_seconds=2, required=True,
        ))

    def contribution(self) -> ContextRuntimeContribution:
        return ContextRuntimeContribution(
            provider_factories={self.spec.provider_id: self},
            permission_revalidators=(self,),
        )

    def create(self, inputs: ContextProviderInputs) -> TravelPlanSource:
        binding = application_plan_source_binding.get()
        pending = inputs.pending_message
        if (
            binding is None
            or binding.scope.application_id != "travel"
            or binding.scope.workspace_id is not None
            or not _request_matches(binding, inputs.scope)
            or pending is None
            or (pending.conversation_id, pending.owner_id, pending.application_id, pending.workspace_id)
            != (binding.conversation_id, binding.owner_id, "travel", None)
        ):
            raise ContextPreparationError(DENIED)
        return replace(self, binding=binding)

    def validate_selection(self, selection, inputs) -> None:
        if (
            self.binding is None
            or not _request_matches(self.binding, inputs.scope)
            or selection.fields != CURRENT_FIELDS
            or selection.operation != "current"
            or selection.entity_refs
            or selection.federation is not None
            or selection.target_scope is not None
            or selection.window_start is not None
            or selection.max_results != 1
            or selection.max_bytes != SOURCE_MAX_BYTES
            or not selection.required
        ):
            raise ContextPreparationError(DENIED)

    def _grants(self, binding, *, deadline):
        grants = []
        for reader, purpose, recipient in (
            (self.read_grant, "source-read", binding.target_id),
            (self.runtime_grant, "runtime-handoff", binding.runtime_recipient),
            (self.model_grant, "inference-disclosure", binding.model_recipient),
        ):
            if monotonic() >= deadline:
                raise ContextPreparationError(DENIED)
            try:
                grant = reader(
                    binding, purpose=purpose, recipient=recipient,
                    fields=CURRENT_FIELDS, deadline=deadline,
                )
            except Exception:  # noqa: BLE001 - unavailable authority denies the read
                raise ContextPreparationError(DENIED) from None
            if (
                not isinstance(grant, ApplicationPlanSourceGrant)
                or grant.binding != binding
                or grant.fields != CURRENT_FIELDS
                or (grant.purpose, grant.recipient) != (purpose, recipient)
                or grant.expires_at <= datetime.now(UTC)
            ):
                raise ContextPreparationError(DENIED)
            grants.append(grant)
        return tuple(grants)

    def fetch(self, selection, scope, *, deadline):
        binding = self.binding
        if (
            binding is None
            or binding != application_plan_source_binding.get()
            or not _request_matches(binding, scope)
        ):
            raise ContextPreparationError(DENIED)
        require_current_client_authority()
        grants = self._grants(binding, deadline=deadline)
        record, payload = self.client.read(binding, expected_revision=None, deadline=deadline)
        authority = ApplicationPlanSourceAuthority(
            binding=binding, fields=CURRENT_FIELDS, source_id=record.source_id,
            item_id=APPLICATION_PLAN_SOURCE_ITEM_PREFIX + record.source_id,
            source_version=record.source_version,
            source_fingerprint=record.source_refs[0].fingerprint,
            source_sensitivity=record.sensitivity,
            field_sensitivities=tuple(
                (field.field, field.sensitivity) for field in record.field_sensitivity
            ),
            observed_at=record.observed_at,
            grants=grants,
        )
        return (ContextItem(
            source_class=self.spec.source_class, provider_id=self.spec.provider_id,
            source_id=record.source_id, item_id=authority.item_id,
            source_version=record.source_version, owner_id=binding.owner_id,
            application_id="travel", workspace_id=None,
            authority=record.authority, observed_at=record.observed_at,
            effective_at=record.effective_at, expires_at=record.expires_at,
            sensitivity=record.sensitivity, source_refs=record.source_refs,
            permission_dependencies=record.permission_dependencies,
            field_sensitivity=record.field_sensitivity, payload=payload,
            application_plan_authority=authority,
        ),)

    def supports(self, _dependency) -> bool:
        # A legacy ACL pointer alone cannot authorize the private source.
        return False

    def supports_application_plan_source(self, snapshot: ContextSourceSnapshot) -> bool:
        return snapshot.provider_id == self.spec.provider_id

    def is_application_plan_source_current(self, snapshot: ContextSourceSnapshot) -> bool:
        authority = snapshot.application_plan_authority
        if (
            authority is None
            or not self.supports_application_plan_source(snapshot)
            or authority.fields != CURRENT_FIELDS
            or authority.binding != application_plan_source_binding.get()
            or not _request_matches(authority.binding, current_request_scope())
            or snapshot.expires_at is not None
        ):
            return False
        deadline = monotonic() + 0.75
        require_current_client_authority()
        if self._grants(authority.binding, deadline=deadline) != authority.grants:
            return False
        record, _ = self.client.read(
            authority.binding, expected_revision=snapshot.source_version, deadline=deadline,
        )
        reference = record.source_refs[0]
        return (
            monotonic() < deadline
            and datetime.now(UTC) < authority.expires_at
            and record.source_id == snapshot.source_id
            and record.source_version == snapshot.source_version
            and record.observed_at == authority.observed_at
            and record.sensitivity == authority.source_sensitivity
            and set(authority.field_sensitivities) == {
                (field, record.sensitivity) for field in CURRENT_FIELDS
            }
            and snapshot.permission_dependencies == record.permission_dependencies
            and snapshot.source_refs == (ContextAuthorityReference(
                kind=reference.kind,
                reference_digest=sha256(f"{reference.kind}\0{reference.reference_id}".encode()).hexdigest(),
                fingerprint=authority.source_fingerprint,
            ),)
        )
