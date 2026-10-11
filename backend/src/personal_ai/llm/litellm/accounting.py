"""LiteLLM accounting behavior."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from personal_ai.llm.errors import (
    LLMRateLimitedError,
    LLMTimeoutError,
)


def _outcome_for_error(error: BaseException, http_status: int | None) -> str:
    if http_status == 429 or isinstance(error, LLMRateLimitedError):
        return "rate_limited"
    if http_status is not None and http_status >= 500:
        return "server_error"
    if http_status is not None and http_status >= 400:
        return "rejected"
    if isinstance(error, (TimeoutError, LLMTimeoutError)) or _exception_chain_contains_timeout(
        error
    ):
        return "timeout"
    if http_status is None:
        return "unknown"
    return "failure"


def _state_error_outcome(state: Any, error: BaseException) -> str:
    if state.accounting_violation is not None:
        if state.accounting_violation in {
            "provider_quota_exhausted",
            "provider_endpoint_cooling_down",
        }:
            return "rate_limited"
        return "rejected"
    return _outcome_for_error(error, state.response_status)


def _settle_error(state: Any, error: BaseException) -> str:
    code = getattr(error, "code", None)
    outcome = _state_error_outcome(state, error)
    state.settle_current(
        outcome,
        error_code=code if isinstance(code, str) else "provider_transport_failure",
    )
    return outcome


async def _asettle_error(state: Any, error: BaseException) -> str:
    code = getattr(error, "code", None)
    outcome = _state_error_outcome(state, error)
    await state.asettle_current(
        outcome,
        error_code=code if isinstance(code, str) else "provider_transport_failure",
    )
    return outcome


def _exception_chain_contains_timeout(error: BaseException) -> bool:
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, (TimeoutError, httpx.TimeoutException)) or type(
            current
        ).__name__ in {"Timeout", "APITimeoutError", "ReadTimeout", "ConnectTimeout"}:
            return True
        for name in ("__cause__", "__context__", "original_exception"):
            nested = getattr(current, name, None)
            if isinstance(nested, BaseException):
                pending.append(nested)
        nested_errors = getattr(current, "exceptions", ())
        if isinstance(nested_errors, Sequence) and not isinstance(nested_errors, (str, bytes)):
            pending.extend(item for item in nested_errors if isinstance(item, BaseException))
    return False
