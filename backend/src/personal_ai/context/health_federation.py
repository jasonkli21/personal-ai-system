"""Narrow Health federation exports with a request-bound user assertion."""

from __future__ import annotations

import base64
import hashlib
import re
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.delegation import delegated_user_assertion
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    current_verified_principal,
)
from personal_ai.auth.service_tokens import fetch_google_service_token
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextFieldSensitivity,
    ContextItem,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderError,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.federation.broker import FederationExportResult
from personal_ai.federation.contracts import FederationGrant, FederationGrantIntent

HEALTH_FEDERATION_EXPORT_PATH = "/v1/integrations/personal-ai/federation-export"
HEALTH_FEDERATION_EXPORT_SCHEMA = "health-federation-export-v1"
HEALTH_DIETARY_TO_TRAVEL_PROVIDER_ID = "federation.health_dietary_to_travel"
HEALTH_ERGONOMIC_TO_SHOPPING_PROVIDER_ID = "federation.health_ergonomic_to_shopping"
HEALTH_FEDERATION_PURPOSES = {
    "health_dietary_restrictions_to_travel": (
        "dietary_restrictions",
        "travel",
        "dietary_restrictions",
        HEALTH_DIETARY_TO_TRAVEL_PROVIDER_ID,
    ),
    "health_ergonomic_constraints_to_shopping": (
        "ergonomic_constraints",
        "shopping",
        "ergonomic_constraints",
        HEALTH_ERGONOMIC_TO_SHOPPING_PROVIDER_ID,
    ),
}


class HealthFederationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["health-federation-export-v1"] = HEALTH_FEDERATION_EXPORT_SCHEMA
    application_id: Literal["health"] = "health"
    workspace_id: None = None
    operation: Literal["read", "verify"]
    category: Literal["dietary_restrictions", "ergonomic_constraints"]
    entity_type: Literal["profile_item"] = "profile_item"
    entity_id: UUID
    purpose: Literal[
        "health_dietary_restrictions_to_travel",
        "health_ergonomic_constraints_to_shopping",
    ]
    destination_application_id: Literal["travel", "shopping"]
    fields: tuple[str, ...] = Field(min_length=1, max_length=1)
    max_bytes: Annotated[int, Field(ge=512, le=8192)] = 4096


class HealthFederationSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["record", "source"]
    reference_id: str = Field(min_length=1, max_length=100)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class HealthFederationPermissionDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    permission_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    source_application_id: Literal["health"] = "health"
    destination_application_id: Literal["travel", "shopping"]


class HealthDietaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    dietary_restrictions: str | tuple[str, ...] | None


class HealthErgonomicPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ergonomic_constraints: str | tuple[str, ...] | None


class HealthFederationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    category: Literal["dietary_restrictions", "ergonomic_constraints"]
    entity_type: Literal["profile_item"] = "profile_item"
    entity_id: UUID
    source_revision: Annotated[int, Field(ge=1)]
    source_version: str = Field(min_length=1, max_length=100)
    sensitivity: Literal["restricted"] = "restricted"
    payload: HealthDietaryPayload | HealthErgonomicPayload | None = None
    source_refs: tuple[HealthFederationSourceReference, ...] = Field(
        min_length=2, max_length=2
    )
    permission_dependencies: tuple[HealthFederationPermissionDependency, ...] = Field(
        min_length=1, max_length=1
    )


class HealthFederationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["health-federation-export-v1"] = HEALTH_FEDERATION_EXPORT_SCHEMA
    application_id: Literal["health"] = "health"
    workspace_id: None = None
    operation: Literal["read", "verify"]
    complete: StrictBool
    authoritative_empty: StrictBool
    continuation: None = None
    item: HealthFederationRecord


