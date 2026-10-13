"""Projection contracts shared by the in-memory and Postgres lifecycle adapters."""

from datetime import UTC, datetime
from uuid import uuid4

from personal_ai.memory.lifecycle.contracts import MemoryLifecycleEvent, MemoryLifecycleState
from personal_ai.memory.lifecycle.transition import transition


def test_projection_accepts_unbounded_legal_consolidation_history():
    now = datetime(2026, 10, 12, tzinfo=UTC)
    memory_id = uuid4()
    state = MemoryLifecycleState(memory_id=memory_id, owner_id="local")
    for version in range(12):
        event = MemoryLifecycleEvent(
            id=uuid4(),
            owner_id="local",
            memory_id=memory_id,
            event_type="consolidated",
            reason_code="derived_memory_created",
            policy_version="support-v1",
            occurred_at=now,
            idempotency_key=f"consolidation-{version}",
            related_memory_ids=(uuid4(),),
            expected_state_version=version,
        )
        state = transition(state, event)
    assert state.state_version == 12
    assert "consolidated_into_memory_ids" not in state.model_dump()
