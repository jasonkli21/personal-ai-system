"""LiteLLM transport behavior."""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
import json
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal
from uuid import uuid4

import anyio
import httpx

from personal_ai.llm.client import (
    ProviderRateLimitMetadata,
    UsageMetadata,
)
from personal_ai.llm.errors import (
    LLMError,
    LLMInvalidConfigurationError,
    LLMInvalidRequestError,
    LLMInvalidResponseError,
    LLMRateLimitedError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMUnsupportedCapabilityError,
)
from personal_ai.llm.litellm.accounting import _exception_chain_contains_timeout
from personal_ai.llm.litellm.profiles import _ProviderProfile, _request_is_approved
from personal_ai.llm.litellm.request import _request_preserves_schema
from personal_ai.llm.litellm.streaming import (
    _merge_model_identity,
    _parse_non_negative_int,
    _sse_finish_reason,
    _sse_payload_has_text,
)
from personal_ai.settings import Settings
from personal_ai.usage.accounting import estimated_tokens, unit_reservations
from personal_ai.usage.contracts import (
    AttemptMetadata,
    AttemptResult,
    InvocationMetadata,
    ProviderUsageAccounting,
    UsageAdmissionDenied,
)

_MAX_COMPLETION_RESPONSE_BYTES = 1_048_576

_MAX_STREAM_RESPONSE_BYTES = 2_097_152

_MAX_STREAM_LINE_BYTES = 131_072

_MAX_STREAM_EVENT_BYTES = 131_072

_MAX_COUNT_RESPONSE_BYTES = 65_536

_MAX_EMBEDDING_RESPONSE_BYTES = 4_194_304

_MAX_REQUEST_BYTES = 2_097_152

_RESET_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h)")
logger = logging.getLogger(__name__)


def _sdk_compatible_body(raw: bytes, state: _TransportState) -> bytes:
    """Patch pinned response-parser requirements while retaining raw evidence.

    LiteLLM 1.102.1 rejects otherwise valid Gemini completions when the provider
    omits optional usageMetadata. Its Groq transform also unconditionally reads
    service_tier from a LiteLLM ModelResponse. The SDK sees an empty usage field
    or a default service tier for parsing, while Personal AI derives identity,
    terminal state, and usage only from state.raw_body.
    """
    if (
        state.streaming
        or state.profile.provider not in {"gemini", "groq", "cloudflare_workers_ai"}
        or state.operation != "generation"
    ):
        return raw
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return raw
    if not isinstance(payload, dict):
        return raw
    modified = False
    if state.profile.provider == "gemini" and "usageMetadata" not in payload:
        payload["usageMetadata"] = {}
        state.sdk_usage_supplemented = True
        modified = True
    if state.profile.provider == "groq" and "service_tier" not in payload:
        payload["service_tier"] = "default"
        modified = True
    if not modified:
        return raw
    compatible = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(compatible) > state.max_response_bytes:
        state.violation = "response_size"
        raise _TransportFault("response_size")
    return compatible


