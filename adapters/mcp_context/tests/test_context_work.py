import asyncio
import threading
from time import monotonic

import pytest
from app_context_support.fences import side_effect_fence  # noqa: F401
from app_context_support.fixtures import SOURCES, TRAVEL
from personal_ai_mcp_context import server

import context_host
from test_context_profiles import publications, workspace_less  # noqa: F401
from test_context_server import assert_denied, handle, host, http, rpc, tool  # noqa: F401


pytestmark = pytest.mark.usefixtures("side_effect_fence")


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
        async with http(host, host.token()) as client:
            start = monotonic()
            requests = [
                asyncio.create_task(tool(client, "search", {"query": "Demo"})) for _ in range(8)
            ]
            try:
                assert await asyncio.to_thread(ready.wait, 1.5)
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
                assert await asyncio.to_thread(first_slot_released.wait, 1)
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
