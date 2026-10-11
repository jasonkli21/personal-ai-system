"""Deployment-owned context implementation and planning contributions."""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import ContextProvider, ContextProviderFactory


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


EMPTY_CONTEXT_RUNTIME_REGISTRY = ContextRuntimeRegistry()
