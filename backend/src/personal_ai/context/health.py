"""Health's versioned, restricted read projection through shared context seams."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from hashlib import sha256
from time import monotonic
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictInt,
    ValidationError,
    model_validator,
)

from personal_ai.auth.scope import RequestScope, current_verified_user_identity_token
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

HEALTH_CONTEXT_PATH = "/v1/integrations/personal-ai/context"
HEALTH_CONTEXT_SCHEMA = "health-context-read-v1"
HEALTH_PROFILE_FIELDS = (
    "record",
    "notes",
    "source_kind",
    "confirmation_status",
    "validity",
)
HEALTH_DAILY_FIELDS = (
    "record",
    "domain",
    "notes",
    "time",
    "interval_end",
    "units",
    "source_kind",
    "confirmation_status",
    "quality",
    "uncertainty",
)
HEALTH_MAX_WINDOW = timedelta(days=90)
HEALTH_MAX_RESULTS = 32
HEALTH_MAX_BYTES = 32_768

HEALTH_CATEGORY_PROVIDERS = {
    "health.profile_background_context": ("profile_background", "profile", "domain_profile"),
    "health.profile_constraints_context": ("profile_constraints", "profile", "domain_profile"),
    "health.profile_preferences_context": ("profile_preferences", "profile", "domain_profile"),
    "health.measurements_context": ("measurements", "history", "domain_history"),
    "health.nutrition_context": ("nutrition", "history", "domain_history"),
    "health.exercise_context": ("exercise", "history", "domain_history"),
    "health.sleep_context": ("sleep", "history", "domain_history"),
    "health.symptoms_context": ("symptoms", "history", "domain_history"),
}
HEALTH_CATEGORY_LABELS = {
    "profile_background": "Health profile background",
    "profile_constraints": "Health profile constraints",
    "profile_preferences": "Health profile preferences",
    "measurements": "Health measurements",
    "nutrition": "Health nutrition history",
    "exercise": "Health activity history",
    "sleep": "Health sleep history",
    "symptoms": "Health symptom history",
}

HealthCategory = Literal[
    "profile_background",
    "profile_constraints",
    "profile_preferences",
    "measurements",
    "nutrition",
    "exercise",
    "sleep",
    "symptoms",
]
HealthResourceType = Literal["profile_item", "event", "observation"]
HealthSensitivity = Literal["personal", "sensitive", "restricted"]
HealthSourceKind = Literal["manual", "device", "document", "provider", "ai", "system"]
HealthConfirmation = Literal["unconfirmed", "user_confirmed"]
HealthAuthority = Literal["authoritative"]


class HealthContextEntityReference(BaseModel):
    """Health-owned object reference; it narrows a read but grants no authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    object_type: HealthResourceType
    object_id: UUID


class HealthContextReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["health-context-read-v1"] = HEALTH_CONTEXT_SCHEMA
    application_id: Literal["health"] = "health"
    workspace_id: None = None
    purpose: Literal["personal_ai_context"] = "personal_ai_context"
    operation: Literal["catalog", "profile", "history", "time_series", "verify"]
    category: HealthCategory | None = None
    entity_refs: tuple[HealthContextEntityReference, ...] = Field(default=(), max_length=16)
    fields: tuple[str, ...] = Field(default=(), max_length=12)
    window_start: AwareDatetime | None = None
    window_end: AwareDatetime | None = None
    max_results: Annotated[StrictInt, Field(ge=1, le=HEALTH_MAX_RESULTS)] = 8
    max_bytes: Annotated[StrictInt, Field(ge=512, le=HEALTH_MAX_BYTES)] = 16_384

    @model_validator(mode="after")
    def scope_is_bounded(self) -> HealthContextReadRequest:
        if len(set(self.entity_refs)) != len(self.entity_refs):
            raise ValueError("health_context_entity_refs_not_unique")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("health_context_fields_not_unique")
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("health_context_window_incomplete")
        if self.window_start is not None and (
            self.window_end <= self.window_start
            or self.window_end - self.window_start > HEALTH_MAX_WINDOW
        ):
            raise ValueError("health_context_window_invalid")
        if self.operation == "catalog":
            if self.category is not None or self.entity_refs or self.fields or self.window_start:
                raise ValueError("health_context_catalog_scope_invalid")
            return self
        if self.category is None:
            raise ValueError("health_context_category_required")
        if self.operation == "verify":
            if len(self.entity_refs) != 1 or self.fields != ("permission_version",):
                raise ValueError("health_context_verify_scope_invalid")
            if self.window_start is not None:
                raise ValueError("health_context_verify_window_invalid")
            entity_type = self.entity_refs[0].object_type
            if self.category.startswith("profile_") and entity_type != "profile_item":
                raise ValueError("health_context_verify_entity_type_invalid")
            if self.category == "measurements" and entity_type != "observation":
                raise ValueError("health_context_verify_entity_type_invalid")
            if (
                not self.category.startswith("profile_")
                and self.category != "measurements"
                and entity_type not in {"event", "observation"}
            ):
                raise ValueError("health_context_verify_entity_type_invalid")
            return self
        if not self.fields:
            raise ValueError("health_context_fields_required")
        if self.category.startswith("profile_"):
            if self.operation != "profile" or self.window_start is not None:
                raise ValueError("health_context_profile_scope_invalid")
            if any(item.object_type != "profile_item" for item in self.entity_refs):
                raise ValueError("health_context_profile_entity_type_invalid")
            allowed = set(HEALTH_PROFILE_FIELDS)
        else:
            if self.operation not in {"history", "time_series"} or self.window_start is None:
                raise ValueError("health_context_history_scope_invalid")
            if self.operation == "time_series" and self.category != "measurements":
                raise ValueError("health_context_time_series_category_invalid")
            if self.operation == "history" and self.category == "measurements":
                raise ValueError("health_context_measurement_history_requires_time_series")
            if any(item.object_type == "profile_item" for item in self.entity_refs):
                raise ValueError("health_context_daily_entity_type_invalid")
            if self.category == "measurements" and any(
                item.object_type != "observation" for item in self.entity_refs
            ):
                raise ValueError("health_context_measurement_entity_type_invalid")
            allowed = set(HEALTH_DAILY_FIELDS)
        if not set(self.fields) <= allowed:
            raise ValueError("health_context_fields_invalid")
        return self


class HealthContextFieldSensitivity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    field: str = Field(min_length=1, max_length=80)
    sensitivity: HealthSensitivity


class HealthContextSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["record", "source"]
    reference_id: str = Field(min_length=1, max_length=100)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class HealthContextPermissionDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    permission_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=100)
    purpose: Literal["personal_ai_context"]


