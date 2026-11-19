"""HTTP/SSE adapter for neutral chat-turn events."""

from __future__ import annotations

from collections.abc import AsyncIterator

from personal_ai.api.schemas import (
    SSEMessageCreated,
    SSEResponseCompleted,
    SSEResponseDelta,
    SSEResponseError,
)
from personal_ai.auth.application_clients import external_conversation_namespace
from personal_ai.services.chat.events import (
    TurnCompleted,
    TurnDelta,
    TurnEvent,
    TurnFailed,
    TurnMessageCreated,
)


class SSEFrameStream:
    """Forward service events and preserve close behavior before first iteration."""

    def __init__(self, events: AsyncIterator[TurnEvent]) -> None:
        self._events = events
        self._closed = False

    def __aiter__(self) -> SSEFrameStream:
        return self

    async def __anext__(self) -> str:
        if self._closed:
            raise StopAsyncIteration
        try:
            event = await anext(self._events)
        except StopAsyncIteration:
            self._closed = True
            raise
        return _serialize_event(event)

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._events, "aclose", None)
        if close is not None:
            await close()


def sse_frames(events: AsyncIterator[TurnEvent]) -> SSEFrameStream:
    """Serialize service events using the stable conversation SSE contract."""
    return SSEFrameStream(events)


def conversation_message_for_response(message):
    """Keep retained grant identities inside the isolated service."""
    attribution = message.attribution
    if external_conversation_namespace() and attribution and attribution.source_snapshots:
        return message.model_copy(update={
            "attribution": attribution.model_copy(update={"source_snapshots": ()}),
        })
    return message


def _serialize_event(event: TurnEvent) -> str:
    if isinstance(event, TurnMessageCreated):
        name, payload = (
            "message.created", SSEMessageCreated(message=conversation_message_for_response(event.message))
        )
    elif isinstance(event, TurnDelta):
        name, payload = (
            "response.delta",
            SSEResponseDelta(message_id=event.message_id, delta=event.delta),
        )
    elif isinstance(event, TurnCompleted):
        name, payload = (
            "response.completed", SSEResponseCompleted(message=conversation_message_for_response(event.message))
        )
    elif isinstance(event, TurnFailed):
        name, payload = (
            "response.error",
            SSEResponseError(message_id=event.message_id, code=event.code, message=event.message),
        )
    else:  # pragma: no cover - closed union guard
        raise TypeError(f"unsupported chat turn event: {type(event).__name__}")
    data = payload.model_dump_json()
    if isinstance(event, (TurnCompleted, TurnFailed)) and event.reasoning is not None:
        data = data[:-1] + ',"reasoning":' + event.reasoning.model_dump_json() + "}"
    return f"event: {name}\ndata: {data}\n\n"
