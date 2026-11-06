"""Preview authorization, bounded admission and lifecycle through ASGI."""

import asyncio
from contextlib import aclosing
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from personal_ai.api import synthetic_reasoning as preview
from personal_ai.llm.fake import FakeLLMClient

TOKEN = "a" * 43
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Application-ID": "personal_ai"}


def client(app, headers=HEADERS, *, peer="127.0.0.1"):
    return AsyncClient(
        transport=ASGITransport(app=app, client=(peer, 1000)),
        base_url="http://127.0.0.1",
        headers=headers,
    )


def body(key, **changes):
    return {
        "capability": preview.CAPABILITY,
        "original_key": str(key),
        "task": "sum",
        **changes,
    }


async def runs(client):
    response = await client.get(preview.PREFIX + "/capability")
    assert response.status_code == 200
    return f"{preview.PREFIX}/{response.json()['epoch']}/runs"


def test_wrong_authority_and_invalid_grammar_never_dispatch(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("unexpected generation")
        yield

    monkeypatch.setattr(FakeLLMClient, "stream_events", forbidden)

    async def exercise():
        app = preview.create_preview(TOKEN)
        for headers, peer in (
            ({}, "127.0.0.1"),
            ({**HEADERS, "X-Application-ID": "foreign"}, "127.0.0.1"),
            ({**HEADERS, "X-Workspace-ID": "other"}, "127.0.0.1"),
            ({**HEADERS, "Origin": "https://foreign.invalid"}, "127.0.0.1"),
            (HEADERS, "192.0.2.1"),
        ):
            async with client(app, headers, peer=peer) as foreign:
                assert (await foreign.get(preview.PREFIX + "/capability")).status_code == 403
        async with client(app) as local:
            path = await runs(local)
            key = uuid4()
            for change in (
                {"task": "open_prompt"},
                {"source": "untrusted"},
                {"capability": "v2"},
                {"effort": "unlimited"},
                {"limits": {"external_sources": 1}},
                {"limits": {"provider_cost_usd": "1.00"}},
                {"limits": {"model_calls": 2}},
            ):
                assert (await local.post(path, json=body(key, **change))).status_code == 422
            headers = {"Content-Type": "application/json"}
            assert (await local.post(path, content=b" " * 2049, headers=headers)).status_code == 413
            duplicate = b'{"task":"sum","task":"pair"}'
            assert (await local.post(path, content=duplicate, headers=headers)).status_code == 422
            denied = await local.post(path, json=body(key, limits={"model_calls": 0}))
            assert denied.json()["error"]["code"] == "budget_exhausted"
            assert (await local.get(f"{path}/{key}")).status_code == 404

    asyncio.run(exercise())


def test_concurrent_cancel_blocks_follow_on_work_and_backpressures_submit(monkeypatch):
    original = FakeLLMClient.stream_events
    calls = []

    async def exercise():
        app = preview.create_preview(TOKEN)
        entered, release = asyncio.Event(), asyncio.Event()

        async def pause(client, *args, **kwargs):
            calls.append(True)
            entered.set()
            await release.wait()
            async with aclosing(original(client, *args, **kwargs)) as events:
                async for event in events:
                    yield event

        monkeypatch.setattr(FakeLLMClient, "stream_events", pause)
        async with client(app) as local:
            path = await runs(local)
            key = uuid4()
            active = asyncio.create_task(local.post(path, json=body(key)))
            await asyncio.wait_for(entered.wait(), timeout=2)
            try:
                busy = await local.post(path, json=body(uuid4()))
                assert busy.status_code == 429 and busy.json()["error"]["code"] == "reasoning_busy"
                status = (await local.get(f"{path}/{key}")).json()["progress"]
                assert status["state"] == "running"
                malformed = await local.post(f"{path}/{key}/cancel", json={"unexpected": True})
                assert malformed.status_code == 422
                canceled = (await local.post(f"{path}/{key}/cancel")).json()["progress"]
                assert canceled["state"] == "uncertain" and canceled["cancel_requested"]
            finally:
                release.set()
            completed = (await active).json()
            assert completed == {"progress": canceled, "result": []}
            assert len(calls) == 1
            assert canceled["attempts"][0]["resources"]["physical_attempts"] is None
            assert (await local.post(path, json=body(key))).json() == completed

    asyncio.run(exercise())


def test_capacity_disable_and_epoch_keep_original_receipts(monkeypatch):
    monkeypatch.setattr(preview, "MAX_RUNS", 1)

    async def exercise():
        app = preview.create_preview(TOKEN)
        async with client(app) as local:
            path = await runs(local)
            key = uuid4()
            first = (await local.post(path, json=body(key, effort="max"))).json()
            assert first["result"] == [[0, 3]]
            assert first["progress"]["effort"] == "low"
            next_key = uuid4()
            full = await local.post(path, json=body(next_key))
            assert full.status_code == 429 and full.json()["error"]["code"] == "reasoning_capacity"
            app.state.admissions_enabled = False
            denied = await local.post(path, json=body(next_key))
            assert (
                denied.status_code == 403 and denied.json()["error"]["code"] == "reasoning_disabled"
            )
            same = (await local.post(path, json=body(key, effort="max"))).json()
            assert same == {"progress": first["progress"], "result": []}
            assert (await local.post(path, json=body(key, task="pair"))).status_code == 409
            cursor = first["progress"]["cursor"]
            status = (await local.get(f"{path}/{key}?cursor={cursor}")).json()["progress"]
            assert status["events"] == [] and status["gap"] is False
            assert (await local.get(f"{path}/{key}?cursor={cursor + 1}")).status_code == 422
        async with client(preview.create_preview(TOKEN)) as restarted:
            assert (await restarted.get(f"{path}/{key}")).status_code == 409
            assert (await restarted.post(path, json=body(key))).status_code == 409

    asyncio.run(exercise())
