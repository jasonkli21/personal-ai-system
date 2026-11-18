"""Owner preferences and a side-effect-free eligibility and ordering step."""

import json
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from personal_ai.auth.scope import (
    ApplicationScope,
    current_request_scope,
    current_verified_principal,
)

from .contracts import EndpointProfile, EndpointRef, Sensitivity, sensitivity_exceeds

RouteClass = Literal["subscription", "free_api", "paid_api"]


class PolicyDenied(ValueError):
    """Content-free denial suitable for the isolated composition."""


class ExactRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    route_class: RouteClass
    profile: EndpointRef
    model: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,199}$")
    credential: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,199}$")
    account: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,199}$")
    recipient: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,99}$")
    scope: ApplicationScope
    operation: Literal["bounded_generation"]
    price_revision: str | None = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,99}$")

    @field_validator("profile", mode="before")
    @classmethod
    def exact_profile_version(cls, value):
        if isinstance(value, dict) and type(value.get("profile_version")) is not int:
            raise ValueError("inference_policy_profile_version_invalid")
        return value

    @model_validator(mode="after")
    def price_matches_class(self):
        if (self.price_revision is not None) != (self.route_class == "paid_api"):
            raise ValueError("inference_policy_price_binding_invalid")
        return self

    def matches(self, profile: EndpointProfile) -> bool:
        return (
            profile.ref == self.profile
            and profile.model_id == self.model
            and profile.credential_scope_id == self.credential
            and profile.account_scope_id == self.account
            and (profile.execution_mode, profile.cost_class)
            == {
                "free_api": ("STRICT_FREE", "VERIFIED_FREE"),
                "subscription": ("CHATGPT_PLAN", "SUBSCRIPTION"),
                "paid_api": ("EXPLICIT_BYOK", "USER_BILLED"),
            }[self.route_class]
        )


class OwnerInferencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    schema_version: Literal["inference-policy-v2"]
    mode: Literal["free_only", "custom"]
    routes: tuple[RouteClass, ...] = Field(max_length=3)
    allow: tuple[ExactRoute, ...] = Field(max_length=16)
    owner_monthly_cap_micros: int | None = Field(ge=1, le=2**63 - 1)

    @model_validator(mode="after")
    def coherent(self):
        if len(set(self.routes)) != len(self.routes) or len(set(self.allow)) != len(self.allow):
            raise ValueError("inference_policy_duplicate")
        if self.mode == "free_only" and self.routes != ("free_api",):
            raise ValueError("inference_policy_free_only")
        if any(route.route_class not in self.routes for route in self.allow):
            raise ValueError("inference_policy_class_disabled")
        if ("paid_api" in self.routes) != (self.owner_monthly_cap_micros is not None):
            raise ValueError("inference_policy_cap_invalid")
        return self


FREE_ONLY = OwnerInferencePolicy(
    schema_version="inference-policy-v2",
    mode="free_only",
    routes=("free_api",),
    allow=(),
    owner_monthly_cap_micros=None,
)


def read_policy(payload: bytes | None) -> tuple[OwnerInferencePolicy, str | None]:
    if payload is None:
        return FREE_ONLY, None
    try:
        if len(payload) > 32768:
            raise ValueError
        document = json.loads(payload, object_pairs_hook=_unique_fields)
        if isinstance(document, dict) and document.get("schema_version") == "inference-policy-v1":
            return FREE_ONLY, None
        return OwnerInferencePolicy.model_validate_json(payload), None
    except (ValidationError, ValueError, RecursionError):
        return FREE_ONLY, "inference_policy_invalid_resave"


def _unique_fields(items):
    fields = dict(items)
    if len(fields) != len(items):
        raise ValueError("inference_policy_duplicate_field")
    return fields


class OwnerPolicyRepository(Protocol):
    def read(self, owner_id): ...

    def replace(self, owner_id, expected_revision, policy): ...

    def remaining(self, owner_id, cap): ...


