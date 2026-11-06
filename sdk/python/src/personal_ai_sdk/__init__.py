"""Provisional Personal AI consumer v1.2 Python client."""

from .client import (
    CONSUMER_VERSION,
    APIError,
    CapabilityUnavailable,
    Client,
    CompletedMessage,
    Continuation,
    ContinuationStatus,
    ContractMismatch,
    UncertainTurn,
)
from .synthetic_reasoning import SyntheticReasoning

__all__ = [
    "CONSUMER_VERSION",
    "APIError",
    "CapabilityUnavailable",
    "Client",
    "CompletedMessage",
    "Continuation",
    "ContinuationStatus",
    "ContractMismatch",
    "SyntheticReasoning",
    "UncertainTurn",
]
