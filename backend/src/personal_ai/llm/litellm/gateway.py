"""Personal AI's provider-neutral adapter over the pinned LiteLLM SDK.

LiteLLM is deliberately lazy-loaded here so its SDK types, callbacks, settings,
and request serialization remain below the Personal AI inference boundary.
"""

from __future__ import annotations

import asyncio
import contextvars
import importlib
import importlib.metadata
import logging
import math
import os
import threading
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Any, Literal
from urllib.parse import quote

import httpx

from personal_ai.llm.client import (
    BoundedTextStream,
    ChatMessage,
    EmbeddingResult,
    EmbeddingSpace,
    GenerationEvent,
    GenerationMetadata,
    GenerationResult,
    InferenceContext,
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
    LLMUnsupportedCapabilityError,
)
from personal_ai.settings import Settings
from personal_ai.usage.accounting import estimated_tokens, new_invocation, unit_reservations
from personal_ai.usage.contracts import (
    ProviderUsageAccounting,
)
from personal_ai.usage.profiles import endpoint_for_operation

logger = logging.getLogger(__name__)

LITELLM_VERSION = "1.102.1"


_SDK_LOCK = threading.RLock()
_SDK: Any | None = None
_CF_HOOK_INSTALLED = False
_CF_HOOKS: tuple[Callable[..., Any], Callable[..., Any]] | None = None

from personal_ai.llm.litellm.accounting import (
    _asettle_error,
    _settle_error,
)
from personal_ai.llm.litellm.profiles import (
    _bind_endpoint_profile,
    _provider_profile,
    _ProviderProfile,
    _validate_external_provider,
    _validate_inference_context,
    _validate_schema,
)
from personal_ai.llm.litellm.request import (
    _contains_schema,
    _request_preserves_schema,  # noqa: F401 - historical gateway compatibility export
    _response_format,
    _role_name,
    _sdk_messages,
)
from personal_ai.llm.litellm.streaming import (
    _field,
    _mark_estimated,
    _parse_generation_wire,
    _sdk_completion_text,
    _sdk_refusal,
    _sdk_text_deltas,
    _terminal_error_code,
    _usage_from_sdk,
)
from personal_ai.llm.litellm.transport import (
    _MAX_COMPLETION_RESPONSE_BYTES,
    _MAX_COUNT_RESPONSE_BYTES,
    _MAX_EMBEDDING_RESPONSE_BYTES,
    _MAX_STREAM_EVENT_BYTES,  # noqa: F401 - historical gateway compatibility export
    _MAX_STREAM_LINE_BYTES,  # noqa: F401 - historical gateway compatibility export
    _MAX_STREAM_RESPONSE_BYTES,
    _bounded_timeout,
    _BoundedAsyncTransport,
    _BoundedSyncTransport,
    _close_async_client,
    _close_sdk_stream,
    _close_sync_client,
    _is_non_success_or_redirect,
    _raise_for_status,
    _raise_safe_error,
    _rate_limit_metadata,
    _remaining,
    _sdk_http_handler_types,
    _sync_remaining,
    _TransportState,
)


@dataclass(frozen=True, slots=True)
class _CloudflareHTTPContext:
    profile: _ProviderProfile
    handler: Any


_cloudflare_http_context: contextvars.ContextVar[_CloudflareHTTPContext | None] = (
    contextvars.ContextVar("personal_ai_litellm_cloudflare_http", default=None)
)


