"""DynamoDB branchable message repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from time import monotonic
from typing import Any
from uuid import UUID

from personal_ai.auth.scope import ApplicationScope, current_application_scope, scoped_record
from personal_ai.context.contracts import fingerprint
from personal_ai.entities import Message, MessageStatus
from personal_ai.entities.turn_execution import transition_message
from personal_ai.storage.branches import active_path, descendant_ids, effective_message
from personal_ai.storage.errors import (
    ConversationConflictError,
    ResourceNotFoundError,
    StorageUnavailableError,
)

from ._helpers import (
    MAX_CONVERSATION_MESSAGES,
    MAX_DYNAMO_TRANSACTION_ITEMS,
    _authorized,
    _catalog_item,
    _catalog_key,
    _conditional_failure,
    _conversation_from_item,
    _conversation_keys,
    _conversation_payload,
    _delete,
    _json,
    _message_from_item,
    _message_item,
    _message_key,
    _message_locator,
    _message_payload,
    _parse_timestamp,
    _put,
    _scope_of,
    _timestamp,
    _update,
    _utc,
)
from .client import DynamoDBRuntimeTable
from .conversations import DynamoDBConversationRepository


class DynamoDBMessageRepository:
    """Append-only history with revision-stable strong pagination and bounded cuts."""

    def __init__(
        self,
        table: DynamoDBRuntimeTable,
        conversations: DynamoDBConversationRepository | None = None,
    ):
        self.table = table
        self.conversations = conversations or DynamoDBConversationRepository(table)

    def create(self, message: Message) -> Message:
        message = scoped_record(message)
        scope = _scope_of(message)
        conversation = self.conversations.get(
            owner_id=message.owner_id, conversation_id=message.conversation_id
        )
        key = _conversation_keys(scope, message.conversation_id, message.owner_id)
        meta = self.table.get(key.meta)
        if meta is None:
            raise ResourceNotFoundError("conversation not found")
        revision = int(meta["revision"])
        current_updated = conversation.updated_at
        updated = conversation.model_copy(update={"updated_at": message.created_at})
        item = _message_item(message, scope)
        operations = [
            _put(item, condition="attribute_not_exists(PK)"),
            _put(_message_locator(message, scope), condition="attribute_not_exists(PK)"),
            _update(
                key.meta,
                update_expression="SET #payload=:payload,#updated=:updated,#revision=:next",
                names={
                    "#payload": "payload",
                    "#updated": "updated_at",
                    "#revision": "revision",
                    "#owner": "owner_id",
                },
                values={
                    ":payload": _json(_conversation_payload(updated)),
                    ":updated": _timestamp(updated.updated_at),
                    ":next": revision + 1,
                    ":owner": message.owner_id,
                    ":old": revision,
                },
                condition="#owner=:owner AND revision=:old AND attribute_not_exists(effect_guard) "
                "AND attribute_not_exists(context_preparation_id)",
            ),
        ]
        old_catalog = _catalog_key(scope, conversation.id, current_updated, message.owner_id)
        new_catalog = _catalog_item(updated, revision=revision + 1)
        if old_catalog != {"PK": new_catalog["PK"], "SK": new_catalog["SK"]}:
            operations.extend(
                [_delete(old_catalog), _put(new_catalog, condition="attribute_not_exists(PK)")]
            )
        else:
            operations.append(
                _update(
                    old_catalog,
                    "SET #revision=:revision,#updated=:updated",
                    names={"#revision": "revision", "#updated": "updated_at", "#owner": "owner_id"},
                    values={
                        ":revision": revision + 1,
                        ":updated": _timestamp(updated.updated_at),
                        ":owner": message.owner_id,
                    },
                    condition="#owner=:owner",
                )
            )
        self.table.transact(operations)
        return message

    def get(self, *, owner_id: str, conversation_id: UUID, message_id: UUID) -> Message:
        scope = current_application_scope()
        keys = _conversation_keys(scope, conversation_id, owner_id)
        deadline = monotonic() + 5
        for _ in range(4):
            before = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
            if before is None:
                raise ResourceNotFoundError("conversation not found")
            locator = self.table.get({"PK": keys.partition, "SK": f"MID#{message_id}"})
            if locator is None or not _authorized(locator, owner_id, scope):
                raise ResourceNotFoundError("message not found")
            item = self.table.get({"PK": locator["message_pk"], "SK": locator["message_sk"]})
            if (
                item is None
                or item.get("conversation_id") != str(conversation_id)
                or not _authorized(item, owner_id, scope)
            ):
                raise ResourceNotFoundError("message not found")
            message = _message_from_item(item)
            history = self._read_history(owner_id, conversation_id, scope, deadline=deadline)
            if len(history) > MAX_CONVERSATION_MESSAGES:
                raise StorageUnavailableError("conversation history exceeds bound")
            ancestry = {record.id: record for record in history}
            if message.id not in ancestry:
                raise StorageUnavailableError("message ancestry unavailable")
            after = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
            if after is None:
                raise ResourceNotFoundError("conversation not found")
            if before["revision"] == after["revision"]:
                return effective_message(ancestry[message.id], ancestry)
            if monotonic() >= deadline:
                break
        raise StorageUnavailableError("conversation changed during message read")

    def list_active(
        self, *, owner_id: str, conversation_id: UUID, timeout: float | None = None
    ) -> list[Message]:
        scope = current_application_scope()
        deadline = monotonic() + (timeout if timeout is not None else 5)
        for _ in range(4):
            before = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
            if before is None:
                raise ResourceNotFoundError("conversation not found")
            history = self._read_history(owner_id, conversation_id, scope, deadline=deadline)
            after = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
            if after is None:
                raise ResourceNotFoundError("conversation not found")
            if before["revision"] == after["revision"]:
                return active_path(history)
            if monotonic() >= deadline:
                break
        raise StorageUnavailableError("conversation changed during history read")

    def update_status(
        self,
        *,
        owner_id: str,
        conversation_id: UUID,
        message_id: UUID,
        status: MessageStatus,
        content: str | None = None,
        model: str | None = None,
        error_code: str | None = None,
        updated_at: datetime,
        expected_status: MessageStatus | None = None,
        expected_message: Message | None = None,
        expected_branch_digest: str | None = None,
        replacement: Message | None = None,
    ) -> Message | None:
        current = self.get(
            owner_id=owner_id, conversation_id=conversation_id, message_id=message_id
        )
        if expected_status is not None and current.status is not expected_status:
            return None
        if expected_message is not None and current != expected_message:
            return None
        changes = {"status": status.value}
        if content is not None:
            changes["content"] = content
        if model is not None:
            changes["model"] = model
        if error_code is not None:
            changes["error_code"] = error_code
        updated = current.model_copy(
            update={"status": status, **{k: v for k, v in changes.items() if k != "status"}}
        )
        updated = transition_message(current, replacement or updated)
        if (updated.id, updated.owner_id, updated.conversation_id) != (
            current.id,
            current.owner_id,
            current.conversation_id,
        ):
            raise ConversationConflictError("message identity changed")
        scope = _scope_of(current)
        conversation = self.conversations.get(owner_id=owner_id, conversation_id=conversation_id)
        meta_key = _conversation_keys(scope, conversation_id, owner_id).meta
        metadata = self.table.get(meta_key)
        if metadata is None:
            raise ResourceNotFoundError("conversation not found")
        conversation = _conversation_from_item(metadata)
        revision = int(metadata["revision"])
        if expected_branch_digest is not None:
            active = self.list_active(owner_id=owner_id, conversation_id=conversation_id)
            stable = self.table.get(meta_key)
            if (
                stable is None
                or int(stable["revision"]) != revision
                or not active
                or active[-1].id != message_id
                or fingerprint(active[:-1], include_state=True) != expected_branch_digest
            ):
                return None
        updated_conversation = conversation.model_copy(update={"updated_at": _utc(updated_at)})
        message_key = _message_key(scope, conversation_id, current.created_at, current.id, owner_id)
        names = {"#status": "status", "#owner": "owner_id", "#payload": "payload"}
        message_values: dict[str, Any] = {
            ":status": updated.status.value,
            ":owner": owner_id,
            ":message_payload": _json(_message_payload(updated)),
        }
        message_expression = "SET #status=:status,#payload=:message_payload"
        condition = "#owner=:owner"
        if expected_status is not None:
            condition += " AND #status=:expected"
            message_values[":expected"] = expected_status.value
        if expected_message is not None:
            condition += " AND #payload=:old_payload"
            message_values[":old_payload"] = _json(_message_payload(expected_message))
        operations = [
            _update(
                message_key,
                message_expression,
                names=names,
                values=message_values,
                condition=condition,
            ),
            _update(
                meta_key,
                "SET #payload=:conversation_payload,#updated=:updated,#revision=:next",
                names={
                    "#payload": "payload",
                    "#updated": "updated_at",
                    "#revision": "revision",
                    "#owner": "owner_id",
                },
                values={
                    ":conversation_payload": _json(_conversation_payload(updated_conversation)),
                    ":updated": _timestamp(updated_at),
                    ":next": revision + 1,
                    ":owner": owner_id,
                    ":revision": revision,
                },
                condition="#owner=:owner AND revision=:revision AND attribute_not_exists(effect_guard)",
            ),
        ]
        self._append_catalog_move(
            operations, scope, conversation, updated_conversation, revision + 1
        )
        try:
            self.table.transact(operations)
        except Exception as error:
            if _conditional_failure(error) and (
                expected_status is not None or expected_message is not None
            ):
                return None
            if _conditional_failure(error):
                raise ConversationConflictError("conversation changed") from error
            raise
        return updated

    def prepare_message_turn(
        self,
        *,
        owner_id: str,
        conversation_id: UUID,
        expected_active_ids: Sequence[UUID],
        supersede_from_message_id: UUID | None,
        messages: Sequence[Message],
        updated_at: datetime,
        preparation_id: UUID | None = None,
        complete_preparation: bool = False,
    ) -> list[Message]:
        scope = current_application_scope()
        messages = tuple(scoped_record(item) for item in messages)
        deadline = monotonic() + 5
        metadata = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
        if metadata is None:
            raise ResourceNotFoundError("conversation not found")
        revision = int(metadata["revision"])
        history = self._read_history(owner_id, conversation_id, scope, deadline=deadline)
        stable = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
        if stable is None or int(stable["revision"]) != revision:
            raise ConversationConflictError("conversation changed; retry the request")
        lease = metadata.get("context_preparation_id")
        if complete_preparation and lease != str(preparation_id):
            raise ConversationConflictError("context preparation expired")
        if not complete_preparation and lease is not None:
            raise ConversationConflictError("context preparation is in progress")
        if metadata.get("effect_guard") is not None:
            raise ConversationConflictError("memory effect is being applied")
        active = active_path(history)
        if [item.id for item in active] != list(expected_active_ids):
            raise ConversationConflictError("conversation changed; retry the request")
        if any(item.status in {MessageStatus.STREAMING, MessageStatus.PENDING} for item in active):
            raise ConversationConflictError("a response is already in progress")
        if supersede_from_message_id is not None and supersede_from_message_id not in {
            item.id for item in active
        }:
            raise ConversationConflictError("retry target is no longer active")
        history_ids = {item.id for item in history}
        if any(item.id in history_ids for item in messages):
            raise ConversationConflictError("message already exists")
        if any(
            item.owner_id != owner_id or item.conversation_id != conversation_id
            for item in messages
        ):
            raise ResourceNotFoundError("conversation not found")
        conversation = _conversation_from_item(metadata)
        updated_conversation = conversation.model_copy(update={"updated_at": _utc(updated_at)})
        next_revision = revision + 1
        operations: list[dict[str, Any]] = []
        if supersede_from_message_id is not None:
            target = next((item for item in history if item.id == supersede_from_message_id), None)
            if target is None:
                raise ConversationConflictError("retry target is no longer active")
            operations.append(
                _update(
                    _message_key(scope, conversation_id, target.created_at, target.id, owner_id),
                    "SET #status=:status,#payload=:payload",
                    names={"#status": "status", "#owner": "owner_id", "#payload": "payload"},
                    values={
                        ":status": MessageStatus.SUPERSEDED.value,
                        ":owner": owner_id,
                        ":payload": _json(
                            _message_payload(
                                target.model_copy(update={"status": MessageStatus.SUPERSEDED})
                            )
                        ),
                    },
                    condition="#owner=:owner AND #status <> :status",
                )
            )
        for message in messages:
            canonical = _message_item(message, scope)
            locator = _message_locator(message, scope)
            operations.extend(
                [
                    _put(canonical, condition="attribute_not_exists(PK)"),
                    _put(locator, condition="attribute_not_exists(PK)"),
                ]
            )
        update_expression = "SET #payload=:payload,#updated=:updated,#revision=:next"
        names = {
            "#payload": "payload",
            "#updated": "updated_at",
            "#revision": "revision",
            "#owner": "owner_id",
        }
        values: dict[str, Any] = {
            ":payload": _json(_conversation_payload(updated_conversation)),
            ":updated": _timestamp(updated_at),
            ":next": next_revision,
            ":owner": owner_id,
            ":revision": revision,
        }
        condition = "#owner=:owner AND revision=:revision AND attribute_not_exists(effect_guard)"
        if complete_preparation:
            condition += " AND context_preparation_id=:preparation"
            values[":preparation"] = str(preparation_id)
            update_expression += " REMOVE context_preparation_id,context_preparation_started_at"
        elif preparation_id is not None:
            condition += " AND attribute_not_exists(context_preparation_id)"
            update_expression = (
                "SET #payload=:payload,#updated=:updated,#revision=:next,"
                "context_preparation_id=:preparation,context_preparation_started_at=:started"
            )
            values[":preparation"] = str(preparation_id)
            values[":started"] = _timestamp(updated_at)
        operations.append(
            _update(
                _conversation_keys(scope, conversation_id, owner_id).meta,
                update_expression,
                names=names,
                values=values,
                condition=condition,
            )
        )
        self._append_catalog_move(
            operations, scope, conversation, updated_conversation, next_revision
        )
        try:
            self.table.transact(operations)
        except Exception as error:
            if _conditional_failure(error):
                raise ConversationConflictError(
                    "conversation changed; retry the request"
                ) from error
            raise
        return list(messages)

    def release_preparation(
        self, *, owner_id: str, conversation_id: UUID, preparation_id: UUID
    ) -> None:
        scope = current_application_scope()
        metadata = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
        if metadata is None:
            raise ResourceNotFoundError("conversation not found")
        try:
            self.table.transact(
                [
                    _update(
                        _conversation_keys(scope, conversation_id, owner_id).meta,
                        "REMOVE context_preparation_id,context_preparation_started_at",
                        names={"#owner": "owner_id"},
                        values={":owner": owner_id, ":preparation": str(preparation_id)},
                        condition="#owner=:owner AND context_preparation_id=:preparation "
                        "AND attribute_not_exists(effect_guard)",
                    )
                ]
            )
        except Exception as error:
            if _conditional_failure(error):
                return
            raise

    def recover_stale_turn(
        self,
        *,
        owner_id: str,
        conversation_id: UUID,
        stale_before: datetime,
        updated_at: datetime,
    ) -> None:
        scope = current_application_scope()
        metadata = self.conversations._metadata_item_for(owner_id, conversation_id, scope)
        if metadata is None:
            raise ResourceNotFoundError("conversation not found")
        history = self._read_history(owner_id, conversation_id, scope, timeout=5)
        active = active_path(history)
        stale = [
            m
            for m in active
            if m.status in {MessageStatus.STREAMING, MessageStatus.PENDING}
            and (
                m.created_at < stale_before
                or (m.execution is not None and m.execution.expires_at <= updated_at)
            )
        ]
        started = metadata.get("context_preparation_started_at")
        expired = bool(started and _parse_timestamp(started) < stale_before)
        if not stale and not expired:
            return
        if len(stale) + 4 > MAX_DYNAMO_TRANSACTION_ITEMS:
            raise StorageUnavailableError("stale turn recovery bound exceeded")
        conversation = _conversation_from_item(metadata)
        updated_conversation = conversation.model_copy(update={"updated_at": _utc(updated_at)})
        revision = int(metadata["revision"])
        operations = []
        for message in stale:
            failed = transition_message(
                message,
                message.model_copy(
                    update={"status": MessageStatus.FAILED, "error_code": "turn_interrupted"}
                ),
            )
            operations.append(
                _update(
                    _message_key(scope, conversation_id, message.created_at, message.id, owner_id),
                    "SET #status=:status,#payload=:payload",
                    names={"#status": "status", "#owner": "owner_id", "#payload": "payload"},
                    values={
                        ":status": MessageStatus.FAILED.value,
                        ":owner": owner_id,
                        ":payload": _json(_message_payload(failed)),
                    },
                    condition="#owner=:owner AND #status=:streaming",
                    more_values={":streaming": message.status.value},
                )
            )
        update_expression = "SET #payload=:payload,#updated=:updated,#revision=:next"
        if expired:
            update_expression += " REMOVE context_preparation_id,context_preparation_started_at"
        operations.append(
            _update(
                _conversation_keys(scope, conversation_id, owner_id).meta,
                update_expression,
                names={
                    "#payload": "payload",
                    "#updated": "updated_at",
                    "#revision": "revision",
                    "#owner": "owner_id",
                },
                values={
                    ":payload": _json(_conversation_payload(updated_conversation)),
                    ":updated": _timestamp(updated_at),
                    ":next": revision + 1,
                    ":owner": owner_id,
                    ":revision": revision,
                },
                condition="#owner=:owner AND revision=:revision AND attribute_not_exists(effect_guard)",
            )
        )
        self._append_catalog_move(
            operations, scope, conversation, updated_conversation, revision + 1
        )
        self.table.transact(operations)

    def supersede_path(
        self, *, owner_id: str, conversation_id: UUID, message_id: UUID, updated_at: datetime
    ):
        self.get(owner_id=owner_id, conversation_id=conversation_id, message_id=message_id)
        scope = current_application_scope()
        history = self._read_history(owner_id, conversation_id, scope, timeout=5)
        by_id = {message.id: message for message in history}
        descendants = descendant_ids(history, message_id)
        replaced = [
            by_id[identifier]
            for identifier in descendants
            if identifier in by_id
            and effective_message(by_id[identifier], by_id).status is not MessageStatus.SUPERSEDED
        ]
        self.prepare_message_turn(
            owner_id=owner_id,
            conversation_id=conversation_id,
            expected_active_ids=[message.id for message in active_path(history)],
            supersede_from_message_id=message_id,
            messages=(),
            updated_at=updated_at,
        )
        return [
            message.model_copy(update={"status": MessageStatus.SUPERSEDED})
            for message in sorted(replaced, key=lambda item: (item.created_at, str(item.id)))
        ]

    def _read_history(
        self,
        owner_id: str,
        conversation_id: UUID,
        scope: ApplicationScope,
        timeout: float = 5,
        *,
        deadline: float | None = None,
    ):
        keys = _conversation_keys(scope, conversation_id, owner_id)
        deadline = deadline or monotonic() + timeout
        items = self.table.query(
            partition=keys.partition,
            sort_prefix="MSG#",
            consistent=True,
            deadline=deadline,
            limit=MAX_CONVERSATION_MESSAGES + 1,
        )
        if len(items) > MAX_CONVERSATION_MESSAGES:
            raise StorageUnavailableError("conversation history exceeds bound")
        messages = []
        for item in items:
            if not _authorized(item, owner_id, scope):
                continue
            try:
                messages.append(_message_from_item(item))
            except (ValueError, TypeError, KeyError) as error:
                raise StorageUnavailableError("message record invalid") from error
        return messages

    @staticmethod
    def _append_catalog_move(operations, scope, old, new, revision):
        old_key = _catalog_key(scope, old.id, old.updated_at, old.owner_id)
        item = _catalog_item(new, revision=revision)
        new_key = {"PK": item["PK"], "SK": item["SK"]}
        if old_key != new_key:
            operations.extend([_delete(old_key), _put(item, condition="attribute_not_exists(PK)")])
        else:
            operations.append(
                _update(
                    old_key,
                    "SET #revision=:revision,#updated=:updated",
                    names={"#revision": "revision", "#updated": "updated_at", "#owner": "owner_id"},
                    values={
                        ":revision": revision,
                        ":updated": _timestamp(new.updated_at),
                        ":owner": new.owner_id,
                    },
                    condition="#owner=:owner",
                )
            )
