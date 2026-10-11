"""DynamoDB memory lifecycle job repository."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4

from personal_ai.auth.scope import ApplicationScope, current_application_scope, scoped_record
from personal_ai.storage.errors import ResourceNotFoundError, StorageUnavailableError

from ._helpers import (
    _authorized,
    _conditional_failure,
    _job_catalog_item,
    _job_id_locator,
    _job_item,
    _job_key,
    _marshal,
    _namespace_puts,
    _owner_job_catalog_item,
    _put,
    _same_job_intent,
    _scope_of,
    _timestamp,
    _unmarshal,
    _update,
    _utc,
)
from .client import DynamoDBRuntimeTable


class DynamoDBMemoryJobRepository:
    """Fenced lifecycle execution jobs with one sparse, eventual publication GSI."""

    def __init__(self, table: DynamoDBRuntimeTable) -> None:
        self.table = table

    def create_job(self, job):
        from personal_ai.memory.lifecycle import MemoryJob
        from personal_ai.memory.lifecycle.repositories import job_idempotency_id

        job = scoped_record(job)
        if job.id != job_idempotency_id(job.idempotency_key, job.application_id, job.workspace_id):
            raise ValueError("job_identity_invalid")
        scope = _scope_of(job)
        key = _job_key(scope, job.id, job.owner_id)
        existing = self.table.get(key)
        if existing is not None:
            current = MemoryJob.model_validate(json.loads(existing["payload"]))
            if not _authorized(existing, job.owner_id, scope):
                raise ResourceNotFoundError("memory job not found")
            if _same_job_intent(current, job):
                return current, False
            raise ValueError("idempotency_key_reused")
        item = _job_item(job, revision=1)
        catalog = _job_catalog_item(job, scope)
        owner_catalog = _owner_job_catalog_item(job, scope)
        locator = _job_id_locator(job, scope)
        operations = [
            _put(item, condition="attribute_not_exists(PK)"),
            _put(catalog, condition="attribute_not_exists(PK)"),
            _put(owner_catalog, condition="attribute_not_exists(PK)"),
            _put(locator, condition="attribute_not_exists(PK)"),
            *_namespace_puts(self.table, job.owner_id, scope),
        ]
        try:
            self.table.transact(operations)
        except Exception as error:
            existing = self.table.get(key)
            if existing is not None:
                current = MemoryJob.model_validate(json.loads(existing["payload"]))
                if _same_job_intent(current, job):
                    return current, False
                raise ValueError("idempotency_key_reused") from error
            raise
        return job, True

    def get_job(self, *, owner_id: str, job_id: UUID):
        scope = current_application_scope()
        return self._read_job(owner_id, job_id, scope)

    def get_job_by_id(self, *, job_id: UUID, scope: ApplicationScope | None = None):
        from personal_ai.memory.lifecycle import MemoryJob

        scope = scope or current_application_scope()
        locator = self.table.get({"PK": f"JOBID#{job_id}", "SK": "LOCATOR"})
        if locator is None or not _authorized(locator, locator.get("owner_id", ""), scope):
            raise ResourceNotFoundError("memory job not found")
        item = self.table.get({"PK": locator["record_pk"], "SK": locator["record_sk"]})
        if item is None or not _authorized(item, locator["owner_id"], scope):
            raise ResourceNotFoundError("memory job not found")
        try:
            return MemoryJob.model_validate(json.loads(item["payload"]))
        except (ValueError, TypeError, KeyError) as error:
            raise StorageUnavailableError("memory job invalid") from error

    def claim_job(self, *, owner_id: str, job_id: UUID, now: datetime, lease_seconds: int):

        scope = current_application_scope()
        item = self.table.get(_job_key(scope, job_id, owner_id))
        job = self._decode_job(item, owner_id, scope)
        if item.get("pending_effect") is not None:
            # Recovery must settle the P receipt before any newer generation can
            # replace the job token or act on these source conversations.
            return None
        now = _utc(now)
        if job.status in {"completed", "terminal"}:
            return None
        if job.status == "leased" and job.lease_expires_at and job.lease_expires_at > now:
            return None
        if job.next_attempt_at and job.next_attempt_at > now:
            return None
        revision = int(item["revision"])
        if job.attempt_count >= job.max_attempts:
            terminal = job.model_copy(
                update={
                    "status": "terminal",
                    "retry_reason": "attempts_exhausted",
                    "updated_at": now,
                }
            )
            self._save_job(item, terminal, revision, remove_publication=True)
            return None
        claimed = job.model_copy(
            update={
                "status": "leased",
                "attempt_count": job.attempt_count + 1,
                "lease_expires_at": now + timedelta(seconds=lease_seconds),
                "lease_token": uuid4(),
                "lease_generation": job.lease_generation + 1,
                "publish_pending": False,
                "updated_at": now,
            }
        )
        self._save_job(item, claimed, revision, remove_publication=True)
        return claimed

    def complete_job(self, job, *, token: UUID, now: datetime):
        return self._mutate_fenced(
            job,
            token,
            now,
            {
                "status": "completed",
                "lease_expires_at": None,
                "lease_token": None,
                "retry_reason": None,
                "publish_pending": False,
            },
        )

    def fail_job(self, job, *, token: UUID, now: datetime, reason: str, retryable: bool):
        now = _utc(now)
        retry = retryable and job.attempt_count < job.max_attempts
        delay = min(300, 2 ** max(0, job.attempt_count - 1))
        return self._mutate_fenced(
            job,
            token,
            now,
            {
                "status": "retry" if retry else "terminal",
                "retry_reason": reason[:100],
                "next_attempt_at": now + timedelta(seconds=delay) if retry else None,
                "lease_expires_at": None,
                "lease_token": None,
                "publish_pending": retry,
            },
        )

    def mark_published(self, *, owner_id: str, job_id: UUID, updated_at: datetime):
        scope = current_application_scope()
        item = self.table.get(_job_key(scope, job_id, owner_id))
        job = self._decode_job(item, owner_id, scope)
        if job.status not in {"pending", "retry"} or job.updated_at != _utc(updated_at):
            return job
        return self._save_job(
            item,
            job.model_copy(update={"publish_pending": False, "updated_at": _utc(updated_at)}),
            int(item["revision"]),
            remove_publication=True,
        )

    def pending_for_publish(self, *, now: datetime, limit: int = 50):
        if not 1 <= limit <= 100:
            raise ValueError("job_limit_invalid")
        now = _utc(now)
        candidates = []
        namespaces = self.table.query(
            partition="MAINT#NAMESPACES",
            sort_prefix="NS#",
            consistent=True,
            deadline=monotonic() + 10,
            limit=501,
        )
        if len(namespaces) > 500:
            raise StorageUnavailableError("memory job namespace inventory exceeds bound")
        inspected = 0
        for namespace_item in namespaces:
            scope = ApplicationScope(
                application_id=namespace_item["application_id"],
                workspace_id=(
                    namespace_item["workspace_id"]
                    if namespace_item.get("workspace_id_present")
                    else None
                ),
            )
            namespace = namespace_item["namespace"]
            for status in ("pending", "retry"):
                partition = f"PUB#{namespace}#{status}"
                cursor = None
                eligible_for_partition = 0
                reads = 0
                while eligible_for_partition < limit and reads < 1000:
                    request = {
                        "TableName": self.table.table_name,
                        "IndexName": "job-publication-v1",
                        "KeyConditionExpression": "#pk=:pk",
                        "ExpressionAttributeNames": {"#pk": "PUBPK"},
                        "ExpressionAttributeValues": _marshal({":pk": partition}),
                        "ScanIndexForward": True,
                        "Limit": min(100, 1000 - reads),
                    }
                    if cursor:
                        request["ExclusiveStartKey"] = _marshal(cursor)
                    page = self.table.client.query(**request)
                    indexed_items = [_unmarshal(value) for value in page.get("Items", ())]
                    reads += len(indexed_items)
                    inspected += len(indexed_items)
                    if inspected > 10_000:
                        raise StorageUnavailableError("memory job publication scan bound exceeded")
                    for indexed in indexed_items:
                        canonical = self.table.get(
                            {"PK": indexed["record_pk"], "SK": indexed["record_sk"]}
                        )
                        if canonical is None:
                            raise StorageUnavailableError("memory job publication locator invalid")
                        job = self._decode_job(canonical, namespace_item["owner_id"], scope)
                        if (
                            canonical.get("status") == status
                            and job.publish_pending
                            and (job.next_attempt_at is None or job.next_attempt_at <= now)
                        ):
                            candidates.append(job)
                            eligible_for_partition += 1
                            if eligible_for_partition == limit:
                                break
                    cursor = (
                        _unmarshal(page["LastEvaluatedKey"])
                        if page.get("LastEvaluatedKey")
                        else None
                    )
                    if not cursor:
                        break
                if cursor and reads >= 1000 and eligible_for_partition < limit:
                    raise StorageUnavailableError("memory job publication window exceeds bound")
        return tuple(sorted(candidates, key=lambda item: (item.created_at, str(item.id)))[:limit])

    def _read_job(self, owner_id, job_id, scope):
        item = self.table.get(_job_key(scope, job_id, owner_id))
        return self._decode_job(item, owner_id, scope)

    @staticmethod
    def _decode_job(item, owner_id, scope):
        from personal_ai.memory.lifecycle import MemoryJob

        if item is None or not _authorized(item, owner_id, scope):
            raise ResourceNotFoundError("memory job not found")
        try:
            return MemoryJob.model_validate(json.loads(item["payload"]))
        except (ValueError, TypeError, KeyError) as error:
            raise StorageUnavailableError("memory job invalid") from error

    def _save_job(self, item, updated, revision, *, remove_publication):
        job_item = _job_item(updated, revision=revision + 1)
        sets = ["#payload=:payload", "#status=:status", "#revision=:next", "#updated=:updated"]
        removes = []
        names = {
            "#payload": "payload",
            "#status": "status",
            "#revision": "revision",
            "#updated": "updated_at",
            "#owner": "owner_id",
        }
        values = {
            ":payload": job_item["payload"],
            ":status": updated.status,
            ":next": revision + 1,
            ":updated": _timestamp(updated.updated_at),
            ":revision": revision,
            ":owner": updated.owner_id,
        }
        if updated.status == "leased":
            sets.extend(
                [
                    "#lease_token=:lease_token",
                    "#lease_generation=:lease_generation",
                    "#lease_expires=:lease_expires",
                ]
            )
            names.update(
                {
                    "#lease_token": "lease_token",
                    "#lease_generation": "lease_generation",
                    "#lease_expires": "lease_expires_at",
                }
            )
            values.update(
                {
                    ":lease_token": str(updated.lease_token),
                    ":lease_generation": updated.lease_generation,
                    ":lease_expires": _timestamp(updated.lease_expires_at),
                }
            )
        else:
            removes.extend(["lease_token", "lease_generation", "lease_expires_at"])
        if job_item.get("PUBPK"):
            sets.extend(
                [
                    "PUBPK=:pubpk",
                    "PUBSK=:pubsk",
                    "record_pk=:recordpk",
                    "record_sk=:recordsk",
                    "publish_after=:after",
                ]
            )
        else:
            removes.extend(["PUBPK", "PUBSK", "record_pk", "record_sk", "publish_after"])
        sets.append("job_id=:jobid")
        values[":jobid"] = str(updated.id)
        if job_item.get("PUBPK"):
            values.update(
                {
                    ":pubpk": job_item["PUBPK"],
                    ":pubsk": job_item["PUBSK"],
                    ":recordpk": job_item["record_pk"],
                    ":recordsk": job_item["record_sk"],
                    ":after": job_item["publish_after"],
                }
            )
        expression = "SET " + ",".join(sets)
        if removes:
            expression += " REMOVE " + ",".join(removes)
        try:
            self.table.transact(
                [
                    _update(
                        {"PK": item["PK"], "SK": item["SK"]},
                        expression,
                        names=names,
                        values=values,
                        condition="#owner=:owner AND revision=:revision AND attribute_not_exists(pending_effect)",
                    )
                ]
            )
        except Exception as error:
            if _conditional_failure(error):
                return False
            raise
        return updated

    def _mutate_fenced(self, job, token, now, changes):

        scope = _scope_of(job)
        item = self.table.get(_job_key(scope, job.id, job.owner_id))
        current = self._decode_job(item, job.owner_id, scope)
        now = _utc(now)
        if (
            item.get("pending_effect") is not None
            or current.status != "leased"
            or current.lease_token != token
            or current.lease_generation != job.lease_generation
            or current.lease_expires_at is None
            or current.lease_expires_at <= now
        ):
            return False
        updated = current.model_copy(update={**changes, "updated_at": now})
        return self._save_job(item, updated, int(item["revision"]), remove_publication=True)
