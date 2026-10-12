"""Shopping uses the shared context source, policy, and revalidation contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import httpx
import pytest

from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    bind_verified_user_identity_token,
    reset_verified_user_identity_token,
)
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextFieldSensitivity,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderError,
    ContextSelection,
)
from personal_ai.context.shopping import (
    SHOPPING_CATALOG_PROVIDER_ID,
    SHOPPING_CONTEXT_PATH,
    SHOPPING_CONTEXT_PROVIDER_ID,
    SHOPPING_CONTEXT_SCHEMA,
    ShoppingCatalogSearchProvider,
    ShoppingContextHTTPClient,
    ShoppingContextPermissionRevalidator,
    ShoppingContextProvider,
    ShoppingContextReadRequest,
    ShoppingContextReadResponse,
    ShoppingContextRecord,
    configured_shopping_context_contribution,
)
from personal_ai.settings import Settings


def _scope() -> RequestScope:
    return RequestScope(
        owner_id="owner-1",
        request_id="shopping-context-test",
        application_id="shopping",
        workspace_id=None,
    )


def _references(project_id: str, product_id: str | None = None):
    refs = [
        ContextEntityReference(
            entity_type="project",
            entity_id=project_id,
            application_id="shopping",
            workspace_id=None,
        )
    ]
    if product_id:
        refs.append(
            ContextEntityReference(
                entity_type="project_product",
                entity_id=product_id,
                application_id="shopping",
                workspace_id=None,
            )
        )
    return tuple(refs)


def _selection(provider_id, operation, fields, refs):
    return ContextSelection(
        provider_id=provider_id,
        operation=operation,
        fields=fields,
        entity_refs=refs,
        max_results=8,
        max_bytes=8192,
        max_tokens=512,
        timeout_seconds=2,
        target_scope=ApplicationScope(application_id="shopping", workspace_id=None),
    )


def _record(
    entity_type,
    entity_id,
    *,
    source_class="domain_current",
    authority="authoritative",
    payload,
    project_id=None,
):
    project_id = project_id or (entity_id if entity_type == "project" else str(uuid4()))
    now = datetime.now(UTC)
    field_sensitivity = tuple(
        ContextFieldSensitivity(
            field=field,
            sensitivity="sensitive" if field == "selected_products" else "personal",
        )
        for field in payload
    )
    return ShoppingContextRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        source_id=f"shopping:{entity_id}",
        source_version="4",
        source_class=source_class,
        authority=authority,
        observed_at=now,
        expires_at=now + timedelta(hours=1),
        sensitivity="sensitive",
        payload=payload,
        source_refs=(
            {
                "kind": "record",
                "reference_id": project_id,
                "fingerprint": "a" * 64,
            },
        ),
        permission_dependencies=(
            {
                "permission_id": f"shopping_project_read:{project_id}",
                "version": "4",
                "purpose": "verify current Shopping project ownership and revision",
            },
        ),
        field_sensitivity=field_sensitivity,
    )


class _FakeShoppingClient:
    def __init__(self, *items):
        self.response = ShoppingContextReadResponse(items=items)
        self.requests = []

    def read(self, request, *, deadline):
        self.requests.append((request, deadline))
        return self.response


def test_shopping_product_provider_preserves_exact_identity_and_shared_policy_metadata():
    project_id, membership_id, product_id, variant_id = (str(uuid4()) for _ in range(4))
    selected = {
        "project_product_id": membership_id,
        "product_id": product_id,
        "variant_id": variant_id,
        "canonical_name": "Example vacuum",
        "brand": "Example",
        "variant_name": "Model X, US",
        "decision_state": "rejected",
        "saved": False,
        "rejection_reason": "too_heavy",
    }
    record = _record(
        "project",
        project_id,
        payload={"project_title": "Vacuum", "selected_products": [selected]},
    )
    client = _FakeShoppingClient(record)
    provider = ShoppingContextProvider(client)
    selection = _selection(
        SHOPPING_CONTEXT_PROVIDER_ID,
        "current",
        ("project_title", "selected_products"),
        _references(project_id, membership_id),
    )

    (item,) = provider.fetch(selection, _scope(), deadline=monotonic() + 5)

    assert item.application_id == "shopping"
    assert item.workspace_id is None
    assert [(ref.entity_type, ref.entity_id) for ref in item.entity_refs] == [
        ("project", project_id),
        ("project_product", membership_id),
    ]
    assert item.payload.selected_products[0]["product_id"] == product_id
    assert item.payload.selected_products[0]["variant_id"] == variant_id
    assert item.payload.selected_products[0]["decision_state"] == "rejected"
    assert item.permission_dependencies[0].permission_id.startswith("shopping_project_read:")
    assert item.field_sensitivity[0].field == "project_title"
    assert client.requests[0][0].workspace_id is None
    assert client.requests[0][0].selected_project_product_ids == (membership_id,)


def test_catalog_provider_accepts_only_selected_evidence_with_exact_record_anchor():
    project_id, selected_id, unselected_id = (str(uuid4()) for _ in range(3))
    product_id, variant_id = str(uuid4()), str(uuid4())
    record = _record(
        "evidence",
        selected_id,
        source_class="external_research",
        authority="external",
        payload={
            "catalog_observations": {
                "project_product_id": selected_id,
                "product_id": product_id,
                "product_revision": 2,
                "variant_id": variant_id,
                "variant_revision": 3,
                "observations": [{"freshness": "stale"}],
                "partial_result": True,
                "omitted_count": 2,
                "selection_policy_version": "shopping-catalog-recent-first-v1",
            }
        },
        project_id=project_id,
    )
    record = ShoppingContextRecord.model_validate(
        {
            **record.model_dump(),
            "source_refs": (
                {"kind": "record", "reference_id": selected_id, "fingerprint": "b" * 64},
                {"kind": "evidence", "reference_id": "evidence-1", "fingerprint": "c" * 64},
            ),
        }
    )
    client = _FakeShoppingClient(record)
    selection = _selection(
        SHOPPING_CATALOG_PROVIDER_ID,
        "search",
        ("catalog_observations",),
        _references(project_id, selected_id),
    )
    (item,) = ShoppingCatalogSearchProvider(client).fetch(
        selection, _scope(), deadline=monotonic() + 5
    )
    assert item.source_class == "external_research"
    assert item.authority == "external"
    assert str(item.payload.catalog_observations.project_product_id) == selected_id
    assert str(item.payload.catalog_observations.product_id) == product_id
    assert str(item.payload.catalog_observations.variant_id) == variant_id
    assert item.partial_result is True
    assert item.omitted_count == 2
    assert item.selection_policy_version == "shopping-catalog-recent-first-v1"
    assert {ref.reference_id for ref in item.source_refs if ref.kind == "record"} == {selected_id}
    assert [(ref.entity_type, ref.entity_id) for ref in item.entity_refs] == [
        ("project", project_id),
        ("project_product", selected_id),
        ("product", product_id),
        ("variant", variant_id),
    ]

    unbound_payload = {
        **record.payload,
        "catalog_observations": {
            **record.payload["catalog_observations"],
            "project_product_id": unselected_id,
        },
    }
    unbound = ShoppingContextRecord.model_validate(
        {**record.model_dump(), "payload": unbound_payload}
    )
    with pytest.raises(ContextPreparationError, match="shopping_catalog_identity_mismatch"):
        ShoppingCatalogSearchProvider(_FakeShoppingClient(unbound)).fetch(
            selection, _scope(), deadline=monotonic() + 5
        )

    unselected = ShoppingContextRecord.model_validate(
        {
            **record.model_dump(),
            "entity_id": unselected_id,
            "source_refs": (
                {"kind": "record", "reference_id": unselected_id, "fingerprint": "d" * 64},
                {"kind": "evidence", "reference_id": "evidence-1", "fingerprint": "c" * 64},
            ),
        }
    )
    with pytest.raises(ContextPreparationError, match="shopping_context_unselected_product"):
        ShoppingCatalogSearchProvider(_FakeShoppingClient(unselected)).fetch(
            selection, _scope(), deadline=monotonic() + 5
        )


def test_permission_revalidator_checks_the_exact_project_and_revision():
    project_id = str(uuid4())
    record = _record("project", project_id, payload={"project_revision": 4})
    client = _FakeShoppingClient(record)
    revalidator = ShoppingContextPermissionRevalidator(client)
    dependency = ContextPermissionDependency(
        permission_id=f"shopping_project_read:{project_id}",
        version="4",
        purpose="verify current Shopping project ownership and revision",
    )

    assert revalidator.is_current(dependency) is True
    stale = dependency.model_copy(update={"version": "5"})
    assert revalidator.is_current(stale) is False


def test_permission_revalidator_checks_selected_product_and_variant_version():
    project_id, project_product_id = str(uuid4()), str(uuid4())
    current = _record(
        "project_product",
        project_product_id,
        payload={"selected_products": ()},
        project_id=project_id,
    )
    current = ShoppingContextRecord.model_validate(
        {
            **current.model_dump(),
            "permission_dependencies": (
                {
                    "permission_id": f"shopping_project_read:{project_id}",
                    "version": "4",
                    "purpose": "verify current Shopping project ownership and revision",
                },
                {
                    "permission_id": (
                        f"shopping_product_read:{project_id}:{project_product_id}"
                    ),
                    "version": "b" * 64,
                    "purpose": "verify selected Shopping product and current catalog identity",
                },
            )
        }
    )
    client = _FakeShoppingClient(current)
    revalidator = ShoppingContextPermissionRevalidator(client)
    dependency = ContextPermissionDependency(
        permission_id=f"shopping_product_read:{project_id}:{project_product_id}",
        version="b" * 64,
        purpose="verify selected Shopping product and current catalog identity",
    )

    assert revalidator.is_current(dependency) is True
    request = client.requests[0][0]
    assert request.operation == "verify"
    assert request.fields == ("selected_products",)
    assert request.selected_project_product_ids == (project_product_id,)
    assert revalidator.is_current(dependency.model_copy(update={"version": "c" * 64})) is False


def test_context_http_client_sends_separate_service_and_user_assertions():
    project_id = str(uuid4())
    body = {
        "schema_version": SHOPPING_CONTEXT_SCHEMA,
        "application_id": "shopping",
        "workspace_id": None,
        "items": [
            {
                "entity_type": "project",
                "entity_id": project_id,
                "source_id": f"shopping-project:{project_id}",
                "source_version": "2",
                "source_class": "domain_current",
                "authority": "authoritative",
                "sensitivity": "personal",
                "payload": {"project_title": "Vacuum"},
                "source_refs": [
                    {"kind": "record", "reference_id": project_id, "fingerprint": "a" * 64}
                ],
                "permission_dependencies": [],
                "field_sensitivity": [
                    {"field": "project_title", "sensitivity": "personal"}
                ],
            }
        ],
    }
    observed = {}

    def respond(request):
        observed["method"] = request.method
        observed["url"] = str(request.url)
        observed["headers"] = dict(request.headers)
        observed["body"] = json.loads(request.content)
        return httpx.Response(200, json=body)

    user_identity = bind_verified_user_identity_token("verified-user-token")
    try:
        client = ShoppingContextHTTPClient(
            base_url="https://shopping.example",
            auth_mode="google_oidc",
            service_audience="https://shopping.example",
            service_account="personal-ai@example.iam.gserviceaccount.com",
            service_token_fetcher=lambda *, audience, service_account, deadline: "service-token",
            transport=httpx.MockTransport(respond),
        )
        response = client.read(
            ShoppingContextReadRequest(
                operation="current",
                project_id=project_id,
                fields=("project_title",),
                max_results=1,
                max_bytes=4096,
            ),
            deadline=monotonic() + 5,
        )
    finally:
        reset_verified_user_identity_token(user_identity)

    assert observed["method"] == "POST"
    assert observed["url"].endswith(SHOPPING_CONTEXT_PATH)
    assert observed["headers"]["authorization"] == "Bearer service-token"
    assert observed["headers"]["x-user-id-token"] == "verified-user-token"
    assert observed["headers"]["x-application-id"] == "shopping"
    assert observed["body"]["workspace_id"] is None
    assert response.items[0].entity_id == project_id


def test_shopping_token_fetch_uses_provider_deadline_and_stops_before_http(monkeypatch):
    project_id = str(uuid4())
    user_identity = bind_verified_user_identity_token("verified-user-token")
    token_arguments = {}
    requests = []
    clock_values = iter((100.0, 100.8))
    monkeypatch.setattr("personal_ai.context.shopping.monotonic", lambda: next(clock_values))

    def fetch_token(**kwargs):
        token_arguments.update(kwargs)
        return "service-token"

    client = ShoppingContextHTTPClient(
        base_url="https://shopping.example",
        auth_mode="google_oidc",
        service_audience="https://shopping.example",
        service_account="personal-ai@example.iam.gserviceaccount.com",
        service_token_fetcher=fetch_token,
        transport=httpx.MockTransport(lambda request: requests.append(request)),
    )
    try:
        with pytest.raises(ContextProviderError, match="shopping_context_unavailable"):
            client.read(
                ShoppingContextReadRequest(
                    operation="current",
                    project_id=project_id,
                    fields=("project_title",),
                    max_results=1,
                    max_bytes=4096,
                ),
                deadline=100.5,
            )
    finally:
        reset_verified_user_identity_token(user_identity)

    assert token_arguments["deadline"] == 100.5
    assert requests == []


def test_shopping_contribution_is_off_by_default_and_registry_action_stays_unavailable():
    contribution = configured_shopping_context_contribution(
        Settings(
            _env_file=None,
            ai_provider="fake",
            ai_model="fixture",
            shopping_context_enabled=False,
        )
    )
    assert contribution.provider_factories == {}
    assert contribution.planning_rules

    registry = default_application_registry()
    product_context = registry.capability(
        "shopping", SHOPPING_CONTEXT_PROVIDER_ID, kind="context_provider"
    )
    catalog_search = registry.capability(
        "shopping", SHOPPING_CATALOG_PROVIDER_ID, kind="context_provider"
    )
    action = registry.capability("shopping", "shopping.product_action", kind="tool")
    assert product_context.is_enabled({}) is False
    assert product_context.is_enabled({"shopping_context_enabled": True}) is True
    assert catalog_search.is_enabled({"shopping_context_enabled": True}) is True
    assert action.is_enabled({"shopping_context_enabled": True}) is False
