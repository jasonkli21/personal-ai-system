"""LiteLLM streaming behavior."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from personal_ai.llm.client import (
    UsageMetadata,
)
from personal_ai.llm.errors import (
    LLMIncompleteGenerationError,
    LLMInvalidResponseError,
    LLMRejectedError,
    LLMUnavailableError,
)
from personal_ai.llm.litellm.profiles import _ProviderProfile


@dataclass(frozen=True, slots=True)
class _WireMetadata:
    model_id: str
    status: Literal["success", "incomplete", "rejected"]
    usage: UsageMetadata | None = None
    refused: bool = False


def _sse_payload_has_text(payload: Mapping[str, Any], provider: str) -> bool:
    if provider == "gemini":
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return False
        for candidate in candidates:
            content = _field(candidate, "content")
            parts = _field(content, "parts")
            if isinstance(parts, list) and any(
                isinstance(_field(part, "text"), str) and _field(part, "text") for part in parts
            ):
                return True
        return False
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return False
    for choice in choices:
        if not isinstance(choice, Mapping):
            continue
        for name in ("delta", "message"):
            content = _field(_field(choice, name), "content")
            if isinstance(content, str) and content:
                return True
    return False


def _sse_finish_reason(payload: Mapping[str, Any], provider: str) -> str | None:
    if provider == "gemini":
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return None
        reason: str | None = None
        for candidate in candidates:
            raw_reason = _gemini_reason(_field(candidate, "finishReason"))
            if raw_reason is None:
                continue
            if reason is not None and reason != raw_reason:
                raise LLMInvalidResponseError(
                    "language model emitted conflicting terminal metadata"
                )
            reason = raw_reason
        return reason
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return None
    reason = None
    for choice in choices:
        if not isinstance(choice, Mapping):
            raise LLMInvalidResponseError("language model stream choice was invalid")
        raw_reason = choice.get("finish_reason")
        if raw_reason is None:
            continue
        if not isinstance(raw_reason, str) or not raw_reason:
            raise LLMInvalidResponseError("language model terminal metadata was invalid")
        if reason is not None and reason != raw_reason:
            raise LLMInvalidResponseError("language model emitted conflicting terminal metadata")
        reason = raw_reason
    return reason


def _sdk_text_deltas(chunk: Any) -> tuple[str, ...]:
    choices = _field(chunk, "choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return ()
    result: list[str] = []
    for choice in choices:
        delta = _field(choice, "delta")
        content = _field(delta, "content")
        if isinstance(content, str) and content:
            result.append(content)
    return tuple(result)


def _sdk_completion_text(response: Any) -> str:
    choices = _field(response, "choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or not choices:
        raise LLMInvalidResponseError("language model response had no completion choice")
    message = _field(choices[0], "message")
    content = _field(message, "content")
    if content is None:
        return ""
    if not isinstance(content, str):
        raise LLMInvalidResponseError("language model completion text was invalid")
    return content


def _sdk_refusal(response: Any) -> bool:
    choices = _field(response, "choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return False
    return any(bool(_field(_field(choice, "message"), "refusal")) for choice in choices)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _usage_from_sdk(raw: Any) -> UsageMetadata | None:
    if raw is None:
        return None
    input_tokens = _parse_non_negative_int(
        _field(raw, "prompt_tokens", _field(raw, "input_tokens"))
    )
    output_tokens = _parse_non_negative_int(
        _field(raw, "completion_tokens", _field(raw, "output_tokens"))
    )
    total_tokens = _parse_non_negative_int(_field(raw, "total_tokens"))
    if input_tokens is output_tokens is total_tokens is None:
        return None
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        source="estimated",
        confidence="estimated",
    )


def _mark_estimated(usage: UsageMetadata | None) -> UsageMetadata | None:
    if usage is None:
        return None
    return UsageMetadata(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        source="estimated",
        confidence="estimated",
    )


def _parse_generation_wire(
    profile: _ProviderProfile,
    raw: bytes,
    *,
    streaming: bool,
    require_completed: bool,
) -> _WireMetadata:
    if not require_completed or not raw:
        raise LLMInvalidResponseError("language model response was not fully received")
    if profile.provider == "gemini":
        payloads, _done = _parse_sse(raw) if streaming else (_json_payloads(raw), False)
        return _parse_gemini_payloads(profile, payloads)
    if streaming:
        payloads, done = _parse_sse(raw)
        return _parse_openai_payloads(profile, payloads, done=done)
    payloads = _json_payloads(raw)
    return _parse_openai_payloads(profile, payloads, done=True)


def _json_payloads(raw: bytes) -> list[Mapping[str, Any]]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LLMInvalidResponseError("language model response was invalid") from error
    if not isinstance(payload, Mapping):
        raise LLMInvalidResponseError("language model response was invalid")
    return [payload]


def _parse_sse(raw: bytes) -> tuple[list[Mapping[str, Any]], bool]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise LLMInvalidResponseError("language model stream was invalid") from error
    payloads: list[Mapping[str, Any]] = []
    data_lines: list[str] = []
    done = False
    for line in text.splitlines():
        if line == "":
            event, done = _consume_sse_event(data_lines, payloads, done)
            data_lines = []
            if event:
                continue
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip(" "))
    _, done = _consume_sse_event(data_lines, payloads, done)
    for payload in payloads:
        if payload.get("error") is not None:
            raise LLMUnavailableError("language model stream failed")
    return payloads, done


def _consume_sse_event(
    data_lines: list[str],
    payloads: list[Mapping[str, Any]],
    done: bool,
) -> tuple[bool, bool]:
    if not data_lines:
        return False, done
    data = "\n".join(data_lines)
    if data.strip() == "[DONE]":
        return True, True
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LLMInvalidResponseError("language model emitted malformed stream data") from error
    if not isinstance(payload, Mapping):
        raise LLMInvalidResponseError("language model emitted an invalid stream event")
    if done:
        raise LLMInvalidResponseError("language model emitted data after stream completion")
    payloads.append(payload)
    return True, done


def _parse_gemini_payloads(
    profile: _ProviderProfile, payloads: Sequence[Mapping[str, Any]]
) -> _WireMetadata:
    model: str | None = None
    reason: str | None = None
    usage: UsageMetadata | None = None
    refused = False
    for payload in payloads:
        raw_model = payload.get("modelVersion", payload.get("model_version", payload.get("model")))
        if raw_model is not None:
            model = _merge_model_identity(profile, model, raw_model)
        feedback = payload.get("promptFeedback")
        if isinstance(feedback, Mapping):
            refused = refused or _gemini_reason(feedback.get("blockReason")) == "BLOCKED"
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, Mapping):
                    continue
                candidate_reason = _gemini_reason(candidate.get("finishReason"))
                if candidate_reason is not None:
                    if reason is not None and reason != candidate_reason:
                        raise LLMInvalidResponseError(
                            "language model emitted conflicting terminal metadata"
                        )
                    reason = candidate_reason
        usage = _gemini_usage(payload.get("usageMetadata")) or usage
    if model is None:
        raise LLMInvalidResponseError("language model response omitted its model identity")
    if refused:
        status: Literal["success", "incomplete", "rejected"] = "rejected"
    elif reason in {"STOP", "FINISH_REASON_STOP"}:
        status = "success"
    elif reason in {"SAFETY", "RECITATION", "BLOCKED", "PROHIBITED_CONTENT"}:
        status = "rejected"
    else:
        status = "incomplete"
    return _WireMetadata(model, status, usage, refused)


def _parse_openai_payloads(
    profile: _ProviderProfile,
    payloads: Sequence[Mapping[str, Any]],
    *,
    done: bool,
) -> _WireMetadata:
    model: str | None = None
    reason: str | None = None
    usage: UsageMetadata | None = None
    refused = False
    for payload in payloads:
        raw_model = payload.get("model")
        if raw_model is not None:
            model = _merge_model_identity(profile, model, raw_model)
        usage = _openai_usage(payload.get("usage")) or usage
        choices = payload.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, Mapping):
                raise LLMInvalidResponseError("language model stream choice was invalid")
            raw_reason = choice.get("finish_reason")
            if raw_reason is not None:
                if not isinstance(raw_reason, str) or not raw_reason:
                    raise LLMInvalidResponseError("language model terminal metadata was invalid")
                if reason is not None and reason != raw_reason:
                    raise LLMInvalidResponseError(
                        "language model emitted conflicting terminal metadata"
                    )
                reason = raw_reason
            message = choice.get("message")
            delta = choice.get("delta")
            refused = refused or bool(_field(message, "refusal") or _field(delta, "refusal"))
    if model is None:
        raise LLMInvalidResponseError("language model response omitted its model identity")
    if refused or reason in {"content_filter", "safety"}:
        status: Literal["success", "incomplete", "rejected"] = "rejected"
    elif reason in {"stop", "end_turn", "completed"} and (done or profile.provider != "gemini"):
        status = "success"
    else:
        status = "incomplete"
    if profile.provider in {"groq", "cloudflare_workers_ai"} and not done:
        status = "incomplete"
    return _WireMetadata(model, status, usage, refused)


def _merge_model_identity(profile: _ProviderProfile, existing: str | None, raw_model: Any) -> str:
    if not isinstance(raw_model, str) or not raw_model.strip() or len(raw_model) > 200:
        raise LLMInvalidResponseError("language model response model identity was invalid")
    model = raw_model.strip()
    if model not in profile.approved_models:
        raise LLMInvalidResponseError("language model returned an unapproved model identity")
    if existing is not None and existing != model:
        raise LLMInvalidResponseError("language model emitted conflicting model identities")
    return model


def _gemini_reason(value: Any) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    normalized = str(name if name is not None else value).upper().split(".")[-1]
    return normalized if normalized not in {"", "NONE", "0"} else None


def _gemini_usage(raw: Any) -> UsageMetadata | None:
    if not isinstance(raw, Mapping):
        return None
    input_tokens = _parse_non_negative_int(raw.get("promptTokenCount"))
    output_tokens = _parse_non_negative_int(raw.get("candidatesTokenCount"))
    total_tokens = _parse_non_negative_int(raw.get("totalTokenCount"))
    if input_tokens is output_tokens is total_tokens is None:
        return None
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        source="provider",
        confidence="reported",
    )


def _openai_usage(raw: Any) -> UsageMetadata | None:
    if not isinstance(raw, Mapping):
        return None
    input_tokens = _parse_non_negative_int(raw.get("prompt_tokens", raw.get("input_tokens")))
    output_tokens = _parse_non_negative_int(raw.get("completion_tokens", raw.get("output_tokens")))
    total_tokens = _parse_non_negative_int(raw.get("total_tokens"))
    if input_tokens is output_tokens is total_tokens is None:
        return None
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        source="provider",
        confidence="reported",
    )


def _terminal_error_code(status: str) -> str | None:
    if status == "incomplete":
        return LLMIncompleteGenerationError.code
    if status == "rejected":
        return LLMRejectedError.code
    if status == "failure":
        return LLMUnavailableError.code
    return None


def _parse_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None