class LiteLLMGenerationClient:
    """Provider-selected generation adapter using LiteLLM below neutral contracts."""

    requires_inference_context = True
    transport_retries = 0
    max_http_requests_per_call = 1

    def __init__(
        self,
        settings: Settings,
        provider: Literal["gemini", "groq", "cloudflare_workers_ai"] | None = None,
        *,
        async_transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None,
        sync_transport_factory: Callable[[], httpx.BaseTransport] | None = None,
        usage_accounting: ProviderUsageAccounting | None = None,
        endpoint_profile=None,
    ):
        self._settings = settings
        selected = provider or settings.ai_provider.lower()
        self._profile = _provider_profile(settings, selected)
        self._async_transport_factory = async_transport_factory
        self._sync_transport_factory = sync_transport_factory
        self._usage_accounting = usage_accounting
        self.endpoint_profile = _bind_endpoint_profile(settings, selected, endpoint_profile)
        self.gateway_accounting_enabled = usage_accounting is not None
        self.identity = ProviderIdentity(
            self._profile.provider_id, self._profile.model_id, self._profile.serializer_id
        )
        operations = {"streaming", "bounded_generation"}
        if self._profile.structured_enabled:
            operations.add("structured_generation")
        self.capabilities = ProviderCapabilities(frozenset(operations))

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        inference_context: InferenceContext | None = None,
    ) -> AsyncIterator[str]:
        bounded = self.stream_bounded(
            messages,
            max_output_tokens=self._settings.max_response_tokens,
            timeout_seconds=self._settings.request_timeout_seconds,
            inference_context=inference_context,
        )

        async def consume() -> AsyncIterator[str]:
            try:
                async for delta in bounded:
                    yield delta
            finally:
                await bounded.aclose()

        return consume()

    def stream_bounded(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_output_tokens: int,
        timeout_seconds: float,
        inference_context: InferenceContext | None = None,
    ) -> AsyncIterator[str]:
        return BoundedTextStream(
            self.stream_events(
                messages,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
                inference_context=inference_context,
            )
        )

    async def stream_events(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_output_tokens: int,
        timeout_seconds: float,
        inference_context: InferenceContext | None = None,
    ) -> AsyncIterator[GenerationEvent]:
        self.capabilities.require("streaming")
        self._validate_request(messages, inference_context)
        duration = _bounded_timeout(max_output_tokens, timeout_seconds, self._settings)
        deadline = asyncio.get_running_loop().time() + duration
        state = _TransportState(
            self._profile,
            "generation",
            True,
            _MAX_STREAM_RESPONSE_BYTES,
            deadline=monotonic() + duration,
            **self._usage_state_arguments(
                messages,
                operation="streaming",
                max_output_tokens=max_output_tokens,
            ),
        )
        handler, client = await self._make_async_handler(state, duration)
        stream: Any | None = None
        context_token = self._set_cloudflare_context(handler)
        sdk_usage: UsageMetadata | None = None
        has_non_whitespace_text = False
        try:
            await state.abegin_invocation()
            sdk = _load_litellm()
            arguments = self._completion_arguments(
                messages,
                max_output_tokens=max_output_tokens,
                timeout_seconds=duration,
                stream=True,
            )
            async with asyncio.timeout(_remaining(deadline)):
                stream = await sdk.acompletion(**arguments, client=handler)
            async for chunk in _iterate_sdk_stream(stream, deadline):
                usage = _usage_from_sdk(_field(chunk, "usage"))
                sdk_usage = usage or sdk_usage
                for delta in _sdk_text_deltas(chunk):
                    has_non_whitespace_text = has_non_whitespace_text or bool(delta.strip())
                    yield GenerationEvent.text_delta(delta)
            if state.async_stream is not None:
                await state.async_stream.drain(deadline)
            wire = _parse_generation_wire(
                self._profile,
                bytes(state.raw_body),
                streaming=True,
                require_completed=state.response_complete,
            )
            status = wire.status
            if status == "success" and not has_non_whitespace_text:
                status = "incomplete"
            metadata = GenerationMetadata(
                status=status,
                identity=ProviderIdentity(
                    self._profile.provider_id, wire.model_id, self._profile.serializer_id
                ),
                usage=wire.usage or _mark_estimated(sdk_usage),
                error_code=_terminal_error_code(status),
                rate_limits=_rate_limit_metadata(state.response_headers),
                invocation_id=(str(state.invocation.invocation_id) if state.invocation else None),
                attempt_ids=tuple(state.attempt_ids),
            )
            await state.asettle_current(
                status,
                error_code=metadata.error_code,
                usage=metadata.usage,
                rate_limits=metadata.rate_limits,
            )
            await state.afinish_invocation(status)
            yield GenerationEvent.terminal(metadata)
        except asyncio.CancelledError:
            await asyncio.shield(state.afinish_invocation("unknown"))
            raise
        except LLMError as error:
            await state.afinish_invocation(await _asettle_error(state, error))
            raise
        except Exception as error:  # noqa: BLE001 - LiteLLM exceptions can contain provider payloads.
            await state.afinish_invocation(await _asettle_error(state, error))
            _raise_safe_error(error, state)
        finally:
            await state.afinish_invocation("unknown")
            if stream is not None:
                await _close_sdk_stream(stream)
            if state.async_stream is not None:
                await state.async_stream.force_close()
            if context_token is not None:
                _cloudflare_http_context.reset(context_token)
            await _close_async_client(client)
            _reset_sdk_cache_callbacks()

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_output_tokens: int,
        timeout_seconds: float,
        inference_context: InferenceContext | None = None,
    ) -> GenerationResult:
        return self._generate(
            messages,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            inference_context=inference_context,
            response_schema=None,
        )

    def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        *,
        response_schema: Mapping[str, object],
        max_output_tokens: int,
        timeout_seconds: float,
        inference_context: InferenceContext | None = None,
    ) -> GenerationResult:
        self.capabilities.require("structured_generation")
        _validate_schema(response_schema)
        return self._generate(
            messages,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            inference_context=inference_context,
            response_schema=response_schema,
        )

    def _generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_output_tokens: int,
        timeout_seconds: float,
        inference_context: InferenceContext | None,
        response_schema: Mapping[str, object] | None,
    ) -> GenerationResult:
        self.capabilities.require("bounded_generation")
        self._validate_request(messages, inference_context)
        duration = _bounded_timeout(max_output_tokens, timeout_seconds, self._settings)
        deadline = monotonic() + duration
        state = _TransportState(
            self._profile,
            "generation",
            False,
            _MAX_COMPLETION_RESPONSE_BYTES,
            required_schema=response_schema,
            deadline=deadline,
            **self._usage_state_arguments(
                messages,
                operation=(
                    "structured_generation" if response_schema is not None else "bounded_generation"
                ),
                max_output_tokens=max_output_tokens,
            ),
        )
        handler, client = self._make_sync_handler(state, duration)
        context_token = self._set_cloudflare_context(handler)
        try:
            state.begin_invocation()
            sdk = _load_litellm()
            arguments = self._completion_arguments(
                messages,
                max_output_tokens=max_output_tokens,
                timeout_seconds=_sync_remaining(deadline),
                stream=False,
                response_schema=response_schema,
            )
            _sync_remaining(deadline)
            response = sdk.completion(**arguments, client=handler)
            _sync_remaining(deadline)
            wire = _parse_generation_wire(
                self._profile,
                bytes(state.raw_body),
                streaming=False,
                require_completed=state.response_complete,
            )
            text = _sdk_completion_text(response)
            status = wire.status
            if status == "success" and not text.strip():
                status = "incomplete"
            refusal = _sdk_refusal(response) or wire.refused
            if refusal:
                status = "rejected"
            result = GenerationResult(
                text=text,
                metadata=GenerationMetadata(
                    status=status,
                    identity=ProviderIdentity(
                        self._profile.provider_id, wire.model_id, self._profile.serializer_id
                    ),
                    usage=(
                        wire.usage
                        or (
                            None
                            if state.sdk_usage_supplemented
                            else _mark_estimated(_usage_from_sdk(_field(response, "usage")))
                        )
                    ),
                    error_code=_terminal_error_code(status),
                    rate_limits=_rate_limit_metadata(state.response_headers),
                    invocation_id=(
                        str(state.invocation.invocation_id) if state.invocation else None
                    ),
                    attempt_ids=tuple(state.attempt_ids),
                ),
            )
            state.settle_current(
                result.metadata.status,
                error_code=result.metadata.error_code,
                usage=result.metadata.usage,
                rate_limits=result.metadata.rate_limits,
            )
            state.finish_invocation(result.metadata.status)
            _sync_remaining(deadline)
            return result
        except LLMError as error:
            state.finish_invocation(_settle_error(state, error))
            raise
        except Exception as error:  # noqa: BLE001 - LiteLLM exceptions can contain provider payloads.
            state.finish_invocation(_settle_error(state, error))
            _raise_safe_error(error, state)
        finally:
            state.finish_invocation("unknown")
            if context_token is not None:
                _cloudflare_http_context.reset(context_token)
            _close_sync_client(client)
            _reset_sdk_cache_callbacks()

    def _completion_arguments(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_output_tokens: int,
        timeout_seconds: float,
        stream: bool,
        response_schema: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        token_parameter = self._profile.max_tokens_parameter
        arguments: dict[str, Any] = {
            "model": self._profile.sdk_model,
            "custom_llm_provider": self._profile.sdk_provider,
            "api_base": self._profile.api_base,
            "api_key": self._profile.api_key,
            "messages": _sdk_messages(self._profile, messages),
            token_parameter: max_output_tokens,
            "timeout": timeout_seconds,
            "stream": stream,
            "num_retries": 0,
            "max_retries": 0,
            "caching": False,
            "drop_params": False,
            "fallbacks": [],
            "model_list": None,
            "no-log": True,
        }
        if response_schema is not None:
            arguments["response_format"] = _response_format(response_schema, self._profile.provider)
        return arguments

    def _validate_request(
        self,
        messages: Sequence[ChatMessage],
        inference_context: InferenceContext | None,
    ) -> None:
        _validate_inference_context(inference_context)
        if not messages or any(not isinstance(message, ChatMessage) for message in messages):
            raise LLMInvalidRequestError("at least one valid chat message is required")
        for message in messages:
            role = _role_name(message.role)
            if (
                role not in {"system", "user", "assistant"}
                or not isinstance(message.content, str)
                or not message.content.strip()
            ):
                raise LLMInvalidRequestError("chat messages must not be empty")
        if self._profile.provider == "gemini":
            if self._settings.ai_provider.lower() != "gemini":
                raise LLMInvalidConfigurationError("AI_PROVIDER must be 'gemini'")
            if not self._profile.api_key:
                raise LLMInvalidConfigurationError("AI_API_KEY is not configured")
        else:
            _validate_external_provider(self._settings, self._profile, inference_context)
        _assert_litellm_runtime_safe()

    def _usage_state_arguments(
        self,
        messages: Sequence[ChatMessage],
        *,
        operation: str,
        max_output_tokens: int | None,
    ) -> dict:
        if self._usage_accounting is None:
            return {}
        try:
            endpoint = endpoint_for_operation(
                self._settings,
                provider_id=self._profile.provider_id,
                model_id=self._profile.model_id,
                operation=operation,
                resolver=getattr(self._usage_accounting, "endpoint_profile_resolver", None),
            )
        except Exception as error:  # noqa: BLE001 - profile validation errors stay content-free
            logger.info(
                "provider_usage_endpoint_profile_unavailable error_class=%s", type(error).__name__
            )
            raise LLMInvalidConfigurationError(
                "provider usage endpoint profile is unavailable"
            ) from None
        input_estimate = min(
            2_000_000, sum(estimated_tokens(message.content) for message in messages)
        )
        invocation = new_invocation(
            endpoint,
            operation=operation,
            quota_operation=operation,
            input_tokens_estimate=input_estimate,
            output_tokens_bound=max_output_tokens,
        )
        return {
            "usage_accounting": self._usage_accounting,
            "invocation": invocation,
            "max_attempts": self._settings.provider_usage_max_attempts_per_request,
            "reservation_units": unit_reservations(
                input_tokens=input_estimate, output_tokens=max_output_tokens
            ),
        }

    async def _make_async_handler(
        self, state: _TransportState, timeout_seconds: float
    ) -> tuple[Any, httpx.AsyncClient]:
        sdk = _load_litellm()
        handler_type = _sdk_http_handler_types(sdk)[0]
        handler = handler_type(timeout=timeout_seconds)
        placeholder = handler.client
        await placeholder.aclose()
        transport = (
            self._async_transport_factory()
            if self._async_transport_factory is not None
            else httpx.AsyncHTTPTransport(retries=0)
        )
        bounded_transport = _BoundedAsyncTransport(transport, state)
        client = httpx.AsyncClient(
            transport=bounded_transport,
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"accept-encoding": "identity"},
        )
        handler.client = client
        return handler, client

    def _make_sync_handler(
        self, state: _TransportState, timeout_seconds: float
    ) -> tuple[Any, httpx.Client]:
        sdk = _load_litellm()
        handler_type = _sdk_http_handler_types(sdk)[1]
        handler = handler_type(timeout=timeout_seconds)
        handler.client.close()
        transport = (
            self._sync_transport_factory()
            if self._sync_transport_factory is not None
            else httpx.HTTPTransport(retries=0)
        )
        bounded_transport = _BoundedSyncTransport(transport, state)
        client = httpx.Client(
            transport=bounded_transport,
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"accept-encoding": "identity"},
        )
        handler.client = client
        return handler, client

    def _set_cloudflare_context(self, handler: Any):
        if self._profile.provider != "cloudflare_workers_ai":
            return None
        _install_cloudflare_client_hook()
        return _cloudflare_http_context.set(_CloudflareHTTPContext(self._profile, handler))


