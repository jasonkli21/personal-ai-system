"""Operator-owned client bindings for the narrow external v1 conversation API.

This file is authorization policy, never a token/credential or a plugin loader.
Read on each admission and disclosure check; replacement must be atomic.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.auth.scope import CANONICAL_APPLICATION_IDS


class ClientPolicyUnavailable(RuntimeError):
    pass


class ClientApplicationDenied(ValueError):
    pass


class ClientBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    audience: str = Field(min_length=1, max_length=500)
    authorized_party: str = Field(min_length=1, max_length=500)
    application_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")
    expires_at: int = Field(gt=0)
    enabled: bool = True


class ClientPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["application-client-policy-v1"]
    bindings: tuple[ClientBinding, ...] = Field(max_length=16)

    @model_validator(mode="after")
    def unique_clients(self):
        clients = [(b.audience, b.authorized_party) for b in self.bindings]
        if len(clients) != len(set(clients)):
            raise ValueError("client_binding_duplicate")
        return self


def read_client_policy(settings) -> ClientPolicy:
    filename = settings.auth_application_clients_file
    if not filename:
        return ClientPolicy(schema_version="application-client-policy-v1", bindings=())
    try:
        path = Path(filename)
        if not path.is_absolute():
            raise ValueError("absolute_operator_path_required")
        with path.open("rb") as stream:
            raw = stream.read(32769)
        if len(raw) > 32768:
            raise ValueError("client_policy_too_large")
        policy = ClientPolicy.model_validate_json(raw)
        # The existing UI audience cannot be reinterpreted as another application.
        if any(b.audience == settings.auth_audience for b in policy.bindings):
            raise ValueError("builtin_audience_reserved")
        return policy
    except Exception as error:
        raise ClientPolicyUnavailable from error


def accepted_audiences(settings) -> str | list[str]:
    audiences = sorted(
        {settings.auth_audience, *(b.audience for b in read_client_policy(settings).bindings)}
    )
    return audiences[0] if len(audiences) == 1 else audiences


def require_client_application(principal, settings, application_id: str) -> bool:
    """Return external-lane status only after exact verified client authorization."""
    policy = read_client_policy(settings)
    if not principal.authenticated:
        if settings.auth_mode == "development" and settings.app_environment in {"local", "test"}:
            return False
        raise ClientApplicationDenied
    if principal.expires_at is None or principal.expires_at <= time.time():
        raise ClientApplicationDenied
    if (
        principal.audience == settings.auth_audience
        and principal.authorized_party == settings.auth_audience
    ):
        if application_id in CANONICAL_APPLICATION_IDS:
            return False
        raise ClientApplicationDenied
    for binding in policy.bindings:
        if (
            principal.issuer == "https://accounts.google.com"
            and principal.audience == binding.audience
            and principal.authorized_party == binding.authorized_party
            and application_id == binding.application_id
            and binding.enabled
            and binding.expires_at > time.time()
        ):
            return True
    raise ClientApplicationDenied


def external_operation_allowed(method: str, path: str) -> bool:
    if path == "/v1/conversations":
        return method in {"GET", "POST"}
    root = r"/v1/conversations/[0-9a-fA-F-]{36}"
    return bool(
        method == "GET"
        and re.fullmatch(root + r"(?:/continuations/[0-9a-fA-F-]{36})?", path)
        or method == "POST"
        and re.fullmatch(root + r"/(?:context-preview|continue)", path)
    )


_request_authority: ContextVar[Callable[[], None] | None] = ContextVar(
    "external_request_authority", default=None
)


def bind_client_authority(authority):
    return _request_authority.set(authority)


def reset_client_authority(token):
    _request_authority.reset(token)


def is_external_client_request() -> bool:
    return _request_authority.get() is not None


def require_current_client_authority():
    authority = _request_authority.get()
    if authority is not None:
        # Safe context error maps both pre-stream and stream failures without
        # leaking policy paths, token claims or directory/provider exceptions.
        from personal_ai.context.providers import ContextPreparationError

        try:
            authority()
        except Exception as error:
            raise ContextPreparationError("context_client_authority_changed") from error
