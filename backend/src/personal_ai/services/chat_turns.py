"""Durable Phase 1 chat-turn lifecycle and server-sent event payloads."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4, uuid5

import anyio

from personal_ai.api.schemas import (
    SSEMessageCreated,
    SSEResponseCompleted,
    SSEResponseDelta,
    SSEResponseError,
)
from personal_ai.applications.contracts import ApplicationContextRequest, ContextSensitivity
from personal_ai.auth.scope import ApplicationScope
from personal_ai.context import ContextAssembler
from personal_ai.context.authorization import make_inference_context
from personal_ai.context.contracts import ContextError
from personal_ai.context.deadline import remaining
from personal_ai.context.history import conversation_context_messages
from personal_ai.context.providers import ContextPreparationError
from personal_ai.context.traces import ContextTraceManifest, ContextTraceRepository
from personal_ai.contracts.context_references import ContextEntityReference
from personal_ai.entities import MAX_MESSAGE_CONTENT_CHARS, Message, MessageRole, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.llm import (
    ChatMessage,
    GenerationClient,
    InferenceContext,
    LLMError,
    LLMInvalidRequestError,
    LLMInvalidResponseError,
    LLMTimeoutError,
)
from personal_ai.llm.client import GenerationEvent, GenerationMetadata, GenerationResult
from personal_ai.llm.errors import LLMIncompleteGenerationError
from personal_ai.llm.preparation import require_matching_endpoint
from personal_ai.storage import ConversationConflictError, ResourceNotFoundError
from personal_ai.storage.async_io import io_call
from personal_ai.storage.repositories import ConversationRepository, MessageRepository
from personal_ai.usage.context import bind_usage_task

logger = logging.getLogger(__name__)


class InvalidRetryTargetError(Exception):
    """A regenerate or edit-and-retry target is not in a retryable state."""


@dataclass(frozen=True, slots=True)
class _PreparedTurn:
    created: tuple[Message, ...]
    assistant: Message
    history: tuple[ChatMessage, ...]
    request_id: str
    deadline: float
    selected_memory_ids: tuple[UUID, ...] = ()
    selected_message_ids: tuple[UUID, ...] = ()
    inference_context: InferenceContext | None = None


class _ManagedStream:
    """Async iterator that finalizes a prepared turn when abandoned before start."""

    def __init__(
        self, iterator: AsyncIterator[str], on_abandon: Callable[[], Awaitable[None]]
    ) -> None:
        self._iterator = iterator.__aiter__()
        self._on_abandon = on_abandon
        self._started = False
        self._closed = False

    def __aiter__(self) -> _ManagedStream:
        return self

    async def __anext__(self) -> str:
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

class ChatTurnService:
    """Create append-only turns, stream model output, and finalize state."""

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        llm: GenerationClient,
        *,
        owner_id: str,
        application_context: ApplicationContextRequest | None = None,
        model: str,
        stale_stream_after_seconds: float = 360,
        context_assembler: ContextAssembler,
        context_traces: ContextTraceRepository | None = None,
        memory_retriever=None,
        memory_extraction=None,
        memory_lifecycle=None,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._llm = llm
        self._owner_id = owner_id
        self._application_context = application_context
        self._context = context_assembler
        self._context_traces = context_traces
        self._memory_retriever = memory_retriever
        self._memory_extraction = memory_extraction
        self._memory_lifecycle = memory_lifecycle
        self._post_completion_tasks: set[asyncio.Task[None]] = set()
        self._model = model
        self._stale_stream_after_seconds = stale_stream_after_seconds

    def _active(self, conversation_id: UUID) -> list[Message]:
        self._conversations.get(owner_id=self._owner_id, conversation_id=conversation_id)
        self._recover_stale_turn(conversation_id)
        active = self._messages.list_active(
            owner_id=self._owner_id, conversation_id=conversation_id
        )
        self._ensure_no_streaming_turn(active)
        return active

    def require_context(self, context: ApplicationContextRequest) -> None:
        if self._owner_id != context.scope.owner_id or self._application_context != context:
            raise ContextPreparationError("turn_context_scope_mismatch")

    def get_message(self, conversation_id: UUID, message_id: UUID) -> Message:
        return self._messages.get(
            owner_id=self._owner_id, conversation_id=conversation_id, message_id=message_id
        )

    def transition(self, current: Message, replacement: Message) -> Message:
        result = self._messages.update_status(
            owner_id=self._owner_id,
            conversation_id=current.conversation_id,
            message_id=current.id,
            status=replacement.status,
            updated_at=datetime.now(UTC),
            expected_message=current,
            replacement=replacement,
            expected_branch_digest=current.execution.branch_digest if current.execution else None,
        )
        if result is None:
            raise ConversationConflictError("turn changed; inspect canonical state")
        return result

    def prepare_external(
        self,
        conversation_id: UUID,
        content: str,
        *,
        request_id: str,
        assistant_id: UUID,
        user_id: UUID,
        preparation_hook,
        candidate_message_ids=None,
        candidate_entities: Sequence[ContextEntityReference] = (),
        history_authorizer=None,
        continuation_digest: str,
        context_assembler: ContextAssembler | None = None,
        excluded_source_classes=frozenset(),
        maximum_context_sensitivity: ContextSensitivity | None = None,
    ) -> _PreparedTurn:
        # External assembly must not disclose context to an unrelated count/summary provider.
        from personal_ai.context.tokens import EstimatedTokenCounter

        preparation_context = context_assembler or self._context
        if (
            not isinstance(preparation_context.counter, EstimatedTokenCounter)
            or preparation_context.summarizer is not None
        ):
            raise ContextPreparationError("external_context_requires_local_preparation")
        if self._application_context is None:
            raise ContextPreparationError("application_context_required")
        active = self._active(conversation_id)
        try:
            user = self.get_message(conversation_id, user_id)
        except ResourceNotFoundError:
            abandoned_user = _unfinished_continuation_user(active)
            user = self._new_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=content,
                status=MessageStatus.COMPLETED,
                now=datetime.now(UTC),
                parent_message_id=(
                    abandoned_user.parent_message_id
                    if abandoned_user is not None
                    else (active[-1].id if active else None)
                ),
                message_id=user_id,
                continuation_digest=continuation_digest,
                supersedes_message_id=abandoned_user.id if abandoned_user else None,
            )
            already_persisted = False
            supersede_from = abandoned_user.id if abandoned_user else None
        else:
            if (
                user.role is not MessageRole.USER
                or user.content != content
                or user.continuation_digest != continuation_digest
                or user.status is not MessageStatus.COMPLETED
                or not active
                or active[-1].id != user.id
            ):
                raise ConversationConflictError("idempotency_input_changed_or_turn_not_resumable")
            already_persisted = True
            supersede_from = None
        return self._prepare_context_turn(
            active,
            user,
            () if already_persisted else (user,),
            supersede_from,
            None,
            request_id,
            assistant_id=assistant_id,
            preparation_hook=preparation_hook,
            external=True,
            candidate_message_ids=candidate_message_ids,
            candidate_entities=candidate_entities,
            history_authorizer=history_authorizer,
            continuation_digest=continuation_digest,
            user_already_persisted=already_persisted,
            context_assembler=preparation_context,
            excluded_source_classes=frozenset(excluded_source_classes) | {"ai_memory"},
            maximum_context_sensitivity=maximum_context_sensitivity,
        )

    def preview_external_context(
        self,
        conversation_id: UUID,
        content: str,
        *,
        candidate_message_ids=None,
        candidate_entities: Sequence[ContextEntityReference] = (),
        history_authorizer=None,
        excluded_source_classes=frozenset(),
        maximum_context_sensitivity: ContextSensitivity | None = None,
        context_assembler: ContextAssembler | None = None,
    ):
        """Return a read-only planner projection without reservation or provider work."""
        if self._application_context is None:
            raise ContextPreparationError("application_context_required")
        context = context_assembler or self._context
        self._conversations.get(owner_id=self._owner_id, conversation_id=conversation_id)
        active = self._messages.list_active(
            owner_id=self._owner_id, conversation_id=conversation_id
        )
        history = active
        if candidate_message_ids is not None:
            from personal_ai.context.contracts import complete_turns

            requested = set(candidate_message_ids)
            eligible = complete_turns(active)
            if requested - {message.id for turn in eligible for message in turn}:
                raise ContextPreparationError("continuation_source_not_active_completed")
            history = [
                message
                for turn in eligible
                if any(message.id in requested for message in turn)
                for message in turn
            ]
        history = conversation_context_messages(
            history,
            allow_manual_external=(
                self._application_context.definition.context_policy.sidecar
                .allow_manual_import_context
            ),
        )
        if history_authorizer is not None:
            history_authorizer(tuple(message.id for message in history))
        plan = context.plan_context(
            content,
            self._application_context,
            candidate_entities=candidate_entities,
            excluded_source_classes=frozenset(excluded_source_classes) | {"ai_memory"},
            maximum_sensitivity=maximum_context_sensitivity,
        )
        return plan, len(history)

    def continue_turn(self, conversation_id: UUID, request) -> AsyncIterator[str]:
        """An automatic continuation uses the configured generation lane and shared assembly."""
        if request.choice.mode != "automatic":
            raise ContextPreparationError("external_choice_requires_preparation")
        if request.launch_context is not None:
            if self._application_context is None:
                raise ContextPreparationError("application_context_required")
            try:
                request.launch_context.validate_for(
                    self._application_context.scope, conversation_id
                )
            except ValueError as error:
                raise ContextPreparationError("application_launch_scope_mismatch") from error
        identity = uuid5(
            conversation_id,
            f"{self._owner_id}:{self._application_context.scope.application_id if self._application_context else 'personal_ai'}:{self._application_context.scope.workspace_id if self._application_context else None}:{request.idempotency_key}",
        )
        intent_digest = request.intent_digest
        active = self._active(conversation_id)
        try:
            existing_assistant = self.get_message(conversation_id, identity)
        except ResourceNotFoundError:
            existing_assistant = None
        if existing_assistant is not None:
            if existing_assistant.continuation_digest != intent_digest:
                raise ConversationConflictError("idempotency_input_changed")
            if existing_assistant.status is MessageStatus.COMPLETED:
                return self._replay_completed_continuation(conversation_id, existing_assistant)
            raise ConversationConflictError("continuation_exists_inspect_canonical_state")

        user_id = uuid5(identity, "user")
        try:
            user = self.get_message(conversation_id, user_id)
        except ResourceNotFoundError:
            abandoned_user = _unfinished_continuation_user(active)
            user = self._new_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=request.content,
                status=MessageStatus.COMPLETED,
                now=datetime.now(UTC),
                parent_message_id=(
                    abandoned_user.parent_message_id
                    if abandoned_user is not None
                    else (active[-1].id if active else None)
                ),
                message_id=user_id,
                continuation_digest=intent_digest,
                supersedes_message_id=abandoned_user.id if abandoned_user else None,
            )
            already_persisted = False
            supersede_from = abandoned_user.id if abandoned_user else None
        else:
            if (
                user.role is not MessageRole.USER
                or user.content != request.content
                or user.continuation_digest != intent_digest
                or user.status is not MessageStatus.COMPLETED
                or not active
                or active[-1].id != user.id
            ):
                raise ConversationConflictError("idempotency_input_changed_or_turn_not_resumable")
            already_persisted = True
            supersede_from = None
        return self._prepare_context_stream(
            active,
            user,
            () if already_persisted else (user,),
            supersede_from,
            None,
            request_id=str(request.idempotency_key),
            candidate_message_ids=request.candidate_message_ids,
            candidate_entities=request.entity_refs,
            assistant_id=identity,
            continuation_digest=intent_digest,
            user_already_persisted=already_persisted,
        )

    def send(self, conversation_id: UUID, content: str, *, request_id: str) -> AsyncIterator[str]:
        active = self._active(conversation_id)
        user = self._new_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            status=MessageStatus.COMPLETED,
            now=datetime.now(UTC),
            parent_message_id=active[-1].id if active else None,
        )
        return self._prepare_context_stream(active, user, (user,), None, None, request_id)

    def regenerate(
        self,
        conversation_id: UUID,
        message_id: UUID,
        *,
        request_id: str,
    ) -> AsyncIterator[str]:
        active = self._active(conversation_id)
        target = self._messages.get(
            owner_id=self._owner_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        index = next((i for i, m in enumerate(active) if m.id == message_id), -1)
        if (
            target.role is not MessageRole.ASSISTANT
            or target.status is not MessageStatus.COMPLETED
            or index < 1
        ):
            raise InvalidRetryTargetError("Only active completed assistants can be regenerated.")
        user = active[index - 1]
        if user.role is not MessageRole.USER or target.parent_message_id != user.id:
            raise InvalidRetryTargetError("Assistant has no active user parent.")
        return self._prepare_context_stream(active, user, (), target.id, target.id, request_id)

    def edit_and_retry(
        self,
        conversation_id: UUID,
        message_id: UUID,
        content: str,
        *,
        request_id: str,
    ) -> AsyncIterator[str]:
        active = self._active(conversation_id)
        target = self._messages.get(
            owner_id=self._owner_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        if (
            target.role is not MessageRole.USER
            or target.status is not MessageStatus.COMPLETED
            or not any(m.id == target.id for m in active)
        ):
            raise InvalidRetryTargetError("Only active completed user messages can be retried.")
        user = self._new_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            status=MessageStatus.COMPLETED,
            now=datetime.now(UTC),
            parent_message_id=target.parent_message_id,
            supersedes_message_id=target.id,
        )
        return self._prepare_context_stream(active, user, (user,), target.id, None, request_id)

    def _prepare_context_stream(self, *args, **kwargs) -> AsyncIterator[str]:
        return self._stream(self._prepare_context_turn(*args, **kwargs))

    def _prepare_context_turn(
        self,
        active: Sequence[Message],
        user: Message,
        created_users: tuple[Message, ...],
        supersede_from: UUID | None,
        assistant_supersedes: UUID | None,
        request_id: str,
        *,
        assistant_id: UUID | None = None,
        preparation_hook=None,
        external: bool = False,
        candidate_message_ids=None,
        candidate_entities: Sequence[ContextEntityReference] = (),
        history_authorizer=None,
        continuation_digest: str | None = None,
        user_already_persisted: bool = False,
        context_assembler: ContextAssembler | None = None,
        excluded_source_classes=frozenset(),
        maximum_context_sensitivity: ContextSensitivity | None = None,
    ) -> _PreparedTurn:
        if self._application_context is None and getattr(
            self._llm, "requires_inference_context", True
        ):
            raise ContextPreparationError("application_context_required")
        if not external and getattr(self._llm, "requires_inference_context", False):
            try:
                require_matching_endpoint(self._llm, self._context.counter)
            except LLMInvalidRequestError as error:
                raise ContextPreparationError("generation_counter_endpoint_mismatch") from error
        context = context_assembler or self._context
        reservation = uuid4()
        deadline = monotonic() + context.settings.request_timeout_seconds
        appended_users = self._messages.prepare_message_turn(
            owner_id=self._owner_id,
            conversation_id=user.conversation_id,
            expected_active_ids=[m.id for m in active],
            supersede_from_message_id=supersede_from,
            messages=created_users,
            updated_at=datetime.now(UTC),
            preparation_id=reservation,
        )
        persisted_users = (user,) if user_already_persisted else tuple(appended_users)
        try:
            post_active = self._messages.list_active(
                owner_id=self._owner_id,
                conversation_id=user.conversation_id,
            )
            history_for_context = post_active[:-1]
            if candidate_message_ids is not None:
                from personal_ai.context.contracts import complete_turns

                requested = set(candidate_message_ids)
                eligible = complete_turns(history_for_context)
                if requested - {m.id for pair in eligible for m in pair}:
                    raise ContextPreparationError("continuation_source_not_active_completed")
                history_for_context = [
                    m for pair in eligible if any(m.id in requested for m in pair) for m in pair
                ]
            if self._application_context is not None:
                history_for_context = list(conversation_context_messages(
                    history_for_context,
                    allow_manual_external=(
                        self._application_context.definition.context_policy.sidecar
                        .allow_manual_import_context
                    ),
                ))
            if history_authorizer is not None:
                history_authorizer(tuple(m.id for m in history_for_context))
            context_plan = None
            use_planned_memory = False
            if self._application_context is not None:
                context_plan = context.plan_context(
                    user.content,
                    self._application_context,
                    candidate_entities=candidate_entities,
                    excluded_source_classes=excluded_source_classes,
                    maximum_sensitivity=maximum_context_sensitivity,
                )
                use_planned_memory = any(
                    selection.provider_id == "ai_memory" and selection.operation == "search"
                    for selection in context_plan.selections
                )
            retrieval = None
            if self._memory_retriever is not None and use_planned_memory:
                memory_selection_timeout = next(
                    (
                        selection.timeout_seconds
                        for selection in (context_plan.selections if context_plan else ())
                        if selection.provider_id == "ai_memory" and selection.operation == "search"
                    ),
                    self._context.settings.memory_timeout_seconds,
                )
                retrieval = self._memory_retriever.retrieve(
                    self._owner_id,
                    user.content,
                    post_active,
                    timeout=min(
                        memory_selection_timeout,
                        self._context.settings.memory_timeout_seconds,
                        remaining(deadline),
                    ),
                    application_context=self._application_context,
                )
            assembled = context.assemble(
                history_for_context,
                post_active[-1],
                deadline=deadline,
                retrieval=retrieval,
                refresh=not external,
                application_context=self._application_context,
                context_plan=context_plan,
                expected_counter_identity=(
                    self._llm.identity
                    if not external and getattr(self._llm, "requires_inference_context", False)
                    else None
                ),
            )
            remaining(deadline)
            assistant_id = assistant_id or uuid4()
            if self._context_traces is not None:
                if assembled.manifest is None:
                    raise ContextError("actual_context_manifest_unavailable")
                trace = ContextTraceManifest.from_build(
                    assembled.manifest,
                    request_id=request_id,
                    conversation_id=user.conversation_id,
                    user_message_id=user.id,
                    assistant_message_id=assistant_id,
                    scope=(
                        self._application_context.scope
                        if self._application_context is not None
                        else ApplicationScope(
                            application_id=user.application_id,
                            workspace_id=user.workspace_id,
                        )
                    ),
                    context_plan=context_plan,
                )
                try:
                    self._context_traces.put(
                        owner_id=self._owner_id, trace=trace, deadline=deadline
                    )
                except TimeoutError as error:
                    raise LLMTimeoutError("context preparation timed out") from error
                remaining(deadline)
            if assembled.manifest is None:
                raise ContextError("actual_context_manifest_unavailable")
            inference_context = (
                make_inference_context(
                    self._application_context, assembled.manifest.effective_sensitivity
                )
                if self._application_context is not None
                else None
            )
            assistant = self._new_message(
                conversation_id=user.conversation_id,
                role=MessageRole.ASSISTANT,
                content="",
                status=MessageStatus.STREAMING,
                now=datetime.now(UTC),
                parent_message_id=user.id,
                supersedes_message_id=assistant_supersedes,
                message_id=assistant_id,
                continuation_digest=continuation_digest,
            )
            if preparation_hook is not None:
                assistant = preparation_hook(assistant, assembled, inference_context, post_active)
            persisted_assistant = self._messages.prepare_message_turn(
                owner_id=self._owner_id,
                conversation_id=user.conversation_id,
                expected_active_ids=[m.id for m in post_active],
                supersede_from_message_id=None,
                messages=(assistant,),
                updated_at=datetime.now(UTC),
                preparation_id=reservation,
                complete_preparation=True,
            )
        except BaseException:
            # Release only our lease. Recovery handles unavailable storage/process death;
            # an expired request must never release a newer request's reservation.
            try:
                self._messages.release_preparation(
                    owner_id=self._owner_id,
                    conversation_id=user.conversation_id,
                    preparation_id=reservation,
                )
            except Exception as error:  # noqa: BLE001 - preserve the original safe failure
                logger.error(
                    "Context reservation cleanup failed request_id=%s error_class=%s",
                    request_id,
                    type(error).__name__,
                )
            raise
        logger.info(
            "Context prepared request_id=%s counter_kind=%s tokens=%s selected_count=%s",
            request_id,
            assembled.budget.counter_kind,
            assembled.budget.selected_total,
            len(assembled.selected_message_ids),
        )
        return _PreparedTurn(
            (*persisted_users, persisted_assistant[0]),
            persisted_assistant[0],
            assembled.messages,
            request_id,
            deadline,
            assembled.selected_memory_ids,
            inference_context=inference_context,
            selected_message_ids=assembled.selected_message_ids,
        )

    def _stream(self, turn: _PreparedTurn) -> AsyncIterator[str]:
        completed: list[Message] = []
        return _ManagedStream(
            self._stream_events(turn, completed), lambda: self._abandon_before_start(turn)
        )

    def schedule_post_completion(
        self, message: Message, selected_memory_ids: Sequence[UUID], *, request_id: str
    ) -> None:
        """Run the same optional lifecycle after any canonical assistant completion."""
        if self._memory_extraction is None and self._memory_lifecycle is None:
            return

        async def run() -> None:
            try:
                if self._memory_lifecycle is not None:
                    await anyio.to_thread.run_sync(
                        lambda: self._memory_lifecycle.after_completed(
                            message,
                            tuple(selected_memory_ids),
                            application_context=self._application_context,
                        )
                    )
                elif self._memory_extraction is not None:
                    await anyio.to_thread.run_sync(
                        lambda: self._memory_extraction.run(
                            message, application_context=self._application_context
                        )
                    )
            except Exception as error:  # noqa: BLE001 - optional post-completion work
                logger.info(
                    "Memory post-turn failed request_id=%s error_class=%s",
                    request_id,
                    type(error).__name__,
                )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(run())
            return
        task = loop.create_task(run(), name="post-completion-memory-extraction")
        self._post_completion_tasks.add(task)
        task.add_done_callback(self._post_completion_tasks.discard)

    async def _abandon_before_start(self, turn: _PreparedTurn) -> None:
        await self._fail(turn.assistant, "client_cancelled", "")
        logger.info("Chat stream abandoned before start request_id=%s", turn.request_id)

    def _recover_stale_turn(self, conversation_id: UUID) -> None:
        now = datetime.now(UTC)
        self._messages.recover_stale_turn(
            owner_id=self._owner_id,
            conversation_id=conversation_id,
            stale_before=now - timedelta(seconds=self._stale_stream_after_seconds),
            updated_at=now,
        )

    async def _stream_events(
        self, turn: _PreparedTurn, completed_turn: list[Message]
    ) -> AsyncIterator[str]:
        started_at = monotonic()
        parts: list[str] = []
        content_length = 0
        terminal = False
        try:
            # Keep creation events inside the protected lifecycle. A disconnect
            # while sending either event must fail the already-persisted turn.
            for message in turn.created:
                yield _sse("message.created", SSEMessageCreated(message=message).model_dump_json())
            events: asyncio.Queue[GenerationEvent | Exception | None] = asyncio.Queue(maxsize=1)
            demand = asyncio.Semaphore(0)
            with bind_usage_task("chat_generation"):
                provider_iterator = self._llm.stream_events(
                    turn.history,
                    max_output_tokens=self._context.settings.max_response_tokens,
                    timeout_seconds=remaining(turn.deadline),
                    inference_context=turn.inference_context,
                ).__aiter__()
                # One task owns the entire iterator: SDK timeout scopes and cleanup
                # may depend on task identity remaining stable across every yield.
                provider_task = asyncio.create_task(
                    _produce_deltas(provider_iterator, events, demand, request_id=turn.request_id)
                )
            generation_metadata: GenerationMetadata | None = None
            try:
                while True:
                    demand.release()
                    event = await _next_provider_event(events, turn.deadline)
                    if event is None:
                        break
                    if isinstance(event, Exception):
                        raise event
                    if event.kind == "terminal":
                        generation_metadata = event.metadata
                        # Ask the producer to advance once more so terminal success
                        # is accepted only after the adapter reaches normal exhaustion.
                        demand.release()
                        tail = await _next_provider_event(events, turn.deadline)
                        if isinstance(tail, Exception):
                            raise tail
                        if tail is not None:
                            raise LLMInvalidResponseError(
                                "language model emitted data after its terminal event"
                            )
                        GenerationResult("", generation_metadata).require_success()
                        break
                    delta = event.delta
                    if not delta:
                        continue
                    if content_length + len(delta) > MAX_MESSAGE_CONTENT_CHARS:
                        raise LLMInvalidResponseError(
                            "language model response exceeded the size limit"
                        )
                    parts.append(delta)
                    content_length += len(delta)
                    yield _sse(
                        "response.delta",
                        SSEResponseDelta(
                            message_id=turn.assistant.id, delta=delta
                        ).model_dump_json(),
                    )
            finally:
                await _cancel_provider_task(provider_task, request_id=turn.request_id)

            content = "".join(parts)
            if generation_metadata is None:
                raise LLMIncompleteGenerationError("language model ended without a terminal result")
            if not content.strip():
                raise LLMInvalidResponseError("language model response was empty")
            completed = await io_call(
                self._messages.update_status,
                owner_id=self._owner_id,
                conversation_id=turn.assistant.conversation_id,
                message_id=turn.assistant.id,
                status=MessageStatus.COMPLETED,
                content=content,
                model=generation_metadata.identity.model_id,
                replacement=turn.assistant.model_copy(
                    update={
                        "status": MessageStatus.COMPLETED,
                        "content": content,
                        "model": generation_metadata.identity.model_id,
                        "attribution": TurnAttribution(
                            mode="connected_provider",
                            fact_source="server_observed",
                            execution_origin="automatic_managed",
                            provider_id=generation_metadata.identity.provider_id,
                            model_id=generation_metadata.identity.model_id,
                            recorded_at=datetime.now(UTC),
                            source_message_ids=turn.selected_message_ids,
                            latency_ms=int((monotonic() - started_at) * 1000),
                            usage_source=generation_metadata.usage.source
                            if generation_metadata.usage
                            else None,
                            usage_confidence=generation_metadata.usage.confidence
                            if generation_metadata.usage
                            else None,
                            input_tokens=generation_metadata.usage.input_tokens
                            if generation_metadata.usage
                            else None,
                            output_tokens=generation_metadata.usage.output_tokens
                            if generation_metadata.usage
                            else None,
                        ),
                    }
                ),
                expected_status=MessageStatus.STREAMING,
                updated_at=datetime.now(UTC),
            )
            if completed is None:
                terminal = True
                yield self._stale_turn_event(turn.assistant)
                return
            terminal = True
            completed_turn.append(completed)
            self.schedule_post_completion(
                completed, turn.selected_memory_ids, request_id=turn.request_id
            )
            usage = generation_metadata.usage
            logger.info(
                "Chat generation completed request_id=%s provider=%s model=%s "
                "input_tokens=%s output_tokens=%s usage_confidence=%s",
                turn.request_id,
                generation_metadata.identity.provider_id,
                generation_metadata.identity.model_id,
                usage.input_tokens if usage else None,
                usage.output_tokens if usage else None,
                usage.confidence if usage else "unavailable",
            )
            yield _sse(
                "response.completed", SSEResponseCompleted(message=completed).model_dump_json()
            )
        except asyncio.CancelledError:
            if not terminal:
                await self._fail(turn.assistant, "client_cancelled", "".join(parts))
            logger.info(
                "Chat stream cancelled request_id=%s error_class=CancelledError", turn.request_id
            )
            raise
        except GeneratorExit:
            if not terminal:
                await self._fail(turn.assistant, "client_cancelled", "".join(parts))
                logger.info("Chat stream closed request_id=%s", turn.request_id)
            raise
        except LLMError as error:
            logger.warning(
                "Chat stream failed request_id=%s error_class=%s",
                turn.request_id,
                type(error).__name__,
            )
            event = await self._error_event(turn.assistant, error.code, "".join(parts))
            terminal = True
            yield event
        except Exception:  # noqa: BLE001
            logger.error(
                "Chat stream failed request_id=%s error_class=UnexpectedError", turn.request_id
            )
            event = await self._error_event(turn.assistant, "llm_unavailable", "".join(parts))
            terminal = True
            yield event

    async def _error_event(self, assistant: Message, code: str, content: str) -> str:
        failed = await self._fail(assistant, code, content)
        if failed is None:
            return self._stale_turn_event(assistant)
        return _sse(
            "response.error",
            SSEResponseError(
                message_id=failed.id,
                code=code,
                message="The response could not be completed. Please retry.",
            ).model_dump_json(),
        )

    async def _fail(self, assistant: Message, code: str, content: str) -> Message | None:
        # Persist the terminal state even inside an ASGI disconnect scope. Join
        # the write before returning so a late thread cannot race a retry.
        with anyio.CancelScope(shield=True):
            return await io_call(
                self._messages.update_status,
                owner_id=self._owner_id,
                conversation_id=assistant.conversation_id,
                message_id=assistant.id,
                status=MessageStatus.FAILED,
                content=content,
                error_code=code,
                expected_status=MessageStatus.STREAMING,
                updated_at=datetime.now(UTC),
            )

    @staticmethod
    def _stale_turn_event(assistant: Message) -> str:
        return _sse(
            "response.error",
            SSEResponseError(
                message_id=assistant.id,
                code="turn_interrupted",
                message="The response was interrupted. Please refresh and retry.",
            ).model_dump_json(),
        )

    @staticmethod
    def _ensure_no_streaming_turn(active: Sequence[Message]) -> None:
        if any(
            message.status in {MessageStatus.STREAMING, MessageStatus.PENDING} for message in active
        ):
            raise ConversationConflictError("a response is already in progress")

    def _new_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        status: MessageStatus,
        now: datetime,
        parent_message_id: UUID | None = None,
        supersedes_message_id: UUID | None = None,
        message_id: UUID | None = None,
        continuation_digest: str | None = None,
    ) -> Message:
        return Message(
            id=message_id or uuid4(),
            conversation_id=conversation_id,
            owner_id=self._owner_id,
            role=role,
            content=content,
            status=status,
            created_at=now,
            parent_message_id=parent_message_id,
            supersedes_message_id=supersedes_message_id,
            continuation_digest=continuation_digest,
        )

    def _replay_completed_continuation(
        self, conversation_id: UUID, assistant: Message
    ) -> AsyncIterator[str]:
        async def replay():
            user = self.get_message(conversation_id, uuid5(assistant.id, "user"))
            for message in (user, assistant):
                yield _sse(
                    "message.created", SSEMessageCreated(message=message).model_dump_json()
                )
            yield _sse(
                "response.delta",
                SSEResponseDelta(message_id=assistant.id, delta=assistant.content).model_dump_json(),
            )
            yield _sse(
                "response.completed",
                SSEResponseCompleted(message=assistant).model_dump_json(),
            )

        return replay()


async def _produce_deltas(
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


async def _next_provider_event(events, deadline: float):
    try:
        return await asyncio.wait_for(events.get(), timeout=remaining(deadline))
    except TimeoutError as error:
        raise LLMTimeoutError("language model request timed out") from error


async def _cancel_provider_task(task: asyncio.Task[None], *, request_id: str) -> None:
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


def _sse(event: str, data: str) -> str:
    """Return one correctly terminated SSE frame."""
    return f"event: {event}\ndata: {data}\n\n"


def _unfinished_continuation_user(active: Sequence[Message]) -> Message | None:
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