class HealthContextWirePayload(BaseModel):
    """Selected typed Health values without owner scope or canonical-store authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    category: HealthCategory
    object_type: HealthResourceType
    record: JsonValue | None = None
    domain: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2_000)
    time: JsonValue | None = None
    interval_end: AwareDatetime | None = None
    units: dict[str, str] | None = Field(default=None, max_length=8)
    source_kind: HealthSourceKind | None = None
    confirmation_status: HealthConfirmation | None = None
    quality: dict[str, JsonValue] | None = Field(default=None, max_length=8)
    uncertainty: str | None = Field(default=None, max_length=160)
    validity: dict[str, AwareDatetime | None] | None = None


class HealthContextRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    object_id: UUID
    object_type: HealthResourceType
    object_revision: Annotated[StrictInt, Field(ge=1)]
    schema_version: Annotated[StrictInt, Field(ge=1)]
    source_id: UUID
    source_version: str = Field(min_length=1, max_length=100)
    source_kind: HealthSourceKind
    confirmation_status: HealthConfirmation
    authority: HealthAuthority
    observed_at: AwareDatetime
    effective_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    active_state: Literal["active"]
    sensitivity: HealthSensitivity
    field_sensitivity: tuple[HealthContextFieldSensitivity, ...] = Field(
        min_length=1, max_length=12
    )
    source_refs: tuple[HealthContextSourceReference, ...] = Field(min_length=2, max_length=2)
    permission_dependencies: tuple[HealthContextPermissionDependency, ...] = Field(min_length=1, max_length=1)
    payload: HealthContextWirePayload

    @model_validator(mode="after")
    def projection_references_are_consistent(self) -> HealthContextRecord:
        if self.payload.object_type != self.object_type:
            raise ValueError("health_context_payload_object_type_mismatch")
        references = {value.kind: value.reference_id for value in self.source_refs}
        if references.get("record") != str(self.object_id):
            raise ValueError("health_context_record_reference_mismatch")
        if references.get("source") != str(self.source_id):
            raise ValueError("health_context_source_reference_mismatch")
        dependency = self.permission_dependencies[0]
        expected_permission_id = (
            f"health_context_read:{self.payload.category}:{self.object_type}:{self.object_id}"
        )
        if dependency.permission_id != expected_permission_id:
            raise ValueError("health_context_permission_reference_mismatch")
        payload_fields = set(self.payload.model_dump(exclude_none=True)) - {
            "category",
            "object_type",
        }
        label_fields = {value.field for value in self.field_sensitivity}
        if payload_fields - label_fields or len(label_fields) != len(self.field_sensitivity):
            raise ValueError("health_context_field_sensitivity_invalid")
        return self


class HealthContextPermissionVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    object_id: UUID
    version: str = Field(min_length=1, max_length=100)


class HealthContextCategoryOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    category: HealthCategory
    display_name: str = Field(min_length=1, max_length=64)
    sensitivity: Literal["restricted"] = "restricted"


class HealthContextReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["health-context-read-v1"] = HEALTH_CONTEXT_SCHEMA
    application_id: Literal["health"] = "health"
    workspace_id: None = None
    operation: Literal["catalog", "profile", "history", "time_series", "verify"]
    items: tuple[HealthContextRecord, ...] = Field(default=(), max_length=HEALTH_MAX_RESULTS)
    categories: tuple[HealthContextCategoryOption, ...] = Field(default=(), max_length=8)
    permission_versions: tuple[HealthContextPermissionVersion, ...] = Field(default=(), max_length=16)
    truncated: bool = False

    @model_validator(mode="after")
    def response_shape_matches_operation(self) -> HealthContextReadResponse:
        if self.operation == "catalog":
            if self.items or self.permission_versions or len({item.category for item in self.categories}) != len(self.categories):
                raise ValueError("health_context_catalog_response_invalid")
        elif self.operation == "verify":
            if self.items or self.categories or len({item.object_id for item in self.permission_versions}) != len(self.permission_versions):
                raise ValueError("health_context_verify_response_invalid")
        elif self.categories or self.permission_versions:
            raise ValueError("health_context_categories_unexpected")
        return self


class HealthContextHTTPClient:
    """Bounded transport using separate service and verified-user credentials."""

    def __init__(
        self,
        *,
        base_url: str,
        auth_mode: str,
        service_audience: str = "",
        service_account: str = "",
        timeout_seconds: float = 3.0,
        service_token_fetcher: Callable[..., str] | None = None,
        user_token_provider: Callable[[], str | None] = current_verified_user_identity_token,
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
            raise ValueError("health_context_base_url_invalid")
        self.base_url = base_url.rstrip("/")
        self.auth_mode = auth_mode
        self.service_audience = service_audience
        self.service_account = service_account
        self.timeout_seconds = min(max(timeout_seconds, 0.1), 10.0)
        self.service_token_fetcher = service_token_fetcher
        self.user_token_provider = user_token_provider
        self.transport = transport

    def read(self, request: HealthContextReadRequest, *, deadline: float) -> HealthContextReadResponse:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError
        user_token = self.user_token_provider()
        if not user_token or len(user_token) > 8192:
            raise ContextProviderError("health_context_user_identity_unavailable")
        fetcher = self.service_token_fetcher
        if self.auth_mode != "google_oidc" or fetcher is None:
            raise ContextProviderError("health_context_service_identity_unavailable")
        try:
            service_token = fetcher(
                audience=self.service_audience,
                service_account=self.service_account,
                deadline=deadline,
            )
        except Exception as error:
            raise ContextProviderError("health_context_service_identity_unavailable") from error
        if not service_token or len(service_token) > 8192:
            raise ContextProviderError("health_context_service_identity_unavailable")

        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ContextProviderError("health_context_unavailable")
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
                    f"{self.base_url}{HEALTH_CONTEXT_PATH}",
                    json=request.model_dump(mode="json"),
                    headers={
                        "Authorization": f"Bearer {service_token}",
                        "X-User-ID-Token": user_token,
                    },
                ) as response,
            ):
                response.raise_for_status()
                encoded = bytearray()
                for chunk in response.iter_bytes(4096):
                    encoded.extend(chunk)
                    if len(encoded) > request.max_bytes:
                        raise ContextProviderError("health_context_response_too_large")
                try:
                    result = HealthContextReadResponse.model_validate_json(encoded)
                except (ValueError, TypeError, ValidationError, RecursionError):
                    raise ContextProviderError("health_context_response_invalid") from None
        except ContextProviderError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            raise ContextProviderError("health_context_unavailable") from error
        if result.schema_version != HEALTH_CONTEXT_SCHEMA:
            raise ContextProviderError("health_context_contract_unsupported")
        if result.application_id != "health" or result.workspace_id is not None:
            raise ContextProviderError("health_context_scope_invalid")
        if result.operation != request.operation:
            raise ContextProviderError("health_context_operation_mismatch")
        return result


class HealthContextProvider:
    """One Health category capability with an exact operation and field allowlist."""

    def __init__(self, client: HealthContextHTTPClient, provider_id: str) -> None:
        self.client = client
        self.provider_id = provider_id
        try:
            self.category, self.operation, source_class = HEALTH_CATEGORY_PROVIDERS[provider_id]
        except KeyError as error:
            raise ValueError("health_context_provider_unknown") from error
        self.allowed_fields = (
            HEALTH_PROFILE_FIELDS if self.operation == "profile" else HEALTH_DAILY_FIELDS
        )
        operations = (
            ContextOperationSpec(
                operation=self.operation,
                allowed_fields=self.allowed_fields,
                accepts_entity_refs=True,
                requires_time_window=self.operation == "history",
                maximum_window_seconds=int(HEALTH_MAX_WINDOW.total_seconds())
                if self.operation == "history"
                else 0,
                maximum_results=HEALTH_MAX_RESULTS,
                maximum_bytes=HEALTH_MAX_BYTES,
                maximum_timeout_seconds=5,
            ),
        )
        self.spec = ContextProviderSpec(
            provider_id=provider_id,
            source_class=source_class,
            source_version=HEALTH_CONTEXT_SCHEMA,
            operations=operations,
            maximum_items_per_call=HEALTH_MAX_RESULTS,
        )

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs) -> None:
        if inputs.scope.application_id != "health" or inputs.scope.workspace_id is not None:
            raise ContextPreparationError("health_context_application_scope_required")
        if selection.operation != self.operation:
            raise ContextPreparationError("health_context_operation_invalid")
        if not set(selection.fields) <= set(self.allowed_fields):
            raise ContextPreparationError("health_context_field_not_supported")
        if any(
            reference.application_id != "health" or reference.workspace_id is not None
            for reference in selection.entity_refs
        ):
            raise ContextPreparationError("health_context_entity_scope_invalid")
        expected_type = "profile_item" if self.operation == "profile" else None
        if expected_type and any(reference.entity_type != expected_type for reference in selection.entity_refs):
            raise ContextPreparationError("health_context_profile_entity_type_invalid")
        if self.category == "measurements" and any(
            reference.entity_type != "observation" for reference in selection.entity_refs
        ):
            raise ContextPreparationError("health_context_measurement_entity_type_invalid")
        if self.operation == "profile":
            if selection.window_start is not None or selection.window_end is not None:
                raise ContextPreparationError("health_context_profile_window_invalid")
        elif (
            selection.window_start is None
            or selection.window_end is None
            or selection.window_end - selection.window_start > HEALTH_MAX_WINDOW
        ):
            raise ContextPreparationError("health_context_history_window_required")

    def fetch(
        self, selection: ContextSelection, scope: RequestScope, *, deadline: float
    ) -> tuple[ContextItem[HealthContextPayload], ...]:
        wire_operation = "time_series" if self.category == "measurements" else self.operation
        response = self.client.read(
            HealthContextReadRequest(
                operation=wire_operation,
                category=self.category,
                entity_refs=tuple(
                    HealthContextEntityReference(
                        object_type=reference.entity_type,
                        object_id=UUID(reference.entity_id),
                    )
                    for reference in selection.entity_refs
                ),
                fields=selection.fields,
                window_start=selection.window_start,
                window_end=selection.window_end,
                max_results=min(selection.max_results, HEALTH_MAX_RESULTS),
                max_bytes=min(selection.max_bytes, HEALTH_MAX_BYTES),
            ),
            deadline=deadline,
        )
        if response.truncated:
            raise ContextPreparationError("health_context_result_truncated")
        if len(response.items) > selection.max_results:
            raise ContextPreparationError("health_context_result_limit_exceeded")
        selected_ids = {reference.entity_id for reference in selection.entity_refs}
        items: list[ContextItem[HealthContextPayload]] = []
        for record in response.items:
            if record.payload.category != self.category:
                raise ContextPreparationError("health_context_category_mismatch")
            if record.object_type not in {"profile_item", "event", "observation"}:
                raise ContextPreparationError("health_context_object_type_invalid")
            if self.category.startswith("profile_") and record.object_type != "profile_item":
                raise ContextPreparationError("health_context_profile_type_mismatch")
            if self.category == "measurements" and record.object_type != "observation":
                raise ContextPreparationError("health_context_measurement_type_mismatch")
            if selected_ids and str(record.object_id) not in selected_ids:
                raise ContextPreparationError("health_context_unselected_entity")
            payload_value = record.payload.model_dump(mode="json", exclude_none=True)
            category = payload_value.pop("category", None)
            object_type = payload_value.pop("object_type", None)
            if category != self.category or object_type != record.object_type:
                raise ContextPreparationError("health_context_payload_identity_mismatch")
            for optional_field in ("quality", "units"):
                if optional_field not in selection.fields:
                    payload_value.pop(optional_field, None)
            payload = HealthContextPayload.model_validate(payload_value)
            payload_fields = set(payload.model_dump(exclude_none=True))
            sensitivity_fields = {value.field for value in record.field_sensitivity}
            if payload_fields - set(selection.fields) or sensitivity_fields - set(selection.fields):
                raise ContextPreparationError("health_context_projection_violation")
            if record.sensitivity != "restricted" or record.authority != "authoritative":
                raise ContextPreparationError("health_context_sensitivity_or_authority_invalid")
            labels = tuple(
                ContextFieldSensitivity(field=value.field, sensitivity=value.sensitivity)
                for value in record.field_sensitivity
            )
            reference = ContextEntityReference(
                entity_type=record.object_type,
                entity_id=str(record.object_id),
                application_id="health",
                workspace_id=None,
            )
            dependencies = tuple(
                ContextPermissionDependency(
                    permission_id=value.permission_id,
                    version=value.version,
                    purpose=value.purpose,
                )
                for value in record.permission_dependencies
            )
            source_refs = tuple(
                ContextSourceReference(
                    kind=value.kind,
                    reference_id=value.reference_id,
                    fingerprint=value.fingerprint,
                )
                for value in record.source_refs
            )
            opaque_item = sha256(f"{record.object_type}\0{record.object_id}".encode()).hexdigest()
            items.append(
                ContextItem[HealthContextPayload](
                    source_class=self.spec.source_class,
                    provider_id=self.provider_id,
                    source_id=f"health:{sha256(str(record.source_id).encode()).hexdigest()}",
                    source_version=record.source_version,
                    item_id=f"health:{record.object_type}:{opaque_item[:32]}",
                    owner_id=scope.owner_id,
                    application_id="health",
                    workspace_id=None,
                    entity_refs=(reference,),
                    authority=record.authority,
                    observed_at=record.observed_at,
                    effective_at=record.effective_at,
                    expires_at=record.expires_at,
                    sensitivity=record.sensitivity,
                    source_refs=source_refs,
                    permission_dependencies=dependencies,
                    selected_operation=selection.operation,
                    field_sensitivity=labels,
                    payload=payload,
                )
            )
        return tuple(items)


class HealthContextPayload(BaseModel):
    """Typed selected payload; unknown and unavailable values remain explicit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    record: JsonValue | None = None
    domain: str | None = None
    notes: str | None = None
    time: JsonValue | None = None
    interval_end: AwareDatetime | None = None
    units: dict[str, str] | None = None
    source_kind: HealthSourceKind | None = None
    confirmation_status: HealthConfirmation | None = None
    quality: dict[str, JsonValue] | None = None
    uncertainty: str | None = None
    validity: dict[str, AwareDatetime | None] | None = None


