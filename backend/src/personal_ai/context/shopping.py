"""Shopping's versioned read contract through the shared context pipeline.

Shopping remains the source of project and catalog truth.  This adapter only
fetches explicitly selected project/product references and normalizes them into
the existing provider, policy, and permission-revalidation contracts.
"""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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

SHOPPING_CONTEXT_PATH = "/v1/integrations/personal-ai/context"
SHOPPING_CONTEXT_SCHEMA = "shopping-context-read-v1"
SHOPPING_CONTEXT_PROVIDER_ID = "shopping.product_context"
SHOPPING_CATALOG_PROVIDER_ID = "shopping.catalog_search"
SHOPPING_CONTEXT_FIELDS = (
    "project_title",
    "project_goal",
    "category",
    "requirements",
    "budget_target",
    "budget_maximum",
    "budget_currency",
    "project_notes",
    "selected_products",
    "catalog_observations",
    "project_revision",
)


class ShoppingContextReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["shopping-context-read-v1"] = SHOPPING_CONTEXT_SCHEMA
    application_id: Literal["shopping"] = "shopping"
    # Project IDs are domain references, never workspace IDs.
    workspace_id: None = None
    operation: Literal["current", "search", "verify"]
    project_id: str = Field(min_length=1, max_length=100)
    selected_project_product_ids: tuple[str, ...] = Field(default=(), max_length=16)
    fields: tuple[str, ...] = Field(default=(), max_length=32)
    max_results: int = Field(ge=1, le=50)
    max_bytes: int = Field(ge=1, le=65_536)
    timeout_seconds: float = Field(default=3.0, gt=0, le=5.0)


class ShoppingContextSourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(min_length=1, max_length=80)
    reference_id: str = Field(min_length=1, max_length=500)
    fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ShoppingContextPermission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    permission_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=200)


class ShoppingContextRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: Literal["project", "project_product", "offer", "evidence"]
    entity_id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=100)
    source_class: Literal["domain_current", "external_research"]
    authority: Literal["authoritative", "user_asserted", "derived", "external", "unknown"]
    observed_at: datetime | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    sensitivity: Literal["public", "personal", "sensitive", "restricted", "unknown"]
    payload: dict[str, object] = Field(max_length=32)
    source_refs: tuple[ShoppingContextSourceRef, ...] = Field(min_length=1, max_length=16)
    permission_dependencies: tuple[ShoppingContextPermission, ...] = Field(
        default=(), max_length=16
    )
    field_sensitivity: tuple[ContextFieldSensitivity, ...] = Field(default=(), max_length=32)


class ShoppingContextReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["shopping-context-read-v1"] = SHOPPING_CONTEXT_SCHEMA
    application_id: Literal["shopping"] = "shopping"
    workspace_id: None = None
    items: tuple[ShoppingContextRecord, ...] = Field(default=(), max_length=50)


class ShoppingCatalogEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_product_id: UUID
    product_id: UUID
    variant_id: UUID
    observations: tuple[dict[str, object], ...] = Field(min_length=1, max_length=5)


class ShoppingProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_title: str | None = None
    project_goal: str | None = None
    category: str | None = None
    requirements: tuple[dict[str, object], ...] | None = Field(default=None, max_length=100)
    budget_target: str | None = None
    budget_maximum: str | None = None
    budget_currency: str | None = None
    project_notes: str | None = None
    project_revision: int | None = None
    selected_products: tuple[dict[str, object], ...] | None = Field(default=None, max_length=16)
    catalog_observations: ShoppingCatalogEvidence | None = None


