"""Observable side-effect fences shared by synthetic source tests."""

import socket
from collections import Counter

import pytest


@pytest.fixture
def side_effect_fence(monkeypatch):
    from personal_ai.llm.execution import SelectedGeneration, SendAccounting
    from personal_ai.llm.fake import FakeLLMClient
    from personal_ai.llm.litellm.transport import _TransportState
    from personal_ai.memory.repositories import InMemoryMemoryRepository
    from personal_ai.routing.service import RoutingDecisionService

    counters = Counter(network=0, provider=0, model=0, billing=0, memory=0)

    def guard(boundary):
        def blocked(*_args, **_kwargs):
            counters[boundary] += 1
            pytest.fail(f"unexpected synthetic side effect: {boundary}")
        return blocked

    for target, name, category in (
        (socket.socket, "connect", "network"),
        (socket.socket, "connect_ex", "network"),
        (socket, "getaddrinfo", "network"),
        (_TransportState, "_admit_send", "provider"),
        (SendAccounting, "check_send", "provider"),
        (SendAccounting, "reserve_attempt", "billing"),
        (SelectedGeneration, "stream_events", "model"),
        (FakeLLMClient, "complete", "model"),
        (FakeLLMClient, "stream_events", "model"),
        (RoutingDecisionService, "dispatch", "billing"),
        (InMemoryMemoryRepository, "create", "memory"),
    ):
        monkeypatch.setattr(target, name, guard(category))
    yield counters
    assert counters == Counter(network=0, provider=0, model=0, billing=0, memory=0)
