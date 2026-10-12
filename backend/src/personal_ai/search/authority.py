"""Search rights dependencies flow through shared derived-context revalidation."""

from personal_ai.contracts.context_references import ContextPermissionDependency
from personal_ai.search.contracts import normalize_rights_authorization


def research_export_dependencies(exported):
    """Bind exported snippet bodies to the same current rights authority."""
    from personal_ai.evidence.contracts import SourceObservation

    sources = []
    for row in exported.get("collections", {}).get("research_sessions", ()):
        sources.extend(
            SourceObservation.model_validate(value)
            for value in row["data"].get("observations", ())
            if value.get("observation_version") == "snippet-observation-v2"
            and value.get("status") == "accepted"
        )
    return observation_dependencies(sources)


def observation_dependencies(observations):
    dependencies = []
    for observation in observations:
        if observation.observation_version != "snippet-observation-v2":
            continue
        dependency = ContextPermissionDependency(
            permission_id=(
                "research_snippet_rights:" + observation.rights_authority_id
                if observation.rights_authority_id
                else "research_snippet_rights:" + observation.provider
            ),
            version=(
                f"{observation.rights_epoch}:{observation.rights_reference}"
                if observation.rights_authority_id
                else observation.rights_reference or "unverified"
            ),
            purpose="retain and disclose the exact source-rights authority and epoch",
        )
        if dependency not in dependencies:
            dependencies.append(dependency)
    return tuple(dependencies)


class ResearchSourceRightsRevalidator:
    def __init__(self, settings, *, adapter=None, delegate=None):
        self.settings, self.adapter, self.delegate = settings, adapter, delegate

    @staticmethod
    def supports(dependency):
        return dependency.permission_id.startswith("research_snippet_rights:")

    def is_current(self, dependency):
        if not self.supports(dependency):
            return bool(self.delegate and self.delegate.is_current(dependency))
        from personal_ai.search.runtime import SEARCH_ADAPTERS

        recorded_identity = dependency.permission_id.partition(":")[2]
        provider = recorded_identity.partition(":")[0]
        adapter = self.adapter if self.adapter and self.adapter.name == provider else None
        try:
            if adapter is None:
                registration = SEARCH_ADAPTERS.get(provider)
                if registration is None or registration.operations != ("search",):
                    return False
                adapter = registration.factory(self.settings, None)
            current = normalize_rights_authorization(adapter.authorize_snippets(), provider)
            if current is None:
                return False
            if ":" in recorded_identity:
                return (
                    current.authority_id == recorded_identity
                    and current.dependency_version == dependency.version
                )
            # Historical v1 dependencies were provider-scoped and carried only
            # the opaque preflight reference; retain read compatibility.
            return current.reference == dependency.version
        except Exception:  # noqa: BLE001 - missing/revoked source rights deny all derived reuse
            return False
