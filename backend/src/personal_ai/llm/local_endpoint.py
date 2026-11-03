"""Bounded llama.cpp native inference over an operator-owned Unix socket."""

import json
import math
import os
import stat
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from threading import Lock
from time import monotonic

import anyio
import httpx

from personal_ai.context.providers import ContextPreparationError
from personal_ai.llm.client import (
    GenerationEvent,
    GenerationMetadata,
    GenerationResult,
    ProviderCapabilities,
    ProviderIdentity,
    TokenCount,
    UsageMetadata,
)
from personal_ai.llm.errors import (
    LLMError,
    LLMInvalidConfigurationError,
    LLMInvalidRequestError,
    LLMInvalidResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from personal_ai.routing.contracts import (
    CounterCompatibility,
    DataUsePolicy,
    EndpointProfile,
    ProviderAccessPolicy,
    QuotaBucket,
)
from personal_ai.usage.async_call import AsyncProviderCall
from personal_ai.usage.contracts import UsageAdmissionDenied
from personal_ai.usage.profiles import from_profile
from personal_ai.usage.trace import Event, Reason, State, emit

PROVIDER = "local_llama"
OPERATIONS = frozenset({"streaming", "bounded_generation", "token_counting"})
MAX_BYTES = 256 * 1024
CONTEXT_TOKENS = 4096
OUTPUT_TOKENS = 512
MAX_TIMEOUT = 120
_send_slot = Lock()


def local_profile(settings):
    path = Path(settings.local_llama_socket)
    if (
        settings.app_environment not in {"local", "test"}
        or settings.auth_mode != "development"
        or settings.inference_cost_mode != "local_only"
        or not path.is_absolute()
        or str(path) != settings.local_llama_socket
        or ".." in path.parts
        or path.suffix != ".sock"
        or len(os.fsencode(path)) > 100
        or not settings.local_llama_model_sha256
        or not settings.local_llama_build
        or not settings.local_llama_approval
    ):
        raise LLMInvalidConfigurationError("explicit private local inference configuration required")
    facts = {
        "endpoint_profile_id": "local_llama:generation",
        "endpoint_id": "unix-" + sha256(os.fsencode(path)).hexdigest(),
        "deployment_id": settings.local_llama_build,
        "account_scope_id": "local_llama:operator",
        "credential_scope_id": "local_llama:private-socket",
        "provider_id": PROVIDER,
        "model_id": "sha256-" + settings.local_llama_model_sha256,
        "serializer_id": "local-llama-role-json-token-ids-v1",
    }
    return EndpointProfile(
        **facts, profile_version=1, credential_source="none",
        credential_reference="none:", tier_id="local",
        execution_mode="LOCAL_ONLY", cost_class="LOCAL_NO_CHARGE",
        enabled=True, capabilities=OPERATIONS, runtime_id="llama-cpp-native-http-v1",
        context_limit_tokens=CONTEXT_TOKENS, max_output_tokens=OUTPUT_TOKENS,
        access_policy=ProviderAccessPolicy(
            auth_mode="none", selection_mode="explicit_only",
            credential_runtime="none", automation_eligible=False,
        ),
        data_use_policy=DataUsePolicy(
            status="approved", max_sensitivity="sensitive",
            policy_reference=settings.local_llama_approval,
        ),
        counter=CounterCompatibility(
            **facts, counter_id="llama-cpp-tokenize", approved=True,
            confidence="authoritative", provenance_reference=settings.local_llama_approval,
        ),
        quota_membership="verified",
        quota_buckets=(QuotaBucket(
            bucket_id="local_llama:requests", authority_scope_id="local_llama:operator",
            operations=OPERATIONS, unit="requests", window_seconds=60,
            source="operator_attestation", confidence="verified",
            evidence_reference=settings.local_llama_approval, limit=60,
        ),),
    )


def _socket_identity(path):
    """Resolve only the configured socket in a private, operator-owned directory."""
    try:
        if path.resolve(strict=True) != path:
            raise OSError
        owner = os.geteuid()
        for directory in path.parents:
            metadata = directory.stat()
            if metadata.st_uid not in {owner, 0} or (
                metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX
            ):
                raise OSError
        parent = path.parent.stat()
        endpoint = path.lstat()
        if (
            parent.st_uid != owner or parent.st_mode & 0o077
            or endpoint.st_uid != owner or not stat.S_ISSOCK(endpoint.st_mode)
        ):
            raise OSError
        return endpoint.st_dev, endpoint.st_ino, endpoint.st_ctime_ns
    except (OSError, RuntimeError):
        raise LLMUnavailableError("private local inference socket unavailable") from None


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()


async def _request(client, path, payload=None):
    body = None if payload is None else _json_bytes(payload)
    if body is not None and len(body) > MAX_BYTES:
        raise LLMInvalidRequestError("local inference request exceeds its byte ceiling")
    async with client.stream(
        "GET" if body is None else "POST", path, content=body,
        headers={"Accept-Encoding": "identity", "Content-Type": "application/json"},
    ) as response:
        if response.status_code != 200 or response.headers.get("content-encoding", "identity") != "identity":
            raise LLMInvalidResponseError("local inference response protocol mismatch")
        if response.headers.get("content-type", "").split(";")[0] != "application/json":
            raise LLMInvalidResponseError("local inference response protocol mismatch")
        data = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=8192):
            if len(data) + len(chunk) > MAX_BYTES:
                raise LLMInvalidResponseError("local inference response exceeds its byte ceiling")
            data.extend(chunk)
    try:
        result = json.loads(data)
    except (ValueError, RecursionError):
        raise LLMInvalidResponseError("local inference response is malformed") from None
    if not isinstance(result, dict) or "error" in result:
        raise LLMInvalidResponseError("local inference response is malformed")
    return result


