"""Request-local source revalidation supplied by the owning service, not providers."""

from contextlib import contextmanager
from contextvars import ContextVar

_guard: ContextVar[object] = ContextVar("inference_disclosure_guard", default=None)


@contextmanager
def bind_disclosure_guard(guard):
    token = _guard.set(guard)
    try:
        yield
    finally:
        _guard.reset(token)


def revalidate_disclosure():
    guard = _guard.get()
    if guard is not None:
        guard()
