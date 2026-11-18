"""Two explicit owner actions for the in-process synthetic snapshot fixture."""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from uuid import uuid4

from .client import Intent, TurnBudget
from .wire import SCHEMA, Message, Projection, ProtocolError, digest

COPY_WARNING = "The recipient can keep a copied snapshot after expiry or revocation."


@dataclass(frozen=True)
class Selection:
    source_id: str
    grant_id: str
    record_ref: str
    revision: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotIntent:
    recipient: str
    purpose: str
    selections: tuple[Selection, ...]


class SnapshotDependency(Message):
    grant_id: str
    grant_epoch: int
    grant_revision: int
    installation_epoch: int
    application_id: str
    workspace_id: str


class SnapshotRecord(Message):
    source_id: str
    record_ref: str
    source_revision: str
    record_kind: str
    content_projection: dict[str, str | int]
    dependency: SnapshotDependency


class Snapshot(Message):
    schema_version: str = SCHEMA
    snapshot_id: str
    recipient: str
    purpose: str
    created_at: datetime
    expires_at: datetime
    records: tuple[SnapshotRecord, ...]


@dataclass(frozen=True)
class Preview:
    snapshot_id: str
    digest: str
    expires_at: datetime
    warning: str
    redacted_records: tuple[SnapshotRecord, ...]


@dataclass(frozen=True)
class Receipt:
    event: str
    record_count: int


@dataclass(frozen=True)
class Pending:
    actor_key: tuple
    intent: SnapshotIntent
    snapshot: Snapshot
    digest: str


def _snapshot_record(result):
    record: Projection = result.value
    grant = result.grant
    return SnapshotRecord(
        source_id=record.source_id, record_ref=record.record_ref,
        source_revision=record.source_revision, record_kind=record.record_kind,
        content_projection=dict(record.content_projection),
        dependency=SnapshotDependency(
            grant_id=grant.id, grant_epoch=grant.epoch, grant_revision=grant.version,
            installation_epoch=result.install.epoch,
            application_id=record.application_id, workspace_id=record.workspace_id,
        ),
    )


class SnapshotActions:
    def __init__(self, client, clock, counter, caller):
        self.client = client
        self.clock = clock
        self.counter = counter
        self.caller = caller
        self.receipts = []
        self._pending = {}
        self._lock = Lock()

    def _actor_key(self, principal, scope):
        if scope != self.client.authority.scope(
            principal, scope.application_id, scope.workspace_id, scope.request_id,
        ):
            raise ProtocolError("unavailable")
        return (
            principal.issuer, principal.subject, scope.owner_id, scope.acting_user_id,
            scope.application_id, scope.workspace_id,
        )

    def _prepare(self, principal, scope, intent, deadline):
        if (
            intent.recipient != "manual-chatgpt" or not 1 <= len(intent.selections) <= 10
            or len({(item.source_id, item.record_ref) for item in intent.selections})
            != len(intent.selections)
        ):
            raise ProtocolError("unavailable")
        budget = TurnBudget(deadline, self.counter)
        results = tuple(
            self.client.read(
                "fetch", principal, scope,
                Intent(item.source_id, item.grant_id, intent.recipient, intent.purpose, item.fields),
                budget, caller=self.caller, record_ref=item.record_ref, source_revision=item.revision,
            )
            for item in intent.selections
        )
        # Commit no output until every result has passed its final dependency check.
        for result in results:
            self.client.revalidate(result, principal, scope, self.caller)
        budget.check()
        dependencies = tuple(
            (
                hashlib.sha256(result.raw).hexdigest(), result.policy,
                result.grant.dependency_version, result.grant.expires_at.isoformat(),
                result.install.revision, result.install.expires_at.isoformat(),
                result.expires_at.isoformat(),
            )
            for result in results
        )
        return (
            min(result.expires_at for result in results),
            tuple(map(_snapshot_record, results)), dependencies, budget,
        )

    @staticmethod
    def _digest(actor_key, intent, snapshot, dependencies):
        return digest({
            "actor": actor_key, "snapshot": snapshot.model_dump(mode="json"),
            "dependencies": dependencies,
            "selections": [(item.source_id, item.grant_id, item.record_ref, item.revision,
                            item.fields) for item in intent.selections],
        })

    def preview(self, principal, scope, intent, *, deadline):
        actor_key = self._actor_key(principal, scope)
        expires, records, dependencies, budget = self._prepare(principal, scope, intent, deadline)
        snapshot = Snapshot(
            snapshot_id=f"snap-{uuid4().hex}", recipient=intent.recipient, purpose=intent.purpose,
            created_at=self.clock(), expires_at=expires, records=records,
        )
        approval_digest = self._digest(actor_key, intent, snapshot, dependencies)
        with self._lock:
            budget.check()
            self._pending = {key: value for key, value in self._pending.items()
                             if value.snapshot.expires_at > self.clock()}
            if len(self._pending) >= 64 or self.clock() >= expires:
                raise ProtocolError("unavailable")
            self._pending[snapshot.snapshot_id] = Pending(actor_key, intent, snapshot, approval_digest)
        return Preview(snapshot.snapshot_id, approval_digest, expires, COPY_WARNING,
                       tuple(record.model_copy(deep=True) for record in records))

    def confirm(self, principal, scope, intent, snapshot_id, approval_digest, *, deadline):
        actor_key = self._actor_key(principal, scope)
        with self._lock:
            pending = self._pending.get(snapshot_id)
            if pending is None or pending.actor_key != actor_key:
                raise ProtocolError("unavailable")
            del self._pending[snapshot_id]
        if (
            type(approval_digest) is not str or not approval_digest.isascii()
            or not hmac.compare_digest(pending.digest, approval_digest)
            or pending.intent != intent or self.clock() >= pending.snapshot.expires_at
        ):
            raise ProtocolError("unavailable")
        expires, records, dependencies, budget = self._prepare(principal, scope, intent, deadline)
        snapshot = pending.snapshot.model_copy(update={"expires_at": expires, "records": records})
        if self._digest(actor_key, intent, snapshot, dependencies) != pending.digest:
            raise ProtocolError("stale_dependency")
        budget.check()
        if self.clock() >= expires:
            raise ProtocolError("stale_dependency")
        self.receipts.append(Receipt("synthetic_snapshot_confirmed", len(records)))
        return snapshot