class LiteLLMTokenCounter:
    """Gemini countTokens shim tied to LiteLLM's pinned generation transform."""

    requires_inference_context = True
    count_confidence = "authoritative"
    transport_retries = 0
    max_http_requests_per_call = 1

    def __init__(
        self,
        settings: Settings,
        *,
        sync_transport_factory: Callable[[], httpx.BaseTransport] | None = None,
        usage_accounting: ProviderUsageAccounting | None = None,
        endpoint_profile=None,
    ):
        self.settings = settings
        self._profile = _provider_profile(settings, "gemini")
        self._sync_transport_factory = sync_transport_factory
        self._usage_accounting = usage_accounting
        self.endpoint_profile = _bind_endpoint_profile(settings, "gemini", endpoint_profile)
        if self.endpoint_profile is not None and self.endpoint_profile.counter is None:
            raise LLMInvalidConfigurationError("token counter is not registered for endpoint")
        self.counter_id = (
            self.endpoint_profile.counter.counter_id if self.endpoint_profile is not None else None
        )
        self.gateway_accounting_enabled = usage_accounting is not None
        self.identity = ProviderIdentity("gemini", settings.ai_model, "gemini-content-v1")
        self.capabilities = ProviderCapabilities(frozenset({"token_counting"}))

    def count(
        self,
        messages: Sequence[ChatMessage],
        *,
        response_schema: Mapping[str, object] | None = None,
        inference_context: InferenceContext | None = None,
    ) -> TokenCount:
        return self.count_with_timeout(
            messages,
            None,
            response_schema=response_schema,
            inference_context=inference_context,
        )

    def count_with_timeout(
        self,
        messages: Sequence[ChatMessage],
        timeout_seconds: float | None,
        *,
        response_schema: Mapping[str, object] | None = None,
        inference_context: InferenceContext | None = None,
    ) -> TokenCount:
        _validate_inference_context(inference_context)
        if self.settings.ai_provider.lower() != "gemini":
            raise LLMInvalidConfigurationError("AI_PROVIDER must be 'gemini'")
        if not self._profile.api_key:
            raise LLMInvalidConfigurationError("AI_API_KEY is not configured")
        if not messages or any(not isinstance(message, ChatMessage) for message in messages):
            raise LLMInvalidRequestError("at least one valid chat message is required")
        if any(
            _role_name(message.role) not in {"system", "user", "assistant"}
            or not isinstance(message.content, str)
            or not message.content.strip()
            for message in messages
        ):
            raise LLMInvalidRequestError("chat messages must not be empty")
        if response_schema is not None:
            _validate_schema(response_schema)
        _assert_litellm_runtime_safe()
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.settings.request_timeout_seconds
        )
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise LLMInvalidRequestError("token count deadline is invalid")
        body = _gemini_generation_body(self._profile, messages, response_schema=response_schema)
        request_body = {
            "generateContentRequest": {
                "model": f"models/{self._profile.model_id.removeprefix('models/')}",
                **body,
            }
        }
        state = _TransportState(
            self._profile,
            "token_counting",
            False,
            _MAX_COUNT_RESPONSE_BYTES,
            required_schema=response_schema,
            deadline=monotonic() + timeout,
            **self._usage_state_arguments(messages),
        )
        handler_type = _sdk_http_handler_types(_load_litellm())[1]
        handler = handler_type(timeout=timeout)
        handler.client.close()
        transport = (
            self._sync_transport_factory()
            if self._sync_transport_factory is not None
            else httpx.HTTPTransport(retries=0)
        )
        http_client = httpx.Client(
            transport=_BoundedSyncTransport(transport, state),
            timeout=timeout,
            follow_redirects=False,
            headers={"accept-encoding": "identity"},
        )
        handler.client = http_client
        url = (
            f"{self._profile.api_base}/models/"
            f"{quote(self._profile.model_id.removeprefix('models/'), safe='-_.~')}:countTokens"
        )
        try:
            state.begin_invocation()
            response = handler.post(
                url,
                json=request_body,
                headers={"x-goog-api-key": self._profile.api_key},
                timeout=timeout,
            )
            status = state.response_status or response.status_code
            rate_limits = _rate_limit_metadata(state.response_headers)
            if _is_non_success_or_redirect(status):
                _raise_for_status(status, rate_limits)
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise LLMInvalidResponseError("provider token count was invalid")
            token_count = payload.get("totalTokens", payload.get("total_tokens"))
            if isinstance(token_count, bool) or not isinstance(token_count, int) or token_count < 0:
                raise LLMInvalidResponseError("provider token count was invalid")
            result = TokenCount(
                token_count,
                "provider",
                provider_id="gemini",
                model_id=self.settings.ai_model,
                serializer_id="gemini-content-v1",
                confidence="authoritative",
            )
            usage = UsageMetadata(
                input_tokens=token_count,
                total_tokens=token_count,
                source="provider",
                confidence="reported",
            )
            state.settle_current("success", usage=usage, rate_limits=rate_limits)
            state.finish_invocation("success")
            return result
        except LLMError as error:
            state.finish_invocation(_settle_error(state, error))
            raise
        except Exception as error:  # noqa: BLE001 - SDK errors may contain provider payloads.
            state.finish_invocation(_settle_error(state, error))
            _raise_safe_error(error, state)
        finally:
            state.finish_invocation("unknown")
            _close_sync_client(http_client)

    def _usage_state_arguments(self, messages: Sequence[ChatMessage]) -> dict:
        if self._usage_accounting is None:
            return {}
        input_estimate = min(
            2_000_000, sum(estimated_tokens(message.content) for message in messages)
        )
        try:
            endpoint = endpoint_for_operation(
                self.settings,
                provider_id="gemini",
                model_id=self.settings.ai_model,
                operation="token_counting",
                resolver=getattr(self._usage_accounting, "endpoint_profile_resolver", None),
            )
        except Exception as error:  # noqa: BLE001 - profile validation errors stay content-free
            logger.info(
                "provider_usage_endpoint_profile_unavailable error_class=%s", type(error).__name__
            )
            raise LLMInvalidConfigurationError(
                "provider usage endpoint profile is unavailable"
            ) from None
        invocation = new_invocation(
            endpoint,
            operation="token_counting",
            quota_operation="token_counting",
            input_tokens_estimate=input_estimate,
        )
        return {
            "usage_accounting": self._usage_accounting,
            "invocation": invocation,
            "max_attempts": self.settings.provider_usage_max_attempts_per_request,
            "reservation_units": unit_reservations(input_tokens=input_estimate),
        }


