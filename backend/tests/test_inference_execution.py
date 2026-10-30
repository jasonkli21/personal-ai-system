"""PI-3 composition/admission abuse tests. All provider responses are synthetic."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import RequestScope
from personal_ai.context import ContextAssembler
from personal_ai.entities import Conversation
from personal_ai.llm.client import ChatMessage, InferenceContext, ProviderIdentity
from personal_ai.llm.disclosure import bind_disclosure_guard
from personal_ai.llm.errors import (
    LLMError,
    LLMInvalidConfigurationError,
    LLMInvalidRequestError,
    LLMUnsupportedCapabilityError,
)
from personal_ai.llm.execution import (
    LocalFakeCounter,
    SelectedGeneration,
    SendAccounting,
    compose_memory,
    compose_pair,
    compose_summary,
)
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.llm.preparation import prepare_bounded_input
from personal_ai.memory.extraction import MemoryCandidateExtractor
from personal_ai.routing.configured import build_initial_endpoint_profiles
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services import ChatTurnService
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository
from personal_ai.usage.contracts import UsageAdmissionDenied
from personal_ai.usage.profiles import EndpointProfileResolver

CTX = InferenceContext("personal", "sensitive", "test-policy-v1")
MESSAGES = (ChatMessage("user", "Unicode: ☕ 漢字 😺 \" quotes \\ slash"),)


def settings(**changes):
    return Settings(_env_file=None, ai_provider="fake", ai_model="unused", **changes)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def scope():
    registration = default_application_registry().registration("personal_ai")
    return ApplicationContextRequest(
        scope=RequestScope(
            owner_id="local", acting_user_id="local", application_id="personal_ai", request_id="pi3"
        ),
        definition=registration.definition,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("profile", ["offline_fake", "offline_fake_alt"])
async def test_two_backends_use_canonical_chat_and_exact_local_count(profile):
    config = settings(inference_profile=profile)
    pair = compose_pair(config)
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    now = datetime.now(UTC)
    conversation = conversations.create(Conversation(
        id=uuid4(), owner_id="local", title="PI3", created_at=now, updated_at=now
    ))
    service = ChatTurnService(
        conversations, messages, pair.generator, owner_id="local", application_context=scope(),
        model=pair.generator.identity.model_id, context_assembler=ContextAssembler(config, pair.counter),
    )
    events = [event async for event in service.send(conversation.id, "hello", request_id="pi3")]
    assert events[-1].__class__.__name__ == "TurnCompleted"
    assert len(pair.generator.delegate.requests) == 1
    assert pair.generator.identity.provider_id == profile
    assert pair.counter.identity == pair.generator.identity
    assert pair.generator.delegate.generation_metadata[-1].usage.confidence == "estimated"
    from personal_ai.contracts.execution import ContinuationRequest

    request = ContinuationRequest.model_validate({
        "content": "continue with original key", "idempotency_key": str(uuid4()),
        "choice": {"mode": "automatic"},
    })
    first = [event async for event in service.continue_turn(conversation.id, request)]
    replay = [event async for event in service.continue_turn(conversation.id, request)]
    assert first[-1] == replay[-1]
    assert len(pair.generator.delegate.requests) == 2


@pytest.mark.parametrize("profile", ["groq", "cloudflare_workers_ai", "evil.module:factory", ""])
def test_unapproved_missing_counters_and_factories_fail_before_send(profile):
    config = settings().model_copy(update={"inference_profile": profile})
    with pytest.raises(LLMInvalidConfigurationError):
        compose_pair(config)


@pytest.mark.parametrize("mode", ["explicit_paid", "mostly_free_opt_in"])
def test_paid_modes_disabled_even_with_operator_selection(mode):
    with pytest.raises(LLMInvalidConfigurationError, match="monetary"):
        compose_pair(settings(inference_cost_mode=mode))


def test_missing_counter_mismatched_identity_and_estimates_never_relax_strict_contract():
    from personal_ai.context.tokens import EstimatedTokenCounter

    pair = compose_pair(settings())
    for counter in [None, EstimatedTokenCounter(), LocalFakeCounter(ProviderIdentity("other", "m", "s"))]:
        with pytest.raises(LLMInvalidRequestError):
            SelectedGeneration(pair.generator.delegate, counter, settings())
    with pytest.raises(LLMInvalidRequestError, match="budget"):
        prepare_bounded_input(
            MESSAGES, pair.counter, generator=pair.generator, input_limit=1, inference_context=CTX
        )
    with pytest.raises(LLMInvalidRequestError):
        pair.counter.count(MESSAGES)


def test_local_serialization_covers_unicode_roles_and_schema():
    pair = compose_pair(settings())
    schema = {"type": "object", "properties": {"文字": {"type": "string"}}}
    count = pair.counter.count(MESSAGES, response_schema=schema, inference_context=CTX)
    assert count.tokens == len(json.dumps({
        "messages": [(m.role, m.content) for m in MESSAGES], "schema": schema,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    assert count.confidence == "authoritative" and count.provider_id == "offline_fake"


def test_summary_and_memory_are_explicit_no_gemini_construction():
    config = settings()
    pair = compose_pair(config)
    assert compose_summary(config, pair) is None
    assert compose_memory(config) is None
    assert compose_summary(config.model_copy(update={
        "inference_summary_profile": "offline_fake"
    }), pair).generator is pair.generator
    with pytest.raises(LLMInvalidConfigurationError):
        compose_summary(config.model_copy(update={"inference_summary_profile": "legacy_gemini"}), pair)
    memory = compose_memory(settings(memory_enabled=True))
    with pytest.raises(LLMUnsupportedCapabilityError):
        memory.embed(["private input"], inference_context=CTX)
    with pytest.raises(LLMUnsupportedCapabilityError):
        memory.extract([], timeout=1, inference_context=CTX)


def test_extraction_checks_capability_before_counter_disclosure():
    generator = FakeLLMClient(supports_structured=False)
    class NoCounter:
        def count(self, *args, **kwargs):
            raise AssertionError("source disclosed to counter")
    from personal_ai.evaluation.memory import build_fixture, load_fixtures

    active = build_fixture(load_fixtures()[0])[4][0]
    with pytest.raises(LLMUnsupportedCapabilityError):
        MemoryCandidateExtractor(settings(), generator, NoCounter()).extract(
            active, timeout=10, inference_context=CTX
        )


class Ledger:
    """Test spy for the existing accounting port, not an alternate runtime ledger."""
    def __init__(self, registry):
        self.endpoint_profile_resolver = EndpointProfileResolver(registry)
        self.invocations, self.attempts, self.results = [], [], []
        self.denial = None

    def begin_invocation(self, invocation):
        self.invocations.append(invocation)

    def reserve_attempt(self, invocation, attempt, *, max_attempts):
        if self.denial:
            raise UsageAdmissionDenied(self.denial)
        self.attempts.append((invocation, attempt))
        return attempt

    def settle_attempt(self, invocation, attempt, result):
        self.results.append(result)

    def complete_invocation(self, *args, **kwargs):
        pass


def legacy(**changes):
    config = Settings(
        _env_file=None, ai_provider="gemini", ai_model="fixture-model", ai_api_key="synthetic",
        inference_profile="legacy_gemini", inference_cost_mode="strict_free",
        gemini_account_scope_id="test-account", gemini_free_tier_verified=True,
        gemini_privacy_approved=True, gemini_privacy_max_sensitivity="sensitive",
        gemini_preflight_reference="test:free", gemini_counter_compatibility_verified=True,
        gemini_counter_preflight_reference="test:counter", gemini_quota_membership_verified=True,
        gemini_endpoint_context_limit_tokens=32768, gemini_endpoint_output_limit_tokens=4096,
        gemini_quota_buckets=[{
            "bucket_id": "test:requests", "authority_scope_id": "test-account",
            "operations": ["token_counting", "bounded_generation", "streaming"],
            "unit": "requests", "source": "operator_attestation", "confidence": "verified",
            "evidence_reference": "test:quota", "limit": 1000, "window_seconds": 60,
        }],
    )
    profile = build_initial_endpoint_profiles(config)[0].model_dump(mode="json")
    now = datetime.now(UTC)
    profile["strict_free_attestation"].update({
        "verified_at": (now - timedelta(minutes=1)).isoformat(),
        "valid_until": (now + timedelta(hours=1)).isoformat(),
    })
    profile.update(changes)
    config = config.model_copy(update={"inference_additional_endpoint_profiles": [
        {**profile, "profile_version": 2}
    ]})
    registry = EndpointRegistry(build_initial_endpoint_profiles(config))
    ledger = Ledger(registry)
    return config, ledger, compose_pair(config, ledger)


def install_transport(pair, handler):
    pair.counter.delegate._sync_transport_factory = lambda: httpx.MockTransport(handler)
    pair.generator.delegate._sync_transport_factory = lambda: httpx.MockTransport(handler)
    pair.generator.delegate._async_transport_factory = lambda: httpx.MockTransport(handler)


def response(request):
    if request.url.path.endswith(":countTokens"):
        return httpx.Response(200, json={"totalTokens": 35})
    return httpx.Response(200, json={
        "modelVersion": "fixture-model",
        "candidates": [{"content": {"role": "model", "parts": [{"text": "done"}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 35, "candidatesTokenCount": 1, "totalTokenCount": 36},
    })


def test_explicit_legacy_uses_separate_count_and_generation_attempts_and_prepared_reservations():
    _, ledger, pair = legacy()
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return response(request)
    install_transport(pair, handler)
    result = pair.generator.complete(MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX)
    assert result.text == "done" and result.metadata.identity.provider_id == "gemini"
    assert len(calls) == len(ledger.attempts) == 2
    assert [i.operation for i, _ in ledger.attempts] == ["token_counting", "bounded_generation"]
    assert [a.reserved_tokens for _, a in ledger.attempts] == [32768, 45]
    assert ledger.results[-1].usage_confidence == "exact"


@pytest.mark.parametrize("change", [
    {"enabled": False}, {"tier_verified": False}, {"cost_class": "UNKNOWN"},
    {"strict_free_enabled": False}, {"data_use_policy": {"status": "unknown"}},
    {"data_use_policy": {"status": "approved", "max_sensitivity": "public", "policy_reference": "test:p"}},
    {"quota_membership": "unknown"},
])
def test_strict_free_and_privacy_denial_precedes_count_network(change):
    _, ledger, pair = legacy(**change)
    install_transport(pair, lambda request: pytest.fail("unexpected network disclosure"))
    with pytest.raises((LLMError, ValueError, RuntimeError)):
        pair.generator.complete(MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX)
    assert not ledger.attempts


def test_stale_attestation_and_policy_change_after_count_block_generation():
    _, ledger, pair = legacy()
    profile = pair.generator.admission.profile
    expired = profile.strict_free_attestation.model_copy(update={
        "valid_until": datetime.now(UTC) - timedelta(seconds=1),
        "verified_at": datetime.now(UTC) - timedelta(hours=1),
    })
    pair.generator.admission.profile = profile.model_copy(update={"strict_free_attestation": expired})
    with pytest.raises((LLMError, RuntimeError)):
        pair.counter.count(MESSAGES, inference_context=CTX)
    pair.generator.admission.profile = profile
    # Model a policy revision at exactly the count/send boundary.
    registry = ledger.endpoint_profile_resolver.registry
    def changed(request):
        registry.upsert(profile.model_copy(update={"enabled": False, "profile_version": 3}))
        return response(request)
    install_transport(pair, changed)
    with pytest.raises((LLMError, RuntimeError)):
        pair.generator.complete(MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX)
    assert len(ledger.attempts) == 1
    assert not next(p for p in registry.profiles if p.provider_id == "gemini").enabled


@pytest.mark.parametrize("denial", ["provider_quota_exhausted", "provider_outcome_unresolved"])
def test_p19_reservation_denial_has_no_physical_send(denial):
    _, ledger, pair = legacy()
    ledger.denial = denial
    install_transport(pair, lambda request: pytest.fail("send after quota denial"))
    with pytest.raises(LLMError):
        pair.generator.complete(MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX)
    assert not ledger.attempts


def test_physical_accounting_requires_current_bound_authority():
    _, ledger, _ = legacy()
    with pytest.raises(LLMInvalidRequestError):
        SendAccounting(ledger).reserve_attempt(SimpleNamespace(), SimpleNamespace(), max_attempts=1)


def test_rotated_secret_cannot_reuse_composed_account_attestation():
    from pydantic import SecretStr

    config, _ledger, pair = legacy()
    config.ai_api_key = SecretStr("rotated-synthetic-key")
    with pytest.raises(LLMInvalidConfigurationError, match="credential changed"):
        pair.counter.count(MESSAGES, inference_context=CTX)


@pytest.mark.anyio
async def test_source_revocation_during_additional_generation_count_blocks_send():
    pair = compose_pair(settings())
    current = True
    old = pair.counter.delegate.count
    def count(*args, **kwargs):
        nonlocal current
        result = old(*args, **kwargs)
        current = False
        return result
    pair.counter.delegate.count = count
    def guard():
        if not current:
            raise LLMInvalidRequestError("source revoked")
    with bind_disclosure_guard(guard), pytest.raises(LLMInvalidRequestError):
        _ = [event async for event in pair.generator.stream_events(
            MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX
        )]
    assert not pair.generator.delegate.requests


@pytest.mark.anyio
async def test_invalid_terminal_and_concurrent_profiles_keep_one_send_each():
    async def run(profile):
        pair = compose_pair(settings(inference_profile=profile))
        pair.generator.delegate.include_terminal = False
        with pytest.raises(LLMError):
            _ = [delta async for delta in pair.generator.stream_bounded(
                MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX
            )]
        assert len(pair.generator.delegate.requests) == 1
        return pair.generator.identity
    identities = await asyncio.gather(run("offline_fake"), run("offline_fake_alt"))
    assert identities[0] != identities[1]


def test_operator_profile_enum_rejects_dynamic_import():
    with pytest.raises(ValidationError):
        settings(inference_profile="module:factory")


@pytest.mark.parametrize("failure", [429, 503, "timeout"])
def test_ancillary_failure_never_falls_back_or_sends_generation(failure):
    _, ledger, pair = legacy()
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if failure == "timeout":
            raise httpx.ReadTimeout("secret diagnostic")
        return httpx.Response(failure, json={"error": {"message": "secret diagnostic"}})
    install_transport(pair, handler)
    with pytest.raises(LLMError) as raised:
        pair.generator.complete(MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX)
    assert "secret diagnostic" not in str(raised.value)
    assert len(calls) == len(ledger.attempts) == 1
    assert calls[0].endswith(":countTokens")


def test_policy_revocation_after_preparation_before_physical_reservation_blocks_generation():
    _, ledger, pair = legacy()
    calls = []
    install_transport(pair, lambda request: (calls.append(request.url.path), response(request))[1])
    registry = ledger.endpoint_profile_resolver.registry
    def revoked_transport():
        profile = pair.generator.admission.profile
        registry.upsert(profile.model_copy(update={"profile_version": 3, "enabled": False}))
        return httpx.MockTransport(lambda _: pytest.fail("generation disclosure after revocation"))
    pair.generator.delegate._sync_transport_factory = revoked_transport
    with pytest.raises(LLMError):
        pair.generator.complete(MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX)
    assert len(ledger.attempts) == len(calls) == 1


@pytest.mark.parametrize("interval", ["expired", "unknown", "future"])
def test_attestation_time_is_required_and_current_before_counter(interval):
    _, ledger, pair = legacy()
    profile = pair.generator.admission.profile
    now = datetime.now(UTC)
    times = {
        "expired": {"verified_at": now - timedelta(hours=2), "valid_until": now - timedelta(hours=1)},
        "unknown": {"verified_at": None, "valid_until": None},
        "future": {"verified_at": now + timedelta(hours=1), "valid_until": now + timedelta(hours=2)},
    }[interval]
    profile = profile.model_copy(update={
        "strict_free_attestation": profile.strict_free_attestation.model_copy(update=times)
    })
    pair.generator.admission.profile = profile
    ledger.endpoint_profile_resolver.registry = EndpointRegistry([profile])
    install_transport(pair, lambda _: pytest.fail("counter disclosure with stale free facts"))
    with pytest.raises(LLMError):
        pair.counter.count(MESSAGES, inference_context=CTX)
    assert not ledger.attempts


def test_summary_has_distinct_usage_task_and_own_exact_count():
    config, ledger, pair = legacy()
    config = config.model_copy(update={"inference_summary_profile": "legacy_gemini"})
    install_transport(pair, response)
    from personal_ai.evaluation.context import build_fixture, load_fixtures

    source = build_fixture(load_fixtures()[0])[0][:2]
    draft = compose_summary(config, pair).summarize(source, None, inference_context=CTX)
    assert draft.attribution.identity == pair.generator.identity
    assert [i.operation for i, _ in ledger.attempts] == ["token_counting", "bounded_generation"]
    assert all(i.task_id == "conversation_summary" for i, _ in ledger.attempts)


def test_structured_call_cannot_be_downgraded_to_plain_generation_by_null_schema():
    pair = compose_pair(settings())
    with pytest.raises(LLMInvalidRequestError):
        pair.generator.generate_structured(
            MESSAGES, response_schema=None, max_output_tokens=10, timeout_seconds=10,
            inference_context=CTX,
        )
    assert not pair.generator.delegate.requests


def test_summary_retains_full_preparation_sensitivity():
    from personal_ai.context.deadline import DeadlineCounter
    from personal_ai.context.tokens import FakeTokenCounter
    from personal_ai.evaluation.context import build_fixture, load_fixtures

    config = settings(summary_trigger_tokens=1)
    counter = DeadlineCounter(FakeTokenCounter(), None, InferenceContext("sensitive", "sensitive", "v1"))
    seen = []
    class Summary:
        def summarize(self, source, prior, *, inference_context):
            seen.append(inference_context)
            raise LLMInvalidRequestError("test stops before generation")
    assembler = ContextAssembler(config, counter, summarizer=Summary())
    history = build_fixture(load_fixtures()[0])[0]
    assembler._refresh(
        history, SimpleNamespace(selected_message_ids=()), None, [], application_context=scope()
    )
    assert seen and seen[0].effective_sensitivity == "sensitive"


@pytest.mark.anyio
async def test_selected_stream_cancellation_closes_single_delegate_without_retry():
    pair = compose_pair(settings())
    started, closed = asyncio.Event(), asyncio.Event()
    sends = []
    async def blocked(messages, **kwargs):
        sends.append(messages)
        try:
            from personal_ai.llm.client import GenerationEvent

            yield GenerationEvent.text_delta("partial")
            started.set()
            await asyncio.Event().wait()
        finally:
            closed.set()
    pair.generator.delegate.stream_events = blocked
    async def consume():
        return [event async for event in pair.generator.stream_events(
            MESSAGES, max_output_tokens=10, timeout_seconds=10, inference_context=CTX
        )]
    pending = asyncio.create_task(consume())
    await asyncio.wait_for(started.wait(), 3)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert closed.is_set() and len(sends) == 1
