"""Deployment-owned context implementation and planning contributions."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import ContextProvider, ContextProviderFactory


@dataclass(frozen=True)
class ContextRuntimeContribution:
    """One independently configured set of executable context extensions."""

    provider_factories: Mapping[str, ContextProviderFactory | ContextProvider]
    planning_rules: Sequence[ContextPlanningRule] = ()
    permission_revalidators: Sequence[object] = ()


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


def compose_context_runtime(
    *contributions: ContextRuntimeContribution,
) -> ContextRuntimeRegistry:
    """Compose domain-neutral contributions and reject ambiguous ownership."""
    providers: dict[str, ContextProviderFactory | ContextProvider] = {}
    rules: list[ContextPlanningRule] = []
    revalidators: list[object] = []
    namespaces: set[str] = set()
    for contribution in contributions:
        overlap = providers.keys() & contribution.provider_factories.keys()
        if overlap:
            raise ValueError("context_runtime_provider_id_duplicate")
        providers.update(contribution.provider_factories)
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
    return ContextRuntimeRegistry(providers, rules, revalidators)


EMPTY_CONTEXT_RUNTIME_REGISTRY = ContextRuntimeRegistry()
