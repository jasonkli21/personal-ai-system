"""Principal-bound authority checks for externally disclosed conversation context."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import WorkspaceAuthorizer
from personal_ai.context.authority import permission_dependencies_current
from personal_ai.contracts.context_references import ContextSourceSnapshot
from personal_ai.contracts.execution import ExecutionChoice
from personal_ai.entities import MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.storage.errors import ConversationConflictError


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

        now = self.clock()
        for snapshot in source_snapshots:
            if (
                snapshot.owner_id != scope.owner_id
                or snapshot.application_id != scope.application_id
                or snapshot.workspace_id != scope.workspace_id
                or (snapshot.expires_at is not None and now >= snapshot.expires_at)
            ):
                raise ConversationConflictError("external_source_scope_or_expiry_invalid")
        dependencies = tuple(
            dict.fromkeys(
                dependency
                for snapshot in source_snapshots
                for dependency in snapshot.permission_dependencies
            )
        )
        if not permission_dependencies_current(dependencies, self.permission_revalidator):
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
