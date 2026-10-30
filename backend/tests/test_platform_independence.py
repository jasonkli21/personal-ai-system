"""Core defaults and adversarial composition beyond historical reference tests."""

from types import SimpleNamespace

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from personal_ai.applications.http import attach_contribution_routes
from personal_ai.applications.registry import (
    ApplicationContribution,
    ApplicationContributionCatalog,
    default_application_registry,
)
from personal_ai.applications.selection import load_selected_entry_points
from personal_ai.context.deployment import configured_context_runtime
from personal_ai.context.runtime import ContextRuntimeContributionCatalog
from personal_ai.main import create_app
from personal_ai.settings import Settings, get_settings


def settings(**values):
    return Settings(
        _env_file=None, ai_provider="fake", ai_model="fake", app_environment="test", **values
    )


def test_core_and_explicit_empty_catalogs_have_no_reference_defaults():
    registry = default_application_registry(contribution_catalog=ApplicationContributionCatalog())
    assert registry.application_ids == {"personal_ai"}
    assert {item.capability_id for item in registry.capabilities} == {
        "conversation_history",
        "ai_memory",
        "external_research",
        "global_profile",
        "client_context",
    }
    assert registry.comparison_modules == {}
    assert (
        registry.get("personal_ai").context_policy.operation(
            "booking.document_extraction", "current"
        )
        is None
    )
    runtime = configured_context_runtime(settings(), catalog=ContextRuntimeContributionCatalog())
    assert not runtime.provider_factories and not runtime.federation_cases
    assert not runtime.mutation_adapters and not runtime.mutation_reconciliation_adapters


def test_entry_point_selection_validates_before_loading_and_never_loads_unselected():
    loaded = []

    def point(name):
        return SimpleNamespace(name=name, load=lambda: loaded.append(name) or (lambda: None))

    points = (point("trusted"), point("unselected"))
    assert load_selected_entry_points(points, ()) == ()
    assert not loaded
    with pytest.raises(ValueError, match="not_installed"):
        load_selected_entry_points(points, ("trusted", "missing"))
    with pytest.raises(ValueError, match="duplicate"):
        load_selected_entry_points((*points, point("trusted")), ("trusted",))
    with pytest.raises(ValueError, match="selection_invalid"):
        load_selected_entry_points(points, ("trusted", "trusted"))
    assert not loaded
    assert len(load_selected_entry_points(points, ("trusted",))) == 1
    assert loaded == ["trusted"]


@pytest.mark.parametrize("path", ["/health", "/v1/conversations/{other_id}", "/{anything:path}"])
def test_route_collisions_fail_before_any_attachment(path):
    app = create_app(selected_contributions=())
    router = APIRouter()

    def endpoint():
        return {}

    router.add_api_route(path, endpoint, methods=["GET"])
    before = list(app.routes)
    with pytest.raises(ValueError, match="route_collision"):
        attach_contribution_routes(app, (ApplicationContribution((), routers=(router,)),))
    assert app.routes == before


def test_duplicate_handler_and_invalid_router_fail_before_attachment():
    app = create_app(selected_contributions=())
    with pytest.raises(ValueError, match="handler_duplicate"):
        attach_contribution_routes(
            app,
            (
                ApplicationContribution((), exception_handlers={ValueError: lambda: None}),
                ApplicationContribution((), exception_handlers={ValueError: lambda: None}),
            ),
        )
    with pytest.raises(TypeError, match="router_invalid"):
        attach_contribution_routes(app, (ApplicationContribution((), routers=(object(),)),))


def test_fresh_factory_lifespan_and_error_handlers():
    app = create_app(selected_contributions=())
    app.dependency_overrides[get_settings] = settings
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert (
            client.get("/v1/conversations", headers={"X-Application-Id": "travel"}).status_code
            == 404
        )
        response = client.post("/v1/conversations", json={"title": "x" * 1000})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert not any(
            path.startswith(("/v1/travel", "/v1/domains")) for path in app.openapi()["paths"]
        )


@pytest.mark.parametrize("name", ["travel", "shopping", "finance", "health"])
def test_independent_reference_selection_and_absent_comparison_cannot_be_enabled_by_flag(name):
    from personal_ai_reference_apps.applications import application_contribution
    from personal_ai_reference_apps.domains.service import DomainService

    from personal_ai.decisions.repositories import InMemoryDecisionRepository
    from personal_ai.domains.repositories import InMemoryDomainRepository
    from personal_ai.storage import ResourceNotFoundError

    registry = default_application_registry(
        contribution_catalog=ApplicationContributionCatalog(
            ((name, lambda: application_contribution(name)),)
        )
    )
    assert registry.application_ids == {"personal_ai", name}
    assert set(registry.comparison_modules) == ({name} if name in {"travel", "shopping"} else set())
    service = DomainService(
        settings(decision_enabled=True, travel_enabled=True, shopping_enabled=True),
        InMemoryDecisionRepository(),
        InMemoryDomainRepository(),
        modules=registry.comparison_modules,
    )
    for absent in {"travel", "shopping"} - {name}:
        with pytest.raises(ResourceNotFoundError):
            service.require_domain(absent)


def test_settings_only_selection_is_rejected_and_failed_startup_closes_clients(monkeypatch):
    from personal_ai import main

    monkeypatch.delenv("APPLICATION_CONTRIBUTIONS", raising=False)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings(application_contributions=("travel",))
    closed = []
    monkeypatch.setattr(main, "close_persistence_clients", lambda: closed.append(True))
    with pytest.raises(ValueError, match="requires_process_environment"), TestClient(app):
        pass
    assert closed == [True]


def test_policy_extension_cannot_replace_builtin_provider_policy():
    registry = default_application_registry(contribution_catalog=ApplicationContributionCatalog())
    duplicate = registry.get("personal_ai").context_policy.provider_policies[0]
    with pytest.raises(ValueError, match="providers_must_be_unique"):
        registry.with_contributions(
            ApplicationContribution((), context_policy_extensions={"personal_ai": (duplicate,)})
        )


def test_source_only_reference_selection_does_not_require_destination_or_publish_its_cases():
    from personal_ai_reference_apps.deployment import travel_context

    config = settings(
        travel_federation_enabled=True,
        federation_choice_hmac_key="synthetic-federation-choice-key-32",
    )
    source = travel_context(config)
    assert source.export_adapters  # Real optional factory, no network calls at construction.
    # Travel's sole destination case is Health -> Travel; Travel -> Shopping is unselected.
    runtime = configured_context_runtime(
        config, catalog=ContextRuntimeContributionCatalog((("travel", travel_context),))
    )
    assert set(runtime.provider_factories) == {"federation.health_dietary_to_travel"}
    assert runtime.provider_factories["federation.health_dietary_to_travel"].adapter is None
