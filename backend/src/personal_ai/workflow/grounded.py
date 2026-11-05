"""Trusted fixture source and continuation ports for the canonical workflow."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid5

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.context.authorization import authorize_base_disclosure
from personal_ai.context.providers import ContextProviderCoordinator, ContextProviderError
from personal_ai.contracts.execution import ContinuationRequest, continuation_message_id
from personal_ai.reasoning.grounded import STEP_MS, intersect
from personal_ai.reasoning.grounded_receipts import EvidenceDependency
from personal_ai.reasoning.orchestration import Stop, digest
from personal_ai.reasoning.policy import EFFORTS
from personal_ai.reasoning.proposed_request import Budget, ReasoningRequest
from personal_ai.retrieval.context import (
    PROVIDER_ID,
    RetrievalContextAuthority,
    RetrievalContextProvider,
    context_selection,
    excerpt_context_item,
)
from personal_ai.retrieval.contracts import RetrievalOutcome, RetrievalQuery, item_from_quote
from personal_ai.retrieval.installation import local_rights_authority_id
from personal_ai.workflow.reasoning import ENDPOINT_DIGEST, infer_fixture

FIXTURE_LICENSE = "public-synthetic-fixture-v1"
PURPOSE = "synthetic_grounded_reasoning"


@dataclass(frozen=True, slots=True)
class GroundedHost:
    context: ApplicationContextRequest
    current_ceilings: Callable
    # A trusted host must affirm this exact snapshot for this scope and destination.
    authorize_fixture: Callable

    def check(self, settings, scope):
        if (
            scope is not self.context.scope
            or settings.app_environment not in {"local", "test"}
            or settings.inference_profile != "offline_fake"
            or settings.inference_cost_mode != "offline_fake"
            or settings.external_providers_kill_switch_enabled
            or settings.research_kill_switch_enabled
            or not settings.retrieval_context_enabled
        ):
            raise Stop("policy_denied")
        authorize_base_disclosure(self.context)

    def ceilings(self, settings):
        ceilings = self.current_ceilings()
        endpoint = ceilings.endpoint
        output = min(endpoint.limits.output_bytes, settings.max_response_tokens)
        max_input = settings.max_context_tokens - settings.context_safety_margin_tokens - output
        return ceilings.model_copy(update={"endpoint": endpoint.model_copy(update={
            "limits": endpoint.limits.model_copy(update={
                "output_bytes": output,
                "input_bytes": min(endpoint.limits.input_bytes, max(0, max_input)),
            }),
        })})

    def check_plan(self, plan, settings):
        limits, effort = intersect(self.ceilings(settings), plan.limits, plan.requested_effort)
        if (
            plan.endpoint_digest != ENDPOINT_DIGEST or limits != plan.limits
            or EFFORTS.index(plan.effort) > EFFORTS.index(effort)
            or min(settings.request_timeout_seconds, settings.retrieval_timeout_seconds) * 1000 < STEP_MS
        ):
            raise Stop("policy_denied")

    def authority(self, retrieval):
        return RetrievalContextAuthority(
            retrieval.settings, scope=self.context.scope, authority=retrieval.request_authority,
            context=self.context, current_settings=retrieval.current_settings,
        )

    def authorize_snapshot(self, snapshot, authority, task):
        scope = self.context.scope
        now = datetime.now(UTC)
        if (
            self.authorize_fixture(scope, PURPOSE, snapshot.digest, ENDPOINT_DIGEST, task) is not True
            or snapshot.installation.issuer_id is None
            or any(
                doc.sensitivity != "public" or doc.license != FIXTURE_LICENSE
                or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", doc.revision)
                or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", doc.rights_epoch)
                for doc in snapshot.installation.documents
            )
            or not any(doc.model_context_allowed and doc.allows(scope, now) for doc in snapshot.installation.documents)
            or authority.snapshot(scope).digest != snapshot.digest
        ):
            raise Stop("source_changed")


def evidence_dependency(snapshot, item):
    return EvidenceDependency(
        source_id=item.source_id, source_revision=item.source_revision,
        issuer_id=snapshot.installation.issuer_id, rights_authority_id=item.rights_authority_id,
        rights_epoch=item.rights_epoch, rights_reference_digest=digest(item.rights_reference),
        passage_id=item.passage_id, citation_id=item.citation_id,
        content_fingerprint=item.content_fingerprint,
        observed_at=item.observed_at, expires_at=item.expires_at,
    )


def require_items(snapshot, items, scope, max_age):
    """Re-derive complete provenance from the installed source and exact span."""
    now = datetime.now(UTC)
    docs = {doc.source_id: doc for doc in snapshot.installation.documents}
    for item in items:
        doc = docs.get(item.source_id)
        if (
            doc is None or not doc.allows(scope, now) or not doc.model_context_allowed
            or item.expires_at <= now or item.end > len(doc.text)
            or item.end <= item.start
        ):
            raise Stop("source_changed")
        expected = item_from_quote(
            source_id=doc.source_id, revision=doc.revision, quote=doc.text[item.start:item.end],
            start=item.start, origin="local", provider="local_lexical_v1",
            quote_basis="literal_document", revision_basis="operator_revision",
            rights_authority_id=local_rights_authority_id(snapshot.installation.issuer_id, scope, doc.source_id),
            rights_epoch=doc.rights_epoch, rights_reference=doc.rights_reference,
            license=doc.license, sensitivity=doc.sensitivity, title=doc.title,
            observed_at=doc.observed_at, published_at=doc.published_at,
            expires_at=min(doc.expires_at, doc.observed_at + timedelta(seconds=max_age)),
            freshness_basis="publication" if doc.published_at else "observation_only",
        )
        if expected != item:
            raise Stop("source_changed")


def validate_retrieval(outcome, query, snapshot, scope):
    outcome = RetrievalOutcome.model_validate_json(outcome.model_dump_json())
    items = outcome.items
    if (
        outcome.idempotency_key != query.idempotency_key
        or outcome.usage_invocation_id is not None or outcome.usage_attempt_id is not None
        or len(items) > query.max_items or len({item.citation_id for item in items}) != len(items)
        or sum(len(item.quote.encode()) for item in items) != outcome.quote_bytes
        or outcome.quote_bytes > query.max_quote_bytes
        or sum(len(item.model_dump_json().encode()) for item in items) != outcome.token_upper_bound
        or outcome.token_upper_bound > query.max_tokens
    ):
        raise Stop("internal_failure")
    require_items(snapshot, items, scope, query.max_age_seconds)
    return items


def retrieval_query(run_id, plan, step, remaining, *, field=None):
    limits = plan.limits
    item_count, quote_bytes, token_bound = remaining
    if field is None:
        # Reserve a fair share of evidence space for a possible focused read.
        divisor = limits.retrieval_calls
        item_count = max(1, item_count // divisor)
        quote_bytes = max(64, quote_bytes // divisor)
        token_bound = max(64, token_bound // divisor)
    return RetrievalQuery(
        idempotency_key=uuid5(run_id, step),
        query=f"{plan.task.subject}_{field or 'overview'}",
        sources=("local",), purpose="interactive_retrieval",
        max_items=item_count, max_quote_bytes=quote_bytes, max_tokens=token_bound,
        max_age_seconds=plan.task.max_age_seconds,
    )


def continuation(run_id, plan, context):
    child_key = uuid5(run_id, "synthesis")
    request = ContinuationRequest(
        idempotency_key=child_key, content=plan.task.model_dump_json(),
        reasoning=ReasoningRequest(
            schema_version="reasoning-request-v1", effort="low",
            budget=Budget(
                max_model_calls=1, max_concurrency=1, max_elapsed_seconds=STEP_MS // 1000,
                max_input_tokens=plan.limits.input_bytes, max_output_tokens=plan.limits.output_bytes,
            ),
        ),
    )
    scope = context.scope
    return request, continuation_message_id(run_id, scope.owner_id, scope, child_key)


class PinnedExcerpts:
    """Provide exact in-claim excerpts to the builder without a second search."""

    spec = RetrievalContextProvider.spec

    def __init__(self, items, snapshot, scope, guard):
        self.items, self.snapshot, self.scope, self.guard = items, snapshot, scope, guard

    def validate_selection(self, selection, inputs):
        self.guard()
        if inputs.scope != self.scope or inputs.pending_message is None:
            raise ContextProviderError("grounded_context_unavailable")

    def fetch(self, selection, scope, *, deadline):
        self.guard()
        if scope != self.scope or monotonic() >= deadline:
            raise ContextProviderError("grounded_context_unavailable")
        return tuple(excerpt_context_item(item, scope, self.snapshot.digest) for item in self.items)


async def infer(run_id, host, settings, plan, request, message_id, attempt, guard, snapshot, items, authority):
    provider = PinnedExcerpts(items, snapshot, host.context.scope, guard)
    return await infer_fixture(
        run_id, host.context, settings, request, message_id, attempt, guard,
        input_bytes=plan.limits.input_bytes, output_bytes=plan.limits.output_bytes,
        selection=context_selection(),
        coordinator=ContextProviderCoordinator({PROVIDER_ID: provider}), revalidator=authority,
    )