class HealthFederationExportClient:
    """Call Health with separate service identity and a short-lived signed user assertion."""

    def __init__(
        self,
        *,
        base_url: str,
        service_audience: str,
        service_account: str,
        delegation_issuer: str,
        delegation_key_id: str,
        delegation_audience: str,
        delegation_private_key: Ed25519PrivateKey,
        timeout_seconds: float = 3.0,
        service_token_fetcher=fetch_google_service_token,
        principal_provider=current_verified_principal,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("health_federation_base_url_invalid")
        self.base_url = base_url.rstrip("/")
        self.service_audience = service_audience
        self.service_account = service_account
        self.delegation_issuer = delegation_issuer
        self.delegation_key_id = delegation_key_id
        self.delegation_audience = delegation_audience
        self.delegation_private_key = delegation_private_key
        self.timeout_seconds = min(max(timeout_seconds, 0.1), 10.0)
        self.service_token_fetcher = service_token_fetcher
        self.principal_provider = principal_provider
        self.transport = transport

    def read(
        self,
        request: HealthFederationRequest,
        scope: RequestScope,
        *,
        deadline: float,
    ) -> HealthFederationResponse:
        remaining = deadline - monotonic()
        principal = self.principal_provider()
        if (
            remaining <= 0
            or not isinstance(principal, AuthenticatedPrincipal)
            or scope.acting_user_id != f"{principal.issuer}|{principal.subject}"
        ):
            raise ContextProviderError("health_federation_user_identity_unavailable")
        try:
            assertion = delegated_user_assertion(
                principal=principal,
                request_body=request.model_dump(mode="json"),
                private_key=self.delegation_private_key,
                issuer=self.delegation_issuer,
                audience=self.delegation_audience,
                key_id=self.delegation_key_id,
            )
            service_token = self.service_token_fetcher(
                audience=self.service_audience,
                service_account=self.service_account,
                deadline=deadline,
            )
        except Exception as error:
            raise ContextProviderError("health_federation_identity_unavailable") from error
        if not service_token or len(service_token) > 8192 or len(assertion) > 8192:
            raise ContextProviderError("health_federation_identity_unavailable")

        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ContextProviderError("health_federation_unavailable")
        timeout = min(remaining, self.timeout_seconds)
        try:
            with (
                httpx.Client(
                    timeout=httpx.Timeout(timeout),
                    follow_redirects=False,
                    trust_env=False,
                    transport=self.transport,
                ) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}{HEALTH_FEDERATION_EXPORT_PATH}",
                    json=request.model_dump(mode="json"),
                    headers={
                        "Authorization": f"Bearer {service_token}",
                        "X-Personal-AI-User-Delegation": assertion,
                    },
                ) as response,
            ):
                response.raise_for_status()
                encoded = bytearray()
                for chunk in response.iter_bytes(4096):
                    encoded.extend(chunk)
                    if len(encoded) > request.max_bytes:
                        raise ContextProviderError("health_federation_response_too_large")
                result = HealthFederationResponse.model_validate_json(encoded)
        except ContextProviderError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            raise ContextProviderError("health_federation_unavailable") from error
        except (ValueError, TypeError, ValidationError, RecursionError):
            raise ContextProviderError("health_federation_response_invalid") from None
        if (
            result.schema_version != HEALTH_FEDERATION_EXPORT_SCHEMA
            or result.application_id != "health"
            or result.workspace_id is not None
            or result.operation != request.operation
            or result.complete is not True
            or result.continuation is not None
        ):
            raise ContextProviderError("health_federation_scope_invalid")
        return result


