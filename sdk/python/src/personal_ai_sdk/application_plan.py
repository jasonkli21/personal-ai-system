"""Explicit client for the private synthetic application inference profile."""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Literal, TypedDict, cast

from .client import (
    APIError,
    CapabilityUnavailable,
    Client,
    CompletedMessage,
    Identity,
    UncertainTurn,
    _id,
)

_PREFIX = "/private/application-plan/v1/conversations"
_CONFIRMATION = re.compile(r"[0-9a-f]{64}")
_EXPIRY = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)")


class PlanPreviewChoice(TypedDict):
    mode: Literal["user_owned_plan"]


class PlanConfirmedChoice(PlanPreviewChoice):
    confirmation: str


class PlanPreviewRequest(TypedDict):
    content: str
    idempotency_key: str
    choice: PlanPreviewChoice


class PlanContinuationRequest(TypedDict):
    content: str
    idempotency_key: str
    choice: PlanConfirmedChoice


class PlanDestination(TypedDict):
    application: str
    provider: Literal["ChatGPT"]
    model: str
    runtime: str
    recipient: str


class PlanHistory(TypedDict):
    category: Literal["conversation_history"]
    turns: int


class PlanProjection(TypedDict):
    category: Literal["domain_current", "ai_memory"]
    fields: list[str]


class PlanPreviewResult(TypedDict):
    confirmation: str
    destination: PlanDestination
    purpose: Literal["foreground_application_plan"]
    selected_context: list[PlanHistory | PlanProjection]
    input_tokens_estimated: int
    expires_at: str


def _request_key(body: object, *, confirmed: bool) -> str:
    if not isinstance(body, dict) or set(body) != {
        "content",
        "idempotency_key",
        "choice",
    }:
        raise ValueError("invalid_plan_request")
    content, key, choice = body["content"], body["idempotency_key"], body["choice"]
    if not isinstance(content, str) or not 1 <= len(content) <= 20000:
        raise ValueError("invalid_plan_request")
    try:
        content.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid_plan_request") from None
    fields = {"mode", "confirmation"} if confirmed else {"mode"}
    if (
        not isinstance(choice, dict)
        or set(choice) != fields
        or choice["mode"] != "user_owned_plan"
    ):
        raise ValueError("invalid_plan_choice")
    if confirmed and not _confirmation(choice["confirmation"]):
        raise ValueError("invalid_plan_confirmation")
    if not isinstance(key, str) or _id(key) != key:
        raise ValueError("invalid_uuid")
    return key


def _confirmation(value: object) -> bool:
    return isinstance(value, str) and _CONFIRMATION.fullmatch(value) is not None


def _matches(obj, fields):
    return isinstance(obj, dict) and obj.keys() == fields


def _label(value, limit):
    return (
        isinstance(value, str)
        and 0 < len(value) <= limit
        and all(char.isprintable() for char in value)
    )


def _preview_result(value, application: str) -> PlanPreviewResult:
    def valid_destination(item):
        return (
            _matches(item, {"application", "provider", "model", "runtime", "recipient"})
            and item["application"] == application
            and item["provider"] == "ChatGPT"
            and _label(item["model"], 200)
            and _label(item["runtime"], 160)
            and _label(item["recipient"], 160)
        )

    def valid_history(item):
        return (
            _matches(item, {"category", "turns"})
            and item["category"] == "conversation_history"
            and type(item["turns"]) is int
            and 0 <= item["turns"] <= 3072
        )

    def valid_projection(item):
        return (
            _matches(item, {"category", "fields"})
            and item["category"] in ("domain_current", "ai_memory")
            and isinstance(item["fields"], list)
            and bool(item["fields"])
            and all(
                isinstance(field, str) and field.isidentifier()
                for field in item["fields"]
            )
            and len(set(item["fields"])) == len(item["fields"])
            and (item["category"] != "ai_memory" or item["fields"] == ["content"])
        )

    fields = {
        "confirmation",
        "destination",
        "purpose",
        "selected_context",
        "input_tokens_estimated",
        "expires_at",
    }
    if not _matches(value, fields):
        raise UncertainTurn("invalid_plan_preview")
    count = value["input_tokens_estimated"]
    items = value["selected_context"]
    expiry = value["expires_at"]
    if not (
        _confirmation(value["confirmation"])
        and valid_destination(value["destination"])
        and value["purpose"] == "foreground_application_plan"
        and type(count) is int
        and 1 <= count <= 10240
        and isinstance(items, list)
        and len(items) == 3
        and valid_history(items[0])
        and all(valid_projection(item) for item in items[1:])
        and {item["category"] for item in items[1:]} == {"domain_current", "ai_memory"}
        and isinstance(expiry, str)
        and _EXPIRY.fullmatch(expiry)
    ):
        raise UncertainTurn("invalid_plan_preview")
    try:
        datetime.fromisoformat(expiry)
    except ValueError:
        raise UncertainTurn("invalid_plan_preview") from None
    return cast(PlanPreviewResult, value)


class ApplicationPlan:
    """Use the isolated profile with the same target and verified scope as Client."""

    def __init__(self, client: Client, *, profile_version: Literal[1] = 1) -> None:
        if type(profile_version) is not int or profile_version != 1:
            raise CapabilityUnavailable("application_plan_profile_unsupported")
        self._client = client

    def preview(
        self, conversation_id: Identity, body: PlanPreviewRequest
    ) -> PlanPreviewResult:
        _request_key(body, confirmed=False)
        try:
            value = self._client._json(
                "POST",
                f"{_PREFIX}/{_id(conversation_id)}/context-preview",
                body,
                max_response=8192,
                strict_response=True,
            )
        except APIError as error:
            if error.status == 404:
                raise CapabilityUnavailable("application_plan_unavailable") from None
            raise
        return _preview_result(value, self._client._application)

    def continue_turn(
        self,
        conversation_id: Identity,
        body: PlanContinuationRequest,
        provisional: Callable[[str], None] | None = None,
    ) -> CompletedMessage:
        key = _request_key(body, confirmed=True)
        try:
            return self._client._continue_at(
                f"{_PREFIX}/{_id(conversation_id)}/continue",
                conversation_id,
                key,
                body,
                provisional,
                max_output_bytes=100,
            )
        except APIError as error:
            if error.status == 404:
                raise CapabilityUnavailable("application_plan_unavailable") from None
            raise
