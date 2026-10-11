"""DynamoDB bounded context-trace repository."""

from __future__ import annotations

import json
from time import monotonic
from uuid import UUID

from personal_ai.auth.scope import ApplicationScope
from personal_ai.context.traces import (
    MAX_CONTEXT_TRACE_BYTES,
    MAX_CONTEXT_TRACE_RETENTION,
    ContextTraceManifest,
    UnsupportedContextTraceSchemaError,
)
from personal_ai.storage.errors import ResourceNotFoundError, StorageUnavailableError

from ._helpers import (
    _authorized,
    _check_context_trace_deadline,
    _conditional_failure,
    _conversation_keys_for,
    _delete,
    _put,
    _timestamp,
    _update,
)
from .client import DynamoDBRuntimeTable


class DynamoDBContextTraceRepository:
    """Compact actual-build manifests in the scoped conversation partition."""

    def __init__(self, table: DynamoDBRuntimeTable) -> None:
        self.table = table

    def put(
        self,
        *,
        owner_id: str,
        trace: ContextTraceManifest,
        deadline: float | None = None,
    ) -> None:
        try:
            scope = ApplicationScope(
                application_id=trace.application_id,
                workspace_id=trace.workspace_id,
            )
            keys = _conversation_keys_for(owner_id, scope, trace.conversation_id)
            _check_context_trace_deadline(deadline)
            conversation = self.table.get(keys.meta)
            _check_context_trace_deadline(deadline)
            if conversation is None or not _authorized(conversation, owner_id, scope):
                raise ResourceNotFoundError("resource not found")
            payload = trace.model_dump_json()
            if len(payload.encode("utf-8")) > MAX_CONTEXT_TRACE_BYTES:
                raise StorageUnavailableError("context trace exceeds size limit")
            state_key = {"PK": keys.partition, "SK": "CTX_STATE"}
            item = {
                "PK": keys.partition,
                "SK": f"CTX#{_timestamp(trace.recorded_at)}#{trace.assistant_message_id}",
                "kind": "context-trace",
                "owner_id": owner_id,
                "application_id": scope.application_id,
                "workspace_id_present": scope.workspace_id is not None,
                "workspace_id": scope.workspace_id or "",
                "conversation_id": str(trace.conversation_id),
                "user_message_id": str(trace.user_message_id),
                "assistant_message_id": str(trace.assistant_message_id),
                "request_id": trace.request_id,
                "recorded_at": _timestamp(trace.recorded_at),
                "payload": payload,
            }
            for attempt in range(3):
                _check_context_trace_deadline(deadline)
                state = self.table.get(state_key)
                _check_context_trace_deadline(deadline)
                if state is not None and not _authorized(state, owner_id, scope):
                    raise StorageUnavailableError("context trace state scope mismatch")
                previous_sequence = int(state.get("sequence", 0)) if state else 0
                sequence = previous_sequence + 1
                if sequence > MAX_CONTEXT_TRACE_RETENTION:
                    retained = self.table.query(
                        partition=keys.partition,
                        sort_prefix="CTX#",
                        consistent=True,
                        descending=False,
                        deadline=min(deadline, monotonic() + 5)
                        if deadline is not None
                        else monotonic() + 5,
                        limit=MAX_CONTEXT_TRACE_RETENTION,
                    )
                    obsolete = next(
                        (
                            row
                            for row in retained
                            if int(row.get("sequence", -1))
                            == sequence - MAX_CONTEXT_TRACE_RETENTION
                        ),
                        None,
                    )
                else:
                    obsolete = None
                if state is None:
                    next_state = {
                        **state_key,
                        "kind": "context-trace-state",
                        "owner_id": owner_id,
                        "application_id": scope.application_id,
                        "workspace_id_present": scope.workspace_id is not None,
                        "workspace_id": scope.workspace_id or "",
                        "sequence": sequence,
                    }
                    operations = [_put(next_state, condition="attribute_not_exists(PK)")]
                else:
                    operations = [
                        _update(
                            state_key,
                            "SET #sequence = :next",
                            names={"#sequence": "sequence"},
                            values={":next": sequence, ":previous": previous_sequence},
                            condition="#sequence = :previous",
                        )
                    ]
                item["sequence"] = sequence
                operations.append(_put(item, condition="attribute_not_exists(PK)"))
                if obsolete is not None:
                    operations.append(_delete({"PK": obsolete["PK"], "SK": obsolete["SK"]}))
                try:
                    _check_context_trace_deadline(deadline)
                    self.table.transact(operations)
                    _check_context_trace_deadline(deadline)
                    return
                except Exception as error:
                    if not _conditional_failure(error) or attempt == 2:
                        raise
            raise StorageUnavailableError("context trace write conflict")
        except (ResourceNotFoundError, StorageUnavailableError):
            raise
        except TimeoutError:
            raise
        except Exception as error:
            raise StorageUnavailableError("context trace persistence unavailable") from error

    def latest_for_user_turn(
        self,
        *,
        owner_id: str,
        scope: ApplicationScope,
        conversation_id: UUID,
        user_message_id: UUID,
    ) -> ContextTraceManifest | None:
        keys = _conversation_keys_for(owner_id, scope, conversation_id)
        try:
            items = self.table.query(
                partition=keys.partition,
                sort_prefix="CTX#",
                consistent=True,
                descending=True,
                deadline=monotonic() + 5,
                limit=MAX_CONTEXT_TRACE_RETENTION,
            )
            latest: ContextTraceManifest | None = None
            latest_sequence = -1
            latest_unsupported_sequence = -1
            for item in items:
                if not _authorized(item, owner_id, scope):
                    raise ResourceNotFoundError("resource not found")
                if item.get("conversation_id") != str(conversation_id) or item.get(
                    "user_message_id"
                ) != str(user_message_id):
                    continue
                sequence = int(item.get("sequence", -1))
                payload = json.loads(item["payload"])
                if not isinstance(payload, dict):
                    raise StorageUnavailableError("context trace payload invalid")
                if payload.get("schema_version") != "context-trace-v1":
                    latest_unsupported_sequence = max(latest_unsupported_sequence, sequence)
                    continue
                trace = ContextTraceManifest.model_validate(payload)
                if (
                    trace.conversation_id != conversation_id
                    or trace.user_message_id != user_message_id
                    or trace.assistant_message_id != UUID(item["assistant_message_id"])
                    or trace.request_id != item.get("request_id")
                    or trace.application_id != scope.application_id
                    or trace.workspace_id != scope.workspace_id
                ):
                    raise StorageUnavailableError("context trace identity mismatch")
                if sequence > latest_sequence:
                    latest = trace
                    latest_sequence = sequence
            if latest_unsupported_sequence > latest_sequence:
                raise UnsupportedContextTraceSchemaError("unsupported_context_trace_schema")
            return latest
        except UnsupportedContextTraceSchemaError:
            raise
        except (ResourceNotFoundError, StorageUnavailableError):
            raise
        except Exception as error:
            raise StorageUnavailableError("context trace lookup unavailable") from error
