"""Deterministic clock and ordered work queues for iterative tests/evaluations."""

import inspect
from collections import deque
from datetime import UTC, datetime, timedelta

from personal_ai.search.contracts import FakeSearchAdapter, SearchDispatch, SearchResult
from personal_ai.search.planning import SearchOperation


class DeterministicClock:
    def __init__(self, start: datetime | None = None):
        self.value = start or datetime(2026, 1, 1, tzinfo=UTC)
        self.elapsed_seconds = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds: float):
        self.value += timedelta(seconds=seconds)
        self.elapsed_seconds += seconds
        return self.value

    def elapsed(self):
        return self.elapsed_seconds


class DeterministicQueue:
    def __init__(self, values=()):
        self.values = deque(values)

    def pop(self, default=None):
        return self.values.popleft() if self.values else default

    def __len__(self):
        return len(self.values)


class FakeIterativeSearchAdapter(FakeSearchAdapter):
    name = "fake"

    def __init__(
        self, scripts: dict[str, list[SearchResult] | Exception], default=(), *, on_search=None
    ):
        self.scripts = {" ".join(key.split()).casefold(): value for key, value in scripts.items()}
        self.default = tuple(default)
        self.calls: list[SearchOperation] = []
        self.responses = DeterministicQueue()
        self.on_search = on_search

    @classmethod
    def queued(cls, responses, *, on_search=None):
        adapter = cls({}, ())
        adapter.responses = DeterministicQueue(responses)
        adapter.on_search = on_search
        return adapter

    async def search(self, operation: SearchOperation):
        normalized = " ".join(operation.query.split()).casefold()
        self.calls.append(operation)
        if self.on_search is not None:
            result = self.on_search(operation.query, operation.max_results)
            if inspect.isawaitable(result):
                await result
        result = self.responses.pop(self.scripts.get(normalized, self.default))
        if isinstance(result, Exception):
            raise result
        if isinstance(result, DeterministicQueue):
            result = result.pop(())
        return SearchDispatch(tuple(result[:operation.max_results]))
