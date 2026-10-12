"""Pure lifecycle state transition policy."""

from __future__ import annotations

from personal_ai.memory.lifecycle.contracts import MemoryLifecycleEvent, MemoryLifecycleState


def transition(state: MemoryLifecycleState, event: MemoryLifecycleEvent) -> MemoryLifecycleState:
    """Apply one validated transition to a projection, or raise a safe reason code."""
    if event.owner_id != state.owner_id or event.memory_id != state.memory_id:
        raise ValueError("owner_or_memory_mismatch")
    if event.expected_state_version != state.state_version:
        raise ValueError("state_version_conflict")
    changes: dict[str, object] = {
        "state_version": state.state_version + 1,
        "effective_status_at": event.occurred_at,
        "last_event_id": event.id,
    }
    if event.event_type in ("superseded", "forgotten", "reactivated", "review_required"):
        changes["validity_epoch"] = state.validity_epoch + 1
    if event.event_type == "consolidated":
        changes["consolidated_into_memory_ids"] = tuple(
            sorted(set(state.consolidated_into_memory_ids) | set(event.related_memory_ids), key=str)
        )
    elif event.event_type == "retrieved":
        changes["retrieval_count"] = state.retrieval_count + 1
        changes["last_retrieved_at"] = event.occurred_at
        changes["effective_status_at"] = state.effective_status_at
    elif event.event_type == "superseded":
        if (
            state.retrieval_status != "active"
            or len(event.related_memory_ids) != 1
            or event.related_memory_ids[0] == state.memory_id
        ):
            raise ValueError("transition_invalid")
        changes["retrieval_status"] = "superseded"
        changes["superseded_by_memory_id"] = event.related_memory_ids[0]
    elif event.event_type == "forgotten":
        if state.retrieval_status != "active":
            raise ValueError("transition_invalid")
        changes["retrieval_status"] = "forgotten"
    elif event.event_type == "reactivated":
        if state.retrieval_status == "active" or state.superseded_by_memory_id is not None:
            raise ValueError("transition_invalid")
        changes["retrieval_status"] = "active"
        changes["effective_status_at"] = event.occurred_at
    elif event.event_type == "review_required":
        changes["unresolved_conflict"] = True
        changes["effective_status_at"] = state.effective_status_at
    else:
        raise ValueError("event_type_invalid")
    return MemoryLifecycleState.model_validate({**state.model_dump(), **changes})