class ShoppingContextHTTPClient:
    """Bounded Shopping API client with separate service and user identities."""

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
            raise ValueError("shopping_context_base_url_invalid")
        self.base_url = base_url.rstrip("/")
        self.auth_mode = auth_mode
        self.service_audience = service_audience
        self.service_account = service_account
        self.timeout_seconds = min(max(timeout_seconds, 0.1), 10.0)
        self.service_token_fetcher = service_token_fetcher
        self.transport = transport

    def read(
        self, request: ShoppingContextReadRequest, *, deadline: float
    ) -> ShoppingContextReadResponse:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError
        user_token = current_verified_user_identity_token()
        if not user_token or len(user_token) > 8192:
            raise ContextProviderError("shopping_user_identity_unavailable")
        fetcher = self.service_token_fetcher
        if self.auth_mode != "google_oidc" or fetcher is None:
            raise ContextProviderError("shopping_service_identity_unavailable")
        try:
            service_token = fetcher(
                audience=self.service_audience,
                service_account=self.service_account,
            )
        except Exception as error:
            raise ContextProviderError("shopping_service_identity_unavailable") from error
        if not service_token or len(service_token) > 8192:
            raise ContextProviderError("shopping_service_identity_unavailable")

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
                    f"{self.base_url}{SHOPPING_CONTEXT_PATH}",
                    json=request.model_dump(mode="json"),
                    headers={
                        "Authorization": f"Bearer {service_token}",
                        "X-User-ID-Token": user_token,
                        "X-Application-ID": "shopping",
                    },
                ) as response,
            ):
                response.raise_for_status()
                encoded = bytearray()
                for chunk in response.iter_bytes(4096):
                    encoded.extend(chunk)
                    if len(encoded) > request.max_bytes:
                        raise ContextProviderError("shopping_context_response_too_large")
                try:
                    result = ShoppingContextReadResponse.model_validate(json.loads(encoded))
                except (ValueError, TypeError, ValidationError, RecursionError):
                    raise ContextProviderError("shopping_context_response_invalid") from None
        except ContextProviderError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            raise ContextProviderError("shopping_context_unavailable") from error
        if result.schema_version != SHOPPING_CONTEXT_SCHEMA:
            raise ContextProviderError("shopping_context_contract_unsupported")
        if result.application_id != "shopping" or result.workspace_id is not None:
            raise ContextProviderError("shopping_context_scope_invalid")
        return result


class ShoppingContextProvider:
    spec = ContextProviderSpec(
        provider_id=SHOPPING_CONTEXT_PROVIDER_ID,
        source_class="domain_current",
        source_version=SHOPPING_CONTEXT_SCHEMA,
        operations=(
            ContextOperationSpec(
                operation="current",
                allowed_fields=(
                    "project_title",
                    "project_goal",
                    "category",
                    "requirements",
                    "budget_target",
                    "budget_maximum",
                    "budget_currency",
                    "project_notes",
                    "project_revision",
                    "selected_products",
                ),
                accepts_entity_refs=True,
                maximum_results=24,
                maximum_bytes=32_768,
                maximum_timeout_seconds=5,
            ),
        ),
        maximum_items_per_call=24,
    )

    def __init__(self, client: ShoppingContextHTTPClient) -> None:
        self.client = client

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs):
        _validate_shopping_scope(selection, inputs.scope)
        _project_id(selection.entity_refs)

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        project_id = _project_id(selection.entity_refs)
        selected_ids = _selected_product_ids(selection.entity_refs)
        response = self.client.read(
            ShoppingContextReadRequest(
                operation="current",
                project_id=project_id,
                selected_project_product_ids=selected_ids,
                fields=selection.fields,
                max_results=selection.max_results,
                max_bytes=selection.max_bytes,
                timeout_seconds=min(selection.timeout_seconds, 5.0),
            ),
            deadline=deadline,
        )
        if len(response.items) > selection.max_results:
            raise ContextPreparationError("shopping_context_result_limit_exceeded")
        projects = [record for record in response.items if record.entity_type == "project"]
        if len(projects) != 1 or len(response.items) != 1:
            raise ContextPreparationError("shopping_context_project_result_invalid")
        item = _context_item(projects[0], selection, scope)
        present = {
            str(product.get("project_product_id"))
            for product in (item.payload.selected_products or ())
            if product.get("project_product_id") is not None
        }
        if "selected_products" in selection.fields and not set(selected_ids).issubset(present):
            raise ContextPreparationError("shopping_context_selected_product_missing")
        return (item,)


class ShoppingCatalogSearchProvider:
    spec = ContextProviderSpec(
        provider_id=SHOPPING_CATALOG_PROVIDER_ID,
        source_class="external_research",
        source_version=SHOPPING_CONTEXT_SCHEMA,
        operations=(
            ContextOperationSpec(
                operation="search",
                allowed_fields=("catalog_observations",),
                accepts_entity_refs=True,
                maximum_results=50,
                maximum_bytes=32_768,
                maximum_timeout_seconds=5,
            ),
        ),
        maximum_items_per_call=50,
    )

    def __init__(self, client: ShoppingContextHTTPClient) -> None:
        self.client = client

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs):
        _validate_shopping_scope(selection, inputs.scope)
        _project_id(selection.entity_refs)
        if not _selected_product_ids(selection.entity_refs):
            raise ContextPreparationError("shopping_catalog_selection_required")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        project_id = _project_id(selection.entity_refs)
        selected_ids = _selected_product_ids(selection.entity_refs)
        response = self.client.read(
            ShoppingContextReadRequest(
                operation="search",
                project_id=project_id,
                selected_project_product_ids=selected_ids,
                fields=selection.fields,
                max_results=selection.max_results,
                max_bytes=selection.max_bytes,
                timeout_seconds=min(selection.timeout_seconds, 5.0),
            ),
            deadline=deadline,
        )
        if len(response.items) > selection.max_results:
            raise ContextPreparationError("shopping_context_result_limit_exceeded")
        items = [_context_item(record, selection, scope) for record in response.items]
        if any(item.source_class != "external_research" for item in items):
            raise ContextPreparationError("shopping_catalog_authority_invalid")
        selected_set = set(selected_ids)
        for item in items:
            anchors = [ref.reference_id for ref in item.source_refs if ref.kind == "record"]
            catalog = item.payload.catalog_observations
            if (
                len(anchors) != 1
                or anchors[0] not in selected_set
                or catalog is None
                or str(catalog.project_product_id) != anchors[0]
            ):
                raise ContextPreparationError("shopping_context_unselected_product")
        return tuple(items)