@dataclass(slots=True)
class _TransportState:
    profile: _ProviderProfile
    operation: Literal["generation", "token_counting", "embeddings"]
    streaming: bool
    max_response_bytes: int
    response_status: int | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    raw_body: bytearray = field(default_factory=bytearray)
    request_count: int = 0
    response_complete: bool = False
    violation: (
        Literal[
            "endpoint",
            "request_size",
            "response_size",
            "response_encoding",
            "required_parameter",
            "generation_replay",
        ]
        | None
    ) = None
    line_bytes: int = 0
    event_bytes: int = 0
    line_ends_with_cr: bool = False
    request_model_id: str | None = None
    sdk_usage_supplemented: bool = False
    required_schema: Mapping[str, object] | None = None
    deadline: float | None = None
    embedding_texts: tuple[str, ...] | None = None
    sse_line_buffer: bytearray = field(default_factory=bytearray)
    sse_data_lines: list[bytes] = field(default_factory=list)
    sse_model_id: str | None = None
    sse_finish_reason: str | None = None
    sse_done: bool = False
    async_stream: Any | None = None
    stream_error: LLMError | None = None
    usage_accounting: ProviderUsageAccounting | None = None
    invocation: InvocationMetadata | None = None
    invocation_started: bool = False
    max_attempts: int = 1
    reservation_units: tuple[tuple[str, int], ...] = (("requests", 1),)
    expected_request_count: int = 1
    embedding_batch_index: int | None = None
    sent_embedding_batches: set[int] = field(default_factory=set)
    active_attempt: AttemptMetadata | None = None
    active_attempt_started_monotonic: float | None = None
    last_attempt_id: Any | None = None
    attempt_ids: list[str] = field(default_factory=list)
    invocation_finalized: bool = False
    accounting_violation: str | None = None

    def record_request(self, request: httpx.Request) -> None:
        if not _request_is_approved(
            request, self.profile, self.operation, self.streaming, self.request_model_id
        ):
            self.violation = "endpoint"
            raise _TransportFault("endpoint")
        if self.operation == "embeddings":
            self._reset_response_evidence()
            self._rewrite_embedding_request(request)
        self._apply_deadline_to_request(request)
        content_length = _parse_non_negative_int(request.headers.get("content-length"))
        if content_length is not None and content_length > _MAX_REQUEST_BYTES:
            self.violation = "request_size"
            raise _TransportFault("request_size")
        if self.required_schema is not None:
            try:
                request_body = json.loads(request.content)
            except (UnicodeDecodeError, json.JSONDecodeError, httpx.RequestNotRead):
                self.violation = "required_parameter"
                raise _TransportFault("required_parameter") from None
            if not _request_preserves_schema(request_body, self.profile, self.required_schema):
                self.violation = "required_parameter"
                raise _TransportFault("required_parameter")

        if self.operation == "embeddings":
            batch = self.embedding_batch_index
            if batch is None or batch in self.sent_embedding_batches:
                self.violation = "generation_replay"
                raise _TransportFault("generation_replay")
            self.sent_embedding_batches.add(batch)
        elif self.request_count >= self.expected_request_count:
            self.violation = "generation_replay"
            raise _TransportFault("generation_replay")

        self._admit_send()
        self.request_count += 1

    async def arecord_request(self, request: httpx.Request) -> None:
        await anyio.to_thread.run_sync(self.record_request, request)

    def begin_embedding_batch(self, index: int, texts: Sequence[str]) -> None:
        self.embedding_batch_index = index
        estimate = sum(estimated_tokens(text) for text in texts)
        self.reservation_units = unit_reservations(input_tokens=estimate)

    def _admit_send(self) -> None:
        if self.usage_accounting is None or self.invocation is None:
            return
        self.begin_invocation()
        if self.deadline is not None:
            _sync_remaining(self.deadline)
        attempt = self._new_attempt()
        try:
            reserved_attempt = self.usage_accounting.reserve_attempt(
                self.invocation, attempt, max_attempts=self.max_attempts
            )
        except UsageAdmissionDenied as error:
            self.accounting_violation = error.code
            self._raise_accounting_denial(error.code)
        except Exception:  # noqa: BLE001 - block dispatch and hide storage details
            self.accounting_violation = "provider_usage_ledger_unavailable"
            raise LLMUnavailableError("provider usage accounting is unavailable") from None
        self.active_attempt = reserved_attempt or attempt
        self.active_attempt_started_monotonic = monotonic()
        self.last_attempt_id = self.active_attempt.attempt_id
        self.attempt_ids.append(str(self.active_attempt.attempt_id))

    def _new_attempt(self, *, parent_attempt_id=None) -> AttemptMetadata:
        number = self.request_count + 1
        values = dict(self.reservation_units)
        input_tokens = values.get("input_tokens", 0)
        output_tokens = values.get("output_tokens", 0)
        tokens = values.get("tokens", input_tokens + output_tokens)
        return AttemptMetadata(
            attempt_id=uuid4(),
            parent_attempt_id=parent_attempt_id,
            send_number=number,
            started_at=datetime.now(UTC),
            reservation_units=self.reservation_units,
            reserved_tokens=max(0, int(tokens)),
        )

    def begin_invocation(self) -> None:
        if self.usage_accounting is None or self.invocation is None or self.invocation_started:
            return
        try:
            self.usage_accounting.begin_invocation(self.invocation)
        except Exception:  # noqa: BLE001 - normalize ledger failures before dispatch
            self.accounting_violation = "provider_usage_ledger_unavailable"
            raise LLMUnavailableError("provider usage accounting is unavailable") from None
        self.invocation_started = True

    async def abegin_invocation(self) -> None:
        if self.usage_accounting is None or self.invocation is None or self.invocation_started:
            return
        try:
            await anyio.to_thread.run_sync(self.begin_invocation)
        except LLMError:
            raise
        except Exception:  # noqa: BLE001 - normalize ledger failures before dispatch
            self.accounting_violation = "provider_usage_ledger_unavailable"
            raise LLMUnavailableError("provider usage accounting is unavailable") from None

    def settle_current(
        self,
        outcome: str,
        *,
        error_code: str | None = None,
        usage: UsageMetadata | None = None,
        rate_limits: ProviderRateLimitMetadata | None = None,
    ) -> None:
        attempt = self.active_attempt
        invocation = self.invocation
        if attempt is None or invocation is None or self.usage_accounting is None:
            return
        completed_at = datetime.now(UTC)
        latency_ms = int(
            max(0.0, monotonic() - (self.active_attempt_started_monotonic or monotonic())) * 1000
        )
        if usage is None:
            input_tokens = output_tokens = total_tokens = None
            usage_source, confidence = "unknown", "unknown"
        else:
            input_tokens, output_tokens, total_tokens = (
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
            )
            usage_source = usage.source
            confidence = "exact" if usage.source == "provider" else "derived"
        result = AttemptResult(
            outcome=outcome,  # type: ignore[arg-type]
            completed_at=completed_at,
            latency_ms=latency_ms,
            http_status=self.response_status,
            error_code=error_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            usage_source=usage_source,
            usage_confidence=confidence,  # type: ignore[arg-type]
            rate_limits=rate_limits or _rate_limit_metadata(self.response_headers),
        )
        try:
            self.usage_accounting.settle_attempt(invocation, attempt, result)
        except Exception as error:  # noqa: BLE001 - the reserved row remains an unresolved fence
            logger.info(
                "provider_usage_settlement_pending attempt_id=%s error_class=%s",
                attempt.attempt_id,
                type(error).__name__,
            )
        self.active_attempt = None
        self.active_attempt_started_monotonic = None

    def finish_invocation(self, outcome: str) -> None:
        if self.invocation_finalized:
            return
        self.invocation_finalized = True
        if self.active_attempt is not None:
            self.settle_current("unknown", error_code="provider_outcome_unknown")
        if self.invocation is None or self.usage_accounting is None:
            return
        try:
            self.usage_accounting.complete_invocation(
                self.invocation,
                outcome=outcome,  # type: ignore[arg-type]
                completed_at=datetime.now(UTC),
            )
        except Exception as error:  # noqa: BLE001 - completed output remains usable
            logger.info(
                "provider_usage_invocation_completion_pending invocation_id=%s error_class=%s",
                self.invocation.invocation_id,
                type(error).__name__,
            )

    async def asettle_current(self, outcome: str, **kwargs) -> None:
        await anyio.to_thread.run_sync(lambda: self.settle_current(outcome, **kwargs))

    async def afinish_invocation(self, outcome: str) -> None:
        await anyio.to_thread.run_sync(self.finish_invocation, outcome)

    @staticmethod
    def _raise_accounting_denial(code: str) -> None:
        if code in {"provider_quota_exhausted", "provider_endpoint_cooling_down"}:
            raise LLMRateLimitedError("provider capacity is temporarily unavailable") from None
        raise LLMUnavailableError("provider dispatch was blocked by its usage budget") from None

    def _reset_response_evidence(self) -> None:
        self.response_status = None
        self.response_headers.clear()
        self.raw_body.clear()
        self.response_complete = False
        self.violation = None
        self.line_bytes = 0
        self.event_bytes = 0
        self.line_ends_with_cr = False
        self.sse_line_buffer.clear()
        self.sse_data_lines.clear()
        self.sse_model_id = None
        self.sse_finish_reason = None
        self.sse_done = False

    def _rewrite_embedding_request(self, request: httpx.Request) -> None:
        texts = self.embedding_texts
        if texts is None:
            self.violation = "required_parameter"
            raise _TransportFault("required_parameter")
        try:
            payload = json.loads(request.content)
            items = payload["requests"]
            if not isinstance(items, list) or len(items) != len(texts):
                raise ValueError
            for item, text in zip(items, texts, strict=True):
                content = item.get("content")
                if not isinstance(content, dict):
                    raise TypeError
                content["parts"] = [{"text": text}]
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self.violation = "required_parameter"
            raise _TransportFault("required_parameter") from None
        request.headers["content-length"] = str(len(body))
        request._content = body
        request.stream = httpx.ByteStream(body)

    def _apply_deadline_to_request(self, request: httpx.Request) -> None:
        if self.deadline is None:
            return
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("request deadline expired")
        request.extensions["timeout"] = httpx.Timeout(remaining).as_dict()

    def record_response(self, response: httpx.Response) -> None:
        self.response_status = response.status_code
        self.response_headers = _safe_rate_headers(response.headers)

    def record_chunk(self, chunk: bytes) -> None:
        if len(self.raw_body) + len(chunk) > self.max_response_bytes:
            self.violation = "response_size"
            raise _TransportFault("response_size")
        if self.streaming:
            self._record_sse_bounds(chunk)
            try:
                self._validate_sse_chunk(chunk)
            except LLMError as error:
                self.stream_error = error
                raise
        self.raw_body.extend(chunk)

    def _record_sse_bounds(self, chunk: bytes) -> None:
        for byte in chunk:
            self.event_bytes += 1
            if self.event_bytes > _MAX_STREAM_EVENT_BYTES:
                self.violation = "response_size"
                raise _TransportFault("response_size")
            if byte == 0x0A:
                current_line_bytes = self.line_bytes - int(self.line_ends_with_cr)
                if current_line_bytes > _MAX_STREAM_LINE_BYTES:
                    self.violation = "response_size"
                    raise _TransportFault("response_size")
                blank_line = current_line_bytes == 0
                self.line_bytes = 0
                self.line_ends_with_cr = False
                if blank_line:
                    self.event_bytes = 0
            else:
                self.line_bytes += 1
                self.line_ends_with_cr = byte == 0x0D
                if self.line_bytes > _MAX_STREAM_LINE_BYTES + 1:
                    self.violation = "response_size"
                    raise _TransportFault("response_size")

    def finish_response(self) -> None:
        if (
            self.streaming
            and self.line_bytes - int(self.line_ends_with_cr) > _MAX_STREAM_LINE_BYTES
        ):
            self.violation = "response_size"
            raise _TransportFault("response_size")
        if self.streaming:
            try:
                if self.sse_line_buffer:
                    self._consume_sse_line(bytes(self.sse_line_buffer).removesuffix(b"\r"))
                    self.sse_line_buffer.clear()
                self._consume_sse_event()
            except LLMError as error:
                self.stream_error = error
                raise

    def _validate_sse_chunk(self, chunk: bytes) -> None:
        for byte in chunk:
            if byte == 0x0A:
                line = bytes(self.sse_line_buffer).removesuffix(b"\r")
                self.sse_line_buffer.clear()
                self._consume_sse_line(line)
            else:
                self.sse_line_buffer.append(byte)

    def _consume_sse_line(self, line: bytes) -> None:
        if not line:
            self._consume_sse_event()
        elif line.startswith(b"data:"):
            self.sse_data_lines.append(line[5:].lstrip(b" "))

    def _consume_sse_event(self) -> None:
        if not self.sse_data_lines:
            return
        raw_data = b"\n".join(self.sse_data_lines)
        self.sse_data_lines.clear()
        try:
            data = raw_data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise LLMInvalidResponseError("language model stream was invalid") from None
        if data.strip() == "[DONE]":
            if self.sse_done:
                raise LLMInvalidResponseError("language model emitted duplicate terminal markers")
            self.sse_done = True
            return
        if self.sse_done:
            raise LLMInvalidResponseError("language model emitted data after stream completion")
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            raise LLMInvalidResponseError("language model emitted malformed stream data") from None
        if not isinstance(payload, Mapping):
            raise LLMInvalidResponseError("language model emitted an invalid stream event")
        if payload.get("error") is not None:
            raise LLMUnavailableError("language model stream failed")
        raw_model = (
            payload.get("modelVersion", payload.get("model_version", payload.get("model")))
            if self.profile.provider == "gemini"
            else payload.get("model")
        )
        if raw_model is not None:
            self.sse_model_id = _merge_model_identity(self.profile, self.sse_model_id, raw_model)
        has_text = _sse_payload_has_text(payload, self.profile.provider)
        if has_text and self.sse_model_id is None:
            raise LLMInvalidResponseError("language model response omitted its model identity")
        if has_text and self.sse_finish_reason is not None:
            raise LLMInvalidResponseError("language model emitted text after terminal metadata")
        reason = _sse_finish_reason(payload, self.profile.provider)
        if reason is not None:
            if self.sse_finish_reason is not None and self.sse_finish_reason != reason:
                raise LLMInvalidResponseError(
                    "language model emitted conflicting terminal metadata"
                )
            self.sse_finish_reason = reason

    def _check_deadline(self) -> None:
        if self.deadline is not None and monotonic() >= self.deadline:
            raise TimeoutError("request deadline expired")


