"""Per-operation offline information handling effect observation and loopback-only Python fence."""

from __future__ import annotations

import sys
from contextvars import ContextVar
from dataclasses import dataclass, field

EVENTS = (
    "model_dispatch",
    "external_send",
    "write_tool",
    "stale_disclosure",
    "auth_denial",
    "memory_read",
    "memory_denial",
    "memory_mutation",
    "audit_overflow",
)
FORBIDDEN = ("external_send", "write_tool", "stale_disclosure")
_CURRENT: ContextVar[EffectAudit | None] = ContextVar("offline_information_handling_effect_audit", default=None)


@dataclass
class EffectAudit:
    """Bounded, content-free counts observed at fake ports and HTTP responses."""

    maximum_events: int = 64
    counts: dict[str, int] = field(default_factory=lambda: {event: 0 for event in EVENTS})

    def observe(self, event: str) -> None:
        if event not in self.counts:
            self.counts["audit_overflow"] = 1
            return
        if sum(self.counts.values()) >= self.maximum_events:
            self.counts["audit_overflow"] = 1
            return
        self.counts[event] += 1

    def snapshot(self) -> dict[str, int]:
        return dict(self.counts)


def current_audit() -> EffectAudit | None:
    return _CURRENT.get()


def bind_audit(audit: EffectAudit):
    class Binding:
        def __enter__(self):
            self.token = _CURRENT.set(audit)
            return audit

        def __exit__(self, *_exc):
            _CURRENT.reset(self.token)

    return Binding()


def install_python_network_fence(audit: EffectAudit) -> None:
    """Allow literal loopback only; record any denied operation without content."""

    def fence(event, args):
        denied = False
        if event in {"socket.sendto", "socket.sendmsg"}:
            denied = True
        elif event == "socket.getaddrinfo":
            denied = args[0] not in {"localhost", "127.0.0.1", "::1"}
        elif event in {"socket.connect", "socket.bind"}:
            address = args[1]
            denied = not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1"}
        if denied:
            audit.observe("external_send")
            raise PermissionError("offline_information_handling_network_denied")

    sys.addaudithook(fence)


class BoundedTextSink:
    """Capture at most `limit` UTF-8 bytes; never retain captured content."""

    encoding = "utf-8"

    def __init__(self, limit: int = 4096):
        self.limit = limit
        self.bytes_written = 0
        self.truncated = False

    def write(self, value: str) -> int:
        raw = value.encode("utf-8", errors="replace")
        available = max(0, self.limit - self.bytes_written)
        kept = min(len(raw), available)
        self.bytes_written += kept
        self.truncated = self.truncated or kept != len(raw)
        return len(value)

    def flush(self):
        return None

    def isatty(self):
        return False