class ShoppingContextProviderFactory:
    def __init__(self, client: ShoppingContextHTTPClient) -> None:
        self.client = client
        self.spec = ShoppingContextProvider.spec

    def create(self, inputs: ContextProviderInputs) -> ShoppingContextProvider:
        del inputs
        return ShoppingContextProvider(self.client)


class ShoppingCatalogSearchProviderFactory:
    def __init__(self, client: ShoppingContextHTTPClient) -> None:
        self.client = client
        self.spec = ShoppingCatalogSearchProvider.spec

    def create(self, inputs: ContextProviderInputs) -> ShoppingCatalogSearchProvider:
        del inputs
        return ShoppingCatalogSearchProvider(self.client)


class ShoppingContextPermissionRevalidator:
    """Recheck project ownership and revision before any later disclosure."""

    permission_prefix = "shopping_project_read:"
    permission_namespaces = (permission_prefix,)

    def __init__(self, client: ShoppingContextHTTPClient) -> None:
        self.client = client

    def supports(self, dependency: ContextPermissionDependency) -> bool:
        return dependency.permission_id.startswith(self.permission_prefix)

    def is_current(self, dependency: ContextPermissionDependency) -> bool:
        if not self.supports(dependency):
            return False
        project_id = dependency.permission_id.removeprefix(self.permission_prefix)
        try:
            response = self.client.read(
                ShoppingContextReadRequest(
                    operation="verify",
                    project_id=project_id,
                    fields=("project_revision",),
                    max_results=1,
                    max_bytes=2_048,
                    timeout_seconds=0.75,
                ),
                deadline=monotonic() + 0.75,
            )
        except Exception:  # noqa: BLE001 - unavailable owner checks fail closed
            return False
        return (
            len(response.items) == 1
            and response.items[0].entity_type == "project"
            and response.items[0].entity_id == project_id
            and response.items[0].source_version == dependency.version
        )


def _validate_shopping_scope(selection: ContextSelection, scope: RequestScope) -> None:
    if scope.application_id != "shopping" or scope.workspace_id is not None:
        raise ContextPreparationError("shopping_context_application_scope_required")
    if not selection.entity_refs or any(
        ref.application_id != "shopping" or ref.workspace_id is not None
        for ref in selection.entity_refs
    ):
        raise ContextPreparationError("shopping_context_entity_scope_invalid")
    if any(ref.entity_type not in {"project", "project_product"} for ref in selection.entity_refs):
        raise ContextPreparationError("shopping_context_entity_type_invalid")


def _project_id(entity_refs: tuple[ContextEntityReference, ...]) -> str:
    projects = [ref.entity_id for ref in entity_refs if ref.entity_type == "project"]
    if len(projects) != 1:
        raise ContextPreparationError("shopping_context_project_reference_required")
    try:
        return str(UUID(projects[0]))
    except ValueError:
        raise ContextPreparationError("shopping_context_project_reference_invalid") from None


def _selected_product_ids(entity_refs: tuple[ContextEntityReference, ...]) -> tuple[str, ...]:
    raw_values = tuple(ref.entity_id for ref in entity_refs if ref.entity_type == "project_product")
    if len(raw_values) > 16:
        raise ContextPreparationError("shopping_context_product_reference_limit_exceeded")
    try:
        values = tuple(str(UUID(value)) for value in raw_values)
    except ValueError:
        raise ContextPreparationError("shopping_context_product_reference_invalid") from None
    if len(values) != len(set(values)):
        raise ContextPreparationError("shopping_context_product_references_invalid")
    return values


