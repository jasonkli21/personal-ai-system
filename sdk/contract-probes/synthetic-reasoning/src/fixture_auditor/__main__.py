"""Audit a disposable fixture server through the installed public SDK."""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.util import find_spec
from pathlib import Path
from uuid import uuid4

from personal_ai_sdk import APIError, CapabilityUnavailable, SyntheticReasoning


def expect_error(operation, status, code):
    try:
        operation()
    except APIError as error:
        assert (error.status, error.code) == (status, code)
    else:
        raise AssertionError("operation did not fail closed")


def cancel_stalled_send(client):
    key = uuid4()
    with ThreadPoolExecutor(max_workers=1) as worker:
        submitted = worker.submit(client.submit, key, "sum")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            try:
                progress = client.status(key)["progress"]
            except APIError as error:
                if (error.status, error.code) != (404, "not_found"):
                    raise
            else:
                if any(item["state"] == "dispatched" for item in progress["attempts"]):
                    break
            time.sleep(0.01)
        else:
            raise AssertionError("stalled generation did not reach dispatch")
        canceled = client.cancel(key)
        assert canceled["progress"]["state"] == "uncertain"
        assert canceled["progress"]["reason"] == "uncertain_effect"
        assert (
            canceled["progress"]["attempts"][0]["resources"]["physical_attempts"]
            is None
        )
        assert submitted.result(timeout=8) == {**canceled, "result": []}
        assert client.status(key) == canceled


def main():
    for name in (
        "personal_ai",
        "personal_ai_reference_apps",
        "project_checklist",
        "reading_logbook",
    ):
        assert find_spec(name) is None
    for name in ("fixture_auditor", "personal_ai_sdk"):
        assert Path(find_spec(name).origin).is_relative_to(sys.prefix)

    base = os.environ["FIXTURE_AUDITOR_URL"]
    token = os.environ["SYNTHETIC_REASONING_TOKEN"]
    client = SyntheticReasoning(base, token)
    original = uuid4()
    try:
        client.submit(original, "sum")
    except CapabilityUnavailable:
        pass
    else:
        raise AssertionError("negotiation was bypassed")
    expect_error(SyntheticReasoning(base, "incorrect").negotiate, 403, "access_denied")
    descriptor = client.negotiate()
    first = client.submit(original, "sum", effort="max")
    assert first["result"] == [[0, 3]] and first["progress"]["effort"] == "low"
    assert first["progress"]["outcome"] == "complete"
    reopened = SyntheticReasoning(base, token, expected_epoch=descriptor["epoch"])
    reopened.negotiate()
    assert reopened.status(original) == {"progress": first["progress"]}
    assert client.submit(original, "sum", effort="max") == {
        "progress": first["progress"],
        "result": [],
    }
    expect_error(
        lambda: client.submit(original, "pair"), 409, "reasoning_intent_conflict"
    )
    expect_error(
        lambda: client.submit(uuid4(), "sum", limits={"model_calls": 0}),
        422,
        "budget_exhausted",
    )
    expect_error(
        lambda: client.status(original, cursor=first["progress"]["cursor"] + 1),
        422,
        "reasoning_cursor_invalid",
    )
    partial = client.submit(uuid4(), "pair")
    assert partial["progress"]["outcome"] == "partial" and partial["result"] == [[0, 3]]
    assert client.cancel(original) == {"progress": first["progress"]}
    if os.environ.get("FIXTURE_AUDITOR_STALLED_SEND") == "1":
        cancel_stalled_send(client)
    print("SYNTHETIC_REASONING_INSTALLED_CONSUMER=PASS")


if __name__ == "__main__":
    main()
