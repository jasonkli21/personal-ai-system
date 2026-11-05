"""Attempt binding for the installed, in-process continuation fixture only."""

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from personal_ai.llm.client import GenerationMetadata, ProviderIdentity

from .errors import LLMInvalidRequestError


@dataclass(slots=True)
class FixtureAttempt:
    child_key: UUID
    attempt_id: UUID
    endpoint: ProviderIdentity
    reserve_count: Callable[[], None]
    observe_count: Callable[[int], None]
    dispatch: Callable[[int], None]
    metadata: GenerationMetadata | None = None

    def require_endpoint(self, identity):
        if identity != self.endpoint:
            raise LLMInvalidRequestError("workflow fixture endpoint changed")

    def accept(self, metadata, request_id):
        self.require_endpoint(metadata.identity)
        if (
            request_id != str(self.child_key)
            or metadata.invocation_id != request_id
            or metadata.attempt_ids != (str(self.attempt_id),)
            or metadata.status != "success"
            or self.metadata is not None
        ):
            raise LLMInvalidRequestError("workflow fixture receipt binding changed")
        self.metadata = metadata


fixture_attempt: ContextVar[FixtureAttempt | None] = ContextVar("workflow_fixture_attempt", default=None)


@contextmanager
def bind_fixture_attempt(attempt):
    token = fixture_attempt.set(attempt)
    try:
        yield
    finally:
        fixture_attempt.reset(token)