class HealthContextProviderFactory:
    def __init__(self, client: HealthContextHTTPClient, provider_id: str) -> None:
        self.client = client
        self.spec = HealthContextProvider(client, provider_id).spec
        self.provider_id = provider_id

    def create(self, inputs: ContextProviderInputs) -> HealthContextProvider:
        del inputs
        return HealthContextProvider(self.client, self.provider_id)


class HealthContextPermissionRevalidator:
    """Recheck each selected record with Health before context reuse or dispatch."""

    permission_prefix = "health_context_read:"
    permission_namespaces = (permission_prefix,)

    def __init__(self, client: HealthContextHTTPClient) -> None:
        self.client = client

    def supports(self, dependency: ContextPermissionDependency) -> bool:
        return dependency.permission_id.startswith(self.permission_prefix)

    def is_current(self, dependency: ContextPermissionDependency) -> bool:
        if not self.supports(dependency):
            return False
        try:
            _, category, object_type, object_id = dependency.permission_id.split(":", 3)
            request = HealthContextReadRequest(
                operation="verify",
                category=category,
                entity_refs=(
                    HealthContextEntityReference(
                        object_type=object_type,
                        object_id=UUID(object_id),
                    ),
                ),
                fields=("permission_version",),
                max_results=1,
                max_bytes=4096,
            )
            response = self.client.read(request, deadline=monotonic() + 0.75)
        except Exception:  # noqa: BLE001 - current owner authority fails closed
            return False
        return any(
            value.object_id == UUID(object_id) and value.version == dependency.version
            for value in response.permission_versions
        )


