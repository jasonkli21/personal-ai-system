"""Use cases for the non-streaming Phase 1 conversation API."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.entities import Conversation, Message
from personal_ai.storage.errors import ConversationConflictError, ResourceNotFoundError
from personal_ai.storage.repositories import ConversationRepository, MessageRepository

DEFAULT_CONVERSATION_TITLE = "New conversation"


class ConversationService:
    """Coordinate owner-scoped conversation and active-message retrieval."""

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        *,
        owner_id: str,
        application_context: ApplicationContextRequest | None = None,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._owner_id = owner_id
        self._application_context = application_context

    def inspect_memories(self, settings, repository, memory_ids, lifecycle_repository=None):
        from personal_ai.memory.inspection import inspect_records

        return inspect_records(
            settings,
            repository,
            self._messages,
            self._owner_id,
            memory_ids,
            lifecycle_repository=lifecycle_repository,
        )

    def create_conversation(
        self, *, title: str | None = None, idempotency_key: UUID | None = None
    ) -> Conversation:
        """Create an empty conversation, replaying a supplied stable creation key."""
        now = datetime.now(UTC)
        cleaned_title = title.strip() if title else ""
        normalized_title = cleaned_title or DEFAULT_CONVERSATION_TITLE
        conversation_id = uuid4()
        if idempotency_key is not None:
            scope = self._application_context.scope if self._application_context else None
            scope_value = "\0".join(
                (
                    self._owner_id,
                    scope.application_id if scope else "personal_ai",
                    scope.workspace_id or "" if scope else "",
                    str(idempotency_key),
                )
            )
            conversation_id = uuid5(
                NAMESPACE_URL, f"personal-ai-conversation-create-v1\0{scope_value}"
            )
            try:
                existing = self._conversations.get(
                    owner_id=self._owner_id, conversation_id=conversation_id
                )
            except ResourceNotFoundError:
                existing = None
            if existing is not None:
                if existing.title != normalized_title:
                    raise ConversationConflictError("idempotency_input_changed")
                return existing
        conversation = Conversation(
            id=conversation_id,
            owner_id=self._owner_id,
            title=normalized_title,
            created_at=now,
            updated_at=now,
        )
        try:
            return self._conversations.create(conversation)
        except ConversationConflictError:
            if idempotency_key is None:
                raise
            existing = self._conversations.get(
                owner_id=self._owner_id, conversation_id=conversation_id
            )
            if existing.title != normalized_title:
                raise ConversationConflictError("idempotency_input_changed") from None
            return existing

    def list_conversations(self) -> list[Conversation]:
        """Return the current owner's conversations in repository-defined order."""
        return self._conversations.list(owner_id=self._owner_id)

    def get_conversation(self, conversation_id: UUID) -> tuple[Conversation, list[Message]]:
        """Return a conversation and only its active message path."""
        conversation = self._conversations.get(
            owner_id=self._owner_id, conversation_id=conversation_id
        )
        messages = self._messages.list_active(
            owner_id=self._owner_id, conversation_id=conversation_id
        )
        return conversation, messages
