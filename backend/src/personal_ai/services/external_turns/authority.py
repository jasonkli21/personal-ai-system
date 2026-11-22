"""Principal-bound authority checks for externally disclosed conversation context."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.dispatch_grants import LocalChatScope
from personal_ai.auth.scope import WorkspaceAuthorizer
from personal_ai.context.authority import (
    source_snapshot_authority_complete,
    source_snapshots_current,
)
from personal_ai.context.history import source_snapshots_for_message
from personal_ai.contracts.context_references import ContextSourceSnapshot
from personal_ai.contracts.execution import ExecutionChoice
from personal_ai.entities import MessageRole, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.storage.errors import ConversationConflictError


@dataclass(frozen=True, slots=True)
class LocalChatDispatch:
    """Trusted foreground composition for one independently approved pairing."""

    scope: LocalChatScope
    caller_id: UUID
    audience: UUID
    connection_id: UUID
    connection_revision: int

    def require(self, context, principal, choice):
        scope = context.scope
        if (
            not principal.authenticated
            or scope.owner_id != principal.owner_id
            or scope.acting_user_id != f"{principal.issuer}|{principal.subject}"
            or (scope.application_id, scope.owner_id, scope.acting_user_id, scope.workspace_id)
            != (
                self.scope.application_id, self.scope.owner_id, self.scope.actor_id,
                self.scope.workspace_id,
            )
            or (choice.caller_id, choice.audience, choice.connection_id, choice.connection_revision)
            != (self.caller_id, self.audience, self.connection_id, self.connection_revision)
        ):
            raise ConversationConflictError("local_chat_scope_denied")


def _authority_model_dump(value):
    """Keep authority digests stable for records written before additive context facts."""
    payload = value.model_dump(mode="json")
    if isinstance(value, ContextSourceSnapshot) and not value.source_classes:
        payload.pop("source_classes", None)
    elif isinstance(value, TurnAttribution):
        if value.effective_context_sensitivity is None:
            payload.pop("effective_context_sensitivity", None)
        payload["source_snapshots"] = [
            _authority_model_dump(snapshot) for snapshot in value.source_snapshots
        ]
    return payload


class PrincipalBoundExternalTurnAuthority:
    """Recheck owner, workspace, branch, expiry, and permission versions on each transition.

    This authority is request-scoped. Principal identity is obtained from the verified API
    authentication middleware, never from an execution choice or browser label. Source
    snapshots are accepted only inside the authenticated application scope; their typed
    permission dependencies are revalidated through the shared context policy adapter.
    """

    def __init__(
        self,
        *,
        principal: AuthenticatedPrincipal,
        conversations,
        messages,
        permission_revalidator,
        workspace_authorizer: WorkspaceAuthorizer | None = None,
        allow_development_principal: bool = False,
        clock=lambda: datetime.now(UTC),
    ):
        self.principal = principal
        self.conversations = conversations
        self.messages = messages
        self.permission_revalidator = permission_revalidator
        self.workspace_authorizer = workspace_authorizer
        self.allow_development_principal = allow_development_principal
        self.clock = clock

    def snapshot(
        self,
        context: ApplicationContextRequest,
        conversation_id: UUID,
        choice: ExecutionChoice,
        source_message_ids: tuple[UUID, ...],
        source_snapshots: tuple[ContextSourceSnapshot, ...],
        *,
        source_free: bool = False,
    ) -> str:
        scope = context.scope
        if scope.owner_id != self.principal.owner_id:
            raise ConversationConflictError("external_principal_scope_mismatch")
        if not self.principal.authenticated and not (
            self.allow_development_principal
            and self.principal.issuer == "local-development"
            and self.principal.owner_id == "local"
        ):
            raise ConversationConflictError("external_authenticated_principal_required")
        if scope.workspace_id is not None:
            if self.workspace_authorizer is None:
                raise ConversationConflictError("external_workspace_authority_unavailable")
            try:
                if not self.workspace_authorizer.is_member(
                    self.principal, scope.application_id, scope.workspace_id
                ):
                    raise ConversationConflictError("external_workspace_access_denied")
            except ConversationConflictError:
                raise
            except Exception:  # noqa: BLE001 - membership lookup failures deny disclosure.
                raise ConversationConflictError(
                    "external_workspace_authority_unavailable"
                ) from None

        conversation = self.conversations.get(
            owner_id=scope.owner_id, conversation_id=conversation_id
        )
        if (
            conversation.owner_id != scope.owner_id
            or conversation.application_id != scope.application_id
            or conversation.workspace_id != scope.workspace_id
        ):
            raise ConversationConflictError("external_conversation_scope_mismatch")

        active = self.messages.list_active(owner_id=scope.owner_id, conversation_id=conversation_id)
        active_by_id = {message.id: message for message in active}
        selected = []
        for message_id in source_message_ids:
            message = active_by_id.get(message_id)
            if (
                message is None
                or message.status is not MessageStatus.COMPLETED
                or message.owner_id != scope.owner_id
                or message.application_id != scope.application_id
                or message.workspace_id != scope.workspace_id
            ):
                raise ConversationConflictError("external_history_source_unavailable")
            if source_free and (
                source_snapshots_for_message(message)
                or (message.execution and message.execution.selected_memory_ids)
            ):
                raise ConversationConflictError("local_chat_source_context_denied")
            selected.append(
                {
                    "id": str(message.id),
                    "content": hashlib.sha256(message.content.encode()).hexdigest(),
                    "attribution": (
                        _authority_model_dump(message.attribution)
                        if message.attribution is not None
                        else None
                    ),
                }
            )

        if source_free and source_snapshots:
            raise ConversationConflictError("local_chat_source_context_denied")
        now = self.clock()
        for snapshot in source_snapshots:
            if (
                not source_snapshot_authority_complete(snapshot)
                or snapshot.owner_id != scope.owner_id
                or snapshot.application_id != scope.application_id
                or snapshot.workspace_id != scope.workspace_id
                or (snapshot.expires_at is not None and now >= snapshot.expires_at)
            ):
                raise ConversationConflictError("external_source_scope_or_expiry_invalid")
        if not source_snapshots_current(source_snapshots, self.permission_revalidator, now=now):
            raise ConversationConflictError("external_source_permission_revoked")
        source_digests = [_authority_model_dump(snapshot) for snapshot in source_snapshots]

        principal_digest = hashlib.sha256(
            f"{self.principal.issuer}\0{self.principal.subject}".encode()
        ).hexdigest()
        canonical = {
            "principal": principal_digest,
            "scope": scope.model_dump(mode="json", exclude={"request_id", "client_context"}),
            "conversation": str(conversation_id),
            "choice": choice.model_dump(mode="json"),
            "policy": context.definition.context_policy.model_dump(mode="json"),
            "selected": selected,
            "sources": source_digests,
        }
        return hashlib.sha256(
            json.dumps(
                canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()

    def require_new_local_turn(self, context, conversation_id, content):
        active = self.messages.list_active(
            owner_id=context.scope.owner_id, conversation_id=conversation_id
        )
        self.require_distinct_local_turn(active, content)

    @staticmethod
    def require_distinct_local_turn(active, content):
        # An unfinished preparation can leave one trailing user message behind.
        if active and active[-1].role == MessageRole.USER:
            active = active[:-1]
        if len(active) < 2:
            return
        user, assistant = active[-2:]
        if (
            user.role == MessageRole.USER
            and user.content == content
            and assistant.parent_message_id == user.id
            and assistant.execution is not None
            and assistant.execution.state in {"dispatched", "unknown"}
        ):
            raise ConversationConflictError("local_chat_previous_dispatch_uncertain")
