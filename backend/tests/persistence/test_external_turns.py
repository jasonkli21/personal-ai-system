"""Opt-in DynamoDB transaction/restart coverage; offline fakes are not engine evidence."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from personal_ai.context.contracts import fingerprint
from personal_ai.entities import Conversation, Message, MessageRole, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution, TurnReservation
from personal_ai.persistence.dynamodb import (
    DynamoDBConversationRepository,
    DynamoDBMessageRepository,
    DynamoDBRuntimeTable,
)

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def repositories():
    endpoint = os.environ.get("PERSISTENCE_TEST_DYNAMODB_ENDPOINT")
    if not endpoint:
        pytest.skip("set PERSISTENCE_TEST_DYNAMODB_ENDPOINT to isolated DynamoDB Local")
    table = DynamoDBRuntimeTable(endpoint, table_name=f"external-{uuid4().hex[:20]}")
    table.bootstrap()
    conversations = DynamoDBConversationRepository(table)
    messages = DynamoDBMessageRepository(table, conversations)
    try:
        yield table, conversations, messages
    finally:
        table.client.delete_table(TableName=table.table_name)
        table.close()


def prepared(repositories, mode):
    _, conversations, messages = repositories
    now = datetime.now(UTC)
    cid = uuid4()
    conversations.create(
        Conversation(id=cid, owner_id="local", title="External CAS", created_at=now, updated_at=now)
    )
    user = messages.create(
        Message(
            id=uuid4(),
            conversation_id=cid,
            owner_id="local",
            role=MessageRole.USER,
            content="Question",
            status=MessageStatus.COMPLETED,
            created_at=now,
        )
    )
    branch = fingerprint([user], include_state=True)
    assistant = Message(
        id=uuid4(),
        conversation_id=cid,
        owner_id="local",
        role=MessageRole.ASSISTANT,
        content="",
        status=MessageStatus.PENDING,
        created_at=now + timedelta(microseconds=1),
        parent_message_id=user.id,
    )
    extra = (
        {}
        if mode == "manual_external"
        else {
            "provider_id": "fixture",
            "model_id": "model",
            "connection_id": uuid4(),
            "connection_revision": 1,
            "caller_id": uuid4(),
            "audience": uuid4(),
            "endpoint_profile_id": "fixture:profile",
            "profile_version": 1,
            "profile_digest": "a" * 64,
        }
    )
    reservation = TurnReservation(
        reservation_id=assistant.id,
        request_digest="a" * 64,
        mode=mode,
        package_fingerprint="a" * 64,
        branch_digest=branch,
        authority_digest="a" * 64,
        policy_version="fixture",
        effective_sensitivity="public",
        expires_at=now + timedelta(seconds=120),
        max_output_bytes=80000,
        **extra,
    )
    assistant = assistant.model_copy(update={"execution": reservation})
    assistant = messages.prepare_message_turn(
        owner_id="local",
        conversation_id=cid,
        expected_active_ids=[user.id],
        supersede_from_message_id=None,
        messages=[assistant],
        updated_at=now,
    )[0]
    return assistant, branch, now


def test_manual_finalize_cas_race_and_restart(repositories):
    table, conversations, messages = repositories
    assistant, branch, now = prepared(repositories, "manual_external")
    completed = assistant.model_copy(
        update={
            "status": MessageStatus.COMPLETED,
            "content": "Imported answer",
            "attribution": TurnAttribution(
                mode="manual_external", fact_source="user_declared", recorded_at=now
            ),
            "execution": assistant.execution.model_copy(
                update={"state": "completed", "completion_digest": "b" * 64}
            ),
        }
    )

    def finalize(_):
        return messages.update_status(
            owner_id="local",
            conversation_id=assistant.conversation_id,
            message_id=assistant.id,
            status=MessageStatus.COMPLETED,
            replacement=completed,
            expected_message=assistant,
            expected_branch_digest=branch,
            updated_at=now,
        )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(finalize, range(2)))
    assert sum(value is not None for value in results) == 1
    restarted = DynamoDBMessageRepository(table, conversations)
    recovered = restarted.get(
        owner_id="local", conversation_id=assistant.conversation_id, message_id=assistant.id
    )
    assert recovered.execution.completion_digest == "b" * 64
    assert recovered.attribution.fact_source == "user_declared"
    assert recovered.content == "Imported answer"


def test_dispatch_expiry_recovery_retains_unknown_fence(repositories):
    _, _, messages = repositories
    assistant, branch, now = prepared(repositories, "connected_provider")
    dispatched = assistant.model_copy(
        update={"execution": assistant.execution.model_copy(update={"state": "dispatched"})}
    )
    result = messages.update_status(
        owner_id="local",
        conversation_id=assistant.conversation_id,
        message_id=assistant.id,
        status=MessageStatus.PENDING,
        replacement=dispatched,
        expected_message=assistant,
        expected_branch_digest=branch,
        updated_at=now,
    )
    assert result is not None
    messages.recover_stale_turn(
        owner_id="local",
        conversation_id=assistant.conversation_id,
        stale_before=now - timedelta(seconds=360),
        updated_at=now + timedelta(seconds=121),
    )
    recovered = messages.get(
        owner_id="local", conversation_id=assistant.conversation_id, message_id=assistant.id
    )
    assert recovered.status == MessageStatus.FAILED and recovered.execution.state == "unknown"
    assert recovered.content == ""
