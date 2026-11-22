"""Shared fail-closed revalidation for revocable context authority."""

from __future__ import annotations

from collections.abc import Iterable
from contextvars import ContextVar

from personal_ai.contracts.context_references import (
    APPLICATION_PLAN_SOURCE_ITEM_PREFIX,
    ApplicationPlanSourceBinding,
)

application_plan_source_binding: ContextVar[ApplicationPlanSourceBinding | None] = ContextVar(
    "application_plan_source_binding", default=None,
)


def permission_dependencies_current(dependencies, revalidator) -> bool:
    """Return whether every exact dependency remains current.

    Missing validators and lookup failures deny. Callers retain their own scope
    checks; this function centralizes only the versioned dependency decision.
    """
    dependencies = tuple(dependencies)
    if not dependencies:
        return True
    if revalidator is None:
        return False
    for dependency in dependencies:
        try:
            if not revalidator.is_current(dependency):
                return False
        except Exception:  # noqa: BLE001 - authority lookup failures deny reuse
            return False
    return True


def source_snapshots_current(snapshots: Iterable, revalidator, *, now) -> bool:
    """Check expiry and exact permission dependencies for payload-free snapshots."""
    dependencies = {}
    for snapshot in snapshots:
        if not source_snapshot_authority_complete(snapshot):
            return False
        if snapshot.expires_at is not None and now >= snapshot.expires_at:
            return False
        if snapshot.application_plan_authority is not None:
            if not application_plan_source_current(snapshot, revalidator, now=now):
                return False
            continue
        for dependency in snapshot.permission_dependencies:
            dependencies[dependency] = None
    # Deduplicate only inside this boundary. Never cache a positive across a
    # later count, summary, physical reservation, delta or replay.
    return permission_dependencies_current(dependencies, revalidator)


def application_plan_source_current(snapshot, revalidator, *, now) -> bool:
    """Recheck the private binding and all authority through its installed adapter."""
    authority = snapshot.application_plan_authority
    if (
        authority is None
        or authority.binding != application_plan_source_binding.get()
        or now >= authority.expires_at
        or not source_snapshot_authority_complete(snapshot)
    ):
        return False
    try:
        return revalidator.is_application_plan_source_current(snapshot) is True
    except Exception:  # noqa: BLE001 - unavailable private authority denies disclosure
        return False


def source_snapshot_is_application_plan(snapshot) -> bool:
    return (
        snapshot.application_plan_authority is not None
        or snapshot.item_id.startswith(APPLICATION_PLAN_SOURCE_ITEM_PREFIX)
    )


def source_snapshot_authority_complete(snapshot):
    """A shared-profile source can never become untainted through missing metadata."""
    if (authority := snapshot.application_plan_authority) is not None:
        return (
            snapshot.federation is None
            and snapshot.operation == "current"
            and snapshot.source_classes == ("domain_current",)
            and snapshot.owner_id == authority.binding.owner_id
            and snapshot.application_id == authority.binding.scope.application_id
            and snapshot.workspace_id == authority.binding.scope.workspace_id
            and snapshot.source_id == authority.source_id
            and snapshot.source_version == authority.source_version
            and snapshot.item_id == authority.item_id
            and snapshot.content_fingerprint == authority.source_fingerprint
            and len(snapshot.source_refs) == 1
            and snapshot.source_refs[0].fingerprint == authority.source_fingerprint
            and bool(snapshot.permission_dependencies)
        )
    if source_snapshot_is_application_plan(snapshot):
        return False
    if snapshot.source_version == "application-plan-memory:v1":
        dependencies = snapshot.permission_dependencies
        return (
            snapshot.provider_id == "ai_memory"
            and len(dependencies) == 3
            and len({dep.source_scope for dep in dependencies}) == 1
            and {
                dep.purpose for dep in dependencies
                if dep.permission_id == f"application-plan-memory:{dep.purpose}"
            } == {"approved-pas-memory-origin", "runtime-handoff", "inference-disclosure"}
            and all(
                dep.owner_id == snapshot.owner_id
                and dep.acting_user_id is not None
                and dep.entity_ref is not None
                and dep.entity_ref.entity_id == snapshot.item_id
                and dep.source_scope is not None
                for dep in dependencies
            )
        )
    if snapshot.source_version.startswith("shared-source:"):
        dependencies = snapshot.permission_dependencies
        purposes = {"answer-context", "inference-disclosure"}
        if snapshot.source_version.startswith("shared-source:application-plan:"):
            purposes.add("runtime-handoff")
        return bool(snapshot.expires_at) and len(dependencies) == len(purposes) and {
            dep.purpose for dep in dependencies
            if dep.permission_id.startswith("shared-source:")
            and dep.owner_id == snapshot.owner_id and dep.entity_ref is not None
            and dep.acting_user_id is not None
            and dep.entity_ref.entity_id == snapshot.item_id
            and dep.source_scope is not None
            and dep.source_scope.application_id == snapshot.application_id
            and dep.source_scope.workspace_id == snapshot.workspace_id
        } == purposes
    if snapshot.provider_id == "retrieval_context":
        return bool(snapshot.expires_at) and any(
            dep.permission_id.startswith("retrieval_context:")
            and dep.owner_id == snapshot.owner_id and dep.entity_ref is not None
            and dep.source_scope is not None and dep.acting_user_id is not None
            and dep.source_scope.application_id == snapshot.application_id
            and dep.source_scope.workspace_id == snapshot.workspace_id
            for dep in snapshot.permission_dependencies
        )
    if snapshot.provider_id == "global_profile" or "global_profile" in snapshot.source_classes:
        return any(
            dep.permission_id.startswith("global_profile_share:")
            and dep.owner_id == snapshot.owner_id and dep.entity_ref is not None
            and dep.source_scope is not None and dep.acting_user_id is not None
            for dep in snapshot.permission_dependencies
        )
    return True
