"""Hermetic llama.cpp wire, accounting and disclosure canaries."""

from functools import partial
from uuid import uuid4

import anyio
import httpx
import pytest

from personal_ai.context.providers import ContextPreparationError
from personal_ai.llm import local_endpoint
from personal_ai.llm.disclosure import bind_disclosure_guard
from personal_ai.llm.errors import (
    LLMInvalidConfigurationError,
    LLMInvalidResponseError,
    LLMUnavailableError,
    LLMUnsupportedCapabilityError,
)
from personal_ai.llm.execution import compose_pair
from personal_ai.routing.configured import build_initial_endpoint_profiles
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.settings import Settings
from personal_ai.usage.context import bind_usage_task
from personal_ai.usage.trace import Trace

from .test_inference_execution import CTX, MESSAGES, Ledger


def settings(**overrides):
    return Settings(_env_file=None, **{
        "ai_provider": "fake", "ai_model": "unused", "inference_profile": "local_llama",
        "inference_cost_mode": "local_only", "local_llama_socket": "/private/pas/llama.sock",
        "local_llama_model_sha256": "a" * 64, "local_llama_build": "b42-abcdef0",
        "local_llama_approval": "test:local", **overrides,
    })


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def runtime(monkeypatch):
    config = settings()
    registry = EndpointRegistry(build_initial_endpoint_profiles(config))
    ledger = Ledger(registry)
    pair = compose_pair(config, ledger)
    endpoint = pair.generator.delegate
    calls = []
    monkeypatch.setattr(local_endpoint, "_socket_identity", lambda path: (1, 2, 3))

    def respond(request):
        calls.append(request)
        assert request.url.host == "local-inference.invalid"
        if request.url.path == "/props":
            return httpx.Response(200, json={
                "build_info": config.local_llama_build,
                "model_alias": endpoint.identity.model_id,
                "model_path": f"/models/{endpoint.identity.model_id}.gguf",
                "total_slots": 1, "default_generation_settings": {"n_ctx": 4096},
            })
        assert len(ledger.attempts) == sum(request.url.path != "/props" for request in calls)
        if request.url.path == "/tokenize":
            return httpx.Response(200, json={"tokens": [1, 10, 12]})
        return httpx.Response(200, json={
            "model": endpoint.identity.model_id, "content": "done", "stop": True,
            "stop_type": "eos", "truncated": False, "tokens_evaluated": 3, "tokens_predicted": 2,
        })

    monkeypatch.setattr(endpoint, "_transport", lambda: httpx.MockTransport(respond))
    return pair, ledger, calls, respond


def complete(pair):
    return pair.generator.complete(
        MESSAGES, max_output_tokens=10, timeout_seconds=3, inference_context=CTX,
    )


def test_exact_prepared_tokens_and_one_reservation_per_operation(runtime):
    import json

    pair, ledger, calls, _ = runtime
    trace = Trace()
    with trace.capture(), bind_usage_task("synthetic-task", request_id=str(uuid4())):
        result = complete(pair)
    assert result.text == "done"
    assert [request.url.path for request in calls] == ["/props", "/tokenize", "/props", "/completion"]
    tokenizer = json.loads(calls[1].content)
    assert tokenizer["parse_special"] is False and "Unicode:" in tokenizer["content"]
    generation = json.loads(calls[-1].content)
    assert generation["prompt"] == [1, 10, 12] and generation["stream"] is False
    assert [attempt.reserved_tokens for _, attempt in ledger.attempts] == [4096, 13]
    assert ledger.results[0].usage_source == "unknown"
    assert ledger.results[1].input_tokens == 3 and ledger.results[1].output_tokens == 2
    events, dropped = trace.snapshot()
    assert not dropped and len({event["request"] for event in events}) == 1
    assert {event["attempt"] for event in events if event["event"] == "settle"} == {
        str(attempt.attempt_id) for _, attempt in ledger.attempts
    }
    assert "Unicode" not in json.dumps(events) and "done" not in json.dumps(events)


@pytest.mark.parametrize("overrides", [
    {"local_llama_socket": "http://127.0.0.1:8080"},
    {"local_llama_socket": "/private/pas/../llama.sock"},
    {"local_llama_approval": ""},
    {"local_llama_build": ""},
    {"inference_cost_mode": "strict_free"},
])
def test_local_requires_explicit_bounded_operator_configuration(overrides):
    with pytest.raises(LLMInvalidConfigurationError):
        local_endpoint.local_profile(settings(**overrides))


def test_deployed_configuration_cannot_select_local_profile():
    with pytest.raises(LLMInvalidConfigurationError):
        local_endpoint.local_profile(settings().model_copy(update={"app_environment": "production"}))


def test_missing_or_symlink_endpoint_cannot_dispatch(tmp_path):
    path = tmp_path.resolve() / "absent.sock"
    with pytest.raises(LLMUnavailableError):
        local_endpoint._socket_identity(path)
    path.symlink_to(tmp_path)
    with pytest.raises(LLMUnavailableError):
        local_endpoint._socket_identity(path)


def test_unsupported_schema_and_quota_deny_before_prompt(runtime):
    pair, ledger, calls, _ = runtime
    with pytest.raises(LLMUnsupportedCapabilityError):
        pair.generator.generate_structured(MESSAGES, response_schema={"type": "object"})
    assert not calls
    ledger.denial = "provider_quota_exhausted"
    with pytest.raises(LLMUnavailableError, match="quota"):
        complete(pair)
    assert [request.url.path for request in calls] == ["/props"]
    assert not ledger.attempts


