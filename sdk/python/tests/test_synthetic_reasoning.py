from uuid import uuid4

import pytest
from personal_ai_sdk import CapabilityUnavailable, SyntheticReasoning, UncertainTurn
from personal_ai_sdk.synthetic_reasoning import CEILINGS


def descriptor():
    return {
        "capability": "reasoning.workflow.synthetic.v1",
        "state": "development_only",
        "epoch": str(uuid4()),
        "evidence_tier": "E1",
        "default_enabled": False,
        "strategy": "direct-verified.v1",
        "tasks": ["sum", "pair"],
        "requested_efforts": ["auto", "low", "medium", "high", "max"],
        "effective_effort": "low",
        "limits": CEILINGS,
        "queue": 0,
        "max_originals": 64,
    }


def receipt(*, state="succeeded", result=None):
    progress = {
        "schema_version": "reasoning-run-progress-v1",
        "run_id": str(uuid4()),
        "state": state,
        "cancel_requested": False,
        "reason": None,
        "cursor": 1,
        "gap": False,
        "events": [],
        "attempts": [],
        "policy": "reasoning-finite-policy-v1",
        "catalog": "reasoning-finite-catalog-v1",
        "strategy": "direct",
        "strategy_version": "direct-verified.v1",
        "selection": "simple",
        "requested_effort": "auto",
        "plan_digest": "a" * 64,
        "budget_class": "bounded_synthetic_bytes",
        "effort": "low",
        "phase": "terminal"
        if state in {"succeeded", "failed", "canceled", "uncertain"}
        else "answering",
        "outcome": "complete" if state == "succeeded" else "pending",
    }
    value = {"progress": progress}
    if result is not None:
        value["result"] = result
    return value


def test_changed_or_disabled_epoch_cannot_silently_admit_new_work(monkeypatch):
    client = SyntheticReasoning("http://127.0.0.1:8766", "fixture")
    facts = descriptor()
    monkeypatch.setattr(client, "_exchange", lambda *_: facts)
    client.negotiate()
    facts["epoch"] = str(uuid4())
    with pytest.raises(UncertainTurn, match="epoch_changed"):
        client.negotiate()
    client = SyntheticReasoning("http://127.0.0.1:8766", "fixture")
    monkeypatch.setattr(client, "_exchange", lambda *_: facts | {"state": "disabled"})
    with pytest.raises(CapabilityUnavailable):
        client.negotiate()


def test_disconnect_does_not_retry_and_status_uses_same_epoch_and_key(monkeypatch):
    client = SyntheticReasoning("http://127.0.0.1:8766", "fixture")
    facts = descriptor()
    monkeypatch.setattr(client, "_exchange", lambda *_: facts)
    client.negotiate()
    monkeypatch.undo()
    calls = []

    def disconnect(request, *, timeout):
        calls.append((request, timeout))
        raise TimeoutError

    monkeypatch.setattr(client._client._opener, "open", disconnect)
    key = uuid4()
    with pytest.raises(UncertainTurn, match="retain the original key"):
        client.submit(key, "sum")
    assert len(calls) == 1 and calls[0][0].get_method() == "POST"
    assert str(key).encode() in calls[0][0].data
    with pytest.raises(UncertainTurn):
        client.status(key, cursor=2)
    request, timeout = calls[1]
    assert len(calls) == 2 and timeout == 8 and request.get_method() == "GET"
    assert request.full_url.endswith(f"/{facts['epoch']}/runs/{key}?cursor=2")


def test_oversized_response_is_uncertain(monkeypatch):
    client = SyntheticReasoning("http://127.0.0.1:8766", "fixture")

    class Oversized:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            assert size == 32769
            return b"x" * size

    monkeypatch.setattr(
        client._client._opener, "open", lambda *args, **kwargs: Oversized()
    )
    with pytest.raises(UncertainTurn, match="response_too_large"):
        client.negotiate()


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.pop("run_id"),
        lambda p: p.pop("plan_digest"),
        lambda p: p.pop("strategy_version"),
        lambda p: p.update(cursor=True),
        lambda p: p.update(state="future_state"),
        lambda p: p.update(schema_version="reasoning-run-progress-v2"),
        lambda p: p.update(strategy_version="unknown"),
        lambda p: p.update(state="failed", outcome="complete"),
    ],
)
def test_malformed_success_progress_is_uncertain(change):
    value = receipt(result=[])
    change(value["progress"])
    with pytest.raises(UncertainTurn, match="invalid_reasoning_receipt"):
        SyntheticReasoning._receipt(value, result=True)


@pytest.mark.parametrize(
    "result", [[["not_a_slot", 3]], [[0, "not_an_integer"]], [[0, 3], [0, 4]]]
)
def test_malformed_success_result_is_uncertain(result):
    with pytest.raises(UncertainTurn, match="invalid_reasoning_receipt"):
        SyntheticReasoning._receipt(receipt(result=result), result=True)


def test_valid_partial_result_and_metadata_only_receipts():
    partial = receipt(state="failed", result=[[0, 3]])
    partial["progress"].update(outcome="partial", reason="budget_exhausted")
    assert SyntheticReasoning._receipt(partial, result=True) is partial
    metadata = receipt(state="running")
    assert SyntheticReasoning._receipt(metadata) is metadata
    with pytest.raises(UncertainTurn, match="invalid_reasoning_receipt"):
        SyntheticReasoning._receipt(metadata | {"result": []})
