"""Closed operator composition over canonical inference, endpoint and usage ports.

No routing, retries, dynamic imports, paid admission or additional ledger lives here.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from time import monotonic

import anyio

from personal_ai.llm.client import (
    BoundedTextStream,
    ProviderCapabilities,
    ProviderIdentity,
    TokenCount,
)
from personal_ai.llm.disclosure import revalidate_disclosure
from personal_ai.llm.errors import LLMInvalidConfigurationError, LLMInvalidRequestError
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.llm.litellm.profiles import _validate_inference_context
from personal_ai.llm.preparation import prepare_bounded_input, require_matching_endpoint
from personal_ai.routing.contracts import CountRequirement, EndpointCandidateRequirements
from personal_ai.routing.registry import EndpointRegistryError
from personal_ai.usage.accounting import unit_reservations

PROFILE_VERSION = "pi3-execution-v1"
# Code-reviewed installed factories only. Neither requests nor manifests extend this set.
PROFILES = frozenset({"offline_fake", "offline_fake_alt", "legacy_gemini"})
_send_authority: ContextVar[tuple | None] = ContextVar("pi3_send_authority", default=None)


def schema_identity(schema):
    if schema is None:
        return None
    return "sha256:" + sha256(json.dumps(
        schema, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()).hexdigest()


class LocalFakeCounter:
    """Exact bytes of the local fake's declared serialization; NOT vendor tokens."""

    requires_inference_context = True
    count_confidence = "authoritative"
    capabilities = ProviderCapabilities(frozenset({"token_counting"}))

    def __init__(self, identity):
        self.identity = identity

    def count(self, messages, *, response_schema=None, inference_context=None):
        _validate_inference_context(inference_context)
        wire = json.dumps({
            "messages": [(m.role, m.content) for m in messages],
            "schema": response_schema,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return TokenCount(
            len(wire.encode()), "provider", self.identity.provider_id,
            self.identity.model_id, self.identity.serializer_id, "authoritative",
        )


class LocalFakeGeneration(FakeLLMClient):
    requires_inference_context = True


class SendAccounting:
    """Recheck disclosure at physical reservation, then use the existing P19 ledger."""

    def __init__(self, ledger):
        self.ledger = ledger
        self.endpoint_profile_resolver = ledger.endpoint_profile_resolver

    def __getattr__(self, name):
        return getattr(self.ledger, name)

    def reserve_attempt(self, invocation, attempt, *, max_attempts):
        authority = _send_authority.get()
        if authority is None:
            raise LLMInvalidRequestError("inference send authority is required")
        admission, requirements = authority
        revalidate_disclosure()
        current = admission.check(requirements)
        if (
            invocation.endpoint.endpoint_profile_id != current.endpoint_profile_id
            or invocation.endpoint.profile_version != current.profile_version
            or invocation.operation not in requirements.required_capabilities
        ):
            raise LLMInvalidRequestError("inference send authority mismatch")
        # Reserve the prepared bound, not the transport's character estimate. Count
        # operations reserve the entire approved input ceiling. Unknown outcomes
        # retain P19's existing conservative reservations.
        units = unit_reservations(
            input_tokens=requirements.input_tokens,
            output_tokens=requirements.output_tokens or 0,
        )
        attempt = replace(
            attempt, reservation_units=units,
            reserved_tokens=(requirements.input_tokens or 0) + (requirements.output_tokens or 0),
        )
        return self.ledger.reserve_attempt(invocation, attempt, max_attempts=max_attempts)


class Admission:
    def __init__(self, profile, usage, *, credential_getter=None, credential_fingerprint=None):
        self.profile = profile
        self.usage = usage
        self.bound = None
        self.credential_getter = credential_getter
        self.credential_fingerprint = credential_fingerprint

    def check(self, requirements):
        # A mutable Settings object can be rotated after composition. Do not
        # allow the endpoint facts captured for one credential to authorize a
        # later physical count/send using another value. Keep only a one-way
        # process-local fingerprint; never persist or log it.
        if self.credential_getter is not None:
            current_secret = self.credential_getter()
            current_fingerprint = sha256(current_secret.encode()).digest()
            if (
                not current_secret
                or self.credential_fingerprint is None
                or current_fingerprint != self.credential_fingerprint
            ):
                raise LLMInvalidConfigurationError("inference credential changed; refresh admission")
        if self.usage is None or self.usage.endpoint_profile_resolver is None:
            raise LLMInvalidConfigurationError("canonical inference accounting is required")
        registry = self.usage.endpoint_profile_resolver.endpoint_registry
        profiles = registry.refresh().profiles
        current = next((p for p in profiles if p.endpoint_profile_id == self.profile.endpoint_profile_id), None)
        if current is None or current.model_dump(exclude={"profile_version"}) != self.profile.model_dump(
            exclude={"profile_version"}
        ) or (self.bound is not None and current.ref != self.bound):
            raise LLMInvalidConfigurationError("inference endpoint policy changed")
        try:
            registry.revalidate_selected(current.ref, requirements)
        except EndpointRegistryError:
            raise LLMInvalidConfigurationError("inference endpoint is not admissible") from None
        now = datetime.now(UTC)
        attestation = current.strict_free_attestation
        if (
            current.data_use_policy.status != "approved"
            or not current.data_use_policy.policy_reference
            or attestation is None
            or attestation.verified_at is None or attestation.valid_until is None
            or not attestation.verified_at <= now < attestation.valid_until
        ):
            raise LLMInvalidConfigurationError("current inference preflight is required")
        self.bound = current.ref
        return current

    @contextmanager
    def authorize(self, requirements):
        self.check(requirements)
        token = _send_authority.set((self, requirements))
        try:
            yield
        finally:
            _send_authority.reset(token)


class SelectedCounter:
    requires_inference_context = True
    count_confidence = "authoritative"

    def __init__(self, counter, admission=None):
        self.delegate = counter
        self.identity = counter.identity
        self.capabilities = counter.capabilities
        self.admission = admission

    def count(self, messages, *, response_schema=None, inference_context=None):
        return self.count_with_timeout(
            messages, None, response_schema=response_schema, inference_context=inference_context
        )

    def count_with_timeout(self, messages, timeout_seconds, *, response_schema=None, inference_context=None):
        _validate_inference_context(inference_context)
        revalidate_disclosure()
        self.capabilities.require("token_counting")
        kwargs = {"response_schema": response_schema, "inference_context": inference_context}
        if self.admission is None:
            return self.delegate.count(messages, **kwargs)
        profile = self.admission.profile
        schema_id = schema_identity(response_schema)
        requirements = EndpointCandidateRequirements(
            sensitivity=inference_context.effective_sensitivity,
            required_capabilities=frozenset({"token_counting"}),
            input_tokens=profile.context_limit_tokens,
            count=CountRequirement(structured_schema_id=schema_id),
        )
        with self.admission.authorize(requirements):
            return self.delegate.count_with_timeout(messages, timeout_seconds, **kwargs)


class SelectedGeneration:
    """One chosen backend, exact bounded preparation, zero fallback."""

    requires_inference_context = True

    def __init__(self, generator, counter, settings, admission=None):
        self.delegate, self.counter, self.settings = generator, counter, settings
        self.identity, self.capabilities = generator.identity, generator.capabilities
        self.admission = admission
        require_matching_endpoint(self, counter)

    def _prepare(self, messages, operation, max_output_tokens, timeout_seconds, inference_context, schema=None):
        _validate_inference_context(inference_context)
        self.capabilities.require(operation)
        if max_output_tokens < 1 or timeout_seconds <= 0:
            raise LLMInvalidRequestError("generation bounds are invalid")
        profile = self.admission.profile if self.admission else None
        if profile and (profile.context_limit_tokens is None or profile.max_output_tokens is None):
            raise LLMInvalidConfigurationError("endpoint token limits are required")
        input_limit = min(
            self.settings.max_context_tokens,
            profile.context_limit_tokens if profile else self.settings.max_context_tokens,
        ) - max_output_tokens - self.settings.context_safety_margin_tokens
        if input_limit < 1 or (profile and max_output_tokens > profile.max_output_tokens):
            raise LLMInvalidRequestError("generation bounds exceed endpoint limits")
        # Check generation permission before disclosing even to its counter.
        requirements = EndpointCandidateRequirements(
            sensitivity=inference_context.effective_sensitivity,
            required_capabilities=frozenset({operation}),
            input_tokens=max(1, input_limit), output_tokens=max_output_tokens,
            structured_schema_id=schema_identity(schema),
        )
        if self.admission:
            self.admission.check(requirements)
        prepared = prepare_bounded_input(
            messages, self.counter, generator=self, input_limit=input_limit,
            timeout_seconds=timeout_seconds, response_schema=schema,
            inference_context=inference_context,
        )
        return requirements.model_copy(update={"input_tokens": prepared.token_count.tokens})

    async def stream_events(self, messages, *, max_output_tokens, timeout_seconds, inference_context=None):
        start = monotonic()
        requirements = await anyio.to_thread.run_sync(partial(
            self._prepare, messages, "streaming", max_output_tokens, timeout_seconds, inference_context
        ))
        revalidate_disclosure()
        iterator = self.delegate.stream_events(
            messages, max_output_tokens=max_output_tokens,
            timeout_seconds=max(0, timeout_seconds - (monotonic() - start)),
            inference_context=inference_context,
        )
        try:
            while True:
                try:
                    # Do not leave a ContextVar binding suspended across yield.
                    if self.admission:
                        with self.admission.authorize(requirements):
                            event = await anext(iterator)
                    else:
                        event = await anext(iterator)
                except StopAsyncIteration:
                    break
                yield event
        finally:
            await iterator.aclose()

    def stream_bounded(self, messages, **kwargs):
        return BoundedTextStream(self.stream_events(messages, **kwargs))

    def stream(self, messages, *, inference_context=None):
        return self.stream_bounded(
            messages, max_output_tokens=self.settings.max_response_tokens,
            timeout_seconds=self.settings.request_timeout_seconds, inference_context=inference_context,
        )

    def _complete(self, messages, *, max_output_tokens, timeout_seconds, inference_context=None, response_schema=None):
        start = monotonic()
        operation = "structured_generation" if response_schema is not None else "bounded_generation"
        requirements = self._prepare(
            messages, operation, max_output_tokens, timeout_seconds, inference_context, response_schema
        )
        kwargs = {
            "max_output_tokens": max_output_tokens,
            "timeout_seconds": max(0, timeout_seconds - (monotonic() - start)),
            "inference_context": inference_context,
        }
        revalidate_disclosure()
        method = self.delegate.complete
        if response_schema is not None:
            method = self.delegate.generate_structured
            kwargs["response_schema"] = response_schema
        if self.admission:
            with self.admission.authorize(requirements):
                return method(messages, **kwargs)
        return method(messages, **kwargs)

    def complete(self, messages, **kwargs):
        return self._complete(messages, **kwargs)

    def generate_structured(self, messages, *, response_schema, **kwargs):
        from personal_ai.llm.litellm.profiles import _validate_schema

        self.capabilities.require("structured_generation")
        _validate_schema(response_schema)
        return self._complete(messages, response_schema=response_schema, **kwargs)


@dataclass(frozen=True)
class ExecutionPair:
    generator: SelectedGeneration
    counter: SelectedCounter


def compose_pair(settings, usage=None, *, profile=None):
    selected = profile or settings.inference_profile
    if settings.inference_cost_mode not in {"offline_fake", "strict_free"}:
        raise LLMInvalidConfigurationError("paid dispatch requires enforceable monetary admission")
    if selected not in PROFILES:
        raise LLMInvalidConfigurationError("selected profile has no approved matching counter")
    admission = None
    if selected.startswith("offline_fake"):
        if settings.inference_cost_mode != "offline_fake":
            raise LLMInvalidConfigurationError("fake execution must be explicitly offline")
        generator = LocalFakeGeneration(
            ["Offline test response."], provider_id=selected, model_id=selected + "-v1"
        )
        generator.identity = ProviderIdentity(
            generator.identity.provider_id, generator.identity.model_id, "pi3-local-json-bytes-v1"
        )
        counter = LocalFakeCounter(generator.identity)
    else:
        if settings.inference_cost_mode != "strict_free" or settings.ai_provider.lower() != "gemini":
            raise LLMInvalidConfigurationError("legacy profile requires explicit Gemini strict-free selection")
        from personal_ai.llm.gemini import GeminiLLMClient
        from personal_ai.llm.litellm import LiteLLMTokenCounter

        if usage is None or getattr(usage, "endpoint_profile_resolver", None) is None:
            raise LLMInvalidConfigurationError("canonical inference accounting is required")
        ledger = SendAccounting(usage)
        generator = GeminiLLMClient(settings, usage_accounting=ledger)
        counter = LiteLLMTokenCounter(settings, usage_accounting=ledger)
        credential = settings.ai_api_key.get_secret_value()
        admission = Admission(
            generator.endpoint_profile,
            usage,
            credential_getter=lambda: settings.ai_api_key.get_secret_value(),
            credential_fingerprint=sha256(credential.encode()).digest(),
        )
    selected_counter = SelectedCounter(counter, admission)
    return ExecutionPair(
        SelectedGeneration(generator, selected_counter, settings, admission), selected_counter
    )


def compose_summary(settings, pair):
    if settings.inference_summary_profile == "disabled":
        return None
    if settings.inference_summary_profile != settings.inference_profile:
        raise LLMInvalidConfigurationError("summary must share the approved chat endpoint")
    from personal_ai.llm.context import ConversationSummarizer

    return ConversationSummarizer(settings, pair.generator)


class UnavailableEmbedding:
    """No approved exact embedding-input counter is installed. Never dispatch."""

    requires_inference_context = True
    capability_available = False

    def embed(self, *args, **kwargs):
        from personal_ai.llm.errors import LLMUnsupportedCapabilityError

        raise LLMUnsupportedCapabilityError("embedding input counter is not approved")


def compose_memory(settings, usage=None):
    if not settings.memory_enabled and not settings.memory_inspection_enabled:
        return None
    from personal_ai.llm.memory import MemoryAdapter

    extraction = None
    if settings.inference_extraction_profile != "disabled":
        extraction = compose_pair(settings, usage, profile=settings.inference_extraction_profile)
        extraction.generator.capabilities.require("structured_generation")
    # A different chat profile never implies Gemini embedding disclosure. Keep
    # old rows/spaces intact, refusing new remote vector work until exact input
    # counting is installed. Schema-3 lexical selection remains independent.
    return MemoryAdapter(settings, extraction, UnavailableEmbedding())