@pytest.mark.parametrize("kind", ["redirect", "wrong_build", "too_few_slots", "wrong_model", "bad_tokens", "oversize"])
def test_protocol_denials_never_follow_or_replace_endpoint(runtime, monkeypatch, kind):
    pair, ledger, calls, respond = runtime

    def handler(request):
        if request.url.path == "/props" and kind == "redirect":
            calls.append(request)
            return httpx.Response(307, headers={"location": "https://unapproved.invalid/"})
        response = respond(request)
        if request.url.path == "/props" and kind in {"wrong_build", "too_few_slots"}:
            body = response.json()
            body.update({"build_info": "wrong"} if kind == "wrong_build" else {"total_slots": 0})
            return httpx.Response(200, json=body)
        if request.url.path == "/tokenize" and kind == "bad_tokens":
            return httpx.Response(200, json={"tokens": [True]})
        if request.url.path == "/completion":
            if kind == "wrong_model":
                return httpx.Response(200, json={**response.json(), "model": "wrong"})
            if kind == "oversize":
                return httpx.Response(200, json={"content": "x" * local_endpoint.MAX_BYTES})
        return response

    monkeypatch.setattr(pair.generator.delegate, "_transport", lambda: httpx.MockTransport(handler))
    with pytest.raises((LLMInvalidConfigurationError, LLMInvalidResponseError)):
        complete(pair)
    if kind in {"redirect", "wrong_build", "too_few_slots"}:
        assert len(calls) == 1 and not ledger.attempts
    else:
        assert ledger.results[-1].outcome == "unknown"


def test_source_revoked_after_reservation_stops_physical_send(runtime, monkeypatch):
    pair, ledger, calls, _ = runtime
    original = ledger.reserve_attempt
    revoked = False

    def reserve(*args, **kwargs):
        nonlocal revoked
        attempt = original(*args, **kwargs)
        revoked = True
        return attempt

    def guard():
        if revoked:
            raise ContextPreparationError("synthetic_permission_revoked")

    monkeypatch.setattr(ledger, "reserve_attempt", reserve)
    with bind_disclosure_guard(guard), pytest.raises(ContextPreparationError):
        complete(pair)
    assert [request.url.path for request in calls] == ["/props"]
    assert len(ledger.attempts) == 1
    assert ledger.results[-1].outcome == "failure"


def test_socket_replacement_between_count_and_generation_denies_send(runtime, monkeypatch):
    pair, ledger, calls, respond = runtime

    def handler(request):
        result = respond(request)
        if request.url.path == "/tokenize":
            monkeypatch.setattr(local_endpoint, "_socket_identity", lambda path: (1, 4, 5))
        return result

    monkeypatch.setattr(pair.generator.delegate, "_transport", lambda: httpx.MockTransport(handler))
    with pytest.raises(LLMInvalidConfigurationError, match="socket changed"):
        complete(pair)
    assert len(calls) == 2 and len(ledger.attempts) == 1


@pytest.mark.anyio
async def test_cancelled_generation_settles_uncertain_without_retry(runtime, monkeypatch):
    pair, ledger, calls, respond = runtime
    started = anyio.Event()

    async def handler(request):
        response = respond(request)
        if request.url.path == "/completion":
            started.set()
            await anyio.sleep_forever()
        return response

    monkeypatch.setattr(pair.generator.delegate, "_transport", lambda: httpx.MockTransport(handler))

    async def run():
        iterator = pair.generator.stream_events(
            MESSAGES, max_output_tokens=10, timeout_seconds=5, inference_context=CTX,
        )
        async with anyio.create_task_group() as group:
            group.start_soon(partial(anext, iterator))
            await started.wait()
            group.cancel_scope.cancel()
        await iterator.aclose()

    with anyio.fail_after(10):
        await run()
    assert [request.url.path for request in calls].count("/completion") == 1
    assert ledger.results[-1].outcome == "unknown"


@pytest.mark.anyio
async def test_buffered_local_completion_through_canonical_chat(runtime):
    from personal_ai.evaluation.real_tasks import load_manifest, run

    pair, ledger, calls, _ = runtime
    manifest, _ = load_manifest()
    config = settings(
        max_context_tokens=4096, max_response_tokens=128, summary_trigger_tokens=2048,
    )
    trace = Trace()
    rows = await run(config, pair, manifest, trace, uuid4(), manifest["cases"][:1])
    assert all(row["completed"] for row in rows)
    assert [row["source_selected"] for row in rows] == [False, True, True]
    assert [row["distractor_selected"] for row in rows] == [False, False, True]
    assert sum(request.url.path == "/completion" for request in calls) == 3
    assert sum(invocation.operation == "streaming" for invocation, _ in ledger.attempts) == 3
    events, _ = trace.snapshot()
    for row in rows:
        assert {"context", "count", "source_check", "dispatch", "settle", "output"} <= {
            event["event"] for event in events if event["request"] == row["request"]
        }


def test_settlement_failure_is_traced_without_changing_model_result(runtime, monkeypatch):
    pair, ledger, _, _ = runtime

    def unavailable(*args):
        raise OSError("synthetic ledger outage")

    monkeypatch.setattr(ledger, "settle_attempt", unavailable)
    trace = Trace()
    with trace.capture():
        assert complete(pair).text == "done"
    events, _ = trace.snapshot()
    assert [(event["state"], event["reason"]) for event in events if event["event"] == "settle"] == [
        ("unknown", "accounting"), ("unknown", "accounting"),
    ]
