"""Hermetic effort contract, canonical dispatch and negotiated HTTP coverage."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from personal_ai.api.dependencies import get_chat_turn_service
from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.context import ContextAssembler
from personal_ai.context.providers import ContextPreparationError
from personal_ai.contracts.execution import (
    AutomaticContinuationPayload,
    ContinuationRequestPayload,
)
from personal_ai.entities import Conversation
from personal_ai.llm import synthetic_reasoning
from personal_ai.llm.execution import compose_pair
from personal_ai.llm.native_reasoning import resolve_native
from personal_ai.main import app
from personal_ai.reasoning.policy import Ceilings, ReasoningDenied, TurnObservation, resolve_policy
from personal_ai.services import ChatTurnService
from personal_ai.settings import get_settings
from personal_ai.storage import (
    ConversationConflictError,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
    ResourceNotFoundError,
)
from personal_ai.usage.trace import Trace

from .test_inference_execution import legacy, scope, settings
from .test_local_inference import runtime as local_runtime  # noqa: F401 - shared fixture

BUDGET = {
    "max_model_calls": 1, "max_input_tokens": 4096, "max_output_tokens": 64,
    "max_concurrency": 1, "max_elapsed_seconds": 10,
}
KEY = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
VERSION = {"X-Reasoning-Observation": "reasoning-observation-v2"}


def body(*, effort="max", budget=None, **changes):
    return {
        "content": "credential-CANARY hidden-deliberation-CANARY name-CANARY",
        "idempotency_key": str(KEY),
        "reasoning": {
            "schema_version": "reasoning-request-v1", "effort": effort,
            "budget": BUDGET if budget is None else budget, **changes,
        },
    }


def setup(config, pair=None):
    pair = pair or compose_pair(config)
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    now = datetime.now(UTC)
    conversation = conversations.create(Conversation(
        id=uuid4(), owner_id="local", title="Effort test", created_at=now, updated_at=now,
    ))
    service = ChatTurnService(
        conversations, messages, pair.generator, owner_id="local", application_context=scope(),
        model=pair.generator.identity.model_id, context_assembler=ContextAssembler(config, pair.counter),
    )
    return service, pair, messages, conversation.id


def canonical(payload=None):
    return AutomaticContinuationPayload.model_validate(payload or body()).to_internal_request()


def test_ordinary_payload_and_durable_identity_match_previous_contract():
    payload = {"content": "plain ☕", "idempotency_key": str(KEY)}
    old = ContinuationRequestPayload.model_validate(payload)
    new = AutomaticContinuationPayload.model_validate(payload)
    assert old.model_dump_json() == new.model_dump_json()
    request = new.to_internal_request()
    previous = {
        "content": "plain ☕", "idempotency_key": str(KEY),
        "choice": dict.fromkeys([
            "endpoint", "model_id", "connection_id", "connection_revision", "caller_id", "audience",
        ]) | {"mode": "automatic"},
        "candidate_message_ids": None, "excluded_source_classes": [],
    }
    wire = json.dumps(previous, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    assert request.intent_digest == sha256(wire.encode()).hexdigest()
    assert "reasoning" not in request.model_dump()
    with pytest.raises(ValidationError):
        ContinuationRequestPayload.model_validate(body())


@pytest.mark.parametrize("change", [
    None, {"schema_version": "reasoning-request-v2"},
    {"effort": "extreme"}, {"effective_effort": "max"}, {"policy_version": "trusted"},
    {"capability": {}}, {"native_control": "yes"}, {"account_id": "other"},
    {"paid_opt_in": True}, {"strategy": "unknown"}, {"research": None}, {"budget": None},
    {"budget": {"max_model_calls": True}}, {"budget": {"max_elapsed_seconds": 0.1}},
    {"budget": {"max_input_tokens": -1}}, {"budget": {"max_output_tokens": 100001}},
    {"budget": {"max_provider_cost_usd": "1.0"}}, {"budget": {"max_provider_cost_usd": 1}},
    {"budget": {"unknown": 1}}, {"budget": {"max_sources": None}},
])
def test_closed_schema(change):
    payload = body()
    if change is None:
        payload["reasoning"] = None
    else:
        payload["reasoning"].update(change)
    with pytest.raises(ValidationError):
        canonical(payload)


@pytest.mark.parametrize("field", [
    "max_model_calls", "max_input_tokens", "max_output_tokens", "max_elapsed_seconds",
    "max_concurrency",
])
def test_omitted_work_dimension_means_zero(field):
    config = settings(reasoning_enabled=True)
    service, pair, messages, cid = setup(config)
    request = canonical(body(budget={key: value for key, value in BUDGET.items() if key != field}))
    with pytest.raises(ReasoningDenied, match="budget_exhausted"):
        service.continue_turn(cid, request)
    assert not messages.list_active(owner_id="local", conversation_id=cid)
    assert not pair.generator.delegate.requests


def test_impossible_fake_message_budget_denies_before_consuming_key():
    service, pair, messages, cid = setup(settings(reasoning_enabled=True))
    tiny = body(budget={**BUDGET, "max_input_tokens": 1})
    with pytest.raises(ReasoningDenied, match="budget_exhausted"):
        service.continue_turn(cid, canonical(tiny))
    assert messages.list_active(owner_id="local", conversation_id=cid) == []
    assert not pair.generator.delegate.requests
    with pytest.raises(ReasoningDenied, match="budget_exhausted"):
        service.continue_turn(cid, canonical(tiny))
    assert messages.list_active(owner_id="local", conversation_id=cid) == []


def test_policy_intersects_trusted_ceilings_and_cost_is_zero():
    policy = resolve_policy(
        canonical(body(budget={**BUDGET, "max_provider_cost_usd": "9.99"})).reasoning,
        enabled=True, ceilings=Ceilings("medium", "high", "medium", "low", "max"),
        input_limit=2048, output_limit=32, elapsed_limit=8, count_reservation=100,
    )
    assert policy.ceiling == "low"
    assert policy.reasons == ("policy", "budget")
    assert policy.budget.max_provider_cost_usd == "0.00"
    assert policy.budget.max_input_tokens == 2048


@pytest.mark.parametrize("changes", [{"strategy": "direct"}, {"strategy": "tool_verify"},
                                     {"research": "if_authorized"}])
def test_catalog_and_research_never_dispatch(changes):
    service, pair, messages, cid = setup(settings(reasoning_enabled=True))
    with pytest.raises(ReasoningDenied, match="unsupported"):
        service.continue_turn(cid, canonical(body(**changes)))
    assert not pair.generator.delegate.requests
    assert not messages.list_active(owner_id="local", conversation_id=cid)


@pytest.mark.parametrize(("effort", "effective", "wire"), [
    ("auto", "low", "brief"), ("low", "low", "brief"), ("medium", "low", "brief"),
    ("high", "low", "brief"), ("max", "low", "brief"),
])
def test_exact_final_fake_wire_and_content_free_observation(monkeypatch, effort, effective, wire):
    service, pair, _, cid = setup(settings(reasoning_enabled=True, reasoning_effort_ceiling="max"))
    request = canonical(body(effort=effort))
    captured = []
    consume = synthetic_reasoning.consume_wire

    def capture(payload):
        received = consume(payload)
        captured.append(received)
        return received

    def forbidden(*args, **kwargs):
        pytest.fail("optional sources or auxiliary generation were accessed")

    monkeypatch.setattr(synthetic_reasoning, "consume_wire", capture)
    monkeypatch.setattr(service, "schedule_post_completion", forbidden)
    monkeypatch.setattr(ContextAssembler, "plan_context", forbidden)
    trace = Trace()

    async def run():
        with trace.capture():
            return [event async for event in service.continue_turn(cid, request)]

    events = asyncio.run(run())
    observation = events[-1].reasoning
    assert captured == [{
        "messages": [["user", request.content]], "model": "offline_fake-v1",
        "reasoning": wire, "max_output_tokens": 64,
    }]
    assert observation.effective_effort == effective
    assert observation.native_control == "applied"
    assert observation.capability_version == "fake-native-effort-v1"
    assert observation.provider_acknowledged is None
    assert observation.native_reasoning_observed == "unknown"
    assert observation.model_attempts == len(pair.generator.delegate.requests) == 1
    assert observation.model_reservations is None
    assert observation.model_settlements is None
    assert observation.count_attempts is None
    assert observation.cost_class == "synthetic_no_charge"
    assert observation.usage_confidence == "estimated"
    assert "CANARY" not in observation.model_dump_json()
    rows, dropped = trace.snapshot()
    assert not dropped
    result = next(row for row in rows if row["event"] == "reasoning_resolution")
    dispatch = next(row for row in rows if row.get("operation") == "streaming"
                    and row["event"] == "dispatch")
    assert result["request"] == dispatch["request"]
    assert result["reasoning"] == observation.model_dump(mode="json")
    assert "CANARY" not in json.dumps(rows)


def test_throwing_usage_observer_cannot_change_receipt_or_promote_zero_attempt(monkeypatch):
    service, pair, _, cid = setup(settings(reasoning_enabled=True))

    def fail_observation(*args, **kwargs):
        raise RuntimeError("observer unavailable")

    monkeypatch.setattr(TurnObservation, "record", fail_observation)

    async def run():
        return [event async for event in service.continue_turn(cid, canonical())]

    terminal = asyncio.run(run())[-1]
    assert terminal.reasoning.status == "complete"
    assert terminal.reasoning.model_attempts == 1
    assert terminal.reasoning.model_reservations is None
    assert len(pair.generator.delegate.requests) == 1


def test_missing_generation_receipt_cannot_complete_observation():
    policy = resolve_policy(
        canonical().reasoning, enabled=True,
        ceilings=Ceilings("low", "low", "low", "low", "low"),
        input_limit=4096, output_limit=64, elapsed_limit=10, count_reservation=0,
    )
    from time import monotonic

    observation = TurnObservation(policy, monotonic(), "receipt-probe")
    result = observation.result(complete=True)
    assert result.status == "unavailable"
    assert result.stop_reason == "uncertain_effect"
    assert result.model_attempts is None


def test_missing_or_forged_receipt_does_not_complete_durable_turn(monkeypatch):
    service, pair, messages, cid = setup(settings(reasoning_enabled=True))
    original = pair.generator.stream_events

    async def missing_receipt(*args, **kwargs):
        async for event in original(*args, **kwargs):
            if event.kind == "terminal":
                event = replace(event, metadata=replace(
                    event.metadata, invocation_id=None, attempt_ids=(),
                ))
            yield event

    monkeypatch.setattr(pair.generator, "stream_events", missing_receipt)

    async def run():
        return [event async for event in service.continue_turn(cid, canonical())]

    terminal = asyncio.run(run())[-1]
    assert terminal.reasoning.status == "partial"
    assert terminal.reasoning.stop_reason == "uncertain_effect"
    assert terminal.reasoning.model_attempts is None
    active = messages.list_active(owner_id="local", conversation_id=cid)
    assert active[-1].status.value == "failed"


@pytest.mark.parametrize("field,value", [
    ("profile_version", 2), ("model_id", "model-alias"), ("endpoint_profile_id", "other-profile"),
    ("endpoint_id", "other-endpoint"), ("deployment_id", "other-build"),
    ("account_scope_id", "other-account"), ("credential_scope_id", "other-key"),
    ("credential_reference", "env:OTHER_KEY"), ("serializer_id", "other-serializer"),
    ("runtime_id", "other-runtime"), ("enabled", False),
])
def test_native_exact_profile_proof(field, value):
    proof = synthetic_reasoning._PROOF
    altered = proof.profile.model_copy(update={field: value})
    assert resolve_native(altered, proof.sdk_id, proof.operation, "max", 64, capabilities=(proof,)) is None


def test_native_operation_sdk_expiry_noncontiguous_and_bounds():
    proof = synthetic_reasoning._PROOF
    sdk, profile = proof.sdk_id, proof.profile
    assert resolve_native(profile, sdk, "streaming", "max", 64) is None
    assert resolve_native(profile, "other-sdk", "streaming", "max", 64, capabilities=(proof,)) is None
    assert resolve_native(profile, sdk, "bounded_generation", "max", 64, capabilities=(proof,)) is None
    expired = replace(proof, valid_until=datetime.now(UTC) - timedelta(seconds=1))
    assert resolve_native(profile, sdk, "streaming", "max", 64, capabilities=(expired,)) is None
    assert resolve_native(profile, sdk, "streaming", "max", 0, capabilities=(proof,)) is None
    assert resolve_native(profile, sdk, "streaming", "max", 31, capabilities=(proof,))[1].effort == "low"
    assert resolve_native(profile, sdk, "streaming", "medium", 64, capabilities=(proof,))[1].effort == "low"


@pytest.mark.parametrize("wire_value", [None, "unknown", "extended"])
def test_transformed_native_wire_fails_closed(monkeypatch, wire_value):
    service, pair, _, cid = setup(settings(reasoning_enabled=True))
    serialize = synthetic_reasoning.serialize

    def transform(*args):
        result = json.loads(serialize(*args))
        if wire_value is None:
            result.pop("reasoning")
        else:
            result["reasoning"] = wire_value
        return json.dumps(result).encode()

    monkeypatch.setattr(synthetic_reasoning, "serialize", transform)

    async def run():
        return [event async for event in service.continue_turn(cid, canonical())]

    terminal = asyncio.run(run())[-1]
    assert terminal.reasoning.model_attempts is None
    assert terminal.reasoning.effective_effort is None
    assert terminal.reasoning.native_control == "not_applied"
    assert not pair.generator.delegate.requests


def test_plain_fallback_and_replay_original_key():
    config = settings(reasoning_enabled=True, inference_profile="offline_fake_alt",
                      reasoning_effort_ceiling="max")
    service, pair, _, cid = setup(config)
    request = canonical()

    async def run():
        first = [event async for event in service.continue_turn(cid, request)]
        config.reasoning_effort_ceiling = "low"
        replay = [event async for event in service.continue_turn(cid, request)]
        return first[-1], replay[-1]

    first, replay = asyncio.run(run())
    assert first.reasoning.effective_effort == "low"
    assert first.reasoning.native_control == "not_applied"
    assert "policy" in first.reasoning.narrowing_reasons
    assert replay.reasoning.replayed and replay.reasoning.model_attempts is None
    assert replay.reasoning.policy_version == first.reasoning.policy_version
    assert replay.message == first.message
    for payload in (body(effort="low"), body(budget={**BUDGET, "max_output_tokens": 65})):
        with pytest.raises(ConversationConflictError, match="idempotency_input_changed"):
            service.continue_turn(cid, canonical(payload))
    assert len(pair.generator.delegate.requests) == 1


def test_wrong_scope_and_forbidden_sources_deny_before_count(monkeypatch):
    service, pair, _, cid = setup(settings(reasoning_enabled=True))

    def forbidden(*args, **kwargs):
        pytest.fail("token count was attempted")

    monkeypatch.setattr(pair.counter.delegate, "count", forbidden)
    for payload in [
        body() | {"retrieval_context": True}, body() | {"candidate_message_ids": [str(uuid4())]},
        body() | {"choice": {"mode": "manual_external"}},
    ]:
        with pytest.raises(ReasoningDenied):
            service.continue_turn(cid, canonical(payload))
    original = scope()
    service._application_context = ApplicationContextRequest(
        scope=original.scope.model_copy(update={"workspace_id": str(uuid4())}),
        definition=original.definition,
    )
    with pytest.raises(ResourceNotFoundError):
        service.continue_turn(cid, canonical())


def test_http_negotiation_and_gate_precede_service_composition(monkeypatch):
    config = settings()
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: config)

    def forbidden():
        pytest.fail("service composed before gate or negotiation")

    monkeypatch.setitem(app.dependency_overrides, get_chat_turn_service, forbidden)
    client = TestClient(app)
    path = f"/v1/conversations/{uuid4()}/continue"
    response = client.post(path, json=body())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "reasoning_observation_required"
    response = client.post(path, json=body(), headers=VERSION)
    assert response.status_code == 403
    observation = json.loads(response.headers["X-Reasoning-Observation"])
    assert observation["effective_effort"] is None and observation["model_attempts"] == 0
    assert "CANARY" not in str(response.headers) + response.text


def test_negotiated_http_terminal_and_legacy_wire(monkeypatch):
    config = settings(reasoning_enabled=True, reasoning_effort_ceiling="max")
    service, pair, _, cid = setup(config)
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: config)
    monkeypatch.setitem(app.dependency_overrides, get_chat_turn_service, lambda: service)
    client = TestClient(app)
    path = f"/v1/conversations/{cid}/continue"
    response = client.post(path, json=body(), headers=VERSION)
    assert response.status_code == 200
    assert response.headers["X-Reasoning-Observation"] == VERSION["X-Reasoning-Observation"]
    terminal = json.loads(response.text.split("event: response.completed\ndata: ")[-1])
    assert terminal["reasoning"]["effective_effort"] == "low"
    assert "policy" in terminal["reasoning"]["narrowing_reasons"]
    assert "CANARY" not in json.dumps(terminal["reasoning"])
    ordinary = {"content": "ordinary", "idempotency_key": str(uuid4())}
    response = client.post(path, json=ordinary, headers=VERSION)
    assert response.status_code == 200
    assert "X-Reasoning-Observation" not in response.headers
    assert '"reasoning"' not in response.text
    assert len(pair.generator.delegate.requests) == 2


@pytest.mark.parametrize("fault", ["none", "quota", "ledger", "revoked", "lost_ack", "timeout"])
def test_local_canonical_physical_admission(local_runtime, monkeypatch, fault):  # noqa: F811
    pair, ledger, calls, respond = local_runtime
    pair.generator.settings.reasoning_enabled = True
    service, _, _, cid = setup(pair.generator.settings, pair)
    original = ledger.reserve_attempt
    revoked = False

    def reserve(invocation, attempt, **kwargs):
        nonlocal revoked
        if invocation.operation == "streaming":
            if fault == "quota":
                ledger.denial = "provider_quota_exhausted"
            if fault == "ledger":
                raise RuntimeError("private-CANARY")
            revoked = fault == "revoked"
        return original(invocation, attempt, **kwargs)

    def authority():
        if revoked:
            raise ContextPreparationError("context_source_authority_changed")

    def transport(request):
        response = respond(request)
        if request.url.path == "/completion":
            if fault == "lost_ack":
                raise httpx.RemoteProtocolError("private-CANARY")
            if fault == "timeout":
                raise TimeoutError("private-CANARY")
        return response

    monkeypatch.setattr(ledger, "reserve_attempt", reserve)
    monkeypatch.setattr("personal_ai.services.chat.service.require_current_client_authority", authority)
    monkeypatch.setattr(pair.generator.delegate, "_transport", lambda: httpx.MockTransport(transport))
    request = canonical()

    async def run():
        stream = await asyncio.to_thread(service.continue_turn, cid, request)
        return [event async for event in stream]

    observation = asyncio.run(run())[-1].reasoning
    sent = [call for call in calls if call.url.path == "/completion"]
    expected_attempts = 1 if fault == "none" else None
    assert len(sent) == int(fault in {"none", "lost_ack", "timeout"})
    assert observation.model_attempts == expected_attempts
    assert observation.native_control == "not_applied"
    assert "CANARY" not in observation.model_dump_json()
    if fault == "none":
        assert observation.status == "complete"
        assert observation.effective_effort == "low"
        assert observation.model_reservations is None
        assert observation.model_settlements is None
        assert "reasoning" not in json.loads(sent[0].content)
    else:
        assert observation.status == "unavailable"
        revoked = False
        with pytest.raises(ConversationConflictError):
            service.continue_turn(cid, request)
    if fault in {"lost_ack", "timeout"}:
        assert observation.stop_reason == "uncertain_effect"
        assert ledger.results[-1].outcome == "unknown"


@pytest.mark.parametrize("facts", [
    {}, {"strict_free_attestation": None, "strict_free_enabled": False,
     "cost_class": "UNKNOWN", "tier_verified": False},
    {"tier_verified": False}, {"quota_membership": "unknown"},
])
def test_hosted_plain_and_native_are_unavailable_before_count(monkeypatch, facts):
    config, ledger, pair = legacy(**facts)
    config.reasoning_enabled = True
    service, _, messages, cid = setup(config, pair)

    def forbidden(*args, **kwargs):
        pytest.fail("hosted provider was contacted")

    monkeypatch.setattr(pair.counter, "count_with_timeout", forbidden)
    with pytest.raises(ReasoningDenied, match="unsupported"):
        service.continue_turn(cid, canonical())
    assert not messages.list_active(owner_id="local", conversation_id=cid)
    assert not ledger.attempts


def test_abandoned_before_first_event_has_no_generation():
    service, pair, _, cid = setup(settings(reasoning_enabled=True))
    request = canonical()

    async def run():
        stream = service.continue_turn(cid, request)
        await stream.aclose()

    asyncio.run(run())
    with pytest.raises(ConversationConflictError):
        service.continue_turn(cid, request)
    assert not pair.generator.delegate.requests


def test_gate_revoked_after_creation_before_dispatch():
    config = settings(reasoning_enabled=True)
    service, pair, _, cid = setup(config)

    async def run():
        stream = service.continue_turn(cid, canonical())
        await anext(stream)
        config.reasoning_enabled = False
        return [event async for event in stream][-1]

    observation = asyncio.run(run()).reasoning
    assert observation.stop_reason == "policy_denied"
    assert observation.model_attempts is None
    assert not pair.generator.delegate.requests


def test_local_cancel_after_dispatch_retains_unknown_original_key(
    local_runtime, monkeypatch,  # noqa: F811
):
    pair, ledger, calls, respond = local_runtime
    pair.generator.settings.reasoning_enabled = True
    service, _, _, cid = setup(pair.generator.settings, pair)
    request = canonical()

    async def run():
        sent = asyncio.Event()

        async def transport(http_request):
            result = respond(http_request)
            if http_request.url.path == "/completion":
                sent.set()
                await asyncio.Event().wait()
            return result

        monkeypatch.setattr(pair.generator.delegate, "_transport", lambda: httpx.MockTransport(transport))
        stream = await asyncio.to_thread(service.continue_turn, cid, request)
        await anext(stream)
        await anext(stream)
        pending = asyncio.create_task(anext(stream))
        await asyncio.wait_for(sent.wait(), 5)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        await stream.aclose()

    asyncio.run(run())
    assert sum(call.url.path == "/completion" for call in calls) == 1
    assert ledger.results[-1].outcome == "unknown"
    with pytest.raises(ConversationConflictError):
        service.continue_turn(cid, request)
