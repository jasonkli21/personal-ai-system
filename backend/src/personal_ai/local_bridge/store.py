"""Protected POSIX local state, with cross-process serialization and crash fences."""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

try:
    import fcntl
except ImportError:  # Explicit unsupported-platform failure, no file fallback.
    fcntl = None


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(min_length=1, max_length=32768, repr=False)
    refresh_token: str | None = Field(default=None, max_length=32768, repr=False)
    id_token: str = Field(min_length=1, max_length=32768, repr=False)
    scopes: tuple[str, ...] = Field(max_length=32)
    expires_at: int = Field(ge=0, strict=True)
    earliest_refresh_at: int = Field(default=0, ge=0, strict=True)


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    client_id: str = Field(pattern=r"^oaiapp_[A-Za-z0-9_-]{1,193}$", repr=False)
    issuer: str | None = Field(default=None, repr=False)
    subject: str | None = Field(default=None, max_length=200, repr=False)
    account_name: str | None = Field(default=None, max_length=200)
    account_email: str | None = Field(default=None, max_length=320)
    credentials: Credentials | None = Field(default=None, repr=False)
    revision: int = Field(default=0, strict=True, ge=0)
    state: Literal[
        "connected",
        "disconnected",
        "permission_required",
        "reauth",
        "unavailable",
        "configuration_error",
    ] = "disconnected"
    refresh_pending: bool = False
    remote_revocation: Literal["unknown", "confirmed", "unconfirmed"] = "unknown"


class DispatchReceipt(BaseModel):
    """Durable one-send fence and safe reconciliation status."""

    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal[
        "claimed_pre_send", "send_started", "success", "failure", "rejected", "incomplete"
    ]
    origin: str | None = Field(default=None, max_length=512)
    connection_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
    connection_revision: int | None = Field(default=None, strict=True, ge=0)
    created_at: int = Field(ge=0, strict=True)
    updated_at: int = Field(ge=0, strict=True)
    proof_expires_at: int = Field(ge=0, strict=True)
    terminal_at: int | None = Field(default=None, ge=0, strict=True)
    acknowledged_at: int | None = Field(default=None, ge=0, strict=True)
    claim_token: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$", repr=False)


class LocalState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2] = 2
    clock_high_water: int = Field(default=0, strict=True, ge=0)
    host_id: str
    runtime_id: str
    registrations: dict[str, Registration] = Field(default_factory=dict, max_length=32, repr=False)
    receipts: dict[str, DispatchReceipt] = Field(default_factory=dict, max_length=4096)


class LocalStoreError(RuntimeError):
    def __init__(self, code="local_store_unavailable"):
        super().__init__(code)
        self.code = code


class LocalTransaction:
    def __init__(self, store, state):
        self.store, self.state = store, state

    def save(self):
        self.store._write(self.state)