@dataclass(frozen=True, slots=True)
class LocalTokenCount(TokenCount):
    # Token IDs can reconstruct the prompt and must stay out of diagnostics.
    token_ids: tuple[int, ...] = field(default=(), repr=False)
    socket_identity: tuple[int, ...] = field(default=(), repr=False)


class LocalEndpoint:
    requires_inference_context = True
    uses_prepared_input = True
    count_confidence = "authoritative"
    capabilities = ProviderCapabilities(OPERATIONS)

    def __init__(self, settings, profile, accounting):
        self.path = Path(settings.local_llama_socket)
        self.profile = profile
        self.identity = ProviderIdentity(PROVIDER, profile.model_id, profile.serializer_id)
        self.accounting = accounting
        self.timeout = min(settings.request_timeout_seconds, MAX_TIMEOUT)

    def _transport(self):
        return httpx.AsyncHTTPTransport(uds=str(self.path), trust_env=False, retries=0)

    async def _verify(self, client):
        props = await _request(client, "/props")
        defaults = props.get("default_generation_settings")
        model_path = props.get("model_path")
        if (
            props.get("build_info") != self.profile.deployment_id
            or props.get("model_alias") != self.identity.model_id
            or type(props.get("total_slots")) is not int or props["total_slots"] != 1
            or not isinstance(model_path, str) or Path(model_path).name != self.identity.model_id + ".gguf"
            or not isinstance(defaults, dict) or defaults.get("n_ctx") != CONTEXT_TOKENS
        ):
            raise LLMInvalidConfigurationError("local inference server identity or bounds mismatch")

    async def _call(self, operation, path, payload, timeout, parse, expected_socket=None):
        if not math.isfinite(timeout) or timeout <= 0:
            raise LLMTimeoutError("local inference deadline expired")
        if len(_json_bytes(payload)) > MAX_BYTES:
            raise LLMInvalidRequestError("local inference request exceeds its byte ceiling")
        if not _send_slot.acquire(blocking=False):
            emit(Event.ADMISSION, State.DENIED, operation=operation, reason=Reason.SLOT_BUSY)
            raise LLMUnavailableError("local inference slot unavailable")
        call = None
        state, outcome, usage = State.UNKNOWN, "unknown", None
        dispatched = False
        start = monotonic()
        try:
            with anyio.fail_after(min(timeout, self.timeout)):
                socket = _socket_identity(self.path)
                if expected_socket is not None and socket != expected_socket:
                    raise LLMInvalidConfigurationError("local inference socket changed")
                async with httpx.AsyncClient(
                    transport=self._transport(), base_url="http://local-inference.invalid",
                    follow_redirects=False, trust_env=False, timeout=None,
                ) as client:
                    await self._verify(client)
                    emit(Event.ENDPOINT, State.OK, operation=operation)
                    try:
                        call = await AsyncProviderCall.begin(
                            self.accounting, from_profile(self.profile), operation=operation,
                            quota_operation=operation, max_attempts=1,
                        )
                    except Exception:  # noqa: BLE001 - hide ledger implementation details
                        emit(Event.RESERVE, State.DENIED, operation=operation, reason=Reason.ACCOUNTING)
                        raise LLMUnavailableError("local inference accounting unavailable") from None
                    try:
                        await call.reserve()
                    except UsageAdmissionDenied:
                        state, outcome = State.DENIED, "rejected"
                        emit(Event.RESERVE, State.DENIED, invocation=call.invocation,
                             operation=operation, reason=Reason.QUOTA)
                        raise LLMUnavailableError("local inference quota denied") from None
                    except (LLMError, ContextPreparationError):
                        state, outcome = State.DENIED, "rejected"
                        emit(Event.RESERVE, State.DENIED, invocation=call.invocation, operation=operation)
                        raise
                    except Exception:  # noqa: BLE001 - hide ledger implementation details
                        emit(Event.RESERVE, State.DENIED, invocation=call.invocation, operation=operation)
                        raise LLMUnavailableError("local inference accounting unavailable") from None
                    attempt = call.attempt
                    emit(Event.RESERVE, State.OK, invocation=call.invocation, attempt=attempt,
                         operation=operation, units="reserved", cost="local_no_provider_charge",
                         input_tokens=dict(attempt.reservation_units).get("input_tokens"),
                         output_tokens=dict(attempt.reservation_units).get("output_tokens"))
                    await anyio.to_thread.run_sync(self.accounting.check_send, call.invocation)
                    if _socket_identity(self.path) != socket:
                        raise LLMInvalidConfigurationError("local inference socket changed")
                    await anyio.lowlevel.checkpoint()
                    dispatched = True
                    emit(Event.DISPATCH, State.OK, invocation=call.invocation, attempt=attempt,
                         operation=operation, cost="local_no_provider_charge")
                    parsed, usage, outcome = parse(await _request(client, path, payload))
                    state = State.OK if outcome == "success" else State.INCOMPLETE
                    if operation != "token_counting":
                        emit(Event.OUTPUT, state, invocation=call.invocation, attempt=attempt,
                             operation=operation, elapsed_ms=int((monotonic() - start) * 1000))
                    return parsed, usage, call, socket, outcome
        except TimeoutError:
            state = State.TIMEOUT
            raise LLMTimeoutError("local inference deadline expired") from None
        except anyio.get_cancelled_exc_class():
            state = State.CANCELLED
            raise
        except LLMInvalidConfigurationError:
            state = State.DENIED
            emit(Event.ENDPOINT, state, operation=operation, reason=Reason.ENDPOINT_IDENTITY)
            raise
        except ContextPreparationError:
            state = State.DENIED
            raise
        except httpx.HTTPError:
            raise LLMUnavailableError("local inference transport unavailable") from None
        finally:
            try:
                if call is not None:
                    with anyio.CancelScope(shield=True):
                        recorded = await call.finish(
                            outcome if dispatched or outcome == "rejected" else "failure",
                            usage=usage,
                        )
                    emit(Event.SETTLE, state if recorded else State.UNKNOWN,
                         invocation=call.invocation, attempt=call.attempt,
                         reason=None if recorded else Reason.ACCOUNTING,
                         operation=operation, elapsed_ms=int((monotonic() - start) * 1000),
                         input_tokens=usage.input_tokens if usage else None,
                         output_tokens=usage.output_tokens if usage else None,
                         units="reported" if usage else "unknown", cost="local_no_provider_charge")
                elif state != State.OK:
                    emit(Event.ENDPOINT, state, operation=operation,
                         elapsed_ms=int((monotonic() - start) * 1000))
            finally:
                _send_slot.release()

    def count_with_timeout(self, messages, timeout_seconds, *, response_schema=None, inference_context=None):
        if response_schema is not None or not messages:
            raise LLMInvalidRequestError("local inference requires unstructured chat messages")
        # Separate role boundaries from untrusted content. Tokenize with special
        # parsing disabled and dispatch exactly the returned integer sequence.
        prompt = bytearray(b"Continue this conversation as the assistant.\n")
        for message in messages:
            if len(message.content) > MAX_BYTES:
                raise LLMInvalidRequestError("local inference request exceeds its byte ceiling")
            line = _json_bytes([message.role, message.content])
            if len(prompt) + len(line) >= MAX_BYTES:
                raise LLMInvalidRequestError("local inference request exceeds its byte ceiling")
            prompt.extend(line)
            prompt.extend(b"\n")
        prompt.extend(b'["assistant", ')
        timeout = self.timeout if timeout_seconds is None else timeout_seconds
        return anyio.run(self._count, prompt.decode(), timeout)

    async def _count(self, prompt, timeout):
        def parse(body):
            tokens = body.get("tokens")
            if not isinstance(tokens, list) or not tokens or any(
                type(token) is not int or not 0 <= token <= 2**31 - 1 for token in tokens
            ):
                raise LLMInvalidResponseError("local inference tokenizer returned invalid token IDs")
            return tuple(tokens), None, "success"

        tokens, _, _, socket, _ = await self._call(
            "token_counting", "/tokenize",
            {"content": prompt, "add_special": True, "parse_special": False}, timeout, parse,
        )
        return LocalTokenCount(
            len(tokens), "provider", PROVIDER, self.identity.model_id,
            self.identity.serializer_id, "authoritative", tokens, socket,
        )

    async def _generate(self, operation, *, prepared_input, max_output_tokens, timeout_seconds):
        count = prepared_input.token_count
        if not isinstance(count, LocalTokenCount) or count.tokens != len(count.token_ids):
            raise LLMInvalidRequestError("local inference requires exact prepared tokens")

        def parse(body):
            text = body.get("content")
            stop = body.get("stop_type")
            input_tokens = body.get("tokens_evaluated")
            output_tokens = body.get("tokens_predicted")
            if (
                body.get("model") != self.identity.model_id
                or body.get("stop") is not True or body.get("truncated") is not False
                or stop not in ("eos", "limit")
                or not isinstance(text, str) or not text.strip()
                or (input_tokens is not None and (type(input_tokens) is not int or input_tokens != count.tokens))
                or (output_tokens is not None and (
                    type(output_tokens) is not int or not 0 <= output_tokens <= max_output_tokens
                ))
            ):
                raise LLMInvalidResponseError("local inference completion violated its contract")
            usage = None
            if input_tokens is not None or output_tokens is not None:
                usage = UsageMetadata(input_tokens=input_tokens, output_tokens=output_tokens)
            return text, usage, "success" if stop == "eos" else "incomplete"

        text, usage, call, _, outcome = await self._call(
            operation, "/completion", {
                "prompt": count.token_ids, "n_predict": max_output_tokens, "stream": False,
                "cache_prompt": False, "temperature": 0, "seed": 42,
                "response_fields": [
                    "model", "content", "stop", "stop_type", "truncated",
                    "tokens_evaluated", "tokens_predicted",
                ],
            }, timeout_seconds, parse, count.socket_identity,
        )
        # Preserve incomplete terminal state even if some text was produced.
        return GenerationResult(text, GenerationMetadata(
            outcome, self.identity, usage,
            invocation_id=str(call.invocation.invocation_id),
            attempt_ids=(str(call.attempt.attempt_id),),
        ))

    def complete(self, messages, *, inference_context=None, **kwargs):
        return anyio.run(lambda: self._generate("bounded_generation", **kwargs))

    async def stream_events(self, messages, *, inference_context=None, **kwargs):
        # One validated buffered response. The chat event API does not require
        # the provider to expose an unbounded or partial upstream SSE stream.
        result = await self._generate("streaming", **kwargs)
        if result.metadata.status == "success":
            yield GenerationEvent.text_delta(result.text)
        yield GenerationEvent.terminal(result.metadata)
