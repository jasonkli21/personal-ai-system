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
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
    ContextSensitivity,
    ExternalDisclosurePolicy,
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


class ApplicationContributionCatalog:
    """Named application registrations that can be installed without shared app branches."""

    ENTRY_POINT_GROUP = "personal_ai.application_contributions"

    def __init__(self, registrations=()):
        self._registrations = {}
        for name, factory in registrations:
            self.register(name, factory)

    @classmethod
    def from_entry_points(cls):
        points = sorted(entry_points(group=cls.ENTRY_POINT_GROUP), key=lambda point: point.name)
        return cls((point.name, point.load()) for point in points)

    def register(self, name: str, factory) -> None:
        if (
            not isinstance(name, str)
            or not name
            or name in self._registrations
            or not callable(factory)
        ):
            raise ValueError("application_contribution_registration_invalid")
        self._registrations[name] = factory

    @property
    def registration_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def extend(self, base: "ApplicationRegistry") -> "ApplicationRegistry":
        contributions = tuple(self._registrations[name]() for name in self.registration_names)
        if any(not isinstance(value, ApplicationContribution) for value in contributions):
            raise ValueError("application_contribution_invalid")
        return base.with_contributions(*contributions)


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


def _capability(
    capability_id: str,
    kind: CapabilityKind,
    *,
    available: bool = False,
    feature_gate: str | None = None,
    reason: str = "application_integration_not_implemented",
) -> CapabilityRegistration:
    return CapabilityRegistration(
        capability_id=capability_id,
        kind=kind,
        available=available,
        feature_gate=feature_gate,
        unavailable_reason=None if available else reason,
    )


def _domain_context_policy(
    version: str,
    declarations: tuple[ContextProviderPolicy, ...],
    *,
    sidecar: ApplicationSidecarPolicy | None = None,
    maximum_model_sensitivity: ContextSensitivity | None = None,
) -> ApplicationContextPolicy:
    """Compose explicit app-owned source rules with shared context policies."""
    shared = ApplicationContextPolicy()
    return ApplicationContextPolicy(
        version=version,
        provider_policies=(*shared.provider_policies, *declarations),
        maximum_model_sensitivity=(maximum_model_sensitivity or shared.maximum_model_sensitivity),
        cross_application="deny",
        sidecar=sidecar or ApplicationSidecarPolicy(),
    )


def _field_policy(
    name: str, *, sensitivity: str = "sensitive", model_disclosure: bool = True
) -> ContextFieldPolicy:
    return ContextFieldPolicy(
        field=name, sensitivity=sensitivity, model_disclosure=model_disclosure
    )


def _operation_policy(
    operation: str,
    fields: tuple[str, ...],
    *,
    restricted_fields: tuple[str, ...] = (),
    sensitivity: ContextSensitivity = "sensitive",
) -> ContextOperationPolicy:
    return ContextOperationPolicy(
        operation=operation,
        fields=tuple(
            _field_policy(
                field,
                sensitivity=("restricted" if field in restricted_fields else sensitivity),
                model_disclosure=field not in restricted_fields,
            )
            for field in fields
        ),
        sensitivity=sensitivity,
    )


