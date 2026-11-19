"""Request-local source revalidation supplied by the owning service, not providers."""

from contextlib import contextmanager
from contextvars import ContextVar

from personal_ai.usage.trace import Event, Reason, State, emit

_guard: ContextVar[object] = ContextVar("inference_disclosure_guard", default=None)
_source_references: ContextVar[tuple[str, ...]] = ContextVar(
    "inference_disclosure_source_references", default=()
)


@contextmanager
def bind_disclosure_guard(guard, *, source_references=()):
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
    references = _source_references.set(tuple(dict.fromkeys(
        (*_source_references.get(), *source_references)
    )))
    try:
        yield
    finally:
        _guard.reset(token)
        _source_references.reset(references)


def current_disclosure_source_references() -> tuple[str, ...]:
    return _source_references.get()


def revalidate_disclosure():
    guard = _guard.get()
    if guard is not None:
        guard()
