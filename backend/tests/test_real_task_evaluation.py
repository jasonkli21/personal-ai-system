import json
from uuid import uuid4

import anyio
import pytest

from personal_ai.evaluation.real_tasks import load_manifest, run
from personal_ai.llm.execution import compose_pair
from personal_ai.settings import Settings
from personal_ai.usage.context import bind_usage_task
from personal_ai.usage.trace import Event, State, Trace, emit


def test_frozen_task_corpus_uses_canonical_context_narrowing():
    manifest, digest = load_manifest()
    assert digest == "84f08efcbcf978192ada09d6026078672d5e44931f1090382d17d6abbb2c0e2f"
    cases = manifest["cases"]
    assert len(cases) == len({case["id"] for case in cases}) == 12
    assert len({case["family"] for case in cases if case["split"] == "held_out"}) == 4
    settings = Settings(_env_file=None, ai_provider="fake", ai_model="unused")
    pair, trace = compose_pair(settings), Trace()
    rows = anyio.run(run, settings, pair, manifest, trace, uuid4(), cases)
    assert len(rows) == 36
    assert all(not row["forbidden_output"] for row in rows)
    assert sum(row["scope_denied"] for row in rows) == 3
    assert len(pair.generator.delegate.requests) == 33
    for row in rows:
        if row["completed"]:
            assert row["source_selected"] == (row["arm"] != "direct")
            assert row["distractor_selected"] == (row["arm"] == "eligible")
            assert not row["rubric_pass"]
    events, _ = trace.snapshot()
    for row in rows:
        if row["completed"]:
            assert {"context", "count", "source_check"} <= {
                event["event"] for event in events if event["request"] == row["request"]
            }


def test_trace_is_bounded_redacted_and_cannot_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    trace = Trace(capacity=2)
    with trace.capture(), bind_usage_task("secret-task", request_id="secret-request"):
        for _ in range(3):
            emit(Event.CONTEXT, State.OK, source_refs=("private-evidence",))
    kwargs = {"commit": "a" * 40, "configuration": "b" * 64, "run_id": uuid4()}
    trace.export("receipt.jsonl", **kwargs)
    serialized = (tmp_path / "receipt.jsonl").read_text()
    assert all(marker not in serialized for marker in ("secret", "private-evidence"))
    manifest, first, last = map(json.loads, serialized.splitlines())
    assert manifest["dropped"] == 1 and (first["sequence"], last["sequence"]) == (2, 3)
    with pytest.raises(FileExistsError):
        trace.export("receipt.jsonl", **kwargs)
    (tmp_path / "link.jsonl").symlink_to(tmp_path / "would-be-created")
    with pytest.raises(FileExistsError):
        trace.export("link.jsonl", **kwargs)
    assert not (tmp_path / "would-be-created").exists()
    with pytest.raises(ValueError):
        trace.export("../outside.jsonl", **kwargs)


def test_concurrent_trace_scopes_and_observer_failure_are_isolated(monkeypatch):
    first, second = Trace(), Trace()

    async def worker(trace, request):
        with trace.capture(), bind_usage_task("test", request_id=request):
            await anyio.to_thread.run_sync(emit, Event.SOURCE, State.OK)

    async def run_workers():
        async with anyio.create_task_group() as group:
            group.start_soon(worker, first, "request-one")
            group.start_soon(worker, second, "request-two")

    anyio.run(run_workers)
    for trace, request in ((first, "request-one"), (second, "request-two")):
        events, _ = trace.snapshot()
        assert len(events) == 1 and events[0]["request"] == trace.request_ref(request)

    def broken(*args, **kwargs):
        raise OSError("synthetic observer failure")

    monkeypatch.setattr(first, "record", broken)
    with first.capture():
        emit(Event.ADMISSION, State.DENIED)