def health_context_planning_rules() -> tuple[ContextPlanningRule, ...]:
    """Expose only explicit Health category requests inside the Health app scope."""
    profile_phrases = {
        "profile_background": ("include my health background", "health profile background"),
        "profile_constraints": ("include my health constraints", "health profile constraints"),
        "profile_preferences": ("include my health preferences", "health profile preferences"),
    }
    history_phrases = {
        "measurements": ("include my recent health measurements", "recent health measurements"),
        "nutrition": ("include my recent nutrition history", "recent health nutrition"),
        "exercise": ("include my recent activity history", "recent health activity"),
        "sleep": ("include my recent sleep history", "recent health sleep"),
        "symptoms": ("include my recent symptom history", "recent health symptoms"),
    }
    rules: list[ContextPlanningRule] = []
    for provider_id, (category, operation, _source_class) in HEALTH_CATEGORY_PROVIDERS.items():
        is_profile = operation == "profile"
        rules.append(
            ContextPlanningRule(
                rule_id=f"health.{category}:v1",
                category=f"health_{category}",
                phrases=profile_phrases[category] if is_profile else history_phrases[category],
                provider_id=provider_id,
                operation=operation,
                fields=HEALTH_PROFILE_FIELDS if is_profile else HEALTH_DAILY_FIELDS,
                max_results=6 if is_profile else 12,
                max_bytes=12_288 if is_profile else 24_576,
                max_tokens=512 if is_profile else 1024,
                timeout_seconds=3,
                window_seconds=None if is_profile else int(HEALTH_MAX_WINDOW.total_seconds()),
                application_ids=("health",),
                explanation=f"Read only the explicitly requested {HEALTH_CATEGORY_LABELS[category].casefold()}.",
            )
        )
    return tuple(rules)


def configured_health_context_contribution(settings) -> ContextRuntimeContribution:
    """Install Health readers only behind the separate default-off context gate."""
    if not settings.health_context_enabled:
        return ContextRuntimeContribution(provider_factories={})
    from personal_ai.auth.service_tokens import fetch_google_service_token

    client = HealthContextHTTPClient(
        base_url=str(settings.health_context_base_url),
        auth_mode=settings.auth_mode,
        service_audience=settings.health_context_service_audience,
        service_account=settings.health_context_service_account,
        timeout_seconds=settings.health_context_timeout_seconds,
        service_token_fetcher=fetch_google_service_token,
    )
    return ContextRuntimeContribution(
        provider_factories={
            provider_id: HealthContextProviderFactory(client, provider_id)
            for provider_id in HEALTH_CATEGORY_PROVIDERS
        },
        planning_rules=health_context_planning_rules(),
        permission_revalidators=(HealthContextPermissionRevalidator(client),),
    )
