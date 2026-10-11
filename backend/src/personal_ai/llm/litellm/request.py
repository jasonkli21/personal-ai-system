"""LiteLLM request behavior."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from personal_ai.llm.client import (
    SYSTEM_INSTRUCTION,
    ChatMessage,
)
from personal_ai.llm.litellm.profiles import _ProviderProfile
from personal_ai.llm.litellm.streaming import _field


def _role_name(role: Any) -> str:
    return str(getattr(role, "value", role))


def _sdk_messages(
    profile: _ProviderProfile, messages: Sequence[ChatMessage]
) -> list[dict[str, str]]:
    prepared = list(messages)
    if profile.provider == "gemini":
        system = "\n\n".join(
            [
                SYSTEM_INSTRUCTION,
                *(message.content for message in prepared if _role_name(message.role) == "system"),
            ]
        )
        output = [{"role": "system", "content": system}]
        output.extend(
            {
                "role": "assistant" if _role_name(message.role) == "assistant" else "user",
                "content": message.content,
            }
            for message in prepared
            if _role_name(message.role) != "system"
        )
        return output
    return [{"role": _role_name(message.role), "content": message.content} for message in prepared]


def _response_format(schema: Mapping[str, object], provider: str) -> dict[str, Any]:
    if provider == "cloudflare_workers_ai":
        return {"type": "json_schema", "json_schema": dict(schema)}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "personal_ai_response",
            "strict": False,
            "schema": dict(schema),
        },
    }


def _request_preserves_schema(
    request_body: Any, profile: _ProviderProfile, schema: Mapping[str, object]
) -> bool:
    if profile.provider == "cloudflare_workers_ai":
        response_format = _field(request_body, "response_format")
        return response_format == {
            "type": "json_schema",
            "json_schema": dict(schema),
        }
    if profile.provider == "groq":
        tools = _field(request_body, "tools")
        choice = _field(request_body, "tool_choice")
        expected_function = {
            "name": "json_tool_call",
            "parameters": dict(schema),
        }
        return (
            isinstance(tools, list)
            and any(
                _field(tool, "type") == "function" and _field(tool, "function") == expected_function
                for tool in tools
            )
            and choice
            == {
                "type": "function",
                "function": {"name": "json_tool_call"},
            }
        )
    return _contains_schema_value(request_body, schema)


def _contains_schema(body: Mapping[str, Any], schema: Mapping[str, object]) -> bool:
    generation = body.get("generationConfig")
    if not isinstance(generation, Mapping):
        return False
    return (
        generation.get("response_json_schema") == schema
        or generation.get("response_schema") is not None
    )


def _contains_schema_value(value: Any, schema: Mapping[str, object]) -> bool:
    if isinstance(value, Mapping):
        if value == schema:
            return True
        return any(_contains_schema_value(item, schema) for item in value.values())
    if isinstance(value, list):
        return any(_contains_schema_value(item, schema) for item in value)
    return False
