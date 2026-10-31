"""Existing search registrations, literal snippet attribution and P19 admission."""

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid5

from personal_ai.agents.research.contracts import ResearchError
from personal_ai.llm.disclosure import bind_disclosure_guard
from personal_ai.retrieval.contracts import item_from_quote
from personal_ai.search.contracts import SearchDispatch, normalize_rights_authorization
from personal_ai.search.planning import (
    SearchOperation,
    domains_from_question,
    effective_allowed_domains,
    source_allowed,
)
from personal_ai.search.policy import SnippetExtractor, canonical_url
from personal_ai.search.runtime import compose_search_adapter
from personal_ai.usage.context import bind_usage_task


class ExternalBridge:
    @staticmethod
    def configuration_digest(settings):
        values = settings.model_dump(mode="json")
        policy = {k: v for k, v in values.items() if k.startswith(("research_", "retrieval_"))}
        policy["credential_digest"] = sha256(
            settings.research_api_key.get_secret_value().encode()
        ).hexdigest()
        return sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()

    def __init__(self, settings, usage_factory, *, registrations=None):
        self.settings = settings
        self.initial_configuration = self.configuration_digest(settings)
        self.adapter = compose_search_adapter(settings, usage_factory, registrations=registrations)
        # Non-synthetic implementations must use the canonical P19 accounting path.
        if (
            self.adapter.source_origin != "synthetic"
            and getattr(self.adapter, "usage_accounting", None) is None
        ):
            raise ValueError("external_accounting_required")
        self.initial_rights = self.rights()
        if (
            self.initial_rights is None
            or self.initial_rights.provider_id != self.adapter.name
            or self.initial_rights.epoch == "legacy-v1"
            or any(
                not isinstance(value, str) or not value or len(value) > limit
                for value, limit in (
                    (self.initial_rights.authority_id, 200),
                    (self.initial_rights.epoch, 100),
                    (self.initial_rights.reference, 200),
                )
            )
        ):
            raise ValueError("external_rights_required")

    def rights(self):
        return normalize_rights_authorization(self.adapter.authorize_snippets(), self.adapter.name)

    def current(self, settings=None):
        try:
            return (
                self.configuration_digest(settings or self.settings) == self.initial_configuration
                and self.rights() == self.initial_rights
            )
        except Exception:  # noqa: BLE001 - unprovable rights deny
            return False

    def prepare(self, query, deadline):
        """Build and validate deterministic request constraints before journaling."""
        literal_allowed, literal_excluded = domains_from_question(query.query)
        operation = SearchOperation(
            operation_id=sha256(query.model_dump_json().encode()).hexdigest(),
            query_id=query.idempotency_key,
            query=query.query,
            original_question=query.query,
            strategy_id="retrieval-v1",
            strategy_version=1,
            strategy_reason="literal",
            plan_identity=sha256(query.model_dump_json().encode()).hexdigest(),
            allowed_domains=query.allowed_domains,
            literal_allowed_domains=literal_allowed,
            excluded_domains=tuple(dict.fromkeys((*query.excluded_domains, *literal_excluded))),
            published_after=query.published_after,
            max_results=query.max_items,
            deadline_at=deadline,
        )
        allowed = effective_allowed_domains(operation)
        if (query.allowed_domains or literal_allowed) and not allowed:
            return None
        if not self.current():
            raise ValueError("source_authority_changed")
        preflight = getattr(self.adapter, "preflight", None)
        if callable(preflight):
            preflight(operation)
        return operation

    async def search(self, query, deadline, guard, namespace, *, operation=None):
        operation = operation or self.prepare(query, deadline)
        if operation is None:
            return (), (), None
        guard()
        with (
            bind_disclosure_guard(guard),
            bind_usage_task(
                "retrieval_query",
                invocation_id=uuid5(query.idempotency_key, "retrieval-search:" + namespace),
                send_number=1,
            ),
        ):
            dispatch = await self.adapter.search(operation)
        if not isinstance(dispatch, SearchDispatch) or len(dispatch.results) > query.max_items:
            raise ValueError("invalid_dispatch")
        if self.adapter.source_origin == "external" and (
            dispatch.usage_attempt_id is None or dispatch.usage_invocation_id is None
        ):
            raise ValueError("external_attempt_identity_required")
        allowed = effective_allowed_domains(operation)
        items, reasons = [], []
        now = datetime.now(UTC)
        rights = self.initial_rights
        for result in dispatch.results:
            try:
                url = canonical_url(result.url)
                if not source_allowed(url, allowed, operation.excluded_domains):
                    reasons.append("invalid_source")
                    continue
                quote = SnippetExtractor().extract(result.text)
                if not quote:
                    continue
                if query.published_after and (
                    result.published_at is None or result.published_at < query.published_after
                ):
                    reasons.append("freshness_unverified")
                    continue
                source_id = "web_" + sha256(url.encode()).hexdigest()
                items.append(
                    item_from_quote(
                        source_id=source_id,
                        revision=result.source_revision or sha256(quote.encode()).hexdigest(),
                        quote=quote,
                        origin=self.adapter.source_origin,
                        url=url,
                        provider=self.adapter.name,
                        quote_basis="normalized_provider_snippet",
                        revision_basis="provider_revision"
                        if result.source_revision
                        else "observation_hash",
                        rights_authority_id=rights.authority_id,
                        title=result.title or url,
                        rights_epoch=rights.epoch,
                        rights_reference=rights.reference,
                        license="provider-approved-snippet",
                        sensitivity="public",
                        observed_at=now,
                        published_at=result.published_at,
                        expires_at=now + timedelta(seconds=min(query.max_age_seconds, 3600)),
                        freshness_basis="publication"
                        if result.published_at
                        else "observation_only",
                    )
                )
            except (ResearchError, ValueError, TypeError):
                reasons.append("invalid_source")
        return tuple(items), tuple(dict.fromkeys(reasons)), dispatch
