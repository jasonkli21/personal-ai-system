"""Shared fail-closed revalidation for revocable context authority."""

from __future__ import annotations

from collections.abc import Iterable


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
        for dependency in snapshot.permission_dependencies:
            dependencies[dependency] = None
    # Deduplicate only inside this boundary. Never cache a positive across a
    # later count, summary, physical reservation, delta or replay.
    return permission_dependencies_current(dependencies, revalidator)


def source_snapshot_authority_complete(snapshot):
    """A shared-profile source can never become untainted through missing metadata."""
    if snapshot.provider_id == "global_profile" or "global_profile" in snapshot.source_classes:
        return any(
            dep.permission_id.startswith("global_profile_share:")
            and dep.owner_id == snapshot.owner_id and dep.entity_ref is not None
            and dep.source_scope is not None and dep.acting_user_id is not None
            for dep in snapshot.permission_dependencies
        )
    return True
