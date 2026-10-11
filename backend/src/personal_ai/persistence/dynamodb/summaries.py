"""DynamoDB working-summary repository."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from time import monotonic
from uuid import UUID

from personal_ai.auth.scope import current_application_scope, scoped_record
from personal_ai.context.contracts import ConversationSummary
from personal_ai.context.repositories import newest_compatible
from personal_ai.entities import Message
from personal_ai.storage.errors import ConversationConflictError, StorageUnavailableError

from ._helpers import (
    MAX_DYNAMO_ITEM_BYTES,
    MAX_SUMMARY_CHUNKS,
    _authorized,
    _chunk_manifest,
    _chunks,
    _conversation_keys,
    _item_size,
    _json,
    _put,
    _scope_of,
    _sequence_hash,
    _timestamp,
)
from .client import DynamoDBRuntimeTable
from .conversations import DynamoDBConversationRepository


class DynamoDBSummaryRepository:
    """Append-only summaries published only after bounded provenance chunks."""

    def __init__(
        self,
        table: DynamoDBRuntimeTable,
        conversations: DynamoDBConversationRepository | None = None,
    ):
        self.table = table
        self.conversations = conversations or DynamoDBConversationRepository(table)

    def create(self, summary: ConversationSummary) -> ConversationSummary:
        summary = scoped_record(summary)
        scope = _scope_of(summary)
        self.conversations.get(owner_id=summary.owner_id, conversation_id=summary.conversation_id)
        source_chunks = _chunks(summary.source_message_ids)
        coverage_is_implicit = not summary.coverage_message_ids
        coverage_chunks = _chunks(summary.coverage_message_ids)
        if len(source_chunks) + len(coverage_chunks) > MAX_SUMMARY_CHUNKS:
            raise StorageUnavailableError("summary provenance bound exceeded")
        keys = _conversation_keys(scope, summary.conversation_id, summary.owner_id)
        source_manifest = _chunk_manifest(source_chunks)
        coverage_manifest = _chunk_manifest(coverage_chunks)
        coverage_manifest["implicit_source"] = coverage_is_implicit
        chunks = []
        for kind, values, manifest in (
            ("source", source_chunks, source_manifest),
            ("coverage", coverage_chunks, coverage_manifest),
        ):
            for sequence, values_chunk in enumerate(values):
                item = {
                    "PK": keys.partition,
                    "SK": f"SC#{summary.id}#{kind}#{sequence:06d}",
                    "owner_id": summary.owner_id,
                    "application_id": scope.application_id,
                    "workspace_id_present": scope.workspace_id is not None,
                    "workspace_id": scope.workspace_id or "",
                    "summary_id": str(summary.id),
                    "kind": kind,
                    "sequence": sequence,
                    "payload": _json([str(identifier) for identifier in values_chunk]),
                    "chunk_sha256": manifest["hashes"][sequence],
                    "published": False,
                }
                if _item_size(item) > MAX_DYNAMO_ITEM_BYTES:
                    raise StorageUnavailableError("summary chunk too large")
                chunks.append(item)
        # Chunks are immutable deterministic staging rows. A failed publication
        # leaves only unreadable chunks; the summary header is the publish point.
        for offset in range(0, len(chunks), 25):
            batch = chunks[offset : offset + 25]
            self._put_chunks_idempotently(batch)
        data = summary.model_dump(mode="json")
        data.pop("source_message_ids")
        data.pop("coverage_message_ids")
        item = {
            "PK": keys.partition,
            "SK": f"SUM#{_timestamp(summary.created_at)}#{summary.id}",
            "kind": "summary",
            "owner_id": summary.owner_id,
            "application_id": scope.application_id,
            "workspace_id_present": scope.workspace_id is not None,
            "workspace_id": scope.workspace_id or "",
            "summary_id": str(summary.id),
            "created_at": _timestamp(summary.created_at),
            "source_manifest": _json(source_manifest),
            "coverage_manifest": _json(coverage_manifest),
            "payload": _json(data),
            "published": True,
        }
        try:
            self.table.transact([_put(item, condition="attribute_not_exists(PK)")])
        except Exception as error:
            existing = self.table.get({"PK": item["PK"], "SK": item["SK"]})
            if existing is None:
                raise
            if any(
                existing.get(field) != item.get(field)
                for field in ("payload", "source_manifest", "coverage_manifest")
            ):
                raise ConversationConflictError("summary identity payload changed") from error
        return summary

    def compatible(self, *, owner_id: str, conversation_id: UUID, active: Sequence[Message]):
        scope = current_application_scope()
        self.conversations.get(owner_id=owner_id, conversation_id=conversation_id)
        deadline = monotonic() + 5
        keys = _conversation_keys(scope, conversation_id, owner_id)
        candidates = self.table.query(
            partition=keys.partition,
            sort_prefix="SUM#",
            consistent=True,
            descending=True,
            deadline=deadline,
            limit=101,
        )
        overflow = len(candidates) > 100
        candidates = candidates[:100]
        summaries = []
        for item in candidates:
            if not item.get("published") or not _authorized(item, owner_id, scope):
                continue
            try:
                summaries.append(self._load(item, keys.partition, deadline))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                raise StorageUnavailableError("summary provenance invalid") from error
        selected = newest_compatible(summaries, active)
        if selected is None and overflow:
            raise StorageUnavailableError("summary compatibility window exceeds bound")
        return selected

    def _load(self, item, partition, deadline):
        source_manifest = json.loads(item["source_manifest"])
        coverage_manifest = json.loads(item["coverage_manifest"])
        if source_manifest["chunks"] + coverage_manifest["chunks"] > MAX_SUMMARY_CHUNKS:
            raise StorageUnavailableError("summary chunk manifest invalid")
        source = self._load_manifest(
            partition, item["summary_id"], "source", source_manifest, deadline
        )
        coverage = (
            ()
            if coverage_manifest.get("implicit_source")
            else self._load_manifest(
                partition, item["summary_id"], "coverage", coverage_manifest, deadline
            )
        )
        payload = json.loads(item["payload"])
        return ConversationSummary.model_validate(
            {
                **payload,
                "source_message_ids": source,
                "coverage_message_ids": coverage,
            }
        )

    def _load_manifest(self, partition, summary_id, kind, manifest, deadline):
        if manifest["chunks"] > MAX_SUMMARY_CHUNKS:
            raise StorageUnavailableError("summary chunk manifest invalid")
        chunks = self.table.query(
            partition=partition,
            sort_prefix=f"SC#{summary_id}#{kind}#",
            consistent=True,
            deadline=deadline,
            limit=manifest["chunks"],
        )
        values = []
        hashes = []
        for expected, item in enumerate(chunks):
            if item.get("sequence") != expected or item.get("kind") != kind:
                raise StorageUnavailableError("summary chunk sequence invalid")
            chunk = json.loads(item["payload"])
            actual_hash = hashlib.sha256(_json(chunk).encode()).hexdigest()
            if (
                actual_hash != item.get("chunk_sha256")
                or actual_hash != manifest["hashes"][expected]
            ):
                raise StorageUnavailableError("summary chunk hash invalid")
            values.extend(UUID(identifier) for identifier in chunk)
            hashes.append(actual_hash)
        if len(chunks) != manifest["chunks"] or len(values) != manifest["count"]:
            raise StorageUnavailableError("summary chunk count invalid")
        if _sequence_hash(values) != manifest["sha256"]:
            raise StorageUnavailableError("summary provenance hash invalid")
        return tuple(values)

    def _put_chunks_idempotently(self, items):
        if not items:
            return
        partition = items[0]["PK"]
        summary_id = items[0]["summary_id"]
        existing = self.table.query(
            partition=partition,
            sort_prefix=f"SC#{summary_id}#",
            consistent=True,
            deadline=monotonic() + 5,
            limit=MAX_SUMMARY_CHUNKS + 1,
        )
        if len(existing) > MAX_SUMMARY_CHUNKS:
            raise StorageUnavailableError("summary staging exceeds bound")
        existing_by_key = {entry["SK"]: entry for entry in existing}
        missing = []
        for item in items:
            current = existing_by_key.get(item["SK"])
            if current is None:
                missing.append(item)
            elif current.get("chunk_sha256") != item["chunk_sha256"]:
                raise ConversationConflictError("summary chunk identity conflict")
        for offset in range(0, len(missing), 25):
            batch = missing[offset : offset + 25]
            try:
                self.table.transact(
                    [_put(item, condition="attribute_not_exists(PK)") for item in batch]
                )
            except Exception as error:
                for item in batch:
                    current = self.table.get({"PK": item["PK"], "SK": item["SK"]})
                    if current is None or current.get("chunk_sha256") != item["chunk_sha256"]:
                        raise ConversationConflictError(
                            "summary chunk identity conflict"
                        ) from error
