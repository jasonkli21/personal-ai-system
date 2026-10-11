"""Canonical context source categories shared by planning and application policy."""

from typing import Literal

ContextSourceClass = Literal[
    "global_profile",
    "domain_profile",
    "domain_current",
    "domain_history",
    "ai_memory",
    "conversation",
    "external_research",
    "tool_result",
    "client_context",
]

CONTEXT_SOURCE_CLASSES: tuple[ContextSourceClass, ...] = (
    "global_profile",
    "domain_profile",
    "domain_current",
    "domain_history",
    "ai_memory",
    "conversation",
    "external_research",
    "tool_result",
    "client_context",
)
