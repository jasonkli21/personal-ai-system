"""Installed adapter composition shared by single-pass and iterative research."""

from collections.abc import Callable
from dataclasses import dataclass, field

from personal_ai.agents.research.contracts import ResearchError
from personal_ai.search.contracts import FakeSearchAdapter, SearchCostProfile, SearchResult
from personal_ai.search.providers.brave import BraveSearchAdapter


@dataclass(frozen=True)
class SearchAdapterRegistration:
    factory: Callable
    synthetic: bool = False
    operations: tuple[str, ...] = ("search",)
    cost_profile: SearchCostProfile = field(
        default_factory=lambda: SearchCostProfile("external-search-v1", 0.005)
    )
    settings_validator: Callable | None = None
    endpoint_profile_factory: Callable | None = None
    cost_profile_factory: Callable | None = None


def _synthetic(settings, usage):
    return FakeSearchAdapter((SearchResult(
        url="https://example.org/synthetic-research",
        title="Synthetic fixture",
        text="This is synthetic research evidence for an offline demo. "
             "It makes no claim about the real world.",
    ),))


def _brave_endpoint_profile(settings):
    from personal_ai.routing.configured import _brave_search_profile

    return _brave_search_profile(settings)


def _brave_cost_profile(settings):
    return SearchCostProfile(
        "brave-search-v1", float(settings.iterative_search_cost_usd)
    )


SEARCH_ADAPTERS = {
    "fake": SearchAdapterRegistration(
        _synthetic,
        synthetic=True,
        cost_profile=SearchCostProfile("synthetic-zero-cost-v1", 0.0),
    ),
    "brave": SearchAdapterRegistration(
        lambda settings, usage: BraveSearchAdapter(settings, usage_accounting=usage),
        settings_validator=BraveSearchAdapter.validate_settings,
        endpoint_profile_factory=_brave_endpoint_profile,
        cost_profile_factory=_brave_cost_profile,
    ),
}


def validate_search_settings(settings, *, registrations=None):
    catalog = SEARCH_ADAPTERS if registrations is None else registrations
    registration = catalog.get(settings.research_search_adapter)
    if registration is None or registration.operations != ("search",):
        raise ResearchError("research_configuration_invalid")
    if registration.settings_validator is not None:
        registration.settings_validator(settings)


def compose_search_adapter(settings, usage_factory, *, registrations=None):
    """Compose only the registered search implementation and its policy profile."""
    catalog = SEARCH_ADAPTERS if registrations is None else registrations
    registration = catalog.get(settings.research_search_adapter)
    if registration is None or registration.operations != ("search",):
        raise ResearchError("research_configuration_invalid")
    validate_search_settings(settings, registrations=catalog)
    usage = None if registration.synthetic else usage_factory()
    adapter = registration.factory(settings, usage)
    expected_origin = "synthetic" if registration.synthetic else "external"
    if not callable(getattr(adapter, "search", None)) or not callable(
        getattr(adapter, "authorize_snippets", None)
    ) or (
        getattr(adapter, "source_origin", None) != expected_origin
    ):
        raise ResearchError("research_configuration_invalid")
    cost_profile = (
        registration.cost_profile_factory(settings)
        if registration.cost_profile_factory is not None
        else registration.cost_profile
    )
    try:
        adapter.cost_profile = cost_profile
    except (AttributeError, TypeError):
        if getattr(adapter, "cost_profile", None) != cost_profile:
            raise ResearchError("research_configuration_invalid") from None
    if not isinstance(getattr(adapter, "cost_profile", None), SearchCostProfile):
        raise ResearchError("research_configuration_invalid")
    return adapter
