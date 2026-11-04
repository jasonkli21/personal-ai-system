"""Synthetic restore of derived data with the current authority kept outside it."""

from copy import deepcopy
from uuid import uuid4

import pytest

from personal_ai.api import dependencies as deps
from personal_ai.retrieval.contracts import RetrievalQuery
from personal_ai.retrieval.journal import AttemptJournal, IntentConflict
from personal_ai.storage.fake import InMemoryMessageRepository

from .test_retrieval_http import context_runtime
from .test_retrieval_http import http_platform as signed_http_fixture

http_platform = signed_http_fixture
pytestmark = pytest.mark.loopback_http


@pytest.fixture(autouse=True)
def synthetic_restore_capabilities(monkeypatch):
    # The shared HTTP fixture otherwise enables these capabilities by test-name
    # prefix. This restore test requires the same explicit synthetic grant before
    # it can verify withdrawal; all post-withdrawal denial assertions still apply.
    monkeypatch.setenv("READING_LOGBOOK_RETRIEVAL_ENABLED", "true")
    monkeypatch.setenv("READING_LOGBOOK_RETRIEVAL_CONTEXT_ENABLED", "true")


def test_stale_derived_restore_keeps_revocation_and_original_keys(
    http_platform, tmp_path, monkeypatch
):
    h = http_platform
    path, scope, settings, pair = context_runtime(h, tmp_path)
    conversation = h.client.start("Synthetic restore", uuid4())["id"]
    key = uuid4()
    turn = {"content": "Atlas", "idempotency_key": str(key), "retrieval_context": True}
    assert h.client.ask(conversation, turn)["status"] == "completed"
    assert "Atlas is a book" in str(pair.generator.delegate.requests[0])
    stale_messages = deepcopy(h.messages._messages)

    # The surviving journal is outside the restored message data. Model an
    # ambiguous search acknowledgement separately from the completed chat turn.
    query = RetrievalQuery(query="Atlas", idempotency_key=uuid4(), sources=("external",))
    journal = AttemptJournal(settings.retrieval_attempt_journal_file)
    assert journal.reserve(scope, query) is None
    stale_candidate = path.read_bytes()
    path.unlink()
    quarantine = tmp_path / "quarantined-stale-installation.json"
    quarantine.write_bytes(stale_candidate)

    restored = InMemoryMessageRepository(h.conversations)
    restored._messages = stale_messages
    h.app.dependency_overrides[deps.get_message_repository] = lambda: restored
    detail = h.raw.get(f"/v1/conversations/{conversation}", headers=h.headers)
    assert detail.status_code == 409 and "Atlas" not in detail.text
    replay = h.raw.post(f"/v1/conversations/{conversation}/continue", headers=h.headers, json=turn)
    assert "response.error" in replay.text and "Atlas" not in replay.text
    assert h.client.status(conversation, key)["state"] == "completed"

    new_turn = h.raw.post(
        f"/v1/conversations/{conversation}/continue",
        headers=h.headers,
        json={**turn, "idempotency_key": str(uuid4())},
    )
    assert new_turn.status_code in {409, 422, 503}
    assert "Atlas is a book" not in new_turn.text
    assert len(pair.generator.delegate.requests) == 1

    restarted = AttemptJournal(settings.retrieval_attempt_journal_file)
    monkeypatch.setattr(restarted, "CAPACITY", 1)
    assert restarted.reserve(scope, query) == "external_outcome_unknown"
    with pytest.raises(IntentConflict):
        restarted.reserve(scope, query.model_copy(update={"query": "changed"}))
    assert (
        restarted.reserve(scope, query.model_copy(update={"idempotency_key": uuid4()})) == "quota"
    )
    restarted.complete(scope, query)
    assert restarted.reserve(scope, query) == "external_already_attempted"
    assert quarantine.is_file() and not path.exists()