class LiteLLMEmbeddingClient:
    """Gemini embedding adapter preserving the persisted Personal AI space."""

    requires_inference_context = True

    def __init__(
        self,
        settings: Settings,
        *,
        sync_transport_factory: Callable[[], httpx.BaseTransport] | None = None,
        usage_accounting: ProviderUsageAccounting | None = None,
    ):
        self.settings = settings
        self._profile = _provider_profile(settings, "gemini")
        self._sync_transport_factory = sync_transport_factory
        self._usage_accounting = usage_accounting
        self.identity = ProviderIdentity(
            "google_genai", settings.memory_embedding_model, "gemini-embedding-v1"
        )
        self.capabilities = ProviderCapabilities(frozenset({"embeddings"}))

    def embed(
        self,
        texts: Sequence[str],
        *,
        query: bool = False,
        timeout: float | None = None,
        inference_context: InferenceContext | None = None,
    ) -> tuple[EmbeddingResult, ...]:
        self.capabilities.require("embeddings")
        _validate_inference_context(inference_context)
        if self.settings.ai_provider.lower() != "gemini":
            raise LLMInvalidConfigurationError("AI_PROVIDER must be 'gemini'")
        if not self._profile.api_key:
            raise LLMInvalidConfigurationError("AI_API_KEY is not configured")
        if not texts or any(
            not isinstance(text, str) or not text.strip() or len(text) > 20_000 for text in texts
        ):
            raise LLMInvalidRequestError("embedding input invalid")
        duration = timeout if timeout is not None else self.settings.memory_timeout_seconds
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise LLMInvalidRequestError("embedding deadline expired")
        _assert_litellm_runtime_safe()
        deadline = monotonic() + duration
        state = _TransportState(
            self._profile,
            "embeddings",
            False,
            _MAX_EMBEDDING_RESPONSE_BYTES,
            request_model_id=self.settings.memory_embedding_model,
            deadline=deadline,
            **self._usage_state_arguments(texts),
        )
        handler_type = _sdk_http_handler_types(_load_litellm())[1]
        handler = handler_type(timeout=duration)
        handler.client.close()
        transport = (
            self._sync_transport_factory()
            if self._sync_transport_factory is not None
            else httpx.HTTPTransport(retries=0)
        )
        client = httpx.Client(
            transport=_BoundedSyncTransport(transport, state),
            timeout=duration,
            follow_redirects=False,
            headers={"accept-encoding": "identity"},
        )
        handler.client = client
        task = "query" if query else "document"
        from personal_ai.memory.contracts import vector

        space = EmbeddingSpace(
            provider_id="google_genai",
            model_id=self.settings.memory_embedding_model,
            dimensions=self.settings.memory_embedding_dimensions,
            normalization="l2",
            document_task="RETRIEVAL_DOCUMENT",
            query_task="RETRIEVAL_QUERY",
            version="v1",
        )
        results: list[EmbeddingResult] = []
        try:
            state.begin_invocation()
            sdk = _load_litellm()
            batch_size = self.settings.memory_embedding_batch_size
            state.expected_request_count = math.ceil(len(texts) / batch_size)
            for start in range(0, len(texts), batch_size):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise LLMTimeoutError("embedding request timed out")
                batch = list(texts[start : start + batch_size])
                state.begin_embedding_batch(start // batch_size, batch)
                state.embedding_texts = tuple(batch)
                response = sdk.embedding(
                    model=f"gemini/{self.settings.memory_embedding_model}",
                    custom_llm_provider="gemini",
                    api_base=self._profile.api_base,
                    api_key=self._profile.api_key,
                    input=[f"personal-ai-text-placeholder-{index}" for index in range(len(batch))],
                    dimensions=self.settings.memory_embedding_dimensions,
                    task_type=space.query_task if query else space.document_task,
                    timeout=remaining,
                    num_retries=0,
                    max_retries=0,
                    caching=False,
                    drop_params=False,
                    **{"no-log": True},
                    client=handler,
                )
                data = _field(response, "data")
                if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
                    raise LLMInvalidResponseError("embedding response invalid")
                if len(data) != len(batch):
                    raise LLMInvalidResponseError("embedding response invalid")
                for item in data:
                    values = _field(item, "embedding")
                    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                        raise LLMInvalidResponseError("embedding response invalid")
                    results.append(
                        EmbeddingResult(
                            values=vector(values, space.dimensions),
                            space=space,
                            task=task,
                        )
                    )
                state.settle_current("success")
                if monotonic() >= deadline:
                    raise LLMTimeoutError("embedding request timed out")
            if monotonic() > deadline:
                raise LLMTimeoutError("embedding request timed out")
            state.finish_invocation("success")
            return tuple(results)
        except LLMError as error:
            state.finish_invocation(_settle_error(state, error))
            raise
        except Exception as error:  # noqa: BLE001 - SDK errors may contain provider payloads.
            state.finish_invocation(_settle_error(state, error))
            _raise_safe_error(error, state)
        finally:
            state.finish_invocation("unknown")
            _close_sync_client(client)
            _reset_sdk_cache_callbacks()

    def _usage_state_arguments(self, texts: Sequence[str]) -> dict:
        if self._usage_accounting is None:
            return {}
        input_estimate = min(2_000_000, sum(estimated_tokens(text) for text in texts))
        try:
            endpoint = endpoint_for_operation(
                self.settings,
                provider_id="google_genai",
                model_id=self.settings.memory_embedding_model,
                operation="embeddings",
                resolver=getattr(self._usage_accounting, "endpoint_profile_resolver", None),
            )
        except Exception as error:  # noqa: BLE001 - profile validation errors stay content-free
            logger.info(
                "provider_usage_endpoint_profile_unavailable error_class=%s", type(error).__name__
            )
            raise LLMInvalidConfigurationError(
                "provider usage endpoint profile is unavailable"
            ) from None
        invocation = new_invocation(
            endpoint,
            operation="embeddings",
            quota_operation="embeddings",
            input_tokens_estimate=input_estimate,
        )
        return {
            "usage_accounting": self._usage_accounting,
            "invocation": invocation,
            "max_attempts": self.settings.provider_usage_max_attempts_per_request,
            "reservation_units": unit_reservations(input_tokens=input_estimate),
        }


async def _iterate_sdk_stream(stream: Any, deadline: float):
    iterator = stream.__aiter__()
    while True:
        try:
            async with asyncio.timeout(_remaining(deadline)):
                chunk = await anext(iterator)
        except StopAsyncIteration:
            return
        yield chunk


def _gemini_generation_body(
    profile: _ProviderProfile,
    messages: Sequence[ChatMessage],
    *,
    response_schema: Mapping[str, object] | None,
) -> dict[str, Any]:
    _load_litellm()
    try:
        from litellm.llms.vertex_ai.gemini.transformation import _transform_request_body
        from litellm.utils import get_optional_params

        model = profile.model_id.removeprefix("models/")
        response_format = (
            _response_format(response_schema, "gemini") if response_schema is not None else None
        )
        optional_params = get_optional_params(
            model=model,
            custom_llm_provider="gemini",
            max_tokens=None,
            response_format=response_format,
            drop_params=False,
            messages=_sdk_messages(profile, messages),
        )
        transformed = _transform_request_body(
            messages=_sdk_messages(profile, messages),
            model=model,
            optional_params=optional_params,
            custom_llm_provider="gemini",
            litellm_params={
                "custom_llm_provider": "gemini",
                "api_base": profile.api_base,
                "api_key": profile.api_key,
            },
            cached_content=None,
        )
    except Exception as error:  # noqa: BLE001 - pinned SDK internals can raise varied types.
        raise LLMInvalidConfigurationError(
            f"pinned LiteLLM Gemini serializer is unavailable ({type(error).__name__})"
        ) from None
    if not isinstance(transformed, Mapping):
        raise LLMInvalidRequestError("Gemini request serialization was invalid")
    body = dict(transformed)
    if response_schema is not None and not _contains_schema(body, response_schema):
        raise LLMUnsupportedCapabilityError(
            "LiteLLM did not preserve the required Gemini response schema"
        )
    return body


def _load_litellm() -> Any:
    global _SDK
    if _SDK is None:
        with _SDK_LOCK:
            if _SDK is None:
                # Prevent the optional model-price map download during SDK import.
                os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
                os.environ["LITELLM_LOG"] = "CRITICAL"
                try:
                    sdk = importlib.import_module("litellm")
                except Exception as error:  # noqa: BLE001 - SDK import may fail in varied ways.
                    raise LLMInvalidConfigurationError(
                        f"LiteLLM SDK {LITELLM_VERSION} could not be loaded ({type(error).__name__})"
                    ) from None
                try:
                    version = importlib.metadata.version("litellm")
                except importlib.metadata.PackageNotFoundError:
                    version = None
                if version != LITELLM_VERSION:
                    raise LLMInvalidConfigurationError(
                        "LiteLLM SDK version does not match the lockfile"
                    )
                if getattr(sdk, "cache", None) is not None or any(
                    bool(getattr(sdk, name, None))
                    for name in (
                        "callbacks",
                        "input_callback",
                        "success_callback",
                        "failure_callback",
                        "_async_input_callback",
                        "_async_success_callback",
                        "_async_failure_callback",
                        "pre_call_rules",
                        "post_call_rules",
                    )
                ):
                    raise LLMInvalidConfigurationError(
                        "LiteLLM cache and content hooks must be disabled"
                    )
                sdk.disable_cache()
                sdk.disable_anthropic_gemini_context_caching_transform = True
                sdk.suppress_debug_info = True
                sdk.turn_off_message_logging = True
                sdk.log_raw_request_response = False
                sdk.set_verbose = False
                _suppress_litellm_logging()
                _SDK = sdk
    return _SDK


def _assert_litellm_runtime_safe() -> None:
    sdk = _load_litellm()
    _suppress_litellm_logging()
    hook_names = (
        "callbacks",
        "input_callback",
        "success_callback",
        "failure_callback",
        "_async_input_callback",
        "_async_success_callback",
        "_async_failure_callback",
        "pre_call_rules",
        "post_call_rules",
    )
    if any(bool(getattr(sdk, name, None)) for name in hook_names):
        raise LLMInvalidConfigurationError("LiteLLM content hooks must be disabled")
    if (
        getattr(sdk, "cache", None) is not None
        or bool(getattr(sdk, "model_fallbacks", None))
        or bool(getattr(sdk, "model_alias_map", None))
        or getattr(sdk, "global_disable_no_log_param", False)
        or getattr(sdk, "turn_off_message_logging", False) is not True
        or getattr(sdk, "log_raw_request_response", True)
        or getattr(sdk, "suppress_debug_info", False) is not True
        or getattr(sdk, "drop_params", False)
        or getattr(sdk, "modify_params", False)
        or getattr(sdk, "num_retries_per_request", None) not in {None, 0}
        or getattr(sdk, "num_retries", None) not in {None, 0}
    ):
        raise LLMInvalidConfigurationError("LiteLLM runtime settings are not safe")


def _suppress_litellm_logging() -> None:
    """Suppress the pinned SDK's content-bearing diagnostics at every call."""
    names = {
        "LiteLLM",
        "LiteLLM Proxy",
        "LiteLLM Router",
        *(
            name
            for name in logging.Logger.manager.loggerDict
            if name.startswith(("LiteLLM", "litellm"))
        ),
    }
    for name in names:
        sdk_logger = logging.getLogger(name)
        sdk_logger.setLevel(logging.CRITICAL)
        sdk_logger.propagate = False


def _reset_sdk_cache_callbacks() -> None:
    sdk = _load_litellm()
    sdk.disable_cache()


def _install_cloudflare_client_hook() -> None:
    global _CF_HOOK_INSTALLED, _CF_HOOKS
    if _CF_HOOK_INSTALLED:
        return
    with _SDK_LOCK:
        if _CF_HOOK_INSTALLED:
            return
        module = importlib.import_module("litellm.llms.custom_httpx.llm_http_handler")
        original_async = module.get_async_httpx_client
        original_sync = module._get_httpx_client

        def get_async_httpx_client(*args: Any, **kwargs: Any):
            context = _cloudflare_http_context.get()
            if context is not None:
                return context.handler
            return original_async(*args, **kwargs)

        def get_httpx_client(*args: Any, **kwargs: Any):
            context = _cloudflare_http_context.get()
            if context is not None:
                return context.handler
            return original_sync(*args, **kwargs)

        module.get_async_httpx_client = get_async_httpx_client
        module._get_httpx_client = get_httpx_client
        _CF_HOOKS = (get_async_httpx_client, get_httpx_client)
        _CF_HOOK_INSTALLED = True
