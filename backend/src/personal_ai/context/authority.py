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
    for snapshot in snapshots:
        if snapshot.expires_at is not None and now >= snapshot.expires_at:
            return False
        if not permission_dependencies_current(
            snapshot.permission_dependencies, revalidator
        ):
            return False
    return True
