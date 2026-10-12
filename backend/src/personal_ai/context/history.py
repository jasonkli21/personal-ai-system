"""Shared policy projection for conversation turns used as model context."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING

from personal_ai.applications.contracts import ContextSensitivity, ManualImportReusePolicy
from personal_ai.contracts.context_categories import ContextSourceClass
from personal_ai.contracts.context_references import (
    ContextPermissionDependency,
    ContextSourceSnapshot,
)
from personal_ai.entities import Message, MessageRole

if TYPE_CHECKING:
    from personal_ai.context.contracts import ConversationSummary


def manual_import_is_reusable(
    message: Message, policy: ManualImportReusePolicy
) -> bool:
    """Fail closed when a manual turn has no current, bounded sensitivity fact."""
    attribution = message.attribution
    if attribution is None or attribution.execution_origin != "manual_import":
        return True
    sensitivity = (
        message.execution.effective_sensitivity if message.execution is not None else None
    )
    return policy.allows(sensitivity)


def source_snapshots_for_message(message: Message) -> tuple[ContextSourceSnapshot, ...]:
    """Return the payload-free source authorities retained on a completed turn."""
    snapshots = (
        *((message.attribution.source_snapshots) if message.attribution else ()),
        *((message.execution.source_snapshots) if message.execution else ()),
    )
    unique: dict[str, ContextSourceSnapshot] = {}
    for snapshot in snapshots:
        unique.setdefault(snapshot.model_dump_json(), snapshot)
    return tuple(unique.values())


def message_context_authority(
    message: Message,
) -> tuple[
    tuple[ContextPermissionDependency, ...],
    datetime | None,
    ContextSensitivity,
    tuple[ContextSourceClass, ...],
]:
    """Project inherited dependencies, expiry, and sensitivity from a turn."""
    snapshots = source_snapshots_for_message(message)
    dependencies = tuple(
        dict.fromkeys(
            dependency
            for snapshot in snapshots
            for dependency in snapshot.permission_dependencies
        )
    )
    source_classes = tuple(
        dict.fromkeys(source_class for snapshot in snapshots for source_class in snapshot.source_classes)
    )
    expiries = [snapshot.expires_at for snapshot in snapshots if snapshot.expires_at is not None]
    attribution_sensitivity = (
        message.attribution.effective_context_sensitivity
        if message.attribution is not None
        else None
    )
    execution_sensitivity = (
        message.execution.effective_sensitivity if message.execution is not None else None
    )
    rank = {"public": 0, "personal": 1, "sensitive": 2, "restricted": 3, "unknown": 4}
    sensitivity = max(
        (value for value in (attribution_sensitivity, execution_sensitivity, "personal") if value),
        key=rank.__getitem__,
    )
    return (
        dependencies,
        min(expiries) if expiries else None,
        sensitivity,
        source_classes,
    )


def memory_extraction_context_reason(message: Message) -> str | None:
    """Keep sourced, sensitive, or time-bound assistant context out of durable memory."""
    snapshots = source_snapshots_for_message(message)
    _dependencies, _expires_at, sensitivity, _source_classes = message_context_authority(message)
    if not snapshots:
        return None if sensitivity in ("public", "personal") else "context_sensitive"
    if any(
        not snapshot.source_classes
        or any(source_class != "conversation" for source_class in snapshot.source_classes)
        for snapshot in snapshots
    ):
        return "context_source_not_reusable"
    if any(snapshot.permission_dependencies for snapshot in snapshots):
        return "context_permission_required"
    if any(snapshot.expires_at is not None for snapshot in snapshots):
        return "context_time_bound"
    if sensitivity not in ("public", "personal"):
        return "context_sensitive"
    return None


def summary_authority_snapshot(
    summary: ConversationSummary, messages: Sequence[Message]
) -> ContextSourceSnapshot | None:
    """Retain source authority for a lossy history summary as one bounded record."""
    source_ids = set(summary.source_message_ids)
    assistants = tuple(
        message
        for message in messages
        if message.id in source_ids and message.role is MessageRole.ASSISTANT
    )
    inherited_snapshots = tuple(
        snapshot
        for message in assistants
        for snapshot in source_snapshots_for_message(message)
    )
    authorities = tuple(message_context_authority(message) for message in assistants)
    dependencies = tuple(
        dict.fromkeys(
            dependency
            for item_dependencies, _expiry, _sensitivity, _classes in authorities
            for dependency in item_dependencies
        )
    )
    source_classes = (
        ()
        if any(not snapshot.source_classes for snapshot in inherited_snapshots)
        else tuple(
            dict.fromkeys(
                ("conversation",)
                + tuple(
                    source_class
                    for _dependencies, _expiry, _sensitivity, classes in authorities
                    for source_class in classes
                )
            )
        )
    )
    if len(dependencies) > 16:
        raise ValueError("conversation_context_dependency_limit")
    expiries = [
        expiry
        for _dependencies, expiry, _sensitivity, _classes in authorities
        if expiry is not None
    ]
    return ContextSourceSnapshot(
        provider_id="conversation_history",
        source_id=str(summary.conversation_id),
        source_version="active-branch-summary-v1",
        item_id=str(summary.id),
        source_classes=source_classes,
        owner_id=summary.owner_id,
        application_id=summary.application_id,
        workspace_id=summary.workspace_id,
        operation="history",
        content_fingerprint=sha256(summary.content.encode("utf-8")).hexdigest(),
        permission_dependencies=dependencies,
        expires_at=min(expiries) if expiries else None,
    )


def conversation_context_messages(
    messages: Sequence[Message],
    *,
    manual_import_reuse: ManualImportReusePolicy,
    permission_revalidator=None,
    check_source_permissions: bool = False,
    now: datetime | None = None,
    exclusions: dict | None = None,
) -> tuple[Message, ...]:
    """Omit ineligible manual turns and their paired user prompts.

    The canonical conversation remains untouched. Filtering before summary selection
    also prevents an existing derived summary from reintroducing a denied turn.
    """
    checked_at = (now or datetime.now(UTC)).astimezone(UTC)
    excluded_ids: set = set()
    reasons: dict = {}
    permission_results: dict[ContextPermissionDependency, bool] = {}

    def exclude_turn(message: Message, reason: str) -> None:
        excluded_ids.add(message.id)
        reasons.setdefault(message.id, reason)
        if message.parent_message_id is not None:
            excluded_ids.add(message.parent_message_id)
            reasons.setdefault(message.parent_message_id, reason)

    for message in messages:
        if message.role is not MessageRole.ASSISTANT:
            continue
        if not manual_import_is_reusable(message, manual_import_reuse):
            exclude_turn(message, "source_policy_denied")
            continue
        if not check_source_permissions:
            continue
        for snapshot in source_snapshots_for_message(message):
            if (
                snapshot.owner_id != message.owner_id
                or snapshot.application_id != message.application_id
                or snapshot.workspace_id != message.workspace_id
            ):
                exclude_turn(message, "source_scope_mismatch")
                break
            if snapshot.expires_at is not None and snapshot.expires_at <= checked_at:
                exclude_turn(message, "source_expired")
                break
            if snapshot.permission_dependencies and permission_revalidator is None:
                exclude_turn(message, "source_permission_unverified")
                break
            for dependency in snapshot.permission_dependencies:
                if dependency in permission_results:
                    continue
                try:
                    permission_results[dependency] = bool(
                        permission_revalidator.is_current(dependency)
                    )
                except Exception:  # noqa: BLE001 - source authority fails closed
                    permission_results[dependency] = False
            current = all(
                permission_results[dependency]
                for dependency in snapshot.permission_dependencies
            )
            if not current:
                exclude_turn(message, "source_permission_revoked")
                break

    if exclusions is not None:
        exclusions.update(reasons)
    return tuple(message for message in messages if message.id not in excluded_ids)
