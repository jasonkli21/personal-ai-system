"""Brave web-search snippets only. Never fetch source URLs or raw page bodies."""

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock
from time import monotonic

import anyio
import httpx
from pydantic import ValidationError

from personal_ai.agents.research.contracts import ResearchError
from personal_ai.search.contracts import (
    SearchCostProfile,
    SearchDispatch,
    SearchResult,
    SearchRightsAuthorization,
)
from personal_ai.search.planning import SearchOperation, effective_allowed_domains
from personal_ai.usage.async_call import AsyncProviderCall, rate_limit_metadata
from personal_ai.usage.context import current_usage_context
from personal_ai.usage.contracts import UsageAdmissionDenied
from personal_ai.usage.profiles import endpoint_for_operation

_RATE_LOCK = Lock()
_NEXT_REQUEST = 0.0


class SearchError(ResearchError):
    def __init__(
        self, code: str, retryable: bool = False, *,
        usage_invocation_id=None, usage_attempt_id=None,
    ):
        super().__init__(code)
        self.retryable = retryable
        self.usage_invocation_id = usage_invocation_id
        self.usage_attempt_id = usage_attempt_id


class BraveSearchAdapter:
    name = "brave"
    source_origin = "external"
    cost_profile = SearchCostProfile("brave-search-v1", 0.005)
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, settings, transport=None, *, usage_accounting=None):
        self.settings, self.transport = settings, transport
        self.usage_accounting = usage_accounting

    @staticmethod
    def validate_settings(settings):
        if (
            settings.research_storage != "postgres"
            or not settings.research_provider_storage_approved
            or not settings.research_api_key.get_secret_value()
            or not settings.research_brave_prepaid_verified
            or not settings.research_brave_auto_reload_disabled
            or not settings.research_brave_no_paid_balance_verified
            or not settings.research_brave_source_rights_verified
            or not settings.research_brave_account_scope_id.strip()
            or not settings.research_brave_preflight_reference.strip()
            or not settings.research_brave_rights_epoch.strip()
        ):
            raise SearchError("research_configuration_invalid")

    def authorize_snippets(self):
        if (
            not self.settings.research_provider_storage_approved
            or not self.settings.research_brave_prepaid_verified
            or not self.settings.research_brave_auto_reload_disabled
            or not self.settings.research_brave_no_paid_balance_verified
            or not self.settings.research_brave_source_rights_verified
            or not self.settings.research_brave_account_scope_id.strip()
            or not self.settings.research_brave_preflight_reference.strip()
            or not self.settings.research_brave_rights_epoch.strip()
            or not self.settings.research_api_key.get_secret_value()
        ):
            raise SearchError("research_configuration_invalid")
        account_scope = self.settings.research_brave_account_scope_id.strip()
        authority_id = "brave:" + sha256(account_scope.encode()).hexdigest()
        reference = sha256(json.dumps([
            account_scope,
            self.settings.research_brave_preflight_reference,
        ]).encode()).hexdigest()
        return SearchRightsAuthorization(
            provider_id=self.name,
            authority_id=authority_id,
            epoch=self.settings.research_brave_rights_epoch.strip(),
            reference=reference,
        )

    async def search(self, operation: SearchOperation):
        self.authorize_snippets()
        if not isinstance(operation, SearchOperation):
            raise SearchError("search_invalid_request")
        if operation.published_after is not None:
            # Brave's date filter is coarse and cannot honor an exact mandatory bound.
            raise SearchError("search_constraint_unsupported")
        allowed = effective_allowed_domains(operation)
        if (operation.allowed_domains or operation.literal_allowed_domains) and not allowed:
            raise SearchError("search_source_scope_empty")
        if len(allowed) > 1:
            raise SearchError("search_constraint_unsupported")
        terms = [operation.query]
        if allowed:
            terms.append("site:" + allowed[0])
        terms.extend("-site:" + domain for domain in operation.excluded_domains)
        query = " ".join(terms)
        limit = operation.max_results
        remaining = (operation.deadline_at - datetime.now(UTC)).total_seconds()
        timeout = min(self.settings.research_provider_timeout_seconds, remaining)
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 12 or timeout <= 0:
            raise SearchError("search_invalid_request")
        usage_call = None
        if self.usage_accounting is not None:
            endpoint = endpoint_for_operation(
                self.settings,
                provider_id="brave_search",
                model_id="web-search-v1",
                operation="search",
                resolver=getattr(self.usage_accounting, "endpoint_profile_resolver", None),
            )
            scope = current_usage_context()
            usage_call = await AsyncProviderCall.begin(
                self.usage_accounting,
                endpoint,
                operation="search",
                quota_operation=self.cost_profile.quota_operation,
                max_attempts=self.settings.provider_usage_max_attempts_per_request,
                task_id=scope.task_id if scope is not None else "web_research_search",
            )
        outcome, error_code, response_status, rate_limits = "unknown", None, None, None
        try:
            global _NEXT_REQUEST
            with _RATE_LOCK:
                slot = max(monotonic(), _NEXT_REQUEST)
                _NEXT_REQUEST = slot + self.settings.research_min_request_interval_seconds
            await asyncio.sleep(max(0, slot - monotonic()))
            if usage_call is not None:
                await usage_call.reserve()
            async with (
                httpx.AsyncClient(
                    timeout=timeout,
                    transport=self.transport,
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    "GET",
                    self.endpoint,
                    params={"q": query, "count": limit},
                    headers={
                        "X-Subscription-Token": self.settings.research_api_key.get_secret_value(),
                        "Accept": "application/json",
                        "User-Agent": "personal-ai-research/1",
                    },
                ) as response,
            ):
                response_status = response.status_code
                rate_limits = rate_limit_metadata(response.headers)
                if response_status == 429:
                    outcome, error_code = "rate_limited", "search_quota"
                    raise SearchError("search_quota")
                if response_status >= 500:
                    outcome, error_code = "server_error", "search_unavailable"
                    raise SearchError("search_unavailable", retryable=True)
                if response_status != 200:
                    outcome, error_code = "rejected", "search_rejected"
                    raise SearchError("search_rejected")
                if "application/json" not in response.headers.get("content-type", ""):
                    outcome, error_code = "failure", "search_invalid_response"
                    raise SearchError("search_invalid_response")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(content) + len(chunk) > self.settings.research_max_response_bytes:
                        outcome, error_code = "failure", "search_response_oversized"
                        raise SearchError("search_response_oversized")
                    content.extend(chunk)
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise TypeError("invalid response")
            web = payload.get("web", {})
            if not isinstance(web, dict) or not isinstance(web.get("results", []), list):
                raise TypeError("invalid response")
            results = []
            for value in web.get("results", [])[:limit]:
                if not isinstance(value, dict):
                    raise TypeError("invalid result")
                results.append(
                    SearchResult(
                        url=value["url"],
                        title=value.get("title"),
                        text=value.get("description", ""),
                    )
                )
            outcome = "success"
            return SearchDispatch(
                tuple(results),
                usage_call.invocation.invocation_id if usage_call is not None else None,
                usage_call.attempt.attempt_id
                if usage_call is not None and usage_call.attempt is not None
                else None,
            )
        except UsageAdmissionDenied as error:
            error_code = error.code
            outcome = "rate_limited" if error.code in {
                "provider_quota_exhausted", "provider_endpoint_cooling_down"
            } else "rejected"
            raise SearchError(
                "search_quota" if outcome == "rate_limited" else "search_unavailable",
                # A P19 admission denial has no trustworthy reset horizon here;
                # repeated logical attempts would just recreate a denied call.
                retryable=False,
                usage_invocation_id=(usage_call.invocation.invocation_id if usage_call else None),
                usage_attempt_id=(usage_call.attempt.attempt_id if usage_call and usage_call.attempt else None),
            ) from None
        except SearchError as error:
            error_code = error.code
            error.usage_invocation_id = (
                usage_call.invocation.invocation_id if usage_call is not None else None
            )
            error.usage_attempt_id = (
                usage_call.attempt.attempt_id
                if usage_call is not None and usage_call.attempt is not None else None
            )
            if outcome == "unknown":
                outcome = (
                    "rate_limited" if response_status == 429
                    else "server_error" if response_status is not None and response_status >= 500
                    else "rejected" if response_status is not None and response_status >= 400
                    else "failure"
                )
            raise
        except httpx.TimeoutException as error:
            outcome, error_code = "timeout", "search_timeout"
            raise SearchError("search_timeout") from error
        except TimeoutError as error:
            outcome, error_code = "timeout", "search_timeout"
            raise SearchError("search_timeout") from error
        except httpx.TransportError as error:
            outcome, error_code = "unknown", "search_unavailable"
            raise SearchError("search_unavailable") from error
        except (ValueError, KeyError, TypeError, ValidationError) as error:
            outcome, error_code = "failure", "search_invalid_response"
            raise SearchError("search_invalid_response") from error
        finally:
            if usage_call is not None:
                with anyio.CancelScope(shield=True):
                    await usage_call.finish(
                        outcome,
                        http_status=response_status,
                        error_code=error_code,
                        rate_limits=rate_limits,
                    )
