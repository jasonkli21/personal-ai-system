"""LiteLLM profiles behavior."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote, urlsplit

import httpx

from personal_ai.llm.client import (
    InferenceContext,
)
from personal_ai.llm.errors import (
    LLMInvalidConfigurationError,
    LLMInvalidRequestError,
    LLMUnavailableError,
)
from personal_ai.settings import Settings

_SENSITIVITY_RANK = {"public": 0, "personal": 1, "sensitive": 2, "restricted": 3}


@dataclass(frozen=True, slots=True)
class _ProviderProfile:
    provider: Literal["gemini", "groq", "cloudflare_workers_ai"]
    sdk_provider: Literal["gemini", "groq", "cloudflare"]
    provider_id: str
    model_id: str
    serializer_id: str
    api_base: str
    api_key: str
    approved_models: frozenset[str]
    structured_enabled: bool
    max_tokens_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"

    @property
    def sdk_model(self) -> str:
        return f"{self.sdk_provider}/{self.model_id}"


def _bind_endpoint_profile(settings: Settings, provider: str, endpoint_profile):
    """Bind this fixed transport to one exact configured Phase 18 profile.

    The gateway has provider-specific URL, model, and credential configuration;
    accepting a profile that merely shares its neutral provider identity would
    misattribute account/deployment selection. Custom profile changes therefore
    fail closed until the transport itself supports them.
    """
    from personal_ai.routing.configured import build_initial_endpoint_profiles

    configured = tuple(
        profile
        for profile in build_initial_endpoint_profiles(settings)
        if profile.provider_id == provider
    )
    if not configured and endpoint_profile is None:
        return None
    if endpoint_profile is None:
        if len(configured) != 1:
            raise LLMInvalidConfigurationError("endpoint profile binding is ambiguous")
        return configured[0]
    if endpoint_profile not in configured:
        raise LLMInvalidConfigurationError("endpoint profile is not bound to this transport")
    return endpoint_profile


def _provider_profile(settings: Settings, provider: str) -> _ProviderProfile:
    if provider == "gemini":
        model = settings.ai_model
        return _ProviderProfile(
            "gemini",
            "gemini",
            "gemini",
            model,
            "gemini-content-v1",
            "https://generativelanguage.googleapis.com/v1beta",
            settings.ai_api_key.get_secret_value(),
            frozenset({model}),
            True,
        )
    if provider == "groq":
        model = settings.groq_model
        return _ProviderProfile(
            "groq",
            "groq",
            "groq",
            model or "unconfigured",
            "groq-chat-completions-v1",
            "https://api.groq.com/openai/v1",
            settings.groq_api_key.get_secret_value(),
            frozenset({model, *settings.groq_approved_model_aliases}),
            settings.groq_structured_output_verified,
            "max_completion_tokens",
        )
    if provider == "cloudflare_workers_ai":
        model = settings.cloudflare_model
        account = quote(settings.cloudflare_account_id, safe="")
        return _ProviderProfile(
            "cloudflare_workers_ai",
            "cloudflare",
            "cloudflare_workers_ai",
            model or "unconfigured",
            "cloudflare-workers-ai-chat-v1",
            f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1",
            settings.cloudflare_api_token.get_secret_value(),
            frozenset({model, *settings.cloudflare_approved_model_aliases}),
            settings.cloudflare_structured_output_verified,
        )
    raise LLMInvalidConfigurationError("configured language model provider is unsupported")


def _validate_external_provider(
    settings: Settings,
    profile: _ProviderProfile,
    inference_context: InferenceContext | None,
) -> None:
    if settings.external_providers_kill_switch_enabled:
        raise LLMUnavailableError("external provider calls are disabled")
    if profile.provider == "groq":
        enabled = settings.groq_adapter_enabled
        free = settings.groq_free_tier_verified
        privacy = settings.groq_privacy_approved
        maximum = settings.groq_privacy_max_sensitivity
        preflight = settings.groq_preflight_reference
    else:
        enabled = settings.cloudflare_adapter_enabled
        free = settings.cloudflare_free_tier_verified
        privacy = settings.cloudflare_privacy_approved
        maximum = settings.cloudflare_privacy_max_sensitivity
        preflight = settings.cloudflare_preflight_reference
        if not settings.cloudflare_account_id:
            raise LLMInvalidConfigurationError("provider account scope is not configured")
    if not enabled:
        raise LLMInvalidConfigurationError("provider adapter is disabled")
    if not free or not privacy or not preflight.strip():
        raise LLMInvalidConfigurationError("provider preflight is incomplete")
    if not profile.api_key or profile.model_id == "unconfigured":
        raise LLMInvalidConfigurationError("provider credentials or model are not configured")
    maximum_rank = _SENSITIVITY_RANK.get(maximum, -1)
    if maximum_rank < 0:
        raise LLMInvalidConfigurationError("provider privacy ceiling is invalid")
    effective_rank = _SENSITIVITY_RANK.get(
        inference_context.effective_sensitivity if inference_context else "unknown", 4
    )
    if effective_rank > maximum_rank:
        raise LLMInvalidRequestError("provider privacy preflight does not allow this sensitivity")


def _validate_inference_context(context: InferenceContext | None) -> None:
    if context is None:
        raise LLMInvalidRequestError("context disclosure policy is required")
    try:
        InferenceContext(
            effective_sensitivity=context.effective_sensitivity,
            maximum_sensitivity=context.maximum_sensitivity,
            policy_version=context.policy_version,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise LLMInvalidRequestError("context disclosure policy denied") from error


def _validate_schema(schema: Mapping[str, object] | None) -> None:
    if not isinstance(schema, Mapping) or not schema:
        raise LLMInvalidRequestError("structured response schema is required")
    try:
        json.dumps(schema, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise LLMInvalidRequestError("structured response schema is invalid") from error


def _request_is_approved(
    request: httpx.Request,
    profile: _ProviderProfile,
    operation: str,
    streaming: bool,
    request_model_id: str | None,
) -> bool:
    url = request.url
    base = urlsplit(profile.api_base)
    if (
        request.method != "POST"
        or url.scheme != "https"
        or url.host != base.hostname
        or url.port not in {None, base.port, 443}
        or bool(url.username)
        or bool(url.password)
    ):
        return False
    base_path = base.path.rstrip("/")
    if operation == "generation" and profile.provider == "gemini":
        model = quote(
            (request_model_id or profile.model_id).removeprefix("models/"),
            safe="-_.~",
        )
        suffix = ":streamGenerateContent" if streaming else ":generateContent"
        expected_path = f"{base_path}/models/{model}{suffix}"
        query = url.query.decode("ascii", errors="ignore")
        return url.path == expected_path and query == ("alt=sse" if streaming else "")
    if operation == "token_counting":
        model = quote(
            (request_model_id or profile.model_id).removeprefix("models/"),
            safe="-_.~",
        )
        return url.path == f"{base_path}/models/{model}:countTokens" and not url.query
    if operation == "embeddings":
        model = quote(
            (request_model_id or profile.model_id).removeprefix("models/"),
            safe="-_.~",
        )
        return url.path == f"{base_path}/models/{model}:batchEmbedContents" and not url.query
    if operation == "generation":
        return url.path == f"{base_path}/chat/completions" and not url.query
    return False