class OwnerInferenceSettings:
    """Trusted management surface. App scopes can consume only narrowed settings."""

    def __init__(self, repository: OwnerPolicyRepository, registry, *, is_member):
        self.repository = repository
        self.registry = registry
        self.is_member = is_member

    def verified_scope(self, *, management=False):
        scope = current_request_scope()
        principal = current_verified_principal()
        if (
            scope is None
            or principal is None
            or not principal.authenticated
            or principal.owner_id != scope.owner_id
            or f"{principal.issuer}|{principal.subject}" != scope.acting_user_id
            or (management and (scope.application_id, scope.workspace_id) != ("personal_ai", None))
            or (scope.workspace_id is not None and self.is_member(scope) is not True)
        ):
            raise PolicyDenied("inference_policy_scope_denied")
        return scope

    def read(self):
        scope = self.verified_scope(management=True)
        revision, payload = self.repository.read(scope.owner_id)
        policy, diagnostic = read_policy(payload)
        # No route identities or shared payer balance leave the trusted settings service.
        remaining = self.repository.remaining(scope.owner_id, policy.owner_monthly_cap_micros)
        return revision, policy.routes, diagnostic, remaining

    def update(self, *, expected_revision: int, payload: bytes):
        scope = self.verified_scope(management=True)
        _, diagnostic = read_policy(payload)
        if (
            type(payload) is not bytes
            or diagnostic
            or type(expected_revision) is not int
            or not 0 <= expected_revision < 2**63 - 1
        ):
            raise PolicyDenied("inference_policy_update_invalid")
        try:
            policy = OwnerInferencePolicy.model_validate_json(payload)
        except ValidationError:
            raise PolicyDenied("inference_policy_update_invalid") from None
        profiles = self.registry.refresh().profiles
        if any(not any(route.matches(profile) for profile in profiles) for route in policy.allow):
            raise PolicyDenied("inference_policy_route_unavailable")
        return self.repository.replace(scope.owner_id, expected_revision, policy)


class RouteGrant(BaseModel):
    """Current facts from the operator, credential owner and disclosure authorities."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    route: ExactRoute
    owner_id: str
    actor_id: str
    payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    valid_until: datetime
    maximum_sensitivity: Sensitivity
    operator_enabled: Literal[True]
    credential_owner_verified: Literal[True]
    installation_verified: Literal[True]
    privacy_region_verified: Literal[True]
    prepared_fields_verified: Literal[True]
    counter_verified: Literal[True]
    source_free: Literal[True]
    foreground: Literal[True]

    def permits(self, *, owner_id, actor_id, payload_sha256, sensitivity, now):
        return (
            self.owner_id == owner_id
            and self.actor_id == actor_id
            and self.payload_sha256 == payload_sha256
            and self.valid_until.utcoffset() is not None
            and now < self.valid_until
            and not sensitivity_exceeds(sensitivity, self.maximum_sensitivity)
            and all(
                fact is True
                for fact in (
                    self.operator_enabled,
                    self.credential_owner_verified,
                    self.installation_verified,
                    self.privacy_region_verified,
                    self.prepared_fields_verified,
                    self.counter_verified,
                    self.source_free,
                    self.foreground,
                )
            )
        )


def order_candidates(
    policy: OwnerInferencePolicy,
    *,
    ranked: tuple[ExactRoute, ...],
    grants: tuple[RouteGrant, ...],
    owner_id: str,
    actor_id: str,
    scope: ApplicationScope,
    recipient: str,
    payload_sha256: str,
    sensitivity: Sensitivity,
    now: datetime,
    narrowing: frozenset[ExactRoute] | None = None,
) -> tuple[ExactRoute, ...]:
    """Order already hard-admitted candidates while keeping their within-class rank."""
    eligible = {
        grant.route
        for grant in grants
        if grant.route.scope == scope
        and grant.route.recipient == recipient
        and grant.permits(
            owner_id=owner_id,
            actor_id=actor_id,
            payload_sha256=payload_sha256,
            sensitivity=sensitivity,
            now=now,
        )
    }
    allowed = eligible.intersection(policy.allow)
    if narrowing is not None:
        allowed.intersection_update(narrowing)
    return tuple(
        candidate
        for route_class in policy.routes
        for candidate in dict.fromkeys(ranked)
        if candidate.route_class == route_class and candidate in allowed
    )
