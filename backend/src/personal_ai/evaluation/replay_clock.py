"""Deterministic clock policy for sealed offline evaluation replay.

Sealed offline replay must not change its semantic rows when the host scheduler
delays a step past a wall/monotonic deadline. Production timeout behavior is
verified separately with the real clock; this module freezes only the monotonic
readings used by the offline harness and its bound aliases.

The policy is deliberately narrow: wall-clock timestamps used for persistence
identity stay real, asyncio's event loop clock stays live, and every
personal_ai-module monotonic deadline, lease, and elapsed-time branch observes
one constant reading.

``time.monotonic`` itself is intentionally left unpatched so that asyncio's
event loop clock (``loop.time()``) continues to advance and ``asyncio.timeout``
cancellation remains functional.  Only bound aliases imported directly into
``personal_ai.*`` modules are frozen.
"""

from __future__ import annotations

import sys
import time
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

_real_monotonic = time.monotonic
OFFLINE_REPLAY_MONOTONIC = 1_000.0


def _bound_monotonic_targets():
    """Return personal_ai modules that imported ``monotonic`` directly."""
    seen: set[int] = set()
    targets = []
    for module in tuple(sys.modules.values()):
        if id(module) in seen:
            continue
        name = getattr(module, "__name__", "")
        if name != "personal_ai" and not name.startswith("personal_ai."):
            continue
        if getattr(module, "monotonic", None) is _real_monotonic:
            seen.add(id(module))
            targets.append(module)
    return targets


@contextmanager
def frozen_monotonic(value: float = OFFLINE_REPLAY_MONOTONIC):
    """Freeze every personal_ai bound ``monotonic`` alias to *value*.

    ``time.monotonic`` itself is NOT patched so asyncio's event loop clock
    remains live.  Deadline arithmetic inside personal_ai service code sees the
    frozen value while ``asyncio.timeout`` and ``asyncio.sleep`` continue to
    work normally.
    """
    frozen = lambda: value
    with ExitStack() as stack:
        for target in _bound_monotonic_targets():
            stack.enter_context(patch.object(target, "monotonic", frozen))
        yield value