class ProtectedLocalStore:
    """Single directory, local files only. No managed repository implementation.

    Calls must run outside the event loop. The lock stays held across refresh IO;
    an explicit save before IO makes interrupted rotation unsafe to repeat.
    """

    def __init__(self, directory: Path):
        self.directory = directory.absolute()
        if os.name != "posix" or fcntl is None:
            raise LocalStoreError("protected_storage_unsupported")
        if os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB"):
            raise LocalStoreError("managed_runtime_forbidden")
        # Reject symlinked paths rather than resolve them silently.
        for component in (self.directory, *self.directory.parents):
            if component.is_symlink():
                raise LocalStoreError("unsafe_local_store")
            if (component / ".git").exists():
                raise LocalStoreError("local_store_in_repository")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._check(self.directory, directory=True)
        self._pre_send_mutex = threading.Lock()
        self._claim_fds: dict[str, int] = {}
        self._claim_fds_lock = threading.Lock()

    @staticmethod
    def _check(path: Path, *, directory=False):
        info = path.lstat()
        expected = 0o700 if directory else 0o600
        if (
            info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != expected
            or (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)
        ):
            raise LocalStoreError("unsafe_local_store")

    @contextmanager
    def transaction(self):
        self._check(self.directory, directory=True)
        lock_path = self.directory / "runtime.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            self._check(lock_path)
            deadline = time.monotonic() + 10
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise LocalStoreError("local_store_busy") from None
                    time.sleep(0.01)
            path = self.directory / "state.json"
            if path.exists() or path.is_symlink():
                self._check(path)
                file_descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(file_descriptor, "rb") as file:
                    payload = file.read(2 * 1024 * 1024 + 1)
                if len(payload) > 2 * 1024 * 1024:
                    raise LocalStoreError("local_store_capacity")
                try:
                    raw = json.loads(payload)
                    if not isinstance(raw, dict):
                        raise TypeError()
                    migrated = raw.get("schema_version") == 1
                    if migrated:
                        raw = self._migrate_v1(raw)
                    state = LocalState.model_validate(raw)
                    UUID(state.runtime_id)
                    UUID(state.host_id.removeprefix("urn:uuid:"))
                    for connection_id, registration in state.registrations.items():
                        if str(UUID(connection_id)) != registration.connection_id:
                            raise ValueError()
                    if migrated:
                        self._write(state)
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    raise LocalStoreError("local_store_invalid") from None
            else:
                state = LocalState(host_id=f"urn:uuid:{uuid4()}", runtime_id=str(uuid4()))
                self._write(state)
            yield LocalTransaction(self, state)
        finally:
            os.close(descriptor)

    @staticmethod
    def _migrate_v1(raw):
        """Upgrade the only released local schema without weakening old fences."""
        if set(raw) != {
            "schema_version",
            "host_id",
            "runtime_id",
            "registrations",
            "receipts",
        }:
            raise ValueError("local_state_schema_invalid")
        now = int(time.time())
        receipts = {}
        if not isinstance(raw["receipts"], dict):
            raise TypeError("local_receipts_invalid")
        for identity, old in raw["receipts"].items():
            if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{64}", identity):
                raise ValueError("local_receipt_identity_invalid")
            if not isinstance(old, dict):
                raise TypeError("local_receipt_invalid")
            status = old.get("status")
            if status not in {"success", "failure", "rejected", "incomplete"}:
                # Legacy unknown is an external effect that may have happened.
                status = "send_started"
            receipts[identity] = {
                "fingerprint": old.get("fingerprint"),
                "status": status,
                "origin": None,
                "connection_id": None,
                "connection_revision": None,
                "created_at": now,
                "updated_at": now,
                "proof_expires_at": now + 120,
                "terminal_at": now
                if status in {"success", "failure", "rejected", "incomplete"}
                else None,
                "acknowledged_at": None,
                "claim_token": None,
            }
        return {
            **raw,
            "schema_version": 2,
            "clock_high_water": now,
            "receipts": receipts,
        }

    def _write(self, state: LocalState):
        # Revalidate mutations before they become canonical.
        try:
            state = LocalState.model_validate(state.model_dump())
        except ValueError:
            raise LocalStoreError("local_store_invalid") from None
        payload = state.model_dump_json().encode()
        if len(payload) > 2 * 1024 * 1024:
            raise LocalStoreError("local_store_capacity")
        self._check(self.directory, directory=True)
        descriptor, name = tempfile.mkstemp(prefix=".state-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, self.directory / "state.json")
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _acquire_pre_send(self, *, wait: bool):
        acquired = self._pre_send_mutex.acquire(timeout=10 if wait else 0)
        if not acquired:
            return None
        descriptor = None
        try:
            lock_path = self.directory / "dispatch.lock"
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            self._check(lock_path)
            deadline = time.monotonic() + (10 if wait else 0)
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return descriptor
                except BlockingIOError:
                    if not wait or time.monotonic() >= deadline:
                        os.close(descriptor)
                        self._pre_send_mutex.release()
                        return None
                    time.sleep(0.01)
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
            self._pre_send_mutex.release()
            raise

    def _release_pre_send(self, descriptor: int, claim_token: str | None = None):
        if claim_token is not None:
            with self._claim_fds_lock:
                self._claim_fds.pop(claim_token, None)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
            self._pre_send_mutex.release()

    @staticmethod
    def _prune(state: LocalState, now: int) -> int:
        retained_seconds = 86400
        expired = [
            identity
            for identity, receipt in state.receipts.items()
            if receipt.status in {"success", "failure", "rejected", "incomplete"}
            and receipt.proof_expires_at <= now
            and (
                receipt.acknowledged_at is not None
                or (
                    receipt.terminal_at is not None
                    and receipt.terminal_at + retained_seconds <= now
                )
            )
        ]
        for identity in expired:
            del state.receipts[identity]
        return len(expired)

    def maintain(self, *, now: int | None = None) -> int:
        with self.transaction() as tx:
            current = max(tx.state.clock_high_water, int(time.time()) if now is None else now)
            changed = current != tx.state.clock_high_water
            tx.state.clock_high_water = current
            removed = self._prune(tx.state, current)
            if removed or changed:
                tx.save()
            return removed

    def claim(
        self,
        identity: str,
        fingerprint: str,
        connection: str,
        revision: int,
        proof_expires_at: int,
        *,
        origin: str | None = None,
        now: int | None = None,
    ) -> str:
        if not re.fullmatch(r"[a-f0-9]{64}", identity) or not re.fullmatch(
            r"[a-f0-9]{64}", fingerprint
        ):
            raise LocalStoreError("dispatch_identity_invalid")
        descriptor = self._acquire_pre_send(wait=True)
        if descriptor is None:
            raise LocalStoreError("local_store_busy")
        current = int(time.time()) if now is None else now
        token = uuid4().hex
        try:
            with self.transaction() as tx:
                current = max(current, tx.state.clock_high_water)
                if current != tx.state.clock_high_water:
                    tx.state.clock_high_water = current
                    tx.save()
                if current >= proof_expires_at:
                    raise LocalStoreError("dispatch_authority_expired")
                registration = tx.state.registrations.get(connection)
                if (
                    registration is None
                    or registration.revision != revision
                    or registration.state != "connected"
                    or registration.refresh_pending
                ):
                    raise LocalStoreError("connection_changed")
                pruned = self._prune(tx.state, current)
                if pruned:
                    tx.save()
                previous = tx.state.receipts.get(identity)
                if previous is not None:
                    if previous.status == "claimed_pre_send":
                        # Holding the pre-send lock proves no live executor owns it.
                        del tx.state.receipts[identity]
                    else:
                        raise LocalStoreError("dispatch_already_claimed")
                if len(tx.state.receipts) >= 4096:
                    raise LocalStoreError("local_store_capacity")
                tx.state.receipts[identity] = DispatchReceipt(
                    fingerprint=fingerprint,
                    status="claimed_pre_send",
                    origin=origin,
                    connection_id=connection,
                    connection_revision=revision,
                    created_at=current,
                    updated_at=current,
                    proof_expires_at=proof_expires_at,
                    claim_token=token,
                )
                tx.save()
            with self._claim_fds_lock:
                self._claim_fds[token] = descriptor
            return token
        except BaseException:
            self._release_pre_send(descriptor)
            raise

    def mark_send_started(
        self,
        identity: str,
        fingerprint: str,
        connection: str,
        revision: int,
        claim_token: str,
        *,
        expires_at: int,
        now: int,
    ):
        with self._claim_fds_lock:
            descriptor = self._claim_fds.get(claim_token)
        if descriptor is None:
            raise LocalStoreError("dispatch_claim_lost")
        try:
            with self.transaction() as tx:
                receipt = tx.state.receipts.get(identity)
                registration = tx.state.registrations.get(connection)
                if (
                    receipt is None
                    or receipt.status != "claimed_pre_send"
                    or receipt.fingerprint != fingerprint
                    or receipt.claim_token != claim_token
                ):
                    raise LocalStoreError("dispatch_claim_lost")
                current = max(now, tx.state.clock_high_water)
                if current != tx.state.clock_high_water:
                    tx.state.clock_high_water = current
                    tx.save()
                if current >= expires_at:
                    raise LocalStoreError("dispatch_authority_expired")
                if (
                    registration is None
                    or registration.revision != revision
                    or registration.state != "connected"
                    or registration.refresh_pending
                ):
                    raise LocalStoreError("connection_changed")
                receipt.status = "send_started"
                receipt.updated_at = current
                receipt.claim_token = None
                tx.state.clock_high_water = current
                tx.save()
        finally:
            self._release_pre_send(descriptor, claim_token)

    def release_pre_send(self, identity: str, fingerprint: str, claim_token: str):
        with self._claim_fds_lock:
            descriptor = self._claim_fds.get(claim_token)
        if descriptor is None:
            return
        try:
            with self.transaction() as tx:
                receipt = tx.state.receipts.get(identity)
                if (
                    receipt is not None
                    and receipt.status == "claimed_pre_send"
                    and receipt.fingerprint == fingerprint
                    and receipt.claim_token == claim_token
                ):
                    del tx.state.receipts[identity]
                    tx.save()
        finally:
            self._release_pre_send(descriptor, claim_token)

    def settle(self, identity: str, status: str, *, now: int | None = None):
        if status not in {"success", "failure", "rejected", "incomplete"}:
            raise LocalStoreError("dispatch_status_invalid")
        with self.transaction() as tx:
            receipt = tx.state.receipts.get(identity)
            if receipt is None or receipt.status != "send_started":
                raise LocalStoreError("dispatch_already_settled")
            current = max(
                tx.state.clock_high_water,
                int(time.time()) if now is None else now,
            )
            receipt.status = status
            receipt.updated_at = current
            receipt.terminal_at = current
            tx.state.clock_high_water = current
            tx.save()

    def reconcile(
        self,
        identity: str,
        fingerprint: str,
        connection: str,
        revision: int,
        origin: str | None = None,
    ):
        descriptor = self._acquire_pre_send(wait=False)
        locked = descriptor is not None
        try:
            with self.transaction() as tx:
                receipt = tx.state.receipts.get(identity)
                if (
                    receipt is None
                    or receipt.fingerprint != fingerprint
                    or receipt.origin != origin
                    or receipt.connection_id != connection
                    or receipt.connection_revision != revision
                ):
                    raise LocalStoreError("dispatch_receipt_not_found")
                if receipt.status == "claimed_pre_send":
                    if not locked:
                        return "pre_send_active"
                    del tx.state.receipts[identity]
                    tx.save()
                    return "not_sent"
                if receipt.status == "send_started":
                    return "unknown"
                return receipt.status
        finally:
            if locked:
                self._release_pre_send(descriptor)

    def acknowledge(
        self,
        identity: str,
        fingerprint: str,
        connection: str,
        revision: int,
        origin: str | None = None,
        *,
        now=None,
    ):
        with self.transaction() as tx:
            receipt = tx.state.receipts.get(identity)
            if (
                receipt is None
                or receipt.fingerprint != fingerprint
                or receipt.origin != origin
                or receipt.connection_id != connection
                or receipt.connection_revision != revision
                or receipt.status not in {"success", "failure", "rejected", "incomplete"}
            ):
                raise LocalStoreError("dispatch_receipt_not_found")
            current = max(
                tx.state.clock_high_water,
                int(time.time()) if now is None else now,
            )
            receipt.acknowledged_at = current
            receipt.updated_at = current
            tx.state.clock_high_water = current
            tx.save()