class _TransportFault(Exception):
    """Internal transport failure with a fixed, content-free reason code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _BoundedAsyncByteStream(httpx.AsyncByteStream):
    def __init__(self, response: httpx.Response, state: _TransportState):
        self._response = response
        self._state = state
        self._iterator: Any | None = None

    async def _iterate(self):
        try:
            buffered: list[bytes] = []
            async for chunk in self._response.aiter_raw():
                self._state.record_chunk(chunk)
                if self._state.streaming:
                    yield chunk
                else:
                    buffered.append(chunk)
            self._state.finish_response()
            self._state.response_complete = True
            if not self._state.streaming:
                body = _sdk_compatible_body(b"".join(buffered), self._state)
                if body:
                    yield body
        finally:
            await self._response.aclose()

    def __aiter__(self):
        if self._iterator is None:
            self._iterator = self._iterate()
        return self._iterator

    async def drain(self, deadline: float) -> None:
        if self._iterator is None:
            self._iterator = self._iterate()
        while not self._state.response_complete:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("generation deadline expired")
            try:
                async with asyncio.timeout(remaining):
                    await anext(self._iterator)
            except StopAsyncIteration:
                return

    async def force_close(self) -> None:
        if self._iterator is not None:
            await self._iterator.aclose()
        await self._response.aclose()

    async def aclose(self) -> None:
        if self._state.streaming and self._state.sse_done and not self._state.response_complete:
            return
        await self._response.aclose()


class _BoundedAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport, state: _TransportState):
        self._inner = inner
        self._state = state

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await self._state.arecord_request(request)
        try:
            response = await self._inner.handle_async_request(request)
        except (httpx.ConnectError, httpx.RemoteProtocolError):
            # LiteLLM's AsyncHTTPHandler catches these exceptions and retries on
            # a new, unbounded client even with num_retries=0. Keep ambiguity
            # inside our one-attempt transport and canonical accounting instead.
            raise _TransportFault("connection_failure") from None
        self._state.record_response(response)
        if _is_non_success_or_redirect(response.status_code):
            safe_headers = _safe_rate_headers(response.headers)
            await response.aclose()
            return httpx.Response(
                response.status_code,
                headers={**safe_headers, "content-type": "application/json"},
                content=b"{}",
                request=request,
            )
        try:
            self._check_response_headers(response)
        except _TransportFault:
            await response.aclose()
            raise
        if response.is_stream_consumed:
            content = response.content
            try:
                self._state.record_chunk(content)
                self._state.finish_response()
                self._state.response_complete = True
            except _TransportFault:
                await response.aclose()
                raise
            await response.aclose()
            content = _sdk_compatible_body(content, self._state)
            headers = httpx.Headers(response.headers)
            headers["content-length"] = str(len(content))
            return httpx.Response(
                response.status_code,
                headers=headers,
                content=content,
                extensions=response.extensions,
                request=request,
            )
        headers = response.headers
        if not self._state.streaming:
            headers = httpx.Headers(headers)
            headers.pop("content-length", None)
        stream = _BoundedAsyncByteStream(response, self._state)
        self._state.async_stream = stream
        return httpx.Response(
            response.status_code,
            headers=headers,
            stream=stream,
            extensions=response.extensions,
            request=request,
        )

    def _check_response_headers(self, response: httpx.Response) -> None:
        encoding = response.headers.get("content-encoding", "").strip().lower()
        if encoding not in {"", "identity"}:
            self._state.violation = "response_encoding"
            raise _TransportFault("response_encoding")
        content_length = _parse_non_negative_int(response.headers.get("content-length"))
        if content_length is not None and content_length > self._state.max_response_bytes:
            self._state.violation = "response_size"
            raise _TransportFault("response_size")

    async def aclose(self) -> None:
        await self._inner.aclose()


class _BoundedSyncByteStream(httpx.SyncByteStream):
    def __init__(self, response: httpx.Response, state: _TransportState):
        self._response = response
        self._state = state

    def __iter__(self):
        try:
            buffered: list[bytes] = []
            iterator = iter(self._response.iter_raw())
            while True:
                _apply_deadline_to_response(self._response, self._state)
                try:
                    chunk = next(iterator)
                except StopIteration:
                    break
                self._state._check_deadline()
                self._state.record_chunk(chunk)
                if self._state.streaming:
                    yield chunk
                else:
                    buffered.append(chunk)
            self._state.finish_response()
            self._state.response_complete = True
            if not self._state.streaming:
                body = _sdk_compatible_body(b"".join(buffered), self._state)
                if body:
                    yield body
        finally:
            self._response.close()

    def close(self) -> None:
        self._response.close()


class _BoundedSyncTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport, state: _TransportState):
        self._inner = inner
        self._state = state

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self._state.record_request(request)
        response = self._inner.handle_request(request)
        try:
            self._state._check_deadline()
        except TimeoutError:
            response.close()
            raise
        self._state.record_response(response)
        if _is_non_success_or_redirect(response.status_code):
            safe_headers = _safe_rate_headers(response.headers)
            response.close()
            return httpx.Response(
                response.status_code,
                headers={**safe_headers, "content-type": "application/json"},
                content=b"{}",
                request=request,
            )
        encoding = response.headers.get("content-encoding", "").strip().lower()
        if encoding not in {"", "identity"}:
            self._state.violation = "response_encoding"
            response.close()
            raise _TransportFault("response_encoding")
        content_length = _parse_non_negative_int(response.headers.get("content-length"))
        if content_length is not None and content_length > self._state.max_response_bytes:
            self._state.violation = "response_size"
            response.close()
            raise _TransportFault("response_size")
        if response.is_stream_consumed:
            content = response.content
            try:
                self._state._check_deadline()
                self._state.record_chunk(content)
                self._state.finish_response()
                self._state.response_complete = True
            except _TransportFault:
                response.close()
                raise
            response.close()
            content = _sdk_compatible_body(content, self._state)
            headers = httpx.Headers(response.headers)
            headers["content-length"] = str(len(content))
            return httpx.Response(
                response.status_code,
                headers=headers,
                content=content,
                extensions=response.extensions,
                request=request,
            )
        headers = response.headers
        if self._state.deadline is not None:
            response.extensions["timeout"] = request.extensions.get("timeout")
        if not self._state.streaming:
            headers = httpx.Headers(headers)
            headers.pop("content-length", None)
        return httpx.Response(
            response.status_code,
            headers=headers,
            stream=_BoundedSyncByteStream(response, self._state),
            extensions=response.extensions,
            request=request,
        )

    def close(self) -> None:
        self._inner.close()


def _sync_remaining(deadline: float) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError("request deadline expired")
    return remaining


def _apply_deadline_to_response(response: httpx.Response, state: _TransportState) -> None:
    if state.deadline is None:
        return
    response.extensions["timeout"] = httpx.Timeout(_sync_remaining(state.deadline)).as_dict()


def _bounded_timeout(max_output_tokens: int, timeout_seconds: float, settings: Settings) -> float:
    if (
        isinstance(max_output_tokens, bool)
        or not isinstance(max_output_tokens, int)
        or max_output_tokens < 1
        or isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise LLMInvalidRequestError("generation bounds are invalid")
    return min(float(timeout_seconds), settings.request_timeout_seconds)


def _remaining(deadline: float) -> float:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise TimeoutError("generation deadline expired")
    return remaining


def _raise_for_status(status_code: int, rate_limits: ProviderRateLimitMetadata | None) -> None:
    if 200 <= status_code < 300:
        return
    if status_code < 200 or 300 <= status_code < 400:
        raise LLMUnavailableError("provider redirect or interim response was rejected")
    if status_code == 429:
        raise LLMRateLimitedError(rate_limits=rate_limits)
    if status_code in {401, 403}:
        raise LLMInvalidConfigurationError("provider credentials or model access are invalid")
    if status_code in {408, 504}:
        raise LLMTimeoutError("language model request timed out")
    if status_code in {400, 404, 413, 422}:
        raise LLMInvalidRequestError("language model rejected the request")
    raise LLMUnavailableError("language model is unavailable")


def _raise_safe_error(error: BaseException, state: _TransportState) -> None:
    if state.stream_error is not None:
        raise state.stream_error from None
    if state.deadline is not None and monotonic() >= state.deadline:
        raise LLMTimeoutError("language model request timed out") from None
    if state.violation == "endpoint":
        raise LLMInvalidConfigurationError("provider endpoint was not approved") from None
    if state.violation == "required_parameter":
        raise LLMUnsupportedCapabilityError(
            "provider SDK did not preserve the required structured schema"
        ) from None
    if state.violation == "request_size":
        raise LLMInvalidRequestError("language model request exceeded the size limit") from None
    if state.violation == "response_size":
        raise LLMInvalidResponseError("language model response exceeded the size limit") from None
    if state.violation == "response_encoding":
        raise LLMInvalidResponseError("language model response encoding was invalid") from None
    if state.violation == "generation_replay":
        raise LLMUnavailableError("language model request could not be safely retried") from None
    if state.response_status is not None and _is_non_success_or_redirect(state.response_status):
        _raise_for_status(state.response_status, _rate_limit_metadata(state.response_headers))
    if _exception_chain_contains_timeout(error):
        raise LLMTimeoutError("language model request timed out") from None
    if isinstance(error, (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError)):
        raise LLMInvalidResponseError("language model response was invalid") from None
    raise LLMUnavailableError("language model is unavailable") from None


def _safe_rate_headers(headers: Mapping[str, str]) -> dict[str, str]:
    allowed = (
        "retry-after",
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
        "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-tokens",
        "x-ratelimit-reset-tokens",
    )
    return {name: headers[name] for name in allowed if name in headers}


def _is_non_success_or_redirect(status_code: int) -> bool:
    return status_code < 200 or status_code >= 300


def _rate_limit_metadata(
    headers: Mapping[str, str],
) -> ProviderRateLimitMetadata | None:
    values = {
        "requests_limit": _parse_non_negative_int(headers.get("x-ratelimit-limit-requests")),
        "requests_remaining": _parse_non_negative_int(
            headers.get("x-ratelimit-remaining-requests")
        ),
        "requests_reset_seconds": _duration(headers.get("x-ratelimit-reset-requests")),
        "tokens_limit": _parse_non_negative_int(headers.get("x-ratelimit-limit-tokens")),
        "tokens_remaining": _parse_non_negative_int(headers.get("x-ratelimit-remaining-tokens")),
        "tokens_reset_seconds": _duration(headers.get("x-ratelimit-reset-tokens")),
        "retry_after_seconds": _duration(headers.get("retry-after")),
    }
    if not any(value is not None for value in values.values()):
        return None
    return ProviderRateLimitMetadata(**values)


def _duration(value: str | None) -> float | None:
    if not value:
        return None
    try:
        numeric = float(value)
    except ValueError:
        numeric = None
    if numeric is not None:
        return numeric if numeric >= 0 else None
    parts = tuple(_RESET_PART.finditer(value.strip().lower()))
    if not parts or "".join(part.group(0) for part in parts) != value.strip().lower():
        return None
    factors = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return sum(float(part.group(1)) * factors[part.group(2)] for part in parts)


def _sdk_http_handler_types(sdk: Any) -> tuple[Any, Any]:
    module = importlib.import_module("litellm.llms.custom_httpx.http_handler")
    return module.AsyncHTTPHandler, module.HTTPHandler


async def _close_sdk_stream(stream: Any) -> None:
    close = getattr(stream, "aclose", None)
    if close is None:
        close = getattr(stream, "close", None)
    if close is None:
        return
    with anyio.CancelScope(shield=True):
        with anyio.move_on_after(1):
            try:
                result = close()
                if hasattr(result, "__await__"):
                    await result
            except (Exception, asyncio.CancelledError):  # noqa: BLE001 - best-effort cleanup.
                return


async def _close_async_client(client: httpx.AsyncClient) -> None:
    with anyio.CancelScope(shield=True):
        with anyio.move_on_after(1):
            try:
                await client.aclose()
            except (Exception, asyncio.CancelledError):  # noqa: BLE001 - best-effort cleanup.
                return


def _close_sync_client(client: httpx.Client) -> None:
    try:
        client.close()
    except Exception:  # noqa: BLE001 - request result is already determined.
        logger.debug("LiteLLM client cleanup failed")
