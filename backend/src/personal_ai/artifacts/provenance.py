"""Source snapshot to artifact dependency projection for derived artifact writers."""

from personal_ai.artifacts.contracts import ArtifactUnavailable
from personal_ai.contracts.context_references import ContextSourceSnapshot


def permission_dependencies_from_snapshots(snapshots):
    """Return the exact dependency set required to retain source-derived material."""
    snapshots = tuple(snapshots)
    if not snapshots or any(not isinstance(item, ContextSourceSnapshot) for item in snapshots):
        raise ArtifactUnavailable("artifact_source_snapshots_required")
    if any(
        any(source_class != "conversation" for source_class in item.source_classes)
        and not item.permission_dependencies
        for item in snapshots
    ):
        raise ArtifactUnavailable("artifact_source_dependencies_required")
    dependencies = tuple(
        dict.fromkeys(
            dependency
            for snapshot in snapshots
            for dependency in snapshot.permission_dependencies
        )
    )
    if len(dependencies) > 16:
        raise ArtifactUnavailable("artifact_source_dependency_limit")
    return dependencies
