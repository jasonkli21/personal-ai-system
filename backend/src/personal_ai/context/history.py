"""Shared policy projection for conversation turns used as model context."""

from collections.abc import Sequence

from personal_ai.applications.contracts import ManualImportReusePolicy
from personal_ai.entities import Message, MessageRole


def manual_import_is_reusable(
    message: Message, policy: ManualImportReusePolicy
) -> bool:
    """Fail closed when a manual turn has no current, bounded sensitivity fact."""
    attribution = message.attribution
    if attribution is None or attribution.execution_origin != "manual_import":
        return True
    sensitivity = (
        message.execution.effective_sensitivity if message.execution is not None else None
    )
    return policy.allows(sensitivity)


def conversation_context_messages(
    messages: Sequence[Message], *, manual_import_reuse: ManualImportReusePolicy
) -> tuple[Message, ...]:
    """Omit ineligible manual turns and their paired user prompts.

    The canonical conversation remains untouched. Filtering before summary selection
    also prevents an existing derived summary from reintroducing a denied turn.
    """
    excluded_ids = {
        message.id
        for message in messages
        if message.role is MessageRole.ASSISTANT
        and not manual_import_is_reusable(message, manual_import_reuse)
    }
    excluded_ids.update(
        message.parent_message_id
        for message in messages
        if message.id in excluded_ids and message.parent_message_id is not None
    )
    return tuple(message for message in messages if message.id not in excluded_ids)
