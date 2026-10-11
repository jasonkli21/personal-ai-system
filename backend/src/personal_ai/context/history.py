"""Shared policy projection for conversation turns used as model context."""

from collections.abc import Sequence

from personal_ai.entities import Message, MessageRole


def conversation_context_messages(
    messages: Sequence[Message], *, allow_manual_external: bool
) -> tuple[Message, ...]:
    """Omit imported manual responses and their paired user prompts when denied.

    The canonical conversation remains untouched. Filtering before summary selection
    also prevents an existing derived summary from reintroducing a denied turn.
    """
    if allow_manual_external:
        return tuple(messages)
    excluded_ids = {
        message.id
        for message in messages
        if message.role is MessageRole.ASSISTANT
        and message.attribution is not None
        and message.attribution.mode == "manual_external"
    }
    excluded_ids.update(
        message.parent_message_id
        for message in messages
        if message.id in excluded_ids and message.parent_message_id is not None
    )
    return tuple(message for message in messages if message.id not in excluded_ids)
