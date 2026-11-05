"""Static validation for an unregistered reasoning-request-v1 sketch."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .catalog import CATALOG


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def ceiling(maximum: int):
    return Field(ge=0, le=maximum)


class Budget(Closed):
    max_model_calls: Annotated[int, ceiling(64)] = 0
    max_tool_calls: Annotated[int, ceiling(64)] = 0
    max_elapsed_seconds: Annotated[int, ceiling(600)] = 0
    max_input_tokens: Annotated[int, ceiling(1_000_000)] = 0
    max_output_tokens: Annotated[int, ceiling(100_000)] = 0
    max_concurrency: Annotated[int, ceiling(16)] = 0
    max_sources: Annotated[int, ceiling(64)] = 0
    max_provider_cost_usd: Annotated[str, Field(pattern=r"^(0|[1-9][0-9]?)\.[0-9]{2}$")] = "0.00"


class ReasoningRequest(Closed):
    schema_version: Literal["reasoning-request-v1"]
    effort: Literal["auto", "low", "medium", "high", "max"] = "auto"
    strategy: Annotated[str, Field(max_length=32)] = "auto"
    research: Literal["off", "if_authorized"] = "off"
    budget: Budget = Budget()

    @field_validator("strategy")
    @classmethod
    def known_strategy(cls, strategy: str) -> str:
        if strategy != "auto" and strategy not in CATALOG:
            raise ValueError("unknown strategy")
        return strategy
