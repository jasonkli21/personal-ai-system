"""Deterministic application and capability registration."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.metadata import entry_points
from types import MappingProxyType
from typing import Protocol

from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationDefinition,
    ApplicationRegistryError,
    ApplicationSidecarPolicy,
    CapabilityKind,
    CapabilityRegistration,
    ContextProviderPolicy,
)
from personal_ai.auth.scope import WorkspaceAuthorizer

SHARED_CONTEXT_PROVIDER_IDS = (
    "conversation_history",
    "ai_memory",
    "external_research",
    "global_profile",
    "client_context",
)


class _ComparisonModule(Protocol):
    registration: object


@dataclass(frozen=True, slots=True)
class ApplicationContribution:
    """Application-owned registration metadata installed through the production seam."""

    definitions: tuple[ApplicationDefinition, ...]
    capabilities: tuple[CapabilityRegistration, ...] = ()
    comparison_modules: Mapping[str, _ComparisonModule] | None = None
    workspace_authorizers: Mapping[str, WorkspaceAuthorizer] | None = None
    # Trusted composition only: all routes retain the platform auth middleware.
    routers: tuple[object, ...] = ()
    exception_handlers: Mapping[type[Exception], object] | None = None
    context_policy_extensions: Mapping[str, tuple[ContextProviderPolicy, ...]] | None = None


class ApplicationContributionCatalog:
    """Named application registrations that can be installed without shared app branches."""

    ENTRY_POINT_GROUP = "personal_ai.application_contributions"

    def __init__(self, registrations=()):
        self._registrations = {}
        for name, factory in registrations:
            self.register(name, factory)

    @classmethod
    def from_entry_points(cls, *, selected=None):
        from personal_ai.applications.selection import (
            load_selected_entry_points,
            selected_contribution_names,
        )

        names = selected_contribution_names() if selected is None else selected
        return cls(load_selected_entry_points(entry_points(group=cls.ENTRY_POINT_GROUP), names))

    def register(self, name: str, factory) -> None:
        if (
            not isinstance(name, str)
            or not name
            or name in self._registrations
            or not callable(factory)
        ):
            raise ValueError("application_contribution_registration_invalid")
        self._registrations[name] = factory
        self._contributions = None

    @property
    def registration_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def contributions(self) -> tuple[ApplicationContribution, ...]:
        if getattr(self, "_contributions", None) is None:
            contributions = tuple(self._registrations[name]() for name in self.registration_names)
            if any(not isinstance(value, ApplicationContribution) for value in contributions):
                raise ValueError("application_contribution_invalid")
            self._contributions = contributions
        return self._contributions

    def extend(self, base: "ApplicationRegistry") -> "ApplicationRegistry":
        return base.with_contributions(*self.contributions())


class ApplicationNotRegisteredError(ApplicationRegistryError):
    def __init__(self, application_id: str) -> None:
        self.application_id = application_id
        super().__init__("application_not_registered")


@dataclass(frozen=True, slots=True)
class RegisteredApplication:
    """An app manifest composed with its referenced capability metadata."""

    definition: ApplicationDefinition
    context_providers: tuple[CapabilityRegistration, ...]
    tools: tuple[CapabilityRegistration, ...]
    comparison_modules: tuple[_ComparisonModule, ...]


class ApplicationRegistry:
    """Immutable-by-interface manifest registry, independently constructible in tests."""

    def __init__(
        self,
        definitions: Iterable[ApplicationDefinition],
        capabilities: Iterable[CapabilityRegistration] = (),
        *,
        comparison_modules: Mapping[str, _ComparisonModule] | None = None,
        workspace_authorizers: Mapping[str, WorkspaceAuthorizer] | None = None,
    ) -> None:
        definition_by_id: dict[str, ApplicationDefinition] = {}
        for definition in definitions:
            if definition.application_id in definition_by_id:
                raise ApplicationRegistryError(
                    "application_definition_duplicate",
                    f"Duplicate application definition: {definition.application_id}",
                )
            definition_by_id[definition.application_id] = definition

        capability_values = list(capabilities)
        registered_ids = {item.capability_id for item in capability_values}
        if "conversation_history" not in registered_ids:
            capability_values.append(
                CapabilityRegistration(
                    capability_id="conversation_history",
                    kind="context_provider",
                    available=True,
                )
            )
        if "ai_memory" not in registered_ids:
            capability_values.append(
                CapabilityRegistration(
                    capability_id="ai_memory",
                    kind="context_provider",
                    available=True,
                    feature_gate="memory_enabled",
                )
            )
        if "global_profile" not in registered_ids:
            capability_values.append(
                CapabilityRegistration(
                    capability_id="global_profile",
                    kind="context_provider",
                    available=True,
                )
            )
        if "external_research" not in registered_ids:
            capability_values.append(
                CapabilityRegistration(
                    capability_id="external_research",
                    kind="context_provider",
                    available=True,
                )
            )
        if "client_context" not in registered_ids:
            capability_values.append(
                CapabilityRegistration(
                    capability_id="client_context",
                    kind="context_provider",
                    available=True,
                )
            )

        capability_by_key: dict[tuple[CapabilityKind, str], CapabilityRegistration] = {}
        capability_ids: set[str] = set()
        for capability in capability_values:
            key = (capability.kind, capability.capability_id)
            if capability.capability_id in capability_ids:
                raise ApplicationRegistryError(
                    "application_capability_duplicate",
                    f"Duplicate capability registration: {capability.capability_id}",
                )
            capability_ids.add(capability.capability_id)
            capability_by_key[key] = capability

        comparison_modules = dict(comparison_modules or {})
        for domain_id, module in comparison_modules.items():
            if getattr(module.registration, "domain_id", None) != domain_id:
                raise ApplicationRegistryError("comparison_module_identity_mismatch")

        registrations: dict[str, RegisteredApplication] = {}
        for definition in definition_by_id.values():
            app_providers = self._resolve_capabilities(
                definition, "context_provider", definition.context_provider_ids, capability_by_key
            )
            shared_providers = self._resolve_capabilities(
                definition,
                "context_provider",
                SHARED_CONTEXT_PROVIDER_IDS,
                capability_by_key,
            )
            providers = shared_providers + tuple(
                provider
                for provider in app_providers
                if provider.capability_id not in SHARED_CONTEXT_PROVIDER_IDS
            )
            tools = self._resolve_capabilities(
                definition, "tool", definition.tool_ids, capability_by_key
            )
            missing_domains = set(definition.comparison_domain_ids) - set(comparison_modules)
            if missing_domains:
                missing = ", ".join(sorted(missing_domains))
                raise ApplicationRegistryError(
                    "application_comparison_domain_unknown",
                    f"Application {definition.application_id} references unknown comparison domain(s): {missing}",
                )
            registrations[definition.application_id] = RegisteredApplication(
                definition=definition,
                context_providers=providers,
                tools=tools,
                comparison_modules=tuple(
                    comparison_modules[domain_id] for domain_id in definition.comparison_domain_ids
                ),
            )

        for definition in definition_by_id.values():
            unknown_cross_app_ids = set(definition.cross_application.application_ids) - set(
                definition_by_id
            )
            if unknown_cross_app_ids:
                missing = ", ".join(sorted(unknown_cross_app_ids))
                raise ApplicationRegistryError(
                    "application_cross_reference_unknown",
                    f"Application {definition.application_id} references unregistered application(s): {missing}",
                )

        self._registrations = MappingProxyType(registrations)
        self._capabilities = MappingProxyType(capability_by_key)
        self._comparison_modules = MappingProxyType(comparison_modules)
        workspace_authorizers = dict(workspace_authorizers or {})
        if set(workspace_authorizers) - set(definition_by_id):
            raise ApplicationRegistryError("workspace_authorizer_application_unknown")
        if any(
            not callable(getattr(authorizer, "is_member", None))
            for authorizer in workspace_authorizers.values()
        ):
            raise ApplicationRegistryError("workspace_authorizer_invalid")
        self._workspace_authorizers = MappingProxyType(workspace_authorizers)

    @staticmethod
    def _resolve_capabilities(
        definition: ApplicationDefinition,
        kind: CapabilityKind,
        capability_ids: tuple[str, ...],
        available: Mapping[tuple[CapabilityKind, str], CapabilityRegistration],
    ) -> tuple[CapabilityRegistration, ...]:
        resolved = []
        for capability_id in capability_ids:
            capability = available.get((kind, capability_id))
            if capability is None:
                raise ApplicationRegistryError(
                    "application_capability_unknown",
                    f"Application {definition.application_id} references unknown {kind}: {capability_id}",
                )
            resolved.append(capability)
        return tuple(resolved)

    @property
    def application_ids(self) -> frozenset[str]:
        return frozenset(self._registrations)

    @property
    def capabilities(self) -> tuple[CapabilityRegistration, ...]:
        return tuple(self._capabilities.values())

    @property
    def comparison_modules(self) -> Mapping[str, _ComparisonModule]:
        return self._comparison_modules

    @property
    def workspace_authorizer(self) -> WorkspaceAuthorizer:
        """Return a fail-closed dispatcher for authorities installed with app manifests."""
        authorities = self._workspace_authorizers

        class RegisteredWorkspaceAuthorizer:
            def is_member(self, principal, application_id: str, workspace_id: str) -> bool:
                authorizer = authorities.get(application_id)
                return bool(
                    authorizer and authorizer.is_member(principal, application_id, workspace_id)
                )

        return RegisteredWorkspaceAuthorizer()

    @property
    def workspace_authorizers(self) -> Mapping[str, WorkspaceAuthorizer]:
        return self._workspace_authorizers

    def with_contributions(self, *contributions: ApplicationContribution) -> "ApplicationRegistry":
        definitions = [registration.definition for registration in self._registrations.values()]
        capabilities = list(self.capabilities)
        comparison_modules = dict(self._comparison_modules)
        workspace_authorizers = dict(self._workspace_authorizers)
        for contribution in contributions:
            definitions.extend(contribution.definitions)
            capabilities.extend(contribution.capabilities)
            contributed_modules = dict(contribution.comparison_modules or {})
            if comparison_modules.keys() & contributed_modules.keys():
                raise ApplicationRegistryError("application_comparison_module_duplicate")
            comparison_modules.update(contributed_modules)
            contributed_authorizers = dict(contribution.workspace_authorizers or {})
            if workspace_authorizers.keys() & contributed_authorizers.keys():
                raise ApplicationRegistryError("workspace_authorizer_duplicate")
            workspace_authorizers.update(contributed_authorizers)
            for application_id, policies in (contribution.context_policy_extensions or {}).items():
                if application_id not in {item.application_id for item in definitions}:
                    raise ApplicationRegistryError("application_policy_extension_unknown")
                updated = []
                for definition in definitions:
                    if definition.application_id == application_id:
                        policy = definition.context_policy
                        policy = ApplicationContextPolicy.model_validate(
                            {
                                **policy.model_dump(),
                                "provider_policies": (*policy.provider_policies, *policies),
                            }
                        )
                        definition = definition.model_copy(update={"context_policy": policy})
                    updated.append(definition)
                definitions = updated
        return ApplicationRegistry(
            definitions,
            capabilities,
            comparison_modules=comparison_modules,
            workspace_authorizers=workspace_authorizers,
        )

    def get(self, application_id: str) -> ApplicationDefinition:
        try:
            return self._registrations[application_id].definition
        except KeyError as error:
            raise ApplicationNotRegisteredError(application_id) from error

    def registration(self, application_id: str) -> RegisteredApplication:
        try:
            return self._registrations[application_id]
        except KeyError as error:
            raise ApplicationNotRegisteredError(application_id) from error

    def capability(
        self, application_id: str, capability_id: str, *, kind: CapabilityKind
    ) -> CapabilityRegistration:
        registration = self.registration(application_id)
        declared_ids = (
            tuple(provider.capability_id for provider in registration.context_providers)
            if kind == "context_provider"
            else tuple(tool.capability_id for tool in registration.tools)
        )
        if capability_id not in declared_ids:
            raise ApplicationRegistryError("application_capability_not_declared")
        return self._capabilities[(kind, capability_id)]


def default_application_registry(
    *, contribution_catalog: ApplicationContributionCatalog | None = None
) -> ApplicationRegistry:
    """Builtin standalone consumer; installed code requires explicit selection."""
    registry = ApplicationRegistry(
        (
            ApplicationDefinition(
                application_id="personal_ai",
                display_name="Personal AI",
                workspace_kind="optional",
                memory_namespace="personal_ai",
                context_policy=ApplicationContextPolicy(
                    version="personal-ai-context-policy-v2",
                    external_execution_modes=("connected_provider", "manual_external"),
                    maximum_model_sensitivity="sensitive",
                    sidecar=ApplicationSidecarPolicy(
                        manual_import_reuse={"allowed": True},
                        copy_allowed=True,
                        draft_insert_target_ids=("personal_ai.message_composer",),
                    ),
                ),
            ),
        )
    )
    catalog = (
        ApplicationContributionCatalog.from_entry_points()
        if contribution_catalog is None
        else contribution_catalog
    )
    return catalog.extend(registry)


def application_registry_for(request) -> ApplicationRegistry:
    """Use an app-injected registry when present, otherwise the built-in registry."""
    try:
        configured = getattr(request.app.state, "application_registry", None)
    except (AttributeError, RuntimeError):
        configured = None
    return configured or default_application_registry()
