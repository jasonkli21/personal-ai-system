import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import context_host
import pytest
from app_context_support.fences import side_effect_fence  # noqa: F401
from app_context_support.fixtures import SOURCES, TRAVEL
from context_host import SyntheticHost
from context_workspace import WorkspaceLessHost as ProfileWorkspaceLessHost
from personal_ai_mcp_context import server
from test_context_server import assert_denied, handle, http, rpc, tool

pytestmark = pytest.mark.usefixtures("side_effect_fence")


@pytest.fixture
def host():
    return SyntheticHost()


@pytest.fixture
def workspace_less():
    return ProfileWorkspaceLessHost()


@pytest.fixture
def publications(monkeypatch):
    published = []
    original = server._State.publish

    def observe(state, pending, citations):
        original(state, pending, citations)
        published.append((len(pending), len(citations)))

    monkeypatch.setattr(server._State, "publish", observe)
    return published


def test_timed_out_synchronous_exchanges_keep_eight_worker_slots_until_exit(host, publications, monkeypatch):
    source = host.pas.sources[SOURCES[TRAVEL]]
    original = source.exchange
    real_slots = threading.BoundedSemaphore(8)
    locked = threading.Lock()
    ready, first_slot_released = threading.Event(), threading.Event()
    holds = [threading.Event() for _ in range(8)]
    entered, exited, slot_released = [], [], []

    class ObservedSlots:
        @staticmethod
        def acquire(*, blocking):
            return real_slots.acquire(blocking=blocking)

        @staticmethod
        def release():
            real_slots.release()
            with locked:
                slot_released.append(monotonic())
                first_slot_released.set()

    def blocked(raw, delegation):
        with locked:
            index = len(entered)
            entered.append(monotonic())
            if len(entered) == 8:
                ready.set()
        try:
            if index < 8 and not holds[index].wait(10):
                raise AssertionError("source barrier was not released by test")
            return original(raw, delegation)
        finally:
            with locked:
                exited.append((index, monotonic()))

    monkeypatch.setattr(context_host, "_SOURCE_WORKER_SLOTS", ObservedSlots())
    monkeypatch.setattr(source, "exchange", blocked)

    async def run():
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=9))
        async with http(host, host.token()) as client:
            start = monotonic()
            requests = [
                asyncio.create_task(tool(client, "search", {"query": "Demo"})) for _ in range(8)
            ]
            try:
                ready_deadline = monotonic() + 1.5
                while not ready.is_set() and monotonic() < ready_deadline:
                    await asyncio.sleep(0.01)
                assert ready.is_set()
                ninth = await rpc(client, "tools/call", {"name": "search", "arguments": {"query": "Demo"}})
                assert ninth.status_code == 429 and ninth.content == b""
                for response in await asyncio.wait_for(asyncio.gather(*requests), timeout=3):
                    assert_denied(response)
                timed_out = monotonic()
                assert 1.5 <= timed_out - start < 4
                assert len(entered) == 8 and exited == slot_released == publications == []
                other = {"Authorization": f"Bearer {host.token('b')}"}
                while_full = monotonic()
                assert_denied(await tool(client, "search", {"query": "Demo"}, **other))
                assert monotonic() - while_full < 1
                assert len(entered) == 8 and not publications

                holds[0].set()
                release_deadline = monotonic() + 1
                while not first_slot_released.is_set() and monotonic() < release_deadline:
                    await asyncio.sleep(0.01)
                assert first_slot_released.is_set()
                assert timed_out < exited[0][1] <= slot_released[0]
                result = await tool(client, "search", {"query": "Demo"}, **other)
                assert result["structuredContent"]["results"][0]["title"] == "Demo shuttle B"
                assert publications == [(1, 0)]
            finally:
                for release in holds:
                    release.set()

    assert server.DEADLINE_SECONDS == 2
    asyncio.run(run())
    assert len(entered) == len(exited) == len(slot_released) == 9
    assert publications == [(1, 0)]


def test_cancellable_source_acknowledges_cleanup_before_timeout_response(workspace_less, publications, monkeypatch):
    host = workspace_less
    monkeypatch.setattr(server, "DEADLINE_SECONDS", 0.25)
    observed = {}

    async def stall():
        observed["entered"] = monotonic()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            observed["source_acknowledged"] = monotonic()
            raise

    async def run():
        host.travel.before_lookup = stall
        async with http(host, host.token()) as client:
            result = await asyncio.wait_for(tool(client, "search", {"query": "Demo"}), timeout=2)
            observed["response"] = monotonic()
            assert_denied(result)
            assert host.travel.counts == {"entered": 1, "exited": 1, "active": 0}
            assert host.travel.lookup_paths == publications == []
            assert dict(host.budgets[0].calls) == {"search": 1}
            assert host.travel.counts["active"] == 0
            host.travel.before_lookup = None
            assert await handle(client)

    asyncio.run(run())
    assert observed["entered"] < observed["source_acknowledged"] <= observed["response"]
    assert observed["response"] - observed["source_acknowledged"] < 0.5
    assert publications == [(1, 0)]