class HealthFederationExportAdapter:
    """Exact selected-entity adapter; Health remains the consent and owner authority."""

    permission_prefix = "health_federation:"

    def __init__(self, client: HealthFederationExportClient, purpose: str) -> None:
        if purpose not in HEALTH_FEDERATION_PURPOSES:
            raise ValueError("health_federation_purpose_invalid")
        self.client = client
        self.purpose = purpose
        self.category, self.destination, self.field, self.provider_id = (
            HEALTH_FEDERATION_PURPOSES[purpose]
        )

    @staticmethod
    def _single_entity(entities) -> ContextEntityReference:
        if (
            len(entities) != 1
            or entities[0].application_id != "health"
            or entities[0].workspace_id is not None
            or entities[0].entity_type != "profile_item"
        ):
            raise ContextPreparationError("health_federation_scope_invalid")
        try:
            UUID(entities[0].entity_id)
        except (ValueError, TypeError, AttributeError) as error:
            raise ContextPreparationError("health_federation_scope_invalid") from error
        return entities[0]

    def _request(self, entity: ContextEntityReference, *, operation: str) -> HealthFederationRequest:
        return HealthFederationRequest(
            operation=operation,
            category=self.category,
            entity_id=UUID(entity.entity_id),
            purpose=self.purpose,
            destination_application_id=self.destination,
            fields=("permission_version",) if operation == "verify" else (self.field,),
        )

    def _dependency(
        self,
        record: HealthFederationRecord,
        scope: ApplicationScope,
        entity: ContextEntityReference,
        *,
        owner_id: str,
        acting_user_id: str,
    ) -> ContextPermissionDependency:
        expected_permission = f"health_federation:{self.purpose}:{entity.entity_id}"
        expected_source_version = re.fullmatch(
            rf"health-object-v1:r{record.source_revision}:schema-[1-9][0-9]*",
            record.source_version,
        )
        if (
            record.category != self.category
            or record.entity_type != "profile_item"
            or str(record.entity_id) != entity.entity_id
            or expected_source_version is None
            or len(record.permission_dependencies) != 1
            or len(record.source_refs) != 2
            or {reference.kind for reference in record.source_refs} != {"record", "source"}
            or sum(
                reference.kind == "record" and reference.reference_id == entity.entity_id
                for reference in record.source_refs
            ) != 1
            or any(reference.fingerprint is None for reference in record.source_refs)
        ):
            raise ContextPreparationError("health_federation_source_contract_invalid")
        source_dependency = record.permission_dependencies[0]
        dependency_version = re.fullmatch(
            rf"health-object-v1:r{record.source_revision}:ai[01]:cross[01]",
            source_dependency.version,
        )
        if (
            source_dependency.permission_id != expected_permission
            or source_dependency.purpose != self.purpose
            or source_dependency.source_application_id != "health"
            or source_dependency.destination_application_id != self.destination
            or dependency_version is None
        ):
            raise ContextPreparationError("health_federation_source_policy_invalid")
        return ContextPermissionDependency(
            permission_id=source_dependency.permission_id,
            version=source_dependency.version,
            purpose=self.purpose,
            source_scope=scope,
            entity_ref=entity,
            source_revision=record.source_version,
            owner_id=owner_id,
            acting_user_id=acting_user_id,
        )

    def resolve_source_policy(
        self, intent: FederationGrantIntent, *, deadline: float
    ) -> ContextPermissionDependency:
        if (
            intent.source.application_id != "health"
            or intent.source.workspace_id is not None
            or intent.destination.application_id != self.destination
            or intent.category != self.category
            or intent.purpose != self.purpose
            or tuple(intent.fields) != (self.field,)
        ):
            raise ContextPreparationError("health_federation_scope_invalid")
        entity = self._single_entity(intent.entities)
        response = self.client.read(
            self._request(entity, operation="verify"),
            RequestScope(
                owner_id=intent.owner_id,
                acting_user_id=intent.acting_user_id,
                request_id="federation-source-policy",
                application_id=self.destination,
            ),
            deadline=deadline,
        )
        return self._dependency(
            response.item,
            intent.source,
            entity,
            owner_id=intent.owner_id,
            acting_user_id=intent.acting_user_id,
        )

    def authorize_export(self, grant, selection, scope, *, deadline: float) -> bool:
        if (
            grant.source.application_id != "health"
            or grant.source.workspace_id is not None
            or grant.destination.application_id != self.destination
            or grant.category != self.category
            or grant.purpose != self.purpose
            or grant.fields != (self.field,)
            or selection.fields != grant.fields
            or scope.owner_id != grant.owner_id
            or scope.acting_user_id != grant.acting_user_id
        ):
            return False
        entity = self._single_entity(selection.federation.entities)
        response = self.client.read(self._request(entity, operation="verify"), scope, deadline=deadline)
        current = self._dependency(
            response.item,
            grant.source,
            entity,
            owner_id=grant.owner_id,
            acting_user_id=grant.acting_user_id,
        )
        return current == grant.source_policy

    def fetch(self, grant: FederationGrant, selection: ContextSelection, scope, *, deadline: float):
        if (
            grant.source != ApplicationScope(application_id="health")
            or grant.destination.application_id != self.destination
            or grant.category != self.category
            or grant.purpose != self.purpose
            or grant.fields != (self.field,)
            or selection.fields != grant.fields
            or scope.application_id != self.destination
            or scope.owner_id != grant.owner_id
            or scope.acting_user_id != grant.acting_user_id
        ):
            raise ContextPreparationError("health_federation_scope_invalid")
        entity = self._single_entity(selection.federation.entities)
        request = self._request(entity, operation="read")
        response = self.client.read(request, scope, deadline=deadline)
        record = response.item
        dependency = self._dependency(
            record,
            grant.source,
            entity,
            owner_id=grant.owner_id,
            acting_user_id=grant.acting_user_id,
        )
        if response.operation != "read":
            raise ContextPreparationError("health_federation_export_incomplete")
        if record.payload is None or isinstance(record.payload, HealthDietaryPayload) != (
            self.field == "dietary_restrictions"
        ):
            raise ContextPreparationError("health_federation_source_contract_invalid")
        payload_value = getattr(record.payload, self.field, None)
        if response.authoritative_empty:
            if payload_value not in (None, "", ()):
                raise ContextPreparationError("health_federation_source_contract_invalid")
            return FederationExportResult(
                items=(), complete=True, authoritative_empty_entities=(entity,)
            )
        if record.payload is None:
            raise ContextPreparationError("health_federation_export_incomplete")
        if payload_value is None or payload_value == "" or payload_value == ():
            raise ContextPreparationError("health_federation_export_incomplete")
        payload_model = (
            HealthDietaryPayload(dietary_restrictions=payload_value)
            if self.field == "dietary_restrictions"
            else HealthErgonomicPayload(ergonomic_constraints=payload_value)
        )
        item = ContextItem(
            source_class="domain_current",
            provider_id=self.provider_id,
            source_id=f"health-profile:{entity.entity_id}",
            source_version=record.source_version,
            item_id=f"health-federation:{hashlib.sha256(entity.entity_id.encode()).hexdigest()[:32]}",
            owner_id=scope.owner_id,
            application_id="health",
            workspace_id=None,
            entity_refs=(entity,),
            authority="user_asserted",
            observed_at=datetime.now(UTC),
            expires_at=min(grant.expires_at, datetime.now(UTC) + timedelta(minutes=5)),
            sensitivity="restricted",
            source_refs=tuple(
                ContextSourceReference(
                    kind=reference.kind,
                    reference_id=reference.reference_id,
                    fingerprint=reference.fingerprint,
                )
                for reference in record.source_refs
            ),
            permission_dependencies=(dependency,),
            selected_operation="entity",
            field_sensitivity=(ContextFieldSensitivity(field=self.field, sensitivity="restricted"),),
            payload=payload_model,
        )
        return FederationExportResult(items=(item,), complete=True)


