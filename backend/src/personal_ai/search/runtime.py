"""Installed adapter composition shared by single-pass and iterative research."""

from dataclasses import dataclass
from uuid import uuid5

from personal_ai.agents.research.contracts import ResearchError
from personal_ai.search.contracts import FakeSearchAdapter, SearchResult
from personal_ai.search.providers.brave import BraveSearchAdapter


@dataclass(frozen=True)
class SearchAdapterRegistration:
    factory: object
    synthetic: bool = False
    operations: tuple[str, ...] = ("search",)


def _synthetic(settings, usage):
    return FakeSearchAdapter((SearchResult(
        url="https://example.org/synthetic-research",
        title="Synthetic fixture",
        text="This is synthetic research evidence for an offline demo. "
             "It makes no claim about the real world.",
    ),))


SEARCH_ADAPTERS = {
    "fake": SearchAdapterRegistration(_synthetic, synthetic=True),
    "brave": SearchAdapterRegistration(
        lambda settings, usage: BraveSearchAdapter(settings, usage_accounting=usage)
    ),
}


def search_usage_links(adapter, query_id, send_number):
    """References only; P19 remains authoritative for admission and settlement."""
    if getattr(adapter, "usage_accounting", None) is None:
        return {}
    invocation_id = uuid5(query_id, "provider-usage-search")
    return {"usage_invocation_id": invocation_id,
            "usage_attempt_id": uuid5(invocation_id, f"provider-attempt:{send_number}")}


def compose_research_clients(settings, usage_factory, *, registrations=None):
    from personal_ai.context.tokens import EstimatedTokenCounter
    from personal_ai.llm.context import GeminiTokenCounter
    from personal_ai.llm.fake import FakeResearchLLMClient
    from personal_ai.llm.gemini import GeminiLLMClient

    catalog = SEARCH_ADAPTERS if registrations is None else registrations
    registration = catalog.get(settings.research_search_adapter)
    if registration is None or registration.operations != ("search",):
        raise ResearchError("research_configuration_invalid")
    usage = None if registration.synthetic else usage_factory()
    adapter = registration.factory(settings, usage)
    if not callable(getattr(adapter, "search", None)) or not callable(
        getattr(adapter, "authorize_snippets", None)
    ) or (
        getattr(adapter, "source_origin", None) not in {"synthetic", "external"}
    ):
        raise ResearchError("research_configuration_invalid")
    if registration.synthetic:
        return adapter, EstimatedTokenCounter(), FakeResearchLLMClient()
    return adapter, GeminiTokenCounter(settings, usage_accounting=usage), GeminiLLMClient(
        settings, usage_accounting=usage
    )
