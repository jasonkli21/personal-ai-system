"""Resolve a proposal candidate's canonical output and attribution server-side."""

from personal_ai.auth.scope import RequestScope
from personal_ai.entities import Message, MessageRole, MessageStatus
from personal_ai.mutations.contracts import CanonicalOutputHandle, MutationError


class CanonicalOutputResolver:
    """Read only completed assistant outputs on the active, exactly scoped branch."""

    def __init__(self, conversations, messages):
        self.conversations = conversations
        self.messages = messages

    def resolve(self, scope: RequestScope, handle: CanonicalOutputHandle) -> Message:
        try:
            conversation = self.conversations.get(
                owner_id=scope.owner_id,
                conversation_id=handle.conversation_id,
            )
            message = self.messages.get(
                owner_id=scope.owner_id,
                conversation_id=handle.conversation_id,
                message_id=handle.message_id,
            )
        except Exception as error:
            # Do not distinguish a foreign conversation/message from a missing one.
            from personal_ai.storage.errors import ResourceNotFoundError

            if isinstance(error, ResourceNotFoundError):
                raise MutationError("mutation_output_not_found") from None
            raise

        if (
            conversation.owner_id != scope.owner_id
            or conversation.application_id != scope.application_id
            or conversation.workspace_id != scope.workspace_id
            or message.owner_id != scope.owner_id
            or message.application_id != scope.application_id
            or message.workspace_id != scope.workspace_id
            or message.conversation_id != handle.conversation_id
            or message.role != MessageRole.ASSISTANT
            or message.status != MessageStatus.COMPLETED
            or not message.content
            or message.attribution is None
            or message.attribution.status != "success"
        ):
            raise MutationError("mutation_output_not_found")

        active = self.messages.list_active(
            owner_id=scope.owner_id, conversation_id=handle.conversation_id
        )
        if not any(
            item.id == handle.message_id
            and item.role == MessageRole.ASSISTANT
            and item.status == MessageStatus.COMPLETED
            for item in active
        ):
            raise MutationError("mutation_output_not_active")
        return message