def default_application_registry(
    *, contribution_catalog: ApplicationContributionCatalog | None = None
) -> ApplicationRegistry:
    """Build initial manifests with common chat context and comparison modules."""
    from personal_ai.domains.registry import registry as domain_registry

    comparison_modules = domain_registry()
    capabilities = (
        _capability("conversation_history", "context_provider", available=True),
        _capability(
            "ai_memory",
            "context_provider",
            available=True,
            feature_gate="memory_enabled",
        ),
        _capability("global_profile", "context_provider", available=True),
        _capability("client_context", "context_provider", available=True),
        _capability("external_research", "context_provider", available=True),
        _capability(
            "travel.trip_context",
            "context_provider",
            available=True,
            feature_gate="travel_context_enabled",
        ),
        _capability("travel.itinerary_action", "tool", reason="travel_actions_unavailable"),
        _capability(
            "shopping.product_context",
            "context_provider",
            available=True,
            feature_gate="shopping_context_enabled",
        ),
        _capability(
            "shopping.catalog_search",
            "context_provider",
            available=True,
            feature_gate="shopping_context_enabled",
        ),
        _capability("shopping.product_action", "tool", reason="shopping_actions_unavailable"),
        _capability(
            "finance.account_context",
            "context_provider",
            available=True,
            feature_gate="finance_context_enabled",
        ),
        _capability(
            "finance.portfolio_context",
            "context_provider",
            available=True,
            feature_gate="finance_context_enabled",
        ),
        _capability(
            "finance.research_context",
            "context_provider",
            available=True,
            feature_gate="finance_context_enabled",
        ),
        _capability(
            "finance.research_evidence",
            "context_provider",
            available=True,
            feature_gate="finance_context_enabled",
        ),
        _capability("finance.account_action", "tool", reason="finance_actions_unavailable"),
        *(
            _capability(
                provider_id,
                "context_provider",
                available=False,
                reason="health_delegated_identity_contract_unavailable",
            )
            for provider_id in (
                "health.profile_background_context",
                "health.profile_constraints_context",
                "health.profile_preferences_context",
                "health.measurements_context",
                "health.nutrition_context",
                "health.exercise_context",
                "health.sleep_context",
                "health.symptoms_context",
            )
        ),
        _capability("health.record_action", "tool", reason="health_actions_unavailable"),
    )
    definitions = (
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
        ApplicationDefinition(
            application_id="travel",
            display_name="Travel",
            workspace_kind="optional",
            context_provider_ids=("travel.trip_context",),
            tool_ids=("travel.itinerary_action",),
            memory_namespace="travel",
            sensitivity_defaults={
                "conversation": "personal",
                "memory": "personal",
                "domain_context": "sensitive",
                "client_context": "personal",
            },
            context_policy=_domain_context_policy(
                "travel-context-policy-v1",
                (
                    ContextProviderPolicy(
                        provider_id="travel.trip_context",
                        operations=(
                            _operation_policy(
                                "current",
                                (
                                    "trip_title",
                                    "start_date",
                                    "end_date",
                                    "timezone",
                                    "itinerary_overview",
                                    "trip_revision",
                                ),
                            ),
                            _operation_policy(
                                "entity",
                                (
                                    "day_date",
                                    "day_title",
                                    "item_title",
                                    "item_type",
                                    "item_status",
                                    "item_schedule",
                                    "place_name",
                                    "place_category",
                                    "place_address",
                                    "place_source",
                                    "place_attribution",
                                    "reservation_summary",
                                ),
                            ),
                        ),
                    ),
                ),
                sidecar=ApplicationSidecarPolicy(
                    copy_allowed=True,
                    draft_insert_target_ids=("travel.message_composer",),
                ),
            ),
            comparison_domain_ids=("travel",),
        ),
        ApplicationDefinition(
            application_id="shopping",
            display_name="Shopping",
            workspace_kind="optional",
            context_provider_ids=("shopping.product_context", "shopping.catalog_search"),
            tool_ids=("shopping.product_action",),
            memory_namespace="shopping",
            sensitivity_defaults={
                "conversation": "personal",
                "memory": "personal",
                "domain_context": "sensitive",
                "client_context": "personal",
            },
            context_policy=_domain_context_policy(
                "shopping-context-policy-v1",
                (
                    ContextProviderPolicy(
                        provider_id="shopping.product_context",
                        operations=(
                            _operation_policy(
                                "current",
                                (
                                    "project_title",
                                    "project_goal",
                                    "category",
                                    "requirements",
                                    "budget_target",
                                    "budget_maximum",
                                    "budget_currency",
                                    "project_notes",
                                    "project_revision",
                                    "selected_products",
                                ),
                            ),
                        ),
                    ),
                    ContextProviderPolicy(
                        provider_id="shopping.catalog_search",
                        operations=(
                            _operation_policy(
                                "search",
                                ("catalog_observations",),
                            ),
                        ),
                    ),
                ),
            ),
            comparison_domain_ids=("shopping",),
        ),
        ApplicationDefinition(
            application_id="finance",
            display_name="Finance",
            workspace_kind="optional",
            context_provider_ids=(
                "finance.account_context",
                "finance.portfolio_context",
                "finance.research_context",
                "finance.research_evidence",
            ),
            tool_ids=("finance.account_action",),
            memory_namespace="finance",
            sensitivity_defaults={
                "conversation": "sensitive",
                "memory": "sensitive",
                "domain_context": "restricted",
                "client_context": "sensitive",
            },
            context_policy=_domain_context_policy(
                "finance-context-policy-v1",
                (
                    ContextProviderPolicy(
                        provider_id="finance.account_context",
                        operations=(
                            _operation_policy(
                                "current",
                                ("account_summary", "balance_summary"),
                                sensitivity="restricted",
                            ),
                        ),
                    ),
                    ContextProviderPolicy(
                        provider_id="finance.portfolio_context",
                        operations=(
                            _operation_policy(
                                "current",
                                (
                                    "account_summary",
                                    "balance_summary",
                                    "security_summary",
                                    "position_summary",
                                ),
                                sensitivity="restricted",
                            ),
                        ),
                    ),
                    ContextProviderPolicy(
                        provider_id="finance.research_context",
                        operations=(
                            _operation_policy(
                                "current",
                                ("research_thesis",),
                                sensitivity="restricted",
                            ),
                        ),
                    ),
                    ContextProviderPolicy(
                        provider_id="finance.research_evidence",
                        operations=(
                            _operation_policy(
                                "current",
                                ("research_fact",),
                                sensitivity="restricted",
                            ),
                        ),
                    ),
                ),
                sidecar=ApplicationSidecarPolicy(
                    connected_provider_disclosure=ExternalDisclosurePolicy(
                        allowed=False,
                        maximum_sensitivity="restricted",
                    ),
                    manual_external_disclosure=ExternalDisclosurePolicy(
                        allowed=False,
                        maximum_sensitivity="restricted",
                    ),
                    manual_import_reuse={"allowed": False},
                    copy_allowed=True,
                ),
                maximum_model_sensitivity="restricted",
            ),
        ),
        ApplicationDefinition(
            application_id="health",
            display_name="Health",
            workspace_kind="optional",
            context_provider_ids=(
                "health.profile_background_context",
                "health.profile_constraints_context",
                "health.profile_preferences_context",
                "health.measurements_context",
                "health.nutrition_context",
                "health.exercise_context",
                "health.sleep_context",
                "health.symptoms_context",
            ),
            tool_ids=("health.record_action",),
            memory_namespace="health",
            sensitivity_defaults={
                "conversation": "sensitive",
                "memory": "sensitive",
                "domain_context": "restricted",
                "client_context": "sensitive",
            },
            context_policy=_domain_context_policy(
                "health-context-policy-v2",
                tuple(
                    ContextProviderPolicy(
                        provider_id=provider_id,
                        operations=(
                            _operation_policy(
                                operation,
                                fields,
                                sensitivity="restricted",
                            ),
                        ),
                    )
                    for provider_id, operation, fields in (
                        (
                            "health.profile_background_context",
                            "profile",
                            (
                                "record",
                                "notes",
                                "source_kind",
                                "confirmation_status",
                                "validity",
                            ),
                        ),
                        (
                            "health.profile_constraints_context",
                            "profile",
                            (
                                "record",
                                "notes",
                                "source_kind",
                                "confirmation_status",
                                "validity",
                            ),
                        ),
                        (
                            "health.profile_preferences_context",
                            "profile",
                            (
                                "record",
                                "notes",
                                "source_kind",
                                "confirmation_status",
                                "validity",
                            ),
                        ),
                        (
                            "health.measurements_context",
                            "history",
                            (
                                "record",
                                "domain",
                                "notes",
                                "time",
                                "interval_end",
                                "units",
                                "source_kind",
                                "confirmation_status",
                                "quality",
                                "uncertainty",
                            ),
                        ),
                        *(
                            (
                                provider_id,
                                "history",
                                (
                                    "record",
                                    "domain",
                                    "notes",
                                    "time",
                                    "interval_end",
                                    "units",
                                    "source_kind",
                                    "confirmation_status",
                                    "quality",
                                    "uncertainty",
                                ),
                            )
                            for provider_id in (
                                "health.nutrition_context",
                                "health.exercise_context",
                                "health.sleep_context",
                                "health.symptoms_context",
                            )
                        ),
                    )
                ),
                sidecar=ApplicationSidecarPolicy(
                    connected_provider_disclosure=ExternalDisclosurePolicy(
                        allowed=False,
                        maximum_sensitivity="restricted",
                    ),
                    manual_external_disclosure=ExternalDisclosurePolicy(
                        allowed=False,
                        maximum_sensitivity="restricted",
                    ),
                    manual_import_reuse={"allowed": False},
                    copy_allowed=True,
                ),
                maximum_model_sensitivity="restricted",
            ),
        ),
    )
    from personal_ai.federation.deployment import install_federation_metadata

    definitions, capabilities = install_federation_metadata(definitions, capabilities)
    registry = ApplicationRegistry(definitions, capabilities, comparison_modules=comparison_modules)
    catalog = contribution_catalog or ApplicationContributionCatalog.from_entry_points()
    return catalog.extend(registry) if catalog.registration_names else registry


def application_registry_for(request) -> ApplicationRegistry:
    """Use an app-injected registry when present, otherwise the built-in registry."""
    try:
        configured = getattr(request.app.state, "application_registry", None)
    except (AttributeError, RuntimeError):
        configured = None
    return configured or default_application_registry()
