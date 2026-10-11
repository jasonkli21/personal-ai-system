"""Route-specific provider admission and kill-switch policy."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.safeguards import SafeguardStore
from personal_ai.settings import Settings


def provider_reservation(request: Request, settings: Settings) -> tuple[int, int]:
    """Estimate request usage; this is not accounting for every provider RPC.

    Token counting, summary refresh, embeddings and worker activity can make
    additional calls. See the operational review before treating these counters
    as a provider-spend ceiling.
    """
    if request.method != "POST":
        return (0, 0)
    path = request.url.path
    uses_external = False
    if path.startswith("/v1/conversations/") and path.endswith(
        ("/messages", "/regenerate", "/edit-and-retry")
    ):
        calls = 2 + int(settings.memory_enabled) + int(settings.memory_extraction_enabled)
        uses_external = settings.ai_provider != "fake"
        tokens = settings.max_context_tokens
    elif path.startswith("/v1/research/") and path.endswith("/run"):
        calls = settings.research_max_queries * settings.research_attempt_limit + 2
        tokens = settings.research_max_evidence_context_tokens
        uses_external = settings.research_search_adapter != "fake" or settings.ai_provider != "fake"
    elif path == "/v1/research/iterative" or (
        path.endswith("/resume") and path.startswith("/v1/research/iterative/runs/")
    ):
        calls = settings.iterative_max_queries * settings.iterative_max_iterations + 2
        tokens = settings.iterative_max_tokens
        uses_external = settings.research_search_adapter != "fake" or settings.ai_provider != "fake"
    elif path.startswith("/v1/domains/") and path.endswith("/lookup"):
        calls, tokens = 1, 0
        uses_external = (
            path.startswith("/v1/domains/travel/") and settings.travel_places_adapter != "fake"
        ) or (
            path.startswith("/v1/domains/shopping/")
            and settings.shopping_products_adapter != "fake"
        )
    elif path == "/v1/travel/itinerary-proposals":
        calls = 1
        tokens = settings.itinerary_proposal_max_input_tokens
        uses_external = settings.itinerary_proposal_generator == "gemini"
    elif path == "/v1/travel/booking-extractions":
        calls = 1
        tokens = settings.booking_extraction_max_input_tokens
        uses_external = settings.booking_extraction_generator == "gemini"
    else:
        return (0, 0)
    return (calls, tokens) if uses_external else (0, 0)


def provider_switch_is_on(request: Request, settings: Settings) -> bool:
    path = request.url.path
    method = request.method
    if (
        settings.chat_kill_switch_enabled
        and path.startswith("/v1/conversations/")
        and method in {"POST", "PUT", "PATCH", "DELETE"}
    ):
        return True
    if (
        settings.research_kill_switch_enabled
        and path.startswith(("/v1/research", "/v1/iterative-research"))
        and method in {"POST", "PUT", "PATCH"}
    ):
        return True
    return settings.external_providers_kill_switch_enabled and provider_reservation(
        request, settings
    ) != (0, 0)


class RequestAdmission:
    """Apply request rate limits and route-specific provider reservations."""

    def __init__(self, store_for_request: Callable[[Request, Settings], SafeguardStore]) -> None:
        self._store_for_request = store_for_request

    def check_request(
        self,
        request: Request,
        settings: Settings,
        principal: AuthenticatedPrincipal,
    ) -> None:
        store = self._store_for_request(request, settings)
        store.consume_request(principal.owner_id, settings.api_rate_limit_per_minute)
        calls, tokens = provider_reservation(request, settings)
        if calls or tokens:
            store.reserve_daily(
                principal.owner_id,
                calls,
                tokens,
                settings.provider_calls_per_day_limit,
                settings.input_tokens_per_day_limit,
            )
