"""Opt-in, process-local observations. The usage ledger remains authoritative."""

import json
import os
import re
from collections import Counter, deque
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from hmac import digest
from threading import Lock
from uuid import UUID

from personal_ai.usage.context import resolve_execution_context


class Event(StrEnum):
    CONTEXT = "context"
    SOURCE = "source_check"
    COUNT = "count"
    ENDPOINT = "endpoint_check"
    ADMISSION = "admission"
    RESERVE = "reserve"
    DISPATCH = "dispatch"
    OUTPUT = "output"
    SETTLE = "settle"


class State(StrEnum):
    OK = "ok"
    DENIED = "denied"
    FAILED = "failed"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"


class Reason(StrEnum):
    ENDPOINT_POLICY = "endpoint_policy"
    ENDPOINT_IDENTITY = "endpoint_identity"
    SOURCE_AUTHORITY = "source_authority"
    SOURCE_SCOPE = "source_scope"
    SLOT_BUSY = "slot_busy"
    QUOTA = "quota"
    ACCOUNTING = "accounting"


_active = ContextVar("inference_trace", default=None)


class Trace:
    def __init__(self, capacity=2048):
        if not 1 <= capacity <= 8192:
            raise ValueError("trace_capacity_invalid")
        self._events = deque(maxlen=capacity)
        self._key = os.urandom(32)
        self._lock = Lock()
        self._sequence = 0

    @contextmanager
    def capture(self):
        binding = _active.set(self)
        try:
            yield self
        finally:
            _active.reset(binding)

    def _ref(self, value):
        return digest(self._key, value.encode(), sha256).hex()[:32]

    def request_ref(self, request_id):
        return self._ref(str(request_id))

    def record(
        self, event, state, *, invocation=None, attempt=None, operation=None,
        input_tokens=None, output_tokens=None, elapsed_ms=None, source_count=None,
        source_refs=(), units=None, work_bytes=None, cost=None, reason=None,
    ):
        scope = resolve_execution_context(event.value)
        entry = {
            "version": 1, "event": Event(event).value, "state": State(state).value,
            "timestamp": datetime.now(UTC).isoformat(),
            "request": self._ref(scope.request_id),
            "task": self._ref(scope.task_id),
        }
        if reason is not None:
            entry["reason"] = Reason(reason).value
        if scope.run_id:
            entry["run"] = self._ref(scope.run_id)
        if invocation is not None:
            entry["invocation"] = str(UUID(str(invocation.invocation_id)))
            entry["endpoint"] = self._ref(invocation.endpoint.endpoint_profile_id)
            entry["endpoint_version"] = invocation.endpoint.profile_version
        if attempt is not None:
            entry["attempt"] = str(UUID(str(attempt.attempt_id)))
        if operation in {"token_counting", "streaming", "bounded_generation", "structured_generation"}:
            entry["operation"] = operation
        if units in {"reserved", "reported", "estimated", "unknown", "fake_bytes", "selected_budget"}:
            entry["units"] = units
        if cost in {"local_no_provider_charge", "unknown"}:
            entry["cost"] = cost
        for name, value in (
            ("input_tokens", input_tokens), ("output_tokens", output_tokens),
            ("elapsed_ms", elapsed_ms), ("source_count", source_count),
            ("work_bytes", work_bytes),
        ):
            if type(value) is int and 0 <= value <= 2**53:
                entry[name] = value
        if source_refs:
            entry["sources"] = tuple(
                self._ref(str(ref)) for ref in source_refs[:32]
                if isinstance(ref, UUID) or isinstance(ref, str) and len(ref) <= 200
            )
        with self._lock:
            self._sequence += 1
            entry["sequence"] = self._sequence
            self._events.append(entry)

    def snapshot(self):
        with self._lock:
            return tuple(dict(event) for event in self._events), self._sequence - len(self._events)

    def export(self, filename, *, commit, configuration, run_id):
        """Write a private JSONL receipt in the current working directory."""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}\.jsonl", filename):
            raise ValueError("trace_export_requires_new_jsonl_basename")
        if not re.fullmatch(r"[0-9a-f]{40,64}", commit) or not re.fullmatch(
            r"[0-9a-f]{64}", configuration
        ):
            raise ValueError("trace_manifest_identity_invalid")
        events, dropped = self.snapshot()
        counts = Counter(f"{event['event']}/{event['state']}" for event in events)
        summary = ", ".join(f"{key} {count}" for key, count in sorted(counts.items()))
        manifest = {
            "version": 1, "event": "manifest", "commit": commit,
            "configuration": configuration, "run_id": str(UUID(str(run_id))),
            "retained": len(events), "dropped": dropped, "summary": summary,
        }
        payload = "\n".join(json.dumps(row, sort_keys=True) for row in (manifest, *events)) + "\n"
        temporary = f".{filename}.{os.urandom(12).hex()}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            # A same-directory hard link publishes atomically and fails if the
            # destination already exists, including when it is a symlink.
            os.link(temporary, filename, follow_symlinks=False)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        os.unlink(temporary)
        return summary


def emit(event, state, **facts):
    trace = _active.get()
    if trace is not None:
        try:
            trace.record(event, state, **facts)
        except Exception:  # noqa: BLE001, S110 - observations never authorize or block a send
            pass
