"""DynamoDB conversation catalog repository."""

from __future__ import annotations

from datetime import datetime
from time import monotonic
from uuid import UUID

from personal_ai.auth.scope import ApplicationScope, current_application_scope, scoped_record
from personal_ai.entities import Conversation
from personal_ai.storage.errors import (
    ConversationConflictError,
    ResourceNotFoundError,
    StorageUnavailableError,
)

from ._helpers import (
    _authorized,
    _catalog_item,
    _catalog_key,
    _conditional_failure,
    _conversation_from_item,
    _conversation_keys,
    _conversation_payload,
    _delete,
    _json,
    _metadata_item,
    _namespace,
    _namespace_puts,
    _put,
    _scope_of,
    _timestamp,
    _update,
    _utc,
)
from .client import DynamoDBRuntimeTable


class DynamoDBConversationRepository:
    """Strongly visible owner/app/workspace conversation directory and metadata."""

    def __init__(self, table: DynamoDBRuntimeTable) -> None:
        self.table = table

    def create(self, conversation: Conversation) -> Conversation:
        conversation = scoped_record(conversation)
        if conversation.context_preparation_id is not None:
            raise ValueError("conversation_initialization_invalid")
        scope = _scope_of(conversation)
        payload = _conversation_payload(conversation)
        catalog = _catalog_item(conversation, revision=1)
        operations = [
            _put(_metadata_item(conversation, payload, revision=1)),
            _put(catalog, condition="attribute_not_exists(PK)"),
        ]
        for attempt in range(2):
            scoped_operations = list(operations)
            scoped_operations.extend(_namespace_puts(self.table, conversation.owner_id, scope))
            try:
                self.table.transact(scoped_operations)
                break
            except Exception as error:
                existing = self._metadata_item_for(conversation.owner_id, conversation.id, scope)
                if existing is not None:
                    raise ConversationConflictError("conversation already exists") from error
                if attempt or not _conditional_failure(error):
                    raise
        return conversation.model_copy(update={"persistence_revision": 1})

    def get(self, *, owner_id: str, conversation_id: UUID) -> Conversation:
        scope = current_application_scope()
        return self._read_conversation(owner_id, conversation_id, scope)

    def list(self, *, owner_id: str, limit: int = 50) -> list[Conversation]:
        if limit < 1:
            return []
        if limit > 500:
            raise ValueError("conversation_limit_invalid")
        scope = current_application_scope()
        token = _namespace(scope, owner_id)
        catalog_pk = f"{token}#CATALOG"
        deadline = monotonic() + 5
        entries = self.table.query(
            partition=catalog_pk,
            sort_prefix="CONV#",
            descending=True,
            deadline=deadline,
            limit=min(limit, 500),
        )
        conversations = []
        for entry in entries:
            identifier = UUID(entry["conversation_id"])
            current = self._metadata_item_for(owner_id, identifier, scope)
            if current is None or int(current["revision"]) != int(entry["revision"]):
                raise StorageUnavailableError("conversation directory revision mismatch")
            conversation = self._read_conversation(owner_id, identifier, scope)
            if _timestamp(conversation.updated_at) != entry["updated_at"]:
                # Directory movement is part of the conversation transaction.
                # A mismatch signals an invariant breach instead of a stale page.
                raise StorageUnavailableError("conversation directory revision mismatch")
            conversations.append(conversation)
        return conversations

    def update(self, conversation: Conversation) -> Conversation:
        conversation = scoped_record(conversation)
        scope = _scope_of(conversation)
        if conversation.persistence_revision < 1:
            raise ConversationConflictError("conversation revision missing")
        old_item = self._metadata_item_for(conversation.owner_id, conversation.id, scope)
        if old_item is None:
            raise ResourceNotFoundError("conversation not found")
        if int(old_item["revision"]) != conversation.persistence_revision:
            raise ConversationConflictError("conversation changed")
        old = _conversation_from_item(old_item)
        self._write_conversation(old, conversation)
        return conversation.model_copy(
            update={"persistence_revision": old.persistence_revision + 1}
        )

    def touch(self, *, owner_id: str, conversation_id: UUID, updated_at: datetime) -> Conversation:
        current = self.get(owner_id=owner_id, conversation_id=conversation_id)
        updated = current.model_copy(update={"updated_at": _utc(updated_at)})
        self._write_conversation(current, updated)
        return updated.model_copy(update={"persistence_revision": current.persistence_revision + 1})

    def _read_conversation(self, owner_id: str, conversation_id: UUID, scope: ApplicationScope):
        item = self._metadata_item_for(owner_id, conversation_id, scope)
        if item is None:
            raise ResourceNotFoundError("conversation not found")
        try:
            return _conversation_from_item(item)
        except (ValueError, TypeError, KeyError) as error:
            raise StorageUnavailableError("conversation record invalid") from error

    def _metadata_item_for(self, owner_id: str, conversation_id: UUID, scope: ApplicationScope):
        keys = _conversation_keys(scope, conversation_id, owner_id)
        item = self.table.get(keys.meta)
        if item is None or not _authorized(item, owner_id, scope):
            return None
        return item

    def _write_conversation(self, previous: Conversation, updated: Conversation) -> None:
        scope = _scope_of(previous)
        keys = _conversation_keys(scope, previous.id, previous.owner_id)
        current_item = self.table.get(keys.meta)
        if current_item is None or not _authorized(current_item, previous.owner_id, scope):
            raise ResourceNotFoundError("conversation not found")
        old_revision = int(current_item["revision"])
        if old_revision != previous.persistence_revision:
            raise ConversationConflictError("conversation changed")
        old_catalog = _catalog_key(scope, previous.id, previous.updated_at, previous.owner_id)
        new_catalog = _catalog_item(updated, revision=old_revision + 1)
        payload = _conversation_payload(updated)
        operations = [
            _update(
                keys.meta,
                update_expression="SET #payload=:payload,#updated=:updated,#revision=:next",
                names={"#payload": "payload", "#updated": "updated_at", "#revision": "revision"},
                values={
                    ":payload": _json(payload),
                    ":updated": _timestamp(updated.updated_at),
                    ":next": old_revision + 1,
                    ":owner": previous.owner_id,
                    ":app": scope.application_id,
                    ":workspace_present": scope.workspace_id is not None,
                    ":workspace": scope.workspace_id or "",
                },
                condition="#owner=:owner AND #app=:app AND revision=:old AND attribute_not_exists(effect_guard)",
                more_names={
                    "#owner": "owner_id",
                    "#app": "application_id",
                    "#workspace_present": "workspace_id_present",
                    "#workspace": "workspace_id",
                },
                more_values={":old": old_revision},
            )
        ]
        operations[0]["Update"]["ConditionExpression"] += (
            " AND #workspace_present=:workspace_present AND #workspace=:workspace"
        )
        new_catalog_key = {"PK": new_catalog["PK"], "SK": new_catalog["SK"]}
        if old_catalog != new_catalog_key:
            operations.extend(
                [
                    _delete(old_catalog),
                    _put(new_catalog, condition="attribute_not_exists(PK)"),
                ]
            )
        else:
            operations.append(
                _update(
                    old_catalog,
                    "SET #revision=:revision,#updated=:updated",
                    names={"#revision": "revision", "#updated": "updated_at", "#owner": "owner_id"},
                    values={
                        ":revision": old_revision + 1,
                        ":updated": _timestamp(updated.updated_at),
                        ":owner": previous.owner_id,
                    },
                    condition="#owner=:owner",
                )
            )
        self.table.transact(operations)
