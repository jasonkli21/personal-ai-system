"""Request-local source revalidation supplied by the owning service, not providers."""

from contextlib import contextmanager
from contextvars import ContextVar

from personal_ai.usage.trace import Event, Reason, State, emit

_guard: ContextVar[object] = ContextVar("inference_disclosure_guard", default=None)


@contextmanager
def bind_disclosure_guard(guard):
    outer = _guard.get()

    def combined():
        if outer is not None:
            outer()
        try:
            guard()
        except Exception:
            emit(Event.SOURCE, State.DENIED, reason=Reason.SOURCE_AUTHORITY)
            raise
        emit(Event.SOURCE, State.OK)

    token = _guard.set(combined)
    try:
        yield
    finally:
        _guard.reset(token)


def revalidate_disclosure():
    guard = _guard.get()
    if guard is not None:
        guard()
