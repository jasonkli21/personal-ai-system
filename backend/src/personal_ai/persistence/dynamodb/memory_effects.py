"""DynamoDB memory-source and cross-store effect guards."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from personal_ai.auth.scope import ApplicationScope, scope_matches
from personal_ai.context.contracts import fingerprint
from personal_ai.entities import MessageRole, MessageStatus
from personal_ai.memory.effects import EffectGuardToken
from personal_ai.storage.errors import (
    ConversationConflictError,
    ResourceNotFoundError,
    StorageUnavailableError,
)

from ._helpers import (
    MAX_DYNAMO_ITEM_BYTES,
    _authorized,
    _conditional_failure,
    _conversation_keys,
    _delete,
    _item_size,
    _job_key,
    _json,
    _namespace,
    _parse_timestamp,
    _put,
    _record_fingerprint,
    _scope_of,
    _source_refs,
    _timestamp,
    _update,
)
from .client import DynamoDBRuntimeTable
from .memory_jobs import DynamoDBMemoryJobRepository
from .messages import DynamoDBMessageRepository


class DynamoDBMemoryEffectGuard:
    """Conversation metadata guards and direct-operation receipts in DynamoDB."""

    def __init__(self, table: DynamoDBRuntimeTable, messages: DynamoDBMessageRepository) -> None:
        self.table = table
        self.messages = messages

    def acquire(
        self,
        record: Any,
        *,
        timeout: float,
        operation_id: str | None = None,
        fingerprint_value: str | None = None,
        extra_conversation_ids: tuple[UUID, ...] = (),
        completed_assistant_id: UUID | None = None,
    ) -> EffectGuardToken:
        owner_id = record.owner_id
        scope = ApplicationScope(
            application_id=record.application_id, workspace_id=record.workspace_id
        )
        refs = _source_refs(record)
        if not refs or len(refs) > 4:
            raise ConversationConflictError("memory source set invalid")
        deadline = monotonic() + timeout
        operation_id = operation_id or str(record.id)
        fp = fingerprint_value or _record_fingerprint(record)
        if not operation_id or len(operation_id) > 512:
            raise ValueError("memory_effect_operation_id_invalid")
        guarded_conversations = sorted(
            {ref["conversation_id"] for ref in refs}
            | {str(value) for value in extra_conversation_ids},
            key=str,
        )
        first_ref = refs[0]
        first_partition = _conversation_keys(
            scope, UUID(first_ref["conversation_id"]), owner_id
        ).partition
        prior_operations = self.table.query(
            partition=first_partition,
            sort_prefix=f"OP#{operation_id}#",
            consistent=True,
            deadline=deadline,
            limit=100,
        )
        matching = [item for item in prior_operations if item.get("fingerprint") == fp]
        prior = max(matching, key=lambda item: item.get("created_at", ""), default=None)
        if prior is not None and prior.get("status") == "applied":
            return EffectGuardToken(
                owner_id=owner_id,
                operation_id=operation_id,
                attempt_id=prior["attempt_id"],
                fingerprint=fp,
                execution_deadline=_parse_timestamp(prior["execution_deadline"]),
                scope=scope,
                coordination_conversation_id=UUID(first_ref["conversation_id"]),
            )
        snapshots = {}
        for conversation_id in guarded_conversations:
            metadata = self.messages.conversations._metadata_item_for(
                owner_id, conversation_id, scope
            )
            if metadata is None:
                raise ConversationConflictError("memory source not found")
            if metadata.get("context_preparation_id") or metadata.get("effect_guard"):
                guard = metadata.get("effect_guard", {})
                if guard.get("operation_id") == operation_id and guard.get("fingerprint") == fp:
                    snapshots[str(conversation_id)] = metadata
                    continue
                raise ConversationConflictError("memory source changing")
            snapshots[str(conversation_id)] = metadata
        for ref in refs:
            active = self.messages.list_active(
                owner_id=owner_id,
                conversation_id=UUID(ref["conversation_id"]),
                timeout=max(0.1, deadline - monotonic()),
            )
            sources = [message for message in active if str(message.id) in ref["user_message_ids"]]
            assistant = next(
                (message for message in active if str(message.id) == ref["turn_id"]), None
            )
            if (
                assistant is None
                or assistant.status is not MessageStatus.COMPLETED
                or assistant.role.value != "assistant"
                or assistant.parent_message_id is None
                or str(assistant.parent_message_id) not in ref["user_message_ids"]
                or [str(message.id) for message in sources] != ref["user_message_ids"]
                or fingerprint(sources) != ref["source_fingerprint"]
            ):
                raise ConversationConflictError("memory source inactive")
        if completed_assistant_id is not None:
            if len(extra_conversation_ids) != 1:
                raise ConversationConflictError("assistant_conversation_invalid")
            assistant_conversation_id = extra_conversation_ids[0]
            active = self.messages.list_active(
                owner_id=owner_id,
                conversation_id=assistant_conversation_id,
                timeout=max(0.1, deadline - monotonic()),
            )
            assistant = next((item for item in active if item.id == completed_assistant_id), None)
            if (
                assistant is None
                or assistant.conversation_id != assistant_conversation_id
                or assistant.owner_id != owner_id
                or not scope_matches(assistant, scope)
                or assistant.role is not MessageRole.ASSISTANT
                or assistant.status is not MessageStatus.COMPLETED
            ):
                raise ConversationConflictError("assistant_incomplete")
        existing_attempts = {
            metadata.get("effect_guard", {}).get("attempt_id")
            for metadata in snapshots.values()
            if metadata.get("effect_guard", {}).get("operation_id") == operation_id
            and metadata.get("effect_guard", {}).get("fingerprint") == fp
        }
        if prior is not None and prior.get("status") == "pending":
            attempt_id = prior["attempt_id"]
        elif len(existing_attempts) == 1:
            attempt_id = existing_attempts.pop()
        elif existing_attempts:
            raise ConversationConflictError("memory source guard attempts disagree")
        else:
            attempt_id = str(uuid4())
        operation_key = {"PK": first_partition, "SK": f"OP#{operation_id}#{attempt_id}"}
        fixed_deadline = (
            _parse_timestamp(prior["execution_deadline"])
            if prior is not None and prior.get("status") == "pending"
            else datetime.now(UTC) + timedelta(seconds=max(1, timeout))
        )
        operation_item = {
            **operation_key,
            "kind": "memory-effect",
            "owner_id": owner_id,
            "application_id": scope.application_id,
            "workspace_id_present": scope.workspace_id is not None,
            "workspace_id": scope.workspace_id or "",
            "operation_id": operation_id,
            "attempt_id": attempt_id,
            "fingerprint": fp,
            "status": "pending",
            "execution_deadline": _timestamp(fixed_deadline),
            "refs": _json(refs),
            "guard_conversations": _json(guarded_conversations),
            "coordination_conversation_id": first_ref["conversation_id"],
            "created_at": _timestamp(datetime.now(UTC)),
        }
        if _item_size(operation_item) > MAX_DYNAMO_ITEM_BYTES:
            raise StorageUnavailableError("memory effect guard too large")
        operations = []
        for conversation_key, metadata in snapshots.items():
            conversation_id = UUID(conversation_key)
            key = _conversation_keys(scope, conversation_id, owner_id).meta
            revision = int(metadata["revision"])
            guard = {
                "operation_id": operation_id,
                "attempt_id": attempt_id,
                "fingerprint": fp,
                "execution_deadline": _timestamp(fixed_deadline),
                "source_conversation_id": conversation_key,
            }
            operations.append(
                _update(
                    key,
                    "SET effect_guard=:guard",
                    names={"#owner": "owner_id", "#revision": "revision"},
                    values={
                        ":guard": guard,
                        ":owner": owner_id,
                        ":revision": revision,
                        ":attempt": attempt_id,
                        ":operation": operation_id,
                    },
                    condition="#owner=:owner AND #revision=:revision AND attribute_not_exists(context_preparation_id) "
                    "AND (attribute_not_exists(effect_guard) OR (effect_guard.operation_id=:operation "
                    "AND effect_guard.attempt_id=:attempt))",
                )
            )
        old_operation = self.table.get(operation_key)
        if old_operation is None:
            if not (prior and prior.get("status") == "pending"):
                operation_item["execution_deadline"] = _timestamp(fixed_deadline)
                operations.append(_put(operation_item, condition="attribute_not_exists(PK)"))
                operations.append(
                    _put(
                        {
                            "PK": f"{_namespace(scope, owner_id)}#OPS",
                            "SK": f"DIRECT#{first_ref['conversation_id']}#{operation_id}#{attempt_id}",
                            "kind": "pending-memory-effect",
                            "effect_kind": "direct",
                            "owner_id": owner_id,
                            "application_id": scope.application_id,
                            "workspace_id_present": scope.workspace_id is not None,
                            "workspace_id": scope.workspace_id or "",
                            "operation_pk": operation_key["PK"],
                            "operation_sk": operation_key["SK"],
                            "conversation_id": first_ref["conversation_id"],
                            "created_at": _timestamp(datetime.now(UTC)),
                        },
                        condition="attribute_not_exists(PK)",
                    )
                )
        elif old_operation.get("fingerprint") != fp:
            raise ConversationConflictError("memory effect identity conflict")
        else:
            fixed_deadline = _parse_timestamp(old_operation["execution_deadline"])
        if operations:
            self.table.transact(operations)
        self._operation_conversations = getattr(self, "_operation_conversations", {})
        self._operation_conversations[(operation_id, attempt_id)] = first_ref["conversation_id"]
        return EffectGuardToken(
            owner_id=owner_id,
            operation_id=operation_id,
            attempt_id=attempt_id,
            fingerprint=fp,
            execution_deadline=fixed_deadline,
            scope=scope,
            coordination_conversation_id=UUID(first_ref["conversation_id"]),
        )

    def acquire_lifecycle_event(
        self,
        record: Any,
        *,
        operation_id: str,
        fingerprint: str,
        completed_assistant_id: UUID | None,
        completed_assistant_conversation_id: UUID | None,
        timeout: float,
    ) -> EffectGuardToken:
        extra = (
            ()
            if completed_assistant_conversation_id is None
            else (completed_assistant_conversation_id,)
        )
        return self.acquire(
            record,
            timeout=timeout,
            operation_id=operation_id,
            fingerprint_value=fingerprint,
            extra_conversation_ids=extra,
            completed_assistant_id=completed_assistant_id,
        )

    def acquire_job(
        self,
        job: Any,
        lease_token: UUID,
        record: Any,
        *,
        operation_id: str,
        timeout: float,
    ) -> EffectGuardToken:
        """Fence a P effect with the live D job generation and its chat sources."""
        from personal_ai.memory.lifecycle import MemoryJob

        if not isinstance(job, MemoryJob) or not operation_id or len(operation_id) > 512:
            raise ValueError("memory_job_effect_invalid")
        owner_id = job.owner_id
        scope = _scope_of(job)
        if getattr(record, "owner_id", None) != owner_id or (
            getattr(record, "application_id", None),
            getattr(record, "workspace_id", None),
        ) != (scope.application_id, scope.workspace_id):
            raise ConversationConflictError("memory job effect scope changed")
        refs = _source_refs(record)
        if len(refs) > 4:
            raise ConversationConflictError("memory source set invalid")
        deadline = monotonic() + timeout
        job_key = _job_key(scope, job.id, owner_id)
        item = self.table.get(job_key)
        current = DynamoDBMemoryJobRepository._decode_job(item, owner_id, scope)
        now = datetime.now(UTC)
        if (
            current.status != "leased"
            or current.lease_token != lease_token
            or current.lease_generation != job.lease_generation
            or current.lease_expires_at is None
            or current.lease_expires_at <= now
        ):
            raise ConversationConflictError("memory job lease changed")
        fingerprint_value = _record_fingerprint(record)
        generation_attempt = f"g{current.lease_generation}:{lease_token}"
        acknowledged = item.get("last_effect_ack")
        if (
            acknowledged is not None
            and acknowledged.get("operation_id") == operation_id
            and acknowledged.get("attempt_id") == generation_attempt
            and acknowledged.get("fingerprint") == fingerprint_value
            and acknowledged.get("lease_generation") == current.lease_generation
        ):
            if acknowledged.get("outcome") == "aborted":
                raise ConversationConflictError("memory job effect attempt was aborted")
            if acknowledged.get("outcome") == "applied":
                return EffectGuardToken(
                    owner_id=owner_id,
                    operation_id=operation_id,
                    attempt_id=generation_attempt,
                    fingerprint=fingerprint_value,
                    execution_deadline=_parse_timestamp(acknowledged["execution_deadline"]),
                    scope=scope,
                    coordination_conversation_id=(
                        UUID(refs[0]["conversation_id"]) if refs else None
                    ),
                    coordination_job_id=job.id,
                    lease_generation=current.lease_generation,
                )
        prior = item.get("pending_effect")
        if prior is not None:
            if (
                prior.get("operation_id") == operation_id
                and prior.get("attempt_id") == generation_attempt
                and prior.get("fingerprint") == fingerprint_value
            ):
                return EffectGuardToken(
                    owner_id=owner_id,
                    operation_id=operation_id,
                    attempt_id=generation_attempt,
                    fingerprint=fingerprint_value,
                    execution_deadline=_parse_timestamp(prior["execution_deadline"]),
                    scope=scope,
                    coordination_conversation_id=(
                        UUID(refs[0]["conversation_id"]) if refs else None
                    ),
                    coordination_job_id=job.id,
                    lease_generation=current.lease_generation,
                )
            raise ConversationConflictError("memory job effect already pending")

        snapshots = {}
        for conversation_id in sorted({ref["conversation_id"] for ref in refs}):
            metadata = self.messages.conversations._metadata_item_for(
                owner_id, UUID(conversation_id), scope
            )
            if metadata is None:
                raise ConversationConflictError("memory source not found")
            if metadata.get("context_preparation_id") or metadata.get("effect_guard"):
                raise ConversationConflictError("memory source changing")
            snapshots[conversation_id] = metadata
        for ref in refs:
            active = self.messages.list_active(
                owner_id=owner_id,
                conversation_id=UUID(ref["conversation_id"]),
                timeout=max(0.1, deadline - monotonic()),
            )
            by_id = {str(message.id): message for message in active}
            sources = [by_id.get(identifier) for identifier in ref["user_message_ids"]]
            assistant = by_id.get(ref["turn_id"])
            if (
                any(source is None or source.role.value != "user" for source in sources)
                or assistant is None
                or assistant.status is not MessageStatus.COMPLETED
                or assistant.role.value != "assistant"
                or assistant.parent_message_id is None
                or str(assistant.parent_message_id) not in ref["user_message_ids"]
                or fingerprint(sources) != ref["source_fingerprint"]
            ):
                raise ConversationConflictError("memory source inactive")

        execution_deadline = min(
            current.lease_expires_at,
            now + timedelta(seconds=max(1, timeout)),
        )
        if execution_deadline <= now:
            raise ConversationConflictError("memory job lease expired")
        pending = {
            "operation_id": operation_id,
            "attempt_id": generation_attempt,
            "fingerprint": fingerprint_value,
            "lease_generation": current.lease_generation,
            "lease_token": str(lease_token),
            "execution_deadline": _timestamp(execution_deadline),
            "refs": _json(refs),
        }
        if _item_size({**item, "pending_effect": pending}) > MAX_DYNAMO_ITEM_BYTES:
            raise StorageUnavailableError("memory job effect guard too large")
        operations = []
        for conversation_id, metadata in snapshots.items():
            key = _conversation_keys(scope, UUID(conversation_id), owner_id).meta
            operations.append(
                _update(
                    key,
                    "SET effect_guard=:guard",
                    names={"#owner": "owner_id", "#revision": "revision"},
                    values={
                        ":guard": {
                            "operation_id": operation_id,
                            "attempt_id": generation_attempt,
                            "fingerprint": fingerprint_value,
                            "execution_deadline": _timestamp(execution_deadline),
                            "job_id": str(job.id),
                            "lease_generation": current.lease_generation,
                        },
                        ":owner": owner_id,
                        ":revision": int(metadata["revision"]),
                    },
                    condition="#owner=:owner AND #revision=:revision "
                    "AND attribute_not_exists(context_preparation_id) "
                    "AND attribute_not_exists(effect_guard)",
                )
            )
        operations.append(
            _update(
                job_key,
                "SET pending_effect=:pending,#revision=:next",
                names={
                    "#owner": "owner_id",
                    "#revision": "revision",
                    "#status": "status",
                    "#token": "lease_token",
                    "#generation": "lease_generation",
                    "#expires": "lease_expires_at",
                },
                values={
                    ":pending": pending,
                    ":next": int(item["revision"]) + 1,
                    ":revision": int(item["revision"]),
                    ":owner": owner_id,
                    ":leased": "leased",
                    ":token": str(lease_token),
                    ":generation": current.lease_generation,
                    ":now": _timestamp(now),
                },
                condition="#owner=:owner AND #status=:leased AND revision=:revision "
                "AND #token=:token AND #generation=:generation AND #expires>:now "
                "AND attribute_not_exists(pending_effect)",
            )
        )
        operations.append(
            _put(
                {
                    "PK": f"{_namespace(scope, owner_id)}#OPS",
                    "SK": f"JOB#{job.id}",
                    "kind": "pending-memory-effect",
                    "effect_kind": "job",
                    "owner_id": owner_id,
                    "application_id": scope.application_id,
                    "workspace_id_present": scope.workspace_id is not None,
                    "workspace_id": scope.workspace_id or "",
                    "job_id": str(job.id),
                    "created_at": _timestamp(datetime.now(UTC)),
                },
                condition="attribute_not_exists(PK)",
            )
        )
        self.table.transact(operations)
        return EffectGuardToken(
            owner_id=owner_id,
            operation_id=operation_id,
            attempt_id=generation_attempt,
            fingerprint=fingerprint_value,
            execution_deadline=execution_deadline,
            scope=scope,
            coordination_conversation_id=UUID(refs[0]["conversation_id"]) if refs else None,
            coordination_job_id=job.id,
            lease_generation=current.lease_generation,
        )

    def acknowledge(
        self, token: EffectGuardToken, *, outcome: str, result_refs: dict[str, Any]
    ) -> None:
        if outcome not in {"applied", "aborted"}:
            raise ValueError("memory_effect_outcome_invalid")
        if token.coordination_job_id is not None:
            self._acknowledge_job(token, outcome=outcome, result_refs=result_refs)
            return
        # The operation stores the exact source conversation references; load it
        # strongly before touching guards, then condition every guarded write.
        conversation_id = token.coordination_conversation_id
        if conversation_id is None:
            raise ConversationConflictError("memory effect coordinator missing")
        operation_key = {
            "PK": _conversation_keys(token.scope, conversation_id, token.owner_id).partition,
            "SK": f"OP#{token.operation_id}#{token.attempt_id}",
        }
        operation = self.table.get(operation_key)
        if operation is None or operation.get("fingerprint") != token.fingerprint:
            raise ConversationConflictError("memory effect operation unavailable")
        if operation.get("status") in {"applied", "aborted"}:
            if operation["status"] != outcome:
                raise ConversationConflictError("memory effect outcome conflict")
            return
        refs = json.loads(operation["refs"])
        conversations = json.loads(
            operation.get(
                "guard_conversations", _json(sorted({ref["conversation_id"] for ref in refs}))
            )
        )
        actions = []
        for conversation_key in conversations:
            key = _conversation_keys(token.scope, UUID(conversation_key), token.owner_id).meta
            metadata = self.table.get(key)
            if metadata is None:
                raise ConversationConflictError("memory source conversation unavailable")
            actions.append(
                _update(
                    key,
                    "REMOVE effect_guard",
                    names={"#owner": "owner_id"},
                    values={
                        ":owner": operation["owner_id"],
                        ":operation": token.operation_id,
                        ":attempt": token.attempt_id,
                    },
                    condition="#owner=:owner AND effect_guard.operation_id=:operation "
                    "AND effect_guard.attempt_id=:attempt",
                )
            )
        actions.append(
            _update(
                operation_key,
                "SET #status=:status,#result=:result,#ack=:ack",
                names={"#status": "status", "#result": "result_refs", "#ack": "acknowledged_at"},
                values={
                    ":status": outcome,
                    ":result": _json(result_refs),
                    ":ack": _timestamp(datetime.now(UTC)),
                    ":pending": "pending",
                    ":fingerprint": token.fingerprint,
                },
                condition="#status=:pending AND fingerprint=:fingerprint",
            )
        )
        actions.append(
            _delete(
                {
                    "PK": f"{_namespace(token.scope, token.owner_id)}#OPS",
                    "SK": f"DIRECT#{operation['coordination_conversation_id']}#"
                    f"{token.operation_id}#{token.attempt_id}",
                }
            )
        )
        self.table.transact(actions)

    def _acknowledge_job(self, token, *, outcome, result_refs):
        job_id = token.coordination_job_id
        if job_id is None:
            raise ConversationConflictError("memory job coordinator missing")
        key = _job_key(token.scope, job_id, token.owner_id)
        item = self.table.get(key)
        pending = None if item is None else item.get("pending_effect")
        acknowledged = None if item is None else item.get("last_effect_ack")
        if (
            pending is None
            and acknowledged is not None
            and all(
                acknowledged.get(field) == value
                for field, value in (
                    ("operation_id", token.operation_id),
                    ("attempt_id", token.attempt_id),
                    ("fingerprint", token.fingerprint),
                    ("outcome", outcome),
                    ("lease_generation", token.lease_generation),
                )
            )
        ):
            return
        if pending is None or any(
            pending.get(field) != value
            for field, value in (
                ("operation_id", token.operation_id),
                ("attempt_id", token.attempt_id),
                ("fingerprint", token.fingerprint),
                ("lease_generation", token.lease_generation),
            )
        ):
            raise ConversationConflictError("memory job effect unavailable")
        refs = json.loads(pending.get("refs", "[]"))
        actions = []
        for conversation_id in sorted({ref["conversation_id"] for ref in refs}):
            meta_key = _conversation_keys(token.scope, UUID(conversation_id), token.owner_id).meta
            actions.append(
                _update(
                    meta_key,
                    "REMOVE effect_guard",
                    names={"#owner": "owner_id"},
                    values={
                        ":owner": token.owner_id,
                        ":operation": token.operation_id,
                        ":attempt": token.attempt_id,
                        ":job": str(job_id),
                    },
                    condition="#owner=:owner AND effect_guard.operation_id=:operation "
                    "AND effect_guard.attempt_id=:attempt AND effect_guard.job_id=:job",
                )
            )
        actions.append(
            _update(
                key,
                "SET #revision=:next,#ack=:ack REMOVE pending_effect",
                names={"#owner": "owner_id", "#revision": "revision", "#ack": "last_effect_ack"},
                values={
                    ":owner": token.owner_id,
                    ":revision": int(item["revision"]),
                    ":next": int(item["revision"]) + 1,
                    ":operation": token.operation_id,
                    ":attempt": token.attempt_id,
                    ":fingerprint": token.fingerprint,
                    ":generation": token.lease_generation,
                    ":ack": {
                        "operation_id": token.operation_id,
                        "attempt_id": token.attempt_id,
                        "fingerprint": token.fingerprint,
                        "lease_generation": token.lease_generation,
                        "outcome": outcome,
                        "execution_deadline": pending["execution_deadline"],
                        "result_refs": result_refs,
                        "acknowledged_at": _timestamp(datetime.now(UTC)),
                    },
                },
                condition="#owner=:owner AND revision=:revision "
                "AND pending_effect.operation_id=:operation "
                "AND pending_effect.attempt_id=:attempt "
                "AND pending_effect.fingerprint=:fingerprint "
                "AND pending_effect.lease_generation=:generation",
            )
        )
        actions.append(
            _delete(
                {
                    "PK": f"{_namespace(token.scope, token.owner_id)}#OPS",
                    "SK": f"JOB#{job_id}",
                }
            )
        )
        try:
            self.table.transact(actions)
        except Exception as error:
            if not _conditional_failure(error):
                raise
            latest = self.table.get(key)
            acknowledged = None if latest is None else latest.get("last_effect_ack")
            if acknowledged is not None and all(
                acknowledged.get(field) == value
                for field, value in (
                    ("operation_id", token.operation_id),
                    ("attempt_id", token.attempt_id),
                    ("fingerprint", token.fingerprint),
                    ("outcome", outcome),
                    ("lease_generation", token.lease_generation),
                )
            ):
                return
            raise

    def pending_operations(
        self, *, owner_id: str, conversation_id: UUID, scope: ApplicationScope, limit: int = 50
    ):
        if not 1 <= limit <= 100:
            raise ValueError("operation_limit_invalid")
        items = self.table.query(
            partition=f"{_namespace(scope, owner_id)}#OPS",
            sort_prefix=f"DIRECT#{conversation_id}#",
            consistent=True,
            deadline=monotonic() + 5,
            limit=limit,
        )
        operations = []
        for pointer in items:
            operation = self.table.get(
                {"PK": pointer["operation_pk"], "SK": pointer["operation_sk"]}
            )
            if (
                operation is not None
                and operation.get("kind") == "memory-effect"
                and operation.get("status") == "pending"
                and _authorized(operation, owner_id, scope)
            ):
                operation["coordination_conversation_id"] = str(conversation_id)
                operations.append(operation)
        return tuple(operations)

    def recover_pending(
        self,
        *,
        owner_id: str,
        conversation_id: UUID,
        scope: ApplicationScope,
        receipts,
        limit: int = 50,
    ) -> int:
        """Resolve every pending D guard by serializing an applied/aborted P receipt."""
        operations = self.pending_operations(
            owner_id=owner_id, conversation_id=conversation_id, scope=scope, limit=limit
        )
        for operation in operations:
            args = {
                "owner_id": owner_id,
                "scope": scope,
                "operation_id": operation["operation_id"],
                "attempt_id": operation["attempt_id"],
            }
            receipt = receipts.get(**args)
            if receipt is None:
                receipt = receipts.abort_if_unresolved(
                    **args,
                    fingerprint=operation["fingerprint"],
                    execution_deadline=_parse_timestamp(operation["execution_deadline"]),
                )
            token = EffectGuardToken(
                owner_id=owner_id,
                operation_id=operation["operation_id"],
                attempt_id=operation["attempt_id"],
                fingerprint=operation["fingerprint"],
                execution_deadline=_parse_timestamp(operation["execution_deadline"]),
                scope=scope,
                coordination_conversation_id=conversation_id,
            )
            self.acknowledge(token, outcome=receipt.outcome, result_refs=receipt.result_refs)
        return len(operations)

    def recover_pending_effects(self, *, owner_id: str, limit: int, receipts) -> int:
        """Reconcile a bounded owner namespace inventory through pending-only pointers."""
        if not 1 <= limit <= 100:
            raise ValueError("operation_limit_invalid")
        namespaces = self.table.query(
            partition="MAINT#NAMESPACES",
            sort_prefix="NS#",
            consistent=True,
            deadline=monotonic() + 10,
            limit=501,
        )
        if len(namespaces) > 500:
            raise StorageUnavailableError("memory effect namespace inventory exceeds bound")
        processed = 0
        for entry in namespaces:
            if entry.get("owner_id") != owner_id:
                continue
            scope = ApplicationScope(
                application_id=entry["application_id"],
                workspace_id=entry["workspace_id"] if entry.get("workspace_id_present") else None,
            )
            pointers = []
            for prefix in ("DIRECT#", "JOB#"):
                pointers.extend(
                    self.table.query(
                        partition=f"{entry['namespace']}#OPS",
                        sort_prefix=prefix,
                        consistent=True,
                        deadline=monotonic() + 10,
                        limit=limit,
                    )
                )
            for pointer in pointers:
                if pointer.get("kind") != "pending-memory-effect" or not _authorized(
                    pointer, owner_id, scope
                ):
                    continue
                if pointer.get("effect_kind") == "job":
                    processed += self.recover_pending_job(
                        owner_id=owner_id,
                        job_id=UUID(pointer["job_id"]),
                        scope=scope,
                        receipts=receipts,
                    )
                elif pointer.get("effect_kind") == "direct":
                    operation = self.table.get(
                        {"PK": pointer["operation_pk"], "SK": pointer["operation_sk"]}
                    )
                    if operation is None or operation.get("status") != "pending":
                        self.table.transact([_delete({"PK": pointer["PK"], "SK": pointer["SK"]})])
                        continue
                    args = {
                        "owner_id": owner_id,
                        "scope": scope,
                        "operation_id": operation["operation_id"],
                        "attempt_id": operation["attempt_id"],
                    }
                    receipt = receipts.get(**args)
                    if receipt is None:
                        receipt = receipts.abort_if_unresolved(
                            **args,
                            fingerprint=operation["fingerprint"],
                            execution_deadline=_parse_timestamp(operation["execution_deadline"]),
                        )
                    token = EffectGuardToken(
                        owner_id=owner_id,
                        operation_id=operation["operation_id"],
                        attempt_id=operation["attempt_id"],
                        fingerprint=operation["fingerprint"],
                        execution_deadline=_parse_timestamp(operation["execution_deadline"]),
                        scope=scope,
                        coordination_conversation_id=UUID(pointer["conversation_id"]),
                    )
                    self.acknowledge(
                        token, outcome=receipt.outcome, result_refs=receipt.result_refs
                    )
                    processed += 1
                if processed >= limit:
                    return processed
        return processed

    def recover_pending_job(
        self, *, owner_id: str, job_id: UUID, scope: ApplicationScope, receipts
    ) -> int:
        """Recover one D job's pending P operation before allowing a new lease."""
        key = _job_key(scope, job_id, owner_id)
        item = self.table.get(key)
        if item is None or not _authorized(item, owner_id, scope):
            raise ResourceNotFoundError("memory job not found")
        pending = item.get("pending_effect")
        if pending is None:
            return 0
        args = {
            "owner_id": owner_id,
            "scope": scope,
            "operation_id": pending["operation_id"],
            "attempt_id": pending["attempt_id"],
        }
        receipt = receipts.get(**args)
        if receipt is None:
            receipt = receipts.abort_if_unresolved(
                **args,
                fingerprint=pending["fingerprint"],
                execution_deadline=_parse_timestamp(pending["execution_deadline"]),
            )
        token = EffectGuardToken(
            owner_id=owner_id,
            operation_id=pending["operation_id"],
            attempt_id=pending["attempt_id"],
            fingerprint=pending["fingerprint"],
            execution_deadline=_parse_timestamp(pending["execution_deadline"]),
            scope=scope,
            coordination_conversation_id=None,
            coordination_job_id=job_id,
            lease_generation=int(pending["lease_generation"]),
        )
        self.acknowledge(token, outcome=receipt.outcome, result_refs=receipt.result_refs)
        return 1