def _context_item(
    record: ShoppingContextRecord,
    selection: ContextSelection,
    scope: RequestScope,
) -> ContextItem:
    payload_type = ShoppingProjectPayload
    selected_values = {
        key: value for key, value in record.payload.items() if key in selection.fields
    }
    try:
        payload = payload_type.model_validate(selected_values)
    except ValidationError as error:
        raise ContextPreparationError("shopping_context_payload_invalid") from error
    if record.entity_type == "project" and record.entity_id != _project_id(selection.entity_refs):
        raise ContextPreparationError("shopping_context_unselected_project")
    selected_ids = set(_selected_product_ids(selection.entity_refs))
    if record.entity_type != "project" and record.entity_id not in selected_ids:
        raise ContextPreparationError("shopping_context_unselected_product")
    if any(
        product.get("project_product_id") is not None
        and str(product["project_product_id"]) not in selected_ids
        for product in (payload.selected_products or ())
    ):
        raise ContextPreparationError("shopping_context_unselected_product")
    if record.entity_type == "evidence" and (
        payload.catalog_observations is None
        or str(payload.catalog_observations.project_product_id) != record.entity_id
    ):
        raise ContextPreparationError("shopping_catalog_identity_mismatch")
    if record.source_class == "external_research" and record.authority == "authoritative":
        raise ContextPreparationError("shopping_catalog_authority_invalid")

    return ContextItem(
        source_class=record.source_class,
        provider_id=selection.provider_id,
        source_id=f"shopping:{sha256(record.source_id.encode()).hexdigest()}",
        source_version=record.source_version,
        item_id=f"shopping:{record.entity_type}:{sha256(record.entity_id.encode()).hexdigest()[:32]}",
        owner_id=scope.owner_id,
        application_id="shopping",
        workspace_id=None,
        entity_refs=(),
        authority=record.authority,
        observed_at=record.observed_at,
        effective_at=record.effective_at,
        expires_at=record.expires_at,
        sensitivity=record.sensitivity,
        source_refs=tuple(
            ContextSourceReference(
                kind=source.kind,
                reference_id=source.reference_id,
                fingerprint=source.fingerprint,
            )
            for source in record.source_refs
        ),
        permission_dependencies=tuple(
            ContextPermissionDependency(
                permission_id=item.permission_id,
                version=item.version,
                purpose=item.purpose,
            )
            for item in record.permission_dependencies
        ),
        selected_operation=selection.operation,
        field_sensitivity=record.field_sensitivity,
        payload=payload,
    )


def shopping_context_planning_rules() -> tuple[ContextPlanningRule, ...]:
    """Opt explicitly selected Shopping project/product references into planning."""
    return (
        ContextPlanningRule(
            rule_id="shopping.selected-project-context:v1",
            category="shopping_project_context",
            phrases=("this shopping project", "my shopping project", "project requirements"),
            provider_id=SHOPPING_CONTEXT_PROVIDER_ID,
            operation="current",
            fields=("project_title", "project_goal", "requirements", "selected_products"),
            max_results=12,
            max_bytes=24_576,
            max_tokens=768,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            candidate_entity_types=("project", "project_product"),
            required=True,
            priority=25,
            application_ids=("shopping",),
            explanation="Read the selected Shopping project and its explicit product references.",
        ),
        ContextPlanningRule(
            rule_id="shopping.selected-catalog-evidence:v1",
            category="shopping_selected_catalog_evidence",
            phrases=("compare these selected products", "use selected product evidence"),
            provider_id=SHOPPING_CATALOG_PROVIDER_ID,
            operation="search",
            fields=("catalog_observations",),
            max_results=24,
            max_bytes=24_576,
            max_tokens=768,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("project", "project_product"),
            priority=30,
            application_ids=("shopping",),
            explanation="Read only selected Shopping variants and their bounded observations.",
        ),
    )


def configured_shopping_context_contribution(settings) -> ContextRuntimeContribution:
    """Install Shopping source code only behind its independent deployment gate."""
    planning_rules = shopping_context_planning_rules()
    if not settings.shopping_context_enabled:
        return ContextRuntimeContribution(provider_factories={}, planning_rules=planning_rules)

    from personal_ai.auth.service_tokens import fetch_google_service_token

    client = ShoppingContextHTTPClient(
        base_url=str(settings.shopping_context_base_url),
        auth_mode=settings.auth_mode,
        service_audience=settings.shopping_context_service_audience,
        service_account=settings.shopping_context_service_account,
        timeout_seconds=settings.shopping_context_timeout_seconds,
        service_token_fetcher=fetch_google_service_token,
    )
    return ContextRuntimeContribution(
        provider_factories={
            SHOPPING_CONTEXT_PROVIDER_ID: ShoppingContextProviderFactory(client),
            SHOPPING_CATALOG_PROVIDER_ID: ShoppingCatalogSearchProviderFactory(client),
        },
        planning_rules=planning_rules,
        permission_revalidators=(ShoppingContextPermissionRevalidator(client),),
    )
