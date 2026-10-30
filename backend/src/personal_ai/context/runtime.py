"""Deployment-owned context implementation and planning contributions."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from types import MappingProxyType

from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import ContextProvider, ContextProviderFactory


@dataclass(frozen=True)
class ContextRuntimeContribution:
    """One independently configured set of executable context extensions."""

    provider_factories: Mapping[str, ContextProviderFactory | ContextProvider]
    planning_rules: Sequence[ContextPlanningRule] = ()
    permission_revalidators: Sequence[object] = ()
    export_adapters: Mapping[str, object] = field(default_factory=dict)
    federation_cases: Sequence[object] = ()
    mutation_adapters: Mapping[tuple[str, str, int], object] = field(default_factory=dict)
    # Historical versions are observation/reconciliation-only and are keyed by
    # their immutable contract fingerprint so same-version semantic changes coexist.
    mutation_reconciliation_adapters: Mapping[tuple[str, str, int, str], object] = field(
        default_factory=dict
    )


class ContextRuntimeContributionCatalog:
    """Named startup registrations that can be extended without app branches."""

    ENTRY_POINT_GROUP = "personal_ai.context_contributions"

    def __init__(self, registrations=()):
        self._registrations: dict[str, Callable] = {}
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

    def register(self, name: str, factory: Callable) -> None:
        if (
            not isinstance(name, str)
            or not name
            or name in self._registrations
            or not callable(factory)
        ):
            raise ValueError("context_runtime_registration_invalid")
        self._registrations[name] = factory

    @property
    def registration_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def compose(self, settings):
        contributions = tuple(
            self._registrations[name](settings) for name in self.registration_names
        )
        if any(not isinstance(value, ContextRuntimeContribution) for value in contributions):
            raise ValueError("context_runtime_contribution_invalid")
        return compose_context_runtime(*contributions)


class ContextPermissionRevalidatorRegistry:
    """Route persisted permission dependencies to their owning authority.

    A validator must explicitly claim a dependency before its answer is used;
    unknown dependency namespaces fail closed. This keeps domain authorization
    in registered adapters while preserving one shared builder/dispatch path.
    """

    def __init__(self, validators: Sequence[object] = ()) -> None:
        self.validators = tuple(validators)

    def is_current(self, dependency) -> bool:
        for validator in self.validators:
            supports = getattr(validator, "supports", None)
            if callable(supports) and supports(dependency):
                return bool(validator.is_current(dependency))
        return False


class ContextRuntimeRegistry:
    """Keep executable adapters separate from application capability authorization."""

    def __init__(
        self,
        provider_factories: Mapping[str, ContextProviderFactory | ContextProvider] | None = None,
        planning_rules: Sequence[ContextPlanningRule] = (),
        permission_revalidators: Sequence[object] = (),
        export_adapters: Mapping[str, object] | None = None,
        federation_cases: Sequence[object] = (),
        mutation_adapters: Mapping[tuple[str, str, int], object] | None = None,
        mutation_reconciliation_adapters: Mapping[tuple[str, str, int, str], object] | None = None,
    ) -> None:
        providers = dict(provider_factories or {})
        for provider_id, provider in providers.items():
            if provider_id != provider.spec.provider_id:
                raise ValueError("context_runtime_provider_identity_mismatch")
        rule_ids = [rule.rule_id for rule in planning_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("context_runtime_rule_id_duplicate")
        self.provider_factories = MappingProxyType(providers)
        self.planning_rules = tuple(planning_rules)
        self.permission_revalidators = tuple(permission_revalidators)
        self.export_adapters = MappingProxyType(dict(export_adapters or {}))
        self.federation_cases = tuple(federation_cases)
        from personal_ai.mutations.registration import validate_adapters

        self.mutation_adapters = MappingProxyType(validate_adapters(mutation_adapters or {}))
        from personal_ai.mutations.registration import validate_reconciliation_adapters

        reconciliation = validate_reconciliation_adapters(mutation_reconciliation_adapters or {})
        for key, adapter in self.mutation_adapters.items():
            declaration = adapter.declaration
            reconciliation_key = (*key, declaration.contract_fingerprint)
            existing = reconciliation.get(reconciliation_key)
            if existing is not None and existing is not adapter:
                raise ValueError("mutation_reconciliation_adapter_duplicate")
            reconciliation[reconciliation_key] = adapter
        self.mutation_reconciliation_adapters = MappingProxyType(reconciliation)


def compose_context_runtime(
    *contributions: ContextRuntimeContribution,
) -> ContextRuntimeRegistry:
    """Compose domain-neutral contributions and reject ambiguous ownership."""
    providers: dict[str, ContextProviderFactory | ContextProvider] = {}
    rules: list[ContextPlanningRule] = []
    revalidators: list[object] = []
    namespaces: set[str] = set()
    export_adapters: dict[str, object] = {}
    federation_cases: list[object] = []
    case_provider_ids: set[str] = set()
    mutation_adapters = {}
    mutation_reconciliation_adapters = {}
    for contribution in contributions:
        if mutation_adapters.keys() & contribution.mutation_adapters.keys():
            raise ValueError("mutation_adapter_duplicate")
        mutation_adapters.update(contribution.mutation_adapters)
        if (
            mutation_reconciliation_adapters.keys()
            & contribution.mutation_reconciliation_adapters.keys()
        ):
            raise ValueError("mutation_reconciliation_adapter_duplicate")
        mutation_reconciliation_adapters.update(contribution.mutation_reconciliation_adapters)
        overlap = providers.keys() & contribution.provider_factories.keys()
        if overlap:
            raise ValueError("context_runtime_provider_id_duplicate")
        providers.update(contribution.provider_factories)
        if export_adapters.keys() & contribution.export_adapters.keys():
            raise ValueError("context_runtime_export_adapter_id_duplicate")
        for key, adapter in contribution.export_adapters.items():
            if (
                not isinstance(key, str)
                or not key
                or not callable(getattr(adapter, "authorize_export", None))
                or not callable(getattr(adapter, "resolve_source_policy", None))
                or not callable(getattr(adapter, "fetch", None))
            ):
                raise ValueError("context_runtime_export_adapter_contract_invalid")
        export_adapters.update(contribution.export_adapters)
        for case in contribution.federation_cases:
            provider_id = getattr(getattr(case, "export", None), "provider_id", None)
            if (
                not isinstance(provider_id, str)
                or not provider_id
                or provider_id in case_provider_ids
            ):
                raise ValueError("context_runtime_federation_case_invalid")
            case_provider_ids.add(provider_id)
            federation_cases.append(case)
        rules.extend(contribution.planning_rules)
        for revalidator in contribution.permission_revalidators:
            declared = getattr(revalidator, "permission_namespaces", None)
            if not isinstance(declared, tuple) or not declared:
                raise ValueError("context_runtime_revalidator_namespaces_required")
            if any(not isinstance(value, str) or not value for value in declared):
                raise ValueError("context_runtime_revalidator_namespace_invalid")
            if namespaces.intersection(declared):
                raise ValueError("context_runtime_revalidator_namespace_duplicate")
            namespaces.update(declared)
            revalidators.append(revalidator)
    return ContextRuntimeRegistry(
        providers,
        rules,
        revalidators,
        export_adapters,
        federation_cases,
        mutation_adapters,
        mutation_reconciliation_adapters,
    )


EMPTY_CONTEXT_RUNTIME_REGISTRY = ContextRuntimeRegistry()
