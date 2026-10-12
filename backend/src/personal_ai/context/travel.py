"""Travel's versioned HTTP context adapter for the shared context pipeline.

The adapter sends owner-authentication and service-transport credentials
separately. Travel receives selected entity references only after Personal AI's
shared planner and application policy have bounded the read request.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from personal_ai.auth.scope import (
    RequestScope,
    current_verified_user_identity_token,
)
from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextFieldSensitivity,
    ContextItem,
    ContextOperationSpec,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderError,
    ContextProviderInputs,
    ContextProviderSpec,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.context.runtime import ContextRuntimeContribution
from personal_ai.federation.broker import FederationExportResult

TRAVEL_CONTEXT_PATH = "/v1/integrations/personal-ai/context"
TRAVEL_CONTEXT_SCHEMA = "travel-context-read-v2"
TRAVEL_CONTEXT_PROVIDER_ID = "travel.trip_context"
TRAVEL_TRIP_EXPORT_PROVIDER_ID = "federation.travel_trip_to_shopping"
TRAVEL_TRIP_EXPORT_FIELDS = ("destination", "start_date", "end_date")
TRAVEL_CONTEXT_FIELDS = (
    "trip_title",
    "start_date",
    "end_date",
    "timezone",
    "itinerary_overview",
    "trip_revision",
    "day_date",
    "day_title",
    "item_title",
    "item_type",
    "item_status",
    "item_schedule",
    "place_name",
    "place_category",
    "place_address",
    "place_source",
    "place_attribution",
    "reservation_summary",
)


class TravelContextReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = TRAVEL_CONTEXT_SCHEMA
    application_id: str = "travel"
    workspace_id: None = None
    operation: str
    purpose: Literal["personal_ai_context", "shopping_trip_context"] = "personal_ai_context"
    destination_application_id: Literal["shopping"] | None = None
    entity_refs: tuple[ContextEntityReference, ...] = Field(default=(), max_length=16)
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    max_results: int = Field(ge=1, le=50)
    max_bytes: int = Field(ge=1, le=65_536)


class TravelSelectionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: Literal["trip", "day", "itinerary_item", "place"]
    entity_id: str = Field(min_length=1, max_length=200)
    relationship: Literal[
        "trip_reservation_summary",
        "day_reservation_summary",
        "itinerary_item_reservation_summary",
        "place_reservation_summary",
    ]

    @model_validator(mode="after")
    def relationship_matches_anchor(self) -> TravelSelectionBinding:
        if self.relationship.split("_reservation_summary", 1)[0] != self.entity_type:
            raise ValueError("travel_context_selection_binding_mismatch")
        return self


class TravelContextRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=100)
    authority: str
    observed_at: datetime | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    sensitivity: str
    payload: dict[str, str | int | float | bool | None] = Field(max_length=32)
    source_refs: tuple[ContextSourceReference, ...] = Field(min_length=1, max_length=16)
    permission_dependencies: tuple[ContextPermissionDependency, ...] = Field(
        default=(), max_length=16
    )
    field_sensitivity: tuple[ContextFieldSensitivity, ...] = Field(default=(), max_length=32)
    selection_binding: TravelSelectionBinding | None = None


class TravelContextReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = TRAVEL_CONTEXT_SCHEMA
    application_id: str = "travel"
    workspace_id: None = None
    items: tuple[TravelContextRecord, ...] = Field(default=(), max_length=50)
    complete: bool = True
    authoritative_empty_entities: tuple[str, ...] = Field(default=(), max_length=16)
    continuation: str | None = Field(default=None, max_length=512)


class TravelContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trip_title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    timezone: str | None = None
    itinerary_overview: str | None = None
    trip_revision: int | None = None
    day_date: str | None = None
    day_title: str | None = None
    item_title: str | None = None
    item_type: str | None = None
    item_status: str | None = None
    item_schedule: str | None = None
    place_name: str | None = None
    place_category: str | None = None
    place_address: str | None = None
    place_source: str | None = None
    place_attribution: str | None = None
    reservation_summary: str | None = None
    passage: str | None = None
    observed_at: str | None = None
    expires_at: str | None = None
    citations: str | None = None


class TravelTripExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    destination: str | None
    start_date: str
    end_date: str


class TravelTripFederationExportAdapter:
    """Narrow Travel-owned trip export, authorized by current Travel consent."""

    purpose = "shopping_trip_context"

    def __init__(self, client: TravelContextHTTPClient) -> None:
        self.client = client

    @staticmethod
    def _single_trip(entities) -> ContextEntityReference:
        if (
            len(entities) != 1
            or entities[0].application_id != "travel"
            or entities[0].workspace_id is not None
            or entities[0].entity_type != "trip"
        ):
            raise ContextPreparationError("travel_trip_export_scope_invalid")
        return entities[0]

    @staticmethod
    def _request(entity, *, operation: str) -> TravelContextReadRequest:
        return TravelContextReadRequest(
            operation=operation,
            purpose=TravelTripFederationExportAdapter.purpose,
            destination_application_id="shopping",
            entity_refs=(entity,),
            fields=(
                ("trip_revision",)
                if operation == "verify"
                else TRAVEL_TRIP_EXPORT_FIELDS
            ),
            max_results=1,
            max_bytes=4096,
        )

    @staticmethod
    def _dependency(record, scope, entity, *, owner_id: str, acting_user_id: str):
        if (
            record.entity_type != "trip"
            or record.entity_id != entity.entity_id
            or len(record.permission_dependencies) != 1
        ):
            raise ContextPreparationError("travel_trip_export_policy_invalid")
        source_dependency = record.permission_dependencies[0]
        if (
            source_dependency.permission_id != f"travel_context_read:{entity.entity_id}"
            or source_dependency.purpose != TravelTripFederationExportAdapter.purpose
            or source_dependency.source_application_id != "travel"
            or source_dependency.destination_application_id != "shopping"
        ):
            raise ContextPreparationError("travel_trip_export_policy_invalid")
        return ContextPermissionDependency(
            permission_id=source_dependency.permission_id,
            version=source_dependency.version,
            purpose=TravelTripFederationExportAdapter.purpose,
            source_scope=scope,
            entity_ref=entity,
            source_revision=record.source_version,
            owner_id=owner_id,
            acting_user_id=acting_user_id,
        )

    def _check_intent(self, intent) -> ContextEntityReference:
        if (
            intent.source.application_id != "travel"
            or intent.destination.application_id != "shopping"
            or intent.category != "trip"
            or intent.purpose != self.purpose
            or tuple(intent.fields) != TRAVEL_TRIP_EXPORT_FIELDS
        ):
            raise ContextPreparationError("travel_trip_export_scope_invalid")
        return self._single_trip(intent.entities)

    def resolve_source_policy(self, intent, *, deadline: float):
        entity = self._check_intent(intent)
        response = self.client.read(self._request(entity, operation="verify"), deadline=deadline)
        if len(response.items) != 1:
            raise ContextPreparationError("travel_trip_export_policy_unavailable")
        return self._dependency(
            response.items[0],
            intent.source,
            entity,
            owner_id=intent.owner_id,
            acting_user_id=intent.acting_user_id,
        )

    def authorize_export(self, grant, selection, scope, *, deadline: float) -> bool:
        if (
            grant.source.application_id != "travel"
            or grant.destination.application_id != "shopping"
            or grant.category != "trip"
            or grant.purpose != self.purpose
            or tuple(grant.fields) != TRAVEL_TRIP_EXPORT_FIELDS
            or selection.fields != grant.fields
            or scope.owner_id != grant.owner_id
            or scope.acting_user_id != grant.acting_user_id
        ):
            return False
        entity = self._single_trip(selection.federation.entities)
        response = self.client.read(self._request(entity, operation="verify"), deadline=deadline)
        return (
            len(response.items) == 1
            and self._dependency(
                response.items[0],
                grant.source,
                entity,
                owner_id=grant.owner_id,
                acting_user_id=grant.acting_user_id,
            )
            == grant.source_policy
        )

    def fetch(self, grant, selection, scope, *, deadline: float) -> FederationExportResult:
        entity = self._single_trip(selection.federation.entities)
        response = self.client.read(self._request(entity, operation="federation"), deadline=deadline)
        if not response.complete or response.continuation is not None:
            raise ContextPreparationError("travel_trip_export_incomplete")
        if not response.items:
            if response.authoritative_empty_entities == (entity.entity_id,):
                return FederationExportResult(
                    items=(), complete=True, authoritative_empty_entities=(entity,)
                )
            raise ContextPreparationError("travel_trip_export_incomplete")
        if len(response.items) != 1 or response.authoritative_empty_entities:
            raise ContextPreparationError("travel_trip_export_incomplete")
        record = response.items[0]
        try:
            payload = TravelTripExportPayload.model_validate(record.payload)
            source_dependency = self._dependency(
                record,
                grant.source,
                entity,
                owner_id=grant.owner_id,
                acting_user_id=grant.acting_user_id,
            )
        except (ValueError, TypeError) as error:
            raise ContextPreparationError("travel_trip_export_contract_invalid") from error
        if set(payload.model_dump()) != set(selection.fields):
            raise ContextPreparationError("travel_trip_export_contract_invalid")
        source_refs = tuple(
            ContextSourceReference(
                kind=reference.kind,
                reference_id=reference.reference_id,
                fingerprint=reference.fingerprint,
            )
            for reference in record.source_refs
        )
        field_sensitivity = tuple(
            ContextFieldSensitivity(field=field.field, sensitivity=field.sensitivity)
            for field in record.field_sensitivity
        )
        item = ContextItem(
            source_class="domain_current",
            provider_id=TRAVEL_TRIP_EXPORT_PROVIDER_ID,
            source_id=record.source_id,
            source_version=record.source_version,
            item_id=f"travel-trip:{sha256(record.entity_id.encode()).hexdigest()[:32]}",
            owner_id=scope.owner_id,
            application_id="travel",
            workspace_id=None,
            entity_refs=(entity,),
            authority=record.authority,
            observed_at=record.observed_at,
            effective_at=record.effective_at,
            expires_at=min(grant.expires_at, datetime.now(UTC) + timedelta(minutes=5)),
            sensitivity="sensitive",
            source_refs=source_refs,
            permission_dependencies=(source_dependency,),
            selected_operation="entity",
            field_sensitivity=field_sensitivity,
            payload=payload,
        )
        return FederationExportResult(items=(item,), complete=True)


class TravelContextHTTPClient:
    """Bounded HTTP client; transport identity never stands in for the user."""

    def __init__(
        self,
        *,
        base_url: str,
        auth_mode: str,
        service_audience: str = "",
        service_account: str = "",
        timeout_seconds: float = 3.0,
        service_token_fetcher=None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("travel_context_base_url_invalid")
        self.base_url = base_url.rstrip("/")
        self.auth_mode = auth_mode
        self.service_audience = service_audience
        self.service_account = service_account
        self.timeout_seconds = min(max(timeout_seconds, 0.1), 10.0)
        self.service_token_fetcher = service_token_fetcher
        self.transport = transport

    def read(
        self, request: TravelContextReadRequest, *, deadline: float
    ) -> TravelContextReadResponse:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError
        headers = {"X-Application-ID": "travel"}
        if self.auth_mode == "google_oidc":
            user_token = current_verified_user_identity_token()
            if not user_token or len(user_token) > 8192:
                raise ContextProviderError("travel_user_identity_unavailable")
            fetcher = self.service_token_fetcher
            if fetcher is None:
                raise ContextProviderError("travel_service_identity_unavailable")
            try:
                service_token = fetcher(
                    audience=self.service_audience,
                    service_account=self.service_account,
                )
            except Exception as error:
                raise ContextProviderError("travel_service_identity_unavailable") from error
            if not service_token or len(service_token) > 8192:
                raise ContextProviderError("travel_service_identity_unavailable")
            headers.update(
                {
                    "Authorization": f"Bearer {service_token}",
                    "X-User-ID-Token": user_token,
                }
            )
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
                    f"{self.base_url}{TRAVEL_CONTEXT_PATH}",
                    json=request.model_dump(mode="json"),
                    headers=headers,
                ) as response,
            ):
                response.raise_for_status()
                encoded = bytearray()
                for chunk in response.iter_bytes(4096):
                    encoded.extend(chunk)
                    if len(encoded) > request.max_bytes + 4096:
                        raise ContextProviderError("travel_context_response_too_large")
                try:
                    payload = json.loads(encoded)
                    result = TravelContextReadResponse.model_validate(payload)
                except (ValueError, TypeError, ValidationError, RecursionError):
                    raise ContextProviderError("travel_context_response_invalid") from None
        except ContextProviderError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            raise ContextProviderError("travel_context_unavailable") from error
        if result.schema_version != TRAVEL_CONTEXT_SCHEMA:
            raise ContextProviderError("travel_context_contract_unsupported")
        if result.application_id != "travel" or result.workspace_id is not None:
            raise ContextProviderError("travel_context_scope_invalid")
        if not result.complete or result.continuation is not None:
            raise ContextProviderError("travel_context_export_incomplete")
        return result


class TravelContextProvider:
    spec = ContextProviderSpec(
        provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
        source_class="domain_current",
        source_version=TRAVEL_CONTEXT_SCHEMA,
        operations=(
            ContextOperationSpec(
                operation="current",
                allowed_fields=(
                    "trip_title",
                    "start_date",
                    "end_date",
                    "timezone",
                    "itinerary_overview",
                    "trip_revision",
                ),
                accepts_entity_refs=True,
                maximum_results=8,
                maximum_bytes=24_576,
                maximum_timeout_seconds=5,
            ),
            ContextOperationSpec(
                operation="entity",
                allowed_fields=TRAVEL_CONTEXT_FIELDS,
                accepts_entity_refs=True,
                maximum_results=16,
                maximum_bytes=32_768,
                maximum_timeout_seconds=5,
            ),
        ),
        maximum_items_per_call=16,
    )

    def __init__(self, client: TravelContextHTTPClient) -> None:
        self.client = client

    def validate_selection(
        self, selection: ContextSelection, inputs: ContextProviderInputs
    ) -> None:
        if inputs.scope.application_id != "travel":
            raise ContextPreparationError("travel_context_application_scope_required")
        if inputs.scope.workspace_id is not None:
            raise ContextPreparationError("travel_context_workspace_unsupported")
        if not selection.entity_refs:
            raise ContextPreparationError("travel_context_entity_reference_required")
        if any(
            ref.application_id != "travel" or ref.workspace_id is not None
            for ref in selection.entity_refs
        ):
            raise ContextPreparationError("travel_context_entity_scope_invalid")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        request = TravelContextReadRequest(
            operation=selection.operation,
            entity_refs=selection.entity_refs,
            fields=selection.fields,
            max_results=selection.max_results,
            max_bytes=selection.max_bytes,
        )
        response = self.client.read(request, deadline=deadline)
        if len(response.items) > selection.max_results:
            raise ContextPreparationError("travel_context_result_limit_exceeded")
        items = []
        for record in response.items:
            exact_selection = any(
                ref.entity_id == record.entity_id and ref.entity_type == record.entity_type
                for ref in selection.entity_refs
            )
            binding = record.selection_binding
            bound_selection = binding is not None and any(
                ref.entity_id == binding.entity_id and ref.entity_type == binding.entity_type
                for ref in selection.entity_refs
            )
            if binding is not None and record.entity_type != "reservation":
                raise ContextPreparationError("travel_context_selection_binding_invalid")
            if record.entity_type == "reservation":
                if not exact_selection and not bound_selection:
                    raise ContextPreparationError("travel_context_unselected_entity")
            elif not exact_selection:
                raise ContextPreparationError("travel_context_unselected_entity")
            payload_values = {
                key: value
                for key, value in record.payload.items()
                if key in selection.fields and value is not None
            }
            payload = TravelContextPayload.model_validate(payload_values)
            opaque_id = sha256(f"{record.entity_type}\0{record.entity_id}".encode()).hexdigest()
            items.append(
                ContextItem(
                    source_class="domain_current",
                    provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
                    source_id=f"travel:{opaque_id}",
                    source_version=record.source_version,
                    item_id=f"travel:{record.entity_type}:{opaque_id[:32]}",
                    owner_id=scope.owner_id,
                    application_id="travel",
                    workspace_id=None,
                    # References are used to retrieve and validate the source but
                    # remain out of the model-visible projection.
                    entity_refs=(),
                    authority=record.authority,
                    observed_at=record.observed_at,
                    effective_at=record.effective_at,
                    expires_at=record.expires_at,
                    sensitivity=record.sensitivity,
                    source_refs=record.source_refs,
                    permission_dependencies=record.permission_dependencies,
                    selected_operation=selection.operation,
                    field_sensitivity=record.field_sensitivity,
                    payload=payload,
                )
            )
        return tuple(items)


class TravelContextProviderFactory:
    def __init__(self, client: TravelContextHTTPClient) -> None:
        self.client = client
        self.spec = TravelContextProvider.spec

    def create(self, inputs: ContextProviderInputs) -> TravelContextProvider:
        del inputs
        return TravelContextProvider(self.client)


class TravelContextPermissionRevalidator:
    """Recheck Travel membership and source revision before context disclosure."""

    permission_prefix = "travel_context_read:"
    permission_namespaces = (permission_prefix,)

    def __init__(self, client: TravelContextHTTPClient) -> None:
        self.client = client

    def supports(self, dependency: ContextPermissionDependency) -> bool:
        return dependency.permission_id.startswith(self.permission_prefix)

    def is_current(self, dependency: ContextPermissionDependency) -> bool:
        if not self.supports(dependency):
            return False
        entity_id = dependency.permission_id.removeprefix(self.permission_prefix)
        try:
            is_federation = dependency.purpose == "shopping_trip_context"
            response = self.client.read(
                TravelContextReadRequest(
                    operation="verify",
                    purpose=(
                        "shopping_trip_context" if is_federation else "personal_ai_context"
                    ),
                    destination_application_id="shopping" if is_federation else None,
                    entity_refs=(
                        ContextEntityReference(
                            entity_type="trip",
                            entity_id=entity_id,
                            application_id="travel",
                            workspace_id=None,
                        ),
                    ),
                    fields=("trip_revision",),
                    max_results=1,
                    max_bytes=2048,
                ),
                deadline=monotonic() + 0.75,
            )
        except Exception:  # noqa: BLE001 - an unavailable owner check fails closed
            return False
        return any(record.source_version == dependency.version for record in response.items)


def travel_context_planning_rules() -> tuple[ContextPlanningRule, ...]:
    """Data-driven rules opt Travel into shared planning for selected refs."""
    return (
        ContextPlanningRule(
            rule_id="travel.selected-trip:v1",
            category="travel_current_trip",
            phrases=("this trip", "my trip", "trip itinerary", "current itinerary"),
            provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
            operation="current",
            fields=(
                "trip_title",
                "start_date",
                "end_date",
                "timezone",
                "itinerary_overview",
            ),
            max_results=4,
            max_bytes=24_576,
            max_tokens=512,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("trip",),
            priority=20,
            application_ids=("travel",),
            explanation="Read the selected current trip through the registered Travel provider.",
        ),
        ContextPlanningRule(
            rule_id="travel.selected-entities:v1",
            category="travel_selected_entities",
            phrases=(
                "selected day",
                "selected place",
                "this place",
                "day itinerary",
                "reservation",
            ),
            provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
            operation="entity",
            fields=(
                "day_date",
                "day_title",
                "item_title",
                "item_type",
                "item_status",
                "item_schedule",
                "place_name",
                "place_category",
                "place_address",
                "place_source",
                "place_attribution",
            ),
            max_results=12,
            max_bytes=32_768,
            max_tokens=512,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("day", "itinerary_item", "place", "reservation"),
            priority=25,
            application_ids=("travel",),
            explanation="Read only the selected Travel entities and itinerary fields.",
        ),
        ContextPlanningRule(
            rule_id="travel.selected-booking-summary:v1",
            category="travel_booking_summary",
            phrases=("reservation details", "booking status", "my reservation"),
            provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
            operation="entity",
            fields=("reservation_summary",),
            max_results=4,
            max_bytes=8_192,
            max_tokens=256,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            candidate_entity_types=("trip", "day", "itinerary_item", "place", "reservation"),
            priority=30,
            application_ids=("travel",),
            explanation="Read a minimized booking summary only when the request explicitly asks.",
        ),
        ContextPlanningRule(
            rule_id="travel.selected-research:v2",
            category="travel_selected_research",
            phrases=("use this research", "use the selected research", "based on these sources"),
            provider_id="external_research",
            operation="search",
            fields=("passage", "observed_at", "expires_at"),
            max_results=3,
            max_bytes=16_384,
            max_tokens=384,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("research_session",),
            priority=35,
            application_ids=("travel",),
            explanation="Use only the explicitly selected Personal AI research session.",
        ),
    )


def configured_travel_context_contribution(settings) -> ContextRuntimeContribution:
    """Build Travel's contribution while leaving composition to shared runtime code."""
    providers = {}
    export_adapters = {}
    revalidators = ()
    planning_rules = travel_context_planning_rules()
    if settings.travel_context_enabled or settings.travel_federation_enabled:
        from personal_ai.auth.service_tokens import fetch_google_service_token

        client = TravelContextHTTPClient(
            base_url=str(settings.travel_context_base_url),
            auth_mode=settings.auth_mode,
            service_audience=settings.travel_context_service_audience,
            service_account=settings.travel_context_service_account,
            timeout_seconds=settings.travel_context_timeout_seconds,
            service_token_fetcher=(
                fetch_google_service_token if settings.auth_mode == "google_oidc" else None
            ),
        )
        if settings.travel_context_enabled:
            providers[TRAVEL_CONTEXT_PROVIDER_ID] = TravelContextProviderFactory(client)
        if settings.travel_federation_enabled:
            export_adapters[TRAVEL_TRIP_EXPORT_PROVIDER_ID] = (
                TravelTripFederationExportAdapter(client)
            )
        revalidators = (TravelContextPermissionRevalidator(client),)
    if not settings.travel_context_enabled:
        planning_rules = tuple(
            rule for rule in planning_rules if rule.provider_id == TRAVEL_CONTEXT_PROVIDER_ID
        )
    return ContextRuntimeContribution(
        provider_factories=providers,
        planning_rules=planning_rules,
        permission_revalidators=revalidators,
        export_adapters=export_adapters,
    )
