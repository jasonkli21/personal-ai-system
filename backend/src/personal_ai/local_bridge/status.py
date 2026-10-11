"""Coarse local subscription observations, never strict-free quota or billing facts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CoarseUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state: Literal["available", "limit", "unavailable", "unknown"] = "unknown"
    observed_at: int | None = Field(default=None, strict=True, ge=0)
    fact_source: Literal["local_observed"] = "local_observed"
    # No reset field: generic failures do not establish a reset or remaining capacity.


def usage_observation(code: str | None, *, now: int, success: bool = False) -> CoarseUsage:
    state = (
        "available"
        if success
        else (
            "limit"
            if code == "bridge_usage_limit"
            else "unavailable"
            if code in {"bridge_unavailable", "bridge_usage_unavailable", "bridge_ineligible"}
            else "unknown"
        )
    )
    return CoarseUsage(state=state, observed_at=now)


class RecoveryHooks(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reconnect: Literal["local_operator"] = "local_operator"
    switch_account: Literal["local_operator_new_pairing"] = "local_operator_new_pairing"
    manage_usage: Literal["provider_account_ui"] = "provider_account_ui"