class HealthFederationPermissionRevalidator:
    permission_namespaces = ("health_federation:",)

    def __init__(self, client: HealthFederationExportClient) -> None:
        self.client = client

    def supports(self, dependency: ContextPermissionDependency) -> bool:
        return dependency.permission_id.startswith("health_federation:")

    def is_current(self, dependency: ContextPermissionDependency) -> bool:
        from personal_ai.auth.scope import current_request_scope

        scope = current_request_scope()
        if (
            not self.supports(dependency)
            or scope is None
            or dependency.owner_id != scope.owner_id
            or dependency.acting_user_id != scope.acting_user_id
        ):
            return False
        try:
            _, purpose, entity_id = dependency.permission_id.split(":", 2)
            category, destination, _field, _provider = HEALTH_FEDERATION_PURPOSES[purpose]
            entity = ContextEntityReference(
                entity_type="profile_item",
                entity_id=entity_id,
                application_id="health",
                workspace_id=None,
            )
            request = HealthFederationRequest(
                operation="verify",
                category=category,
                entity_id=UUID(entity_id),
                purpose=purpose,
                destination_application_id=destination,
                fields=("permission_version",),
            )
            response = self.client.read(request, scope, deadline=monotonic() + 0.75)
            adapter = HealthFederationExportAdapter(self.client, purpose)
            current = adapter._dependency(
                response.item,
                ApplicationScope(application_id="health"),
                entity,
                owner_id=scope.owner_id,
                acting_user_id=scope.acting_user_id,
            )
            return (
                current == dependency
            )
        except Exception:  # noqa: BLE001 - source authority fails closed
            return False


def configured_health_federation_export_contribution(settings):
    """Install Health exports only when service and delegated identity are executable."""
    from personal_ai.context.runtime import ContextRuntimeContribution

    if not settings.health_federation_enabled:
        return ContextRuntimeContribution(provider_factories={})
    encoded_key = settings.health_federation_delegation_private_key.get_secret_value().strip()
    try:
        private_bytes = base64.b64decode(
            encoded_key + "=" * (-len(encoded_key) % 4),
            altchars=b"-_",
            validate=True,
        )
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    except (ValueError, TypeError):
        raise ValueError("health_federation_delegation_key_invalid") from None
    audience = settings.health_context_service_audience
    client = HealthFederationExportClient(
        base_url=str(settings.health_context_base_url),
        service_audience=audience,
        service_account=settings.health_context_service_account,
        delegation_issuer=settings.health_federation_delegation_issuer,
        delegation_key_id=settings.health_federation_delegation_key_id,
        delegation_audience=audience,
        delegation_private_key=private_key,
        timeout_seconds=settings.health_context_timeout_seconds,
    )
    dietary = HealthFederationExportAdapter(
        client, "health_dietary_restrictions_to_travel"
    )
    ergonomic = HealthFederationExportAdapter(
        client, "health_ergonomic_constraints_to_shopping"
    )
    return ContextRuntimeContribution(
        provider_factories={},
        export_adapters={
            dietary.provider_id: dietary,
            ergonomic.provider_id: ergonomic,
        },
        permission_revalidators=(HealthFederationPermissionRevalidator(client),),
    )
