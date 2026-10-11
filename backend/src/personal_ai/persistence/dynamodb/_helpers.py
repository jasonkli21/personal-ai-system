"""DynamoDB key, serialization, and operation helpers."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from .client import DynamoDBRuntimeTable

from personal_ai.auth.scope import ApplicationScope
from personal_ai.entities import Conversation, Message
from personal_ai.storage.errors import StorageUnavailableError

RUNTIME_TABLE_NAME = "personal-ai-runtime-v1"

MAX_DYNAMO_ITEM_BYTES = 400 * 1024

MAX_DYNAMO_TRANSACTION_ITEMS = 100

MAX_DYNAMO_TRANSACTION_BYTES = 4 * 1024 * 1024

SUMMARY_CHUNK_IDS = 256

MAX_SUMMARY_CHUNKS = 200

MAX_CONVERSATION_MESSAGES = 10_000


def _check_context_trace_deadline(deadline: float | None) -> None:
    if deadline is not None and monotonic() >= deadline:
        raise TimeoutError("context trace persistence deadline exceeded")


def _b64(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _namespace(scope: ApplicationScope, owner_id: str) -> str:
    return "N2#" + _b64([owner_id, scope.application_id, scope.workspace_id])


def _conversation_keys(
    scope: ApplicationScope, conversation_id: UUID, owner_id: str | None = None
) -> ConversationKeys:
    owner_id = owner_id or _owner_from_scope_context()
    partition = f"{_namespace(scope, owner_id)}#CONV#{conversation_id}"
    return ConversationKeys(partition, {"PK": partition, "SK": "META"})


def _owner_from_scope_context() -> str:
    """Owner is embedded in RequestScope; low-level key helpers can also be passed via item."""
    from personal_ai.auth.scope import current_request_scope

    request_scope = current_request_scope()
    return request_scope.owner_id if request_scope is not None else "local"


def _conversation_keys_for(owner_id: str, scope: ApplicationScope, conversation_id: UUID):
    partition = f"{_namespace(scope, owner_id)}#CONV#{conversation_id}"
    return ConversationKeys(partition, {"PK": partition, "SK": "META"})


def _scope_of(record) -> ApplicationScope:
    return ApplicationScope(
        application_id=getattr(record, "application_id", "personal_ai"),
        workspace_id=getattr(record, "workspace_id", None),
    )


def _authorized(item: dict[str, Any], owner_id: str, scope: ApplicationScope) -> bool:
    application_id = item.get("application_id", "personal_ai")
    workspace_id = (
        item.get("workspace_id")
        if item.get("workspace_id_present", "workspace_id" in item)
        else None
    )
    if "workspace_id_present" in item and not item["workspace_id_present"]:
        workspace_id = None
    return (
        item.get("owner_id") == owner_id
        and application_id == scope.application_id
        and workspace_id == scope.workspace_id
    )


def _conversation_payload(conversation: Conversation) -> dict[str, Any]:
    return conversation.model_dump(
        mode="json", exclude={"context_preparation_id", "context_preparation_started_at"}
    )


def _metadata_item(
    conversation: Conversation, payload: dict[str, Any], *, revision: int
) -> dict[str, Any]:
    scope = _scope_of(conversation)
    item = {
        **_conversation_keys_for(conversation.owner_id, scope, conversation.id).meta,
        "kind": "conversation",
        "owner_id": conversation.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "payload": _json(payload),
        "revision": revision,
        "created_at": _timestamp(conversation.created_at),
        "updated_at": _timestamp(conversation.updated_at),
    }
    if conversation.context_preparation_id is not None:
        item["context_preparation_id"] = str(conversation.context_preparation_id)
    if conversation.context_preparation_started_at is not None:
        item["context_preparation_started_at"] = _timestamp(
            conversation.context_preparation_started_at
        )
    if _item_size(item) > MAX_DYNAMO_ITEM_BYTES:
        raise StorageUnavailableError("conversation item too large")
    return item


def _conversation_from_item(item: dict[str, Any]) -> Conversation:
    payload = json.loads(item["payload"])
    if item.get("context_preparation_id"):
        payload["context_preparation_id"] = UUID(item["context_preparation_id"])
    if item.get("context_preparation_started_at"):
        payload["context_preparation_started_at"] = _parse_timestamp(
            item["context_preparation_started_at"]
        )
    payload["persistence_revision"] = int(item["revision"])
    return Conversation.model_validate(payload)


def _catalog_key(
    scope: ApplicationScope,
    conversation_id: UUID,
    updated_at: datetime,
    owner_id: str | None = None,
):
    owner = owner_id or _owner_from_scope_context()
    return {
        "PK": f"{_namespace(scope, owner)}#CATALOG",
        "SK": f"CONV#{_timestamp(updated_at)}#{conversation_id}",
    }


def _catalog_item(conversation: Conversation, *, revision: int) -> dict[str, Any]:
    scope = _scope_of(conversation)
    return {
        **_catalog_key_for(conversation.owner_id, scope, conversation.id, conversation.updated_at),
        "kind": "conversation-directory",
        "owner_id": conversation.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "conversation_id": str(conversation.id),
        "updated_at": _timestamp(conversation.updated_at),
        "revision": revision,
    }


def _catalog_key_for(owner_id, scope, conversation_id, updated_at):
    return {
        "PK": f"{_namespace(scope, owner_id)}#CATALOG",
        "SK": f"CONV#{_timestamp(updated_at)}#{conversation_id}",
    }


def _namespace_puts(table: DynamoDBRuntimeTable, owner_id: str, scope: ApplicationScope):
    namespace = _namespace(scope, owner_id)
    owner_pk = f"OWNER#{_b64(owner_id)}"
    scope_key = _b64([scope.application_id, scope.workspace_id])
    entries = [
        {
            "PK": owner_pk,
            "SK": f"NS#{scope_key}",
            "kind": "owner-namespace",
            "owner_id": owner_id,
            "application_id": scope.application_id,
            "workspace_id_present": scope.workspace_id is not None,
            "workspace_id": scope.workspace_id or "",
        },
        {
            "PK": "MAINT#NAMESPACES",
            "SK": f"NS#{_b64([owner_id, scope.application_id, scope.workspace_id])}",
            "kind": "maintenance-namespace",
            "owner_id": owner_id,
            "application_id": scope.application_id,
            "workspace_id_present": scope.workspace_id is not None,
            "workspace_id": scope.workspace_id or "",
            "namespace": namespace,
        },
    ]
    operations = []
    for item in entries:
        if table.get({"PK": item["PK"], "SK": item["SK"]}) is None:
            operations.append(_put(item, condition="attribute_not_exists(PK)"))
    return operations


def _message_key(
    scope: ApplicationScope,
    conversation_id: UUID,
    created_at: datetime,
    message_id: UUID,
    owner_id: str | None = None,
):
    owner = owner_id or _owner_from_scope_context()
    partition = f"{_namespace(scope, owner)}#CONV#{conversation_id}"
    return {"PK": partition, "SK": f"MSG#{_timestamp(created_at)}#{message_id}"}


def _message_item(message: Message, scope: ApplicationScope):
    return {
        **_message_key_for(
            message.owner_id, scope, message.conversation_id, message.created_at, message.id
        ),
        "kind": "message",
        "owner_id": message.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "conversation_id": str(message.conversation_id),
        "message_id": str(message.id),
        "created_at": _timestamp(message.created_at),
        "status": message.status.value,
        "payload": _json(_message_payload(message)),
    }


def _message_key_for(owner_id, scope, conversation_id, created_at, message_id):
    partition = f"{_namespace(scope, owner_id)}#CONV#{conversation_id}"
    return {"PK": partition, "SK": f"MSG#{_timestamp(created_at)}#{message_id}"}


def _message_locator(message: Message, scope: ApplicationScope):
    canonical = _message_key_for(
        message.owner_id, scope, message.conversation_id, message.created_at, message.id
    )
    return {
        "PK": canonical["PK"],
        "SK": f"MID#{message.id}",
        "kind": "message-locator",
        "owner_id": message.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "conversation_id": str(message.conversation_id),
        "message_id": str(message.id),
        "message_pk": canonical["PK"],
        "message_sk": canonical["SK"],
    }


def _message_payload(message: Message):
    return message.model_dump(mode="json")


def _message_from_item(item):
    return Message.model_validate(json.loads(item["payload"]))


def _job_key(scope: ApplicationScope, job_id: UUID, owner_id: str | None = None):
    if owner_id is None:
        owner_id = _owner_from_scope_context()
    partition = f"{_namespace(scope, owner_id)}#JOB#{job_id}"
    return {"PK": partition, "SK": "META"}


def _job_id_locator(job, scope):
    key = _job_key(scope, job.id, job.owner_id)
    return {
        "PK": f"JOBID#{job.id}",
        "SK": "LOCATOR",
        "kind": "service-job-locator",
        "owner_id": job.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "record_pk": key["PK"],
        "record_sk": key["SK"],
    }


def _job_item(job, *, revision: int):
    scope = _scope_of(job)
    key = _job_key(scope, job.id, job.owner_id)
    item = {
        **key,
        "kind": "memory-lifecycle-job",
        "owner_id": job.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "job_id": str(job.id),
        "status": job.status,
        "revision": revision,
        "created_at": _timestamp(job.created_at),
        "updated_at": _timestamp(job.updated_at),
        "payload": job.model_dump_json(),
    }
    if job.status == "leased":
        item.update(
            {
                "lease_token": str(job.lease_token),
                "lease_generation": job.lease_generation,
                "lease_expires_at": _timestamp(job.lease_expires_at),
            }
        )
    if job.status in {"pending", "retry"} and job.publish_pending:
        namespace = _namespace(scope, job.owner_id)
        item.update(
            {
                "PUBPK": f"PUB#{namespace}#{job.status}",
                "PUBSK": f"{_timestamp(job.created_at)}#{job.id}",
                "record_pk": key["PK"],
                "record_sk": key["SK"],
                "publish_after": _timestamp(job.next_attempt_at or job.created_at),
            }
        )
    if _item_size(item) > MAX_DYNAMO_ITEM_BYTES:
        raise StorageUnavailableError("memory job item too large")
    return item


def _job_catalog_item(job, scope):
    return {
        "PK": f"{_namespace(scope, job.owner_id)}#CATALOG",
        "SK": f"JOB#{job.id}",
        "kind": "job-directory",
        "owner_id": job.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "job_id": str(job.id),
        "record_pk": _job_key(scope, job.id, job.owner_id)["PK"],
        "record_sk": "META",
    }


def _owner_job_catalog_item(job, scope):
    return {
        "PK": f"OWNER#{_b64(job.owner_id)}",
        "SK": f"JOB#{_b64([scope.application_id, scope.workspace_id])}#{job.id}",
        "kind": "owner-job-directory",
        "owner_id": job.owner_id,
        "application_id": scope.application_id,
        "workspace_id_present": scope.workspace_id is not None,
        "workspace_id": scope.workspace_id or "",
        "job_id": str(job.id),
    }


def _same_job_intent(first, second):
    immutable = {
        "status",
        "attempt_count",
        "lease_expires_at",
        "lease_token",
        "lease_generation",
        "publish_pending",
        "retry_reason",
        "next_attempt_at",
        "updated_at",
        "application_id",
        "workspace_id",
        "scope_version",
    }
    return first.model_dump(exclude=immutable) == second.model_dump(exclude=immutable)


def _source_refs(record):
    if hasattr(record, "sources"):
        sources = record.sources
    else:
        sources = (record,)
    return [
        {
            "conversation_id": str(source.source_conversation_id),
            "turn_id": str(source.source_turn_id),
            "user_message_ids": [str(identifier) for identifier in source.source_message_ids],
            "source_fingerprint": source.source_fingerprint,
        }
        for source in sources
    ]


def _record_fingerprint(record) -> str:
    encoded = record.model_dump_json(exclude_none=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _chunks(values):
    values = tuple(values)
    return [
        values[index : index + SUMMARY_CHUNK_IDS]
        for index in range(0, len(values), SUMMARY_CHUNK_IDS)
    ]


def _chunk_manifest(chunks):
    hashes = [
        hashlib.sha256(_json([str(identifier) for identifier in chunk]).encode()).hexdigest()
        for chunk in chunks
    ]
    flattened = tuple(identifier for chunk in chunks for identifier in chunk)
    return {
        "chunks": len(chunks),
        "count": len(flattened),
        "hashes": hashes,
        "sha256": _sequence_hash(flattened),
    }


def _sequence_hash(values):
    return hashlib.sha256(_json([str(identifier) for identifier in values]).encode()).hexdigest()


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _timestamp(value: datetime) -> str:
    value = _utc(value)
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp_invalid")
    return value.astimezone(UTC)


def _marshal(value: dict[str, Any]):
    from boto3.dynamodb.types import TypeSerializer

    serializer = TypeSerializer()
    return {key: serializer.serialize(item) for key, item in value.items()}


def _unmarshal(value: dict[str, Any]):
    from boto3.dynamodb.types import TypeDeserializer

    deserializer = TypeDeserializer()
    return {key: deserializer.deserialize(item) for key, item in value.items()}


def _put(item, *, condition: str | None = None):
    if _item_size(item) > MAX_DYNAMO_ITEM_BYTES:
        raise StorageUnavailableError("dynamodb item too large")
    request = {"TableName": "", "Item": _marshal(item)}
    # TableName is filled by DynamoDBRuntimeTable.transact.
    if condition:
        request["ConditionExpression"] = condition
    return {"Put": request}


def _update(
    key,
    update_expression,
    *,
    names,
    values,
    condition,
    more_names=None,
    more_values=None,
):
    merged_names = {**names, **(more_names or {})}
    merged_values = {**values, **(more_values or {})}
    return {
        "Update": {
            "TableName": "",
            "Key": _marshal(key),
            "UpdateExpression": update_expression,
            "ConditionExpression": condition,
            "ExpressionAttributeNames": merged_names,
            "ExpressionAttributeValues": _marshal(merged_values),
        }
    }


def _delete(key):
    return {"Delete": {"TableName": "", "Key": _marshal(key)}}


def _operation_size(operation):
    raw = json.dumps(operation, separators=(",", ":"), ensure_ascii=True)
    return len(raw.encode("utf-8")) + 64


def _item_size(item):
    raw = json.dumps(item, default=str, ensure_ascii=False, separators=(",", ":"))
    # Account for DynamoDB's per-attribute name/type overhead conservatively.
    return len(raw.encode("utf-8")) + 16 * len(item)


def _conditional_failure(error: Exception) -> bool:
    response = getattr(error, "response", {})
    code = response.get("Error", {}).get("Code", "")
    if code == "ConditionalCheckFailedException":
        return True
    if code == "TransactionCanceledException":
        reasons = response.get("CancellationReasons", ())
        return not reasons or any(
            reason.get("Code") == "ConditionalCheckFailed" for reason in reasons
        )
    return error.__class__.__name__ in {
        "ConditionalCheckFailedException",
        "TransactionCanceledException",
    }


@dataclass(frozen=True)
class ConversationKeys:
    partition: str
    meta: dict[str, str]
