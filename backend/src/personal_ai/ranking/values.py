"""values ranking policy."""

from __future__ import annotations

from decimal import Decimal

from personal_ai.entities.research import (
    AvailabilityValue,
    DateTimeValue,
    DateValue,
    DateWindowValue,
    LocationValue,
    MoneyValue,
    NumberValue,
    QuantityValue,
    TextValue,
    TypedValue,
)
from personal_ai.ranking.normalization import _identifier

_UNITS: dict[str, tuple[str, Decimal]] = {
    "m": ("length", Decimal(1)),
    "meter": ("length", Decimal(1)),
    "meters": ("length", Decimal(1)),
    "cm": ("length", Decimal("0.01")),
    "mm": ("length", Decimal("0.001")),
    "km": ("length", Decimal(1000)),
    "in": ("length", Decimal("0.0254")),
    "inch": ("length", Decimal("0.0254")),
    "inches": ("length", Decimal("0.0254")),
    "ft": ("length", Decimal("0.3048")),
    "foot": ("length", Decimal("0.3048")),
    "feet": ("length", Decimal("0.3048")),
    "kg": ("mass", Decimal(1)),
    "g": ("mass", Decimal("0.001")),
    "lb": ("mass", Decimal("0.45359237")),
    "lbs": ("mass", Decimal("0.45359237")),
}


def _value_key(value: TypedValue) -> tuple | None:
    if isinstance(value, QuantityValue):
        unit = _UNITS.get(value.unit.casefold())
        if unit is None:
            return None
        dimension, factor = unit
        return ("quantity", dimension, value.amount * factor)
    if isinstance(value, MoneyValue):
        return ("money", value.currency, value.amount)
    if isinstance(value, NumberValue):
        return ("number", value.value)
    if isinstance(value, TextValue):
        return ("text", _identifier(value.value))
    if isinstance(value, DateValue):
        return ("date", value.value.isoformat())
    if isinstance(value, DateTimeValue):
        return ("datetime", value.value.isoformat())
    if isinstance(value, DateWindowValue):
        return ("date_window", value.start.isoformat(), value.end.isoformat())
    if isinstance(value, LocationValue):
        return ("location", round(value.latitude, 7), round(value.longitude, 7))
    if isinstance(value, AvailabilityValue):
        return ("availability", value.value)
    return ("boolean", value.value)


def values_equal(left: TypedValue, right: TypedValue) -> bool | None:
    left_key, right_key = _value_key(left), _value_key(right)
    if left_key is None or right_key is None:
        return None
    if left_key[0] != right_key[0]:
        return False
    # Different currencies and incompatible physical dimensions are unknown,
    # not a false comparison that could masquerade as a hard failure.
    if left_key[0] in {"money", "quantity"} and left_key[1] != right_key[1]:
        return None
    return left_key == right_key


def _numeric(value: TypedValue) -> tuple[Decimal, str] | None:
    if isinstance(value, NumberValue):
        return value.value, "number"
    if isinstance(value, MoneyValue):
        return value.amount, f"currency:{value.currency}"
    if isinstance(value, QuantityValue):
        unit = _UNITS.get(value.unit.casefold())
        if unit is None:
            return None
        dimension, factor = unit
        return value.amount * factor, f"unit:{dimension}"
    return None
