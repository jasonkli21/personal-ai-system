"""Provider stream lifecycle and cancellation handling for chat turns."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

import anyio

from personal_ai.context.deadline import remaining
from personal_ai.entities import Message, MessageRole, MessageStatus
from personal_ai.llm.client import GenerationEvent
from personal_ai.llm.errors import LLMIncompleteGenerationError, LLMTimeoutError
from personal_ai.services.chat.events import TurnEvent

logger = logging.getLogger("personal_ai.services.chat.service")


class ManagedStream:
    """Async iterator that finalizes a prepared turn when abandoned before start."""

    def __init__(
        self, iterator: AsyncIterator[TurnEvent], on_abandon: Callable[[], Awaitable[None]]
    ) -> None:
        self._iterator = iterator.__aiter__()
        self._on_abandon = on_abandon
        self._started = False
        self._closed = False

    def __aiter__(self) -> ManagedStream:
        return self

    async def __anext__(self) -> TurnEvent:
        if self._closed:
            raise StopAsyncIteration
        self._started = True
        try:
            return await self._iterator.__anext__()
        except StopAsyncIteration:
            self._closed = True
            raise

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._started:
            close = getattr(self._iterator, "aclose", None)
            if close is not None:
                await close()
        else:
            await self._on_abandon()


async def produce_deltas(
    iterator: AsyncIterator[GenerationEvent],
    events: asyncio.Queue[GenerationEvent | Exception | None],
    demand: asyncio.Semaphore,
    *,
    request_id: str,
) -> None:
    """Own provider iteration and teardown in a single task with backpressure."""
    failure: Exception | None = None
    saw_terminal = False
    try:
        while True:
            await demand.acquire()
            try:
                event = await anext(iterator)
            except StopAsyncIteration:
                break
            await events.put(event)
            if event.kind == "terminal":
                saw_terminal = True
    except asyncio.CancelledError:
        raise
    # The consumer applies the normal safe model/storage error mapping.
    except Exception as error:  # noqa: BLE001
        failure = error
    finally:
        if failure is None and not saw_terminal:
            failure = LLMIncompleteGenerationError(
                "language model ended without a terminal result"
            )
        close = getattr(iterator, "aclose", None)
        if close is not None:
            with anyio.CancelScope(shield=True):
                with anyio.move_on_after(1) as timeout_scope:
                    try:
                        await close()
                    # Teardown must not replace a model failure or cancellation.
                    except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001
                        logger.error(
                            "Provider stream cleanup failed request_id=%s error_class=%s",
                            request_id,
                            type(error).__name__,
                        )
                if timeout_scope.cancel_called:
                    logger.error("Provider stream cleanup timed out request_id=%s", request_id)
    # Never queue a terminal event on cancellation: the disconnected consumer
    # may no longer be draining the queue. The finally block above still runs.
    await events.put(failure)


async def next_provider_event(events, deadline: float):
    try:
        return await asyncio.wait_for(events.get(), timeout=remaining(deadline))
    except TimeoutError as error:
        raise LLMTimeoutError("language model request timed out") from error


async def cancel_provider_task(task: asyncio.Task[None], *, request_id: str) -> None:
    """Cancel and briefly join provider iteration outside the ASGI cancel scope."""
    if not task.done():
        task.cancel()
    with anyio.CancelScope(shield=True):
        with anyio.move_on_after(1) as timeout_scope:
            try:
                await task
            except asyncio.CancelledError:
                pass
            # Cleanup errors must not replace the request cancellation.
            except Exception as error:  # noqa: BLE001
                logger.error(
                    "Provider task cleanup failed request_id=%s error_class=%s",
                    request_id,
                    type(error).__name__,
                )
        if timeout_scope.cancel_called:
            logger.error("Provider task cleanup timed out request_id=%s", request_id)


def unfinished_continuation_user(active: Sequence[Message]) -> Message | None:
    if not active:
        return None
    message = active[-1]
    if (
        message.role is MessageRole.USER
        and message.status is MessageStatus.COMPLETED
        and message.continuation_digest is not None
    ):
        return message
    return None
