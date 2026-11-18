"""Exact synthetic USD exposure and authoritative settlement facts."""

import hashlib
from datetime import datetime
from fractions import Fraction
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .owner_policy import ExactRoute, PolicyDenied

MAX_MICROS = 2**63 - 1
Dimension = Literal["input", "output", "reasoning", "requests"]


class _Exact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BilledDimension(_Exact):
    dimension: Dimension
    micros_per_million: int = Field(ge=0, le=MAX_MICROS)
    increment: int = Field(ge=1, le=1_000_000)
    minimum: int = Field(ge=0, le=2_000_000)


class BillingGroup(_Exact):
    dimensions: tuple[BilledDimension, ...] = Field(min_length=1, max_length=4)
    minimum_micros: int = Field(ge=0, le=MAX_MICROS)
    fixed_micros: int = Field(ge=0, le=MAX_MICROS)


class PayerPeriod(_Exact):
    start: datetime
    end: datetime
    anchor: datetime
    timezone: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def interval(self):
        try:
            zone = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError("inference_billing_calendar_invalid") from None
        for time in (self.start, self.end, self.anchor):
            if time.utcoffset() is None or time.utcoffset() != time.astimezone(zone).utcoffset():
                raise ValueError("inference_billing_calendar_invalid")
        if not self.anchor <= self.start < self.end:
            raise ValueError("inference_billing_calendar_invalid")
        return self


class PaidExposure(_Exact):
    route: ExactRoute
    payer_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authenticated_rate_source: str = Field(pattern=r"^[a-f0-9]{64}$")
    currency: Literal["USD"]
    period: PayerPeriod
    price_start: datetime
    price_end: datetime
    groups: tuple[BillingGroup, ...] = Field(min_length=1, max_length=8)
    root_cap_micros: int = Field(ge=1, le=MAX_MICROS)
    owner_cap_micros: int = Field(ge=1, le=MAX_MICROS)
    payer_cap_micros: int = Field(ge=1, le=MAX_MICROS)
    reasoning_bound: int = Field(ge=0, le=1_000_000)
    upstream_maximum_micros: int = Field(ge=1, le=MAX_MICROS)
    payer_granted: Literal[True]
    synthetic_account_exclusive: Literal[True]

    @model_validator(mode="after")
    def scope_and_rates(self):
        dimensions = [rate.dimension for group in self.groups for rate in group.dimensions]
        if (
            self.route.route_class != "paid_api"
            or set(dimensions) != {"input", "output", "reasoning", "requests"}
            or len(dimensions) != 4
            or self.price_start.utcoffset() is None
            or self.price_end.utcoffset() is None
            or self.price_start >= self.price_end
            or self.payer_granted is not True
            or self.synthetic_account_exclusive is not True
        ):
            raise ValueError("inference_price_invalid")
        return self

    @property
    def fingerprint(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def maximum(self, *, input_tokens, output_tokens, now):
        if (
            not self.price_start <= now < self.price_end
            or not self.period.start <= now < self.period.end
            or type(input_tokens) is not int
            or not 0 <= input_tokens <= 2_000_000
            or type(output_tokens) is not int
            or not 1 <= output_tokens <= 1_000_000
        ):
            raise PolicyDenied("inference_price_or_bound_invalid")
        units = {
            "input": input_tokens,
            "output": output_tokens,
            "reasoning": self.reasoning_bound,
            "requests": 1,
        }
        total = Fraction(0)
        for group in self.groups:
            amount = Fraction(0)
            for rate in group.dimensions:
                rounded = (
                    (max(units[rate.dimension], rate.minimum) + rate.increment - 1)
                    // rate.increment
                    * rate.increment
                )
                amount += Fraction(rounded * rate.micros_per_million, 1_000_000)
            total += max(group.minimum_micros, amount) + group.fixed_micros
        result = total.__ceil__()
        maximum = max(result, self.upstream_maximum_micros)
        if not 0 < maximum <= MAX_MICROS or result > self.upstream_maximum_micros:
            raise PolicyDenied("inference_provider_maximum_invalid")
        return maximum


class ChargeReceipt(_Exact):
    attempt_id: UUID
    payer_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    binding_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    period_start: datetime
    period_end: datetime
    currency: Literal["USD"]
    receipt_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    actual_micros: int = Field(ge=0, le=MAX_MICROS)
