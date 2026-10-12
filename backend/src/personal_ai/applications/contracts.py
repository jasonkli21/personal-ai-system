"""Typed, versioned metadata for registered applications and capabilities."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.auth.scope import RequestScope
from personal_ai.contracts.context_categories import (
    CONTEXT_SOURCE_CLASSES,
    ContextSourceClass,
)
from personal_ai.contracts.context_references import ContextEntityReference
from personal_ai.contracts.federation import FederationExportDeclaration
from personal_ai.mutations.contracts import MutationOperationDeclaration, OperationRef

ApplicationId = str
Sensitivity = Literal["public", "personal", "sensitive", "restricted"]
ContextSensitivity = Literal["public", "personal", "sensitive", "restricted", "unknown"]
ContextOperation = Literal["profile", "current", "entity", "history", "search"]
CapabilityKind = Literal["context_provider", "tool"]
_VIEW_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$"
_APPLICATION_ID_PATTERN = r"^[a-z][a-z0-9_-]{1,40}$"
_CAPABILITY_ID_PATTERN = r"^[a-z][a-z0-9_.-]{1,80}$"

SENSITIVITY_RANK: dict[ContextSensitivity, int] = {
    "public": 0,
    "personal": 1,
    "sensitive": 2,
    "restricted": 3,
    "unknown": 4,
}


class ApplicationRegistryError(ValueError):
    """A clear, stable registration or lookup failure."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class SensitivityDefaults(BaseModel):
    """Default classifications for context source categories."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation: Sensitivity = "personal"
    memory: Sensitivity = "personal"
    domain_context: Sensitivity = "sensitive"
    client_context: Sensitivity = "personal"


class ContextFieldPolicy(BaseModel):
    """Server-owned classification and disclosure decision for one field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,79}$")
    sensitivity: ContextSensitivity
    source_access: bool = True
    model_disclosure: bool = True


class ContextOperationPolicy(BaseModel):
    """Provider operation allowlist plus field and default sensitivity rules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: ContextOperation
    fields: tuple[ContextFieldPolicy, ...] = Field(default=(), max_length=32)
    allow_dynamic_fields: bool = False
    dynamic_sensitivity: ContextSensitivity | None = None
    allow_empty_fields: bool = False
    sensitivity: ContextSensitivity = "unknown"
    source_access: bool = True
    model_disclosure: bool = True

    @model_validator(mode="after")
    def validate_field_policy(self) -> "ContextOperationPolicy":
        names = [item.field for item in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("context_policy_fields_must_be_unique")
        if self.allow_dynamic_fields != (self.dynamic_sensitivity is not None):
            raise ValueError("context_policy_dynamic_sensitivity_required")
        return self


class ContextProviderPolicy(BaseModel):
    """The operations an application may read and disclose for one provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(pattern=_CAPABILITY_ID_PATTERN, min_length=2, max_length=81)
    operations: tuple[ContextOperationPolicy, ...] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def operations_are_unique(self) -> "ContextProviderPolicy":
        operations = [item.operation for item in self.operations]
        if len(operations) != len(set(operations)):
            raise ValueError("context_policy_operations_must_be_unique")
        return self


def _default_context_provider_policies() -> tuple[ContextProviderPolicy, ...]:
    """Policies for the bounded shared context adapters already in the runtime."""

    def fields(names: tuple[str, ...], sensitivity: ContextSensitivity):
        return tuple(ContextFieldPolicy(field=name, sensitivity=sensitivity) for name in names)

    return (
        ContextProviderPolicy(
            provider_id="conversation_history",
            operations=(ContextOperationPolicy(
                operation="history",
                fields=fields(("content", "role", "created_at", "id", "source_message_ids"), "sensitive"),
                sensitivity="sensitive",
            ),),
        ),
        ContextProviderPolicy(
            provider_id="ai_memory",
            operations=(ContextOperationPolicy(
                operation="search",
                fields=fields(("content", "memory_type", "effective_at"), "sensitive"),
                sensitivity="sensitive",
            ),),
        ),
        ContextProviderPolicy(
            provider_id="global_profile",
            operations=(ContextOperationPolicy(
                operation="profile",
                fields=fields(("preferred_units", "locale", "response_style", "answer_length"), "personal"),
                sensitivity="personal",
            ),),
        ),
        ContextProviderPolicy(
            provider_id="client_context",
            operations=(ContextOperationPolicy(
                operation="profile",
                allow_dynamic_fields=True,
                dynamic_sensitivity="sensitive",
                sensitivity="sensitive",
            ),),
        ),
        ContextProviderPolicy(
            provider_id="external_research",
            operations=(ContextOperationPolicy(
                operation="search",
                fields=fields(
                    ("passage", "observed_at", "expires_at", "evidence_record"),
                    "sensitive",
                ),
                sensitivity="sensitive",
            ),),
        ),
        ContextProviderPolicy(
            provider_id="booking.document_extraction",
            operations=(ContextOperationPolicy(
                operation="current",
                fields=fields(("document_text", "media_type"), "sensitive"),
                sensitivity="sensitive",
            ),),
        ),
        ContextProviderPolicy(
            provider_id="travel.itinerary_context",
            operations=(ContextOperationPolicy(
                operation="current",
                fields=fields(("itinerary_context",), "sensitive"),
                sensitivity="sensitive",
            ),),
        ),
    )


class ApplicationContextPolicy(BaseModel):
    """Versioned server policy for context reads, disclosure, and inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["application-context-policy-v1"] = "application-context-policy-v1"
    version: str = Field(default="application-context-policy-v1", min_length=1, max_length=100)
    provider_policies: tuple[ContextProviderPolicy, ...] = Field(
        default_factory=_default_context_provider_policies, max_length=32
    )
    external_execution_modes: tuple[Literal["connected_provider", "manual_external"], ...] = ()
    maximum_model_sensitivity: ContextSensitivity = "sensitive"
    unknown_sensitivity: Literal["deny"] = "deny"
    cross_application: Literal["deny"] = "deny"
    sidecar: "ApplicationSidecarPolicy" = Field(default_factory=lambda: ApplicationSidecarPolicy())

    @model_validator(mode="after")
    def providers_are_unique(self) -> "ApplicationContextPolicy":
        providers = [item.provider_id for item in self.provider_policies]
        if len(providers) != len(set(providers)):
            raise ValueError("context_policy_providers_must_be_unique")
        if self.maximum_model_sensitivity == "unknown":
            raise ValueError("unknown_model_sensitivity_cannot_be_allowed")
        if len(set(self.external_execution_modes)) != len(self.external_execution_modes):
            raise ValueError("external_execution_modes_must_be_unique")
        return self

    def operation(self, provider_id: str, operation: ContextOperation) -> ContextOperationPolicy | None:
        provider = next(
            (item for item in self.provider_policies if item.provider_id == provider_id), None
        )
        if provider is None:
            return None
        return next((item for item in provider.operations if item.operation == operation), None)


class ExternalDisclosurePolicy(BaseModel):
    """Narrow one external execution lane by category and sensitivity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool = True
    allowed_context_categories: tuple[ContextSourceClass, ...] = Field(
        default=CONTEXT_SOURCE_CLASSES,
        max_length=9,
    )
    maximum_sensitivity: Literal["public", "personal", "sensitive", "restricted"] = "sensitive"

    @model_validator(mode="after")
    def categories_are_unique(self) -> "ExternalDisclosurePolicy":
        if len(set(self.allowed_context_categories)) != len(self.allowed_context_categories):
            raise ValueError("external_disclosure_categories_must_be_unique")
        return self


class ManualImportReusePolicy(BaseModel):
    """Narrow whether imported manual turns may feed later derived context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool = True
    maximum_sensitivity: Literal["public", "personal", "sensitive", "restricted"] = "restricted"

    def allows(self, sensitivity: ContextSensitivity | None) -> bool:
        if not self.allowed or sensitivity is None or sensitivity == "unknown":
            return False
        return SENSITIVITY_RANK[sensitivity] <= SENSITIVITY_RANK[self.maximum_sensitivity]


class ApplicationSidecarPolicy(BaseModel):
    """Application-owned narrowing hooks for shared sidecar disclosure and actions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connected_provider_disclosure: ExternalDisclosurePolicy = Field(
        default_factory=ExternalDisclosurePolicy
    )
    manual_external_disclosure: ExternalDisclosurePolicy = Field(
        default_factory=ExternalDisclosurePolicy
    )
    manual_import_reuse: ManualImportReusePolicy = Field(
        default_factory=ManualImportReusePolicy
    )
    mutation_operations: tuple[OperationRef, ...] = Field(default=(), max_length=16)
    copy_allowed: bool = True
    draft_insert_target_ids: tuple[str, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def action_targets_are_valid(self) -> "ApplicationSidecarPolicy":
        keys = [(item.operation_id, item.version) for item in self.mutation_operations]
        if len(keys) != len(set(keys)):
            raise ValueError("sidecar_mutation_operations_duplicate")
        values = self.draft_insert_target_ids
        if len(values) != len(set(values)) or any(
            not re.fullmatch(_VIEW_ID_PATTERN, value) for value in values
        ):
            raise ValueError("sidecar_draft_insert_target_ids_invalid")
        return self

    def disclosure_for(
        self, mode: Literal["connected_provider", "manual_external"]
    ) -> ExternalDisclosurePolicy:
        return (
            self.connected_provider_disclosure
            if mode == "connected_provider"
            else self.manual_external_disclosure
        )


class ApplicationLaunchContext(BaseModel):
    """Versioned, bounded host hints; every identifier remains non-authoritative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["application-launch-v1"] = "application-launch-v1"
    application_id: str = Field(pattern=_APPLICATION_ID_PATTERN, min_length=2, max_length=42)
    workspace_id: str | None = Field(default=None, max_length=100)
    entity_refs: tuple[ContextEntityReference, ...] = Field(default=(), max_length=16)
    view_id: str | None = Field(default=None, pattern=_VIEW_ID_PATTERN)
    conversation_id: str = Field(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    client_context: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=32
    )

    @model_validator(mode="after")
    def launch_hints_are_bounded_and_scoped(self) -> "ApplicationLaunchContext":
        import json

        try:
            encoded_context = json.dumps(
                self.client_context, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError) as error:
            raise ValueError("application_launch_client_context_invalid") from error
        if len(encoded_context) > 4_096:
            raise ValueError("application_launch_client_context_too_large")
        if len(set(self.entity_refs)) != len(self.entity_refs):
            raise ValueError("application_launch_entity_refs_must_be_unique")
        if any(
            reference.application_id != self.application_id
            or reference.workspace_id != self.workspace_id
            for reference in self.entity_refs
        ):
            raise ValueError("application_launch_entity_scope_mismatch")
        return self

    def validate_for(self, scope: RequestScope, conversation_id) -> None:
        """Bind advisory launch hints to server-derived scope and the route target."""
        if (
            self.application_id != scope.application_id
            or self.workspace_id != scope.workspace_id
            or self.client_context != scope.client_context
            or self.conversation_id != str(conversation_id)
        ):
            raise ValueError("application_launch_scope_mismatch")


class CrossApplicationDeclaration(BaseModel):
    """Declarative cross-app metadata; this contract never grants a data share."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["disabled", "declaration_only"] = "disabled"
    application_ids: tuple[str, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def declaration_is_consistent(self) -> "CrossApplicationDeclaration":
        if len(set(self.application_ids)) != len(self.application_ids):
            raise ValueError("cross_application_ids_must_be_unique")
        if any(not re.fullmatch(_APPLICATION_ID_PATTERN, item) for item in self.application_ids):
            raise ValueError("cross_application_id_invalid")
        if self.mode == "disabled" and self.application_ids:
            raise ValueError("disabled_cross_application_declaration_has_references")
        if self.mode == "declaration_only" and not self.application_ids:
            raise ValueError("cross_application_declaration_requires_references")
        return self


class ApplicationBudgetHints(BaseModel):
    """Optional advisory context budgets; these do not select a model/provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context_tokens: int | None = Field(default=None, ge=1, le=128_000)
    memory_tokens: int | None = Field(default=None, ge=1, le=64_000)
    domain_context_tokens: int | None = Field(default=None, ge=1, le=64_000)

    @model_validator(mode="after")
    def child_budgets_fit_total(self) -> "ApplicationBudgetHints":
        children = [value for value in (self.memory_tokens, self.domain_context_tokens) if value]
        if self.context_tokens is not None and children and sum(children) > self.context_tokens:
            raise ValueError("application_budget_hints_exceed_context_budget")
        return self


class ApplicationDefinition(BaseModel):
    """A registered app's capabilities and defaults, separate from domain state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["application-definition-v1"] = "application-definition-v1"
    application_id: str = Field(pattern=_APPLICATION_ID_PATTERN, min_length=2, max_length=42)
    display_name: str = Field(min_length=1, max_length=100)
    workspace_kind: Literal["unsupported", "optional", "required"] = "optional"
    context_provider_ids: tuple[str, ...] = Field(default=(), max_length=16)
    tool_ids: tuple[str, ...] = Field(default=(), max_length=16)
    memory_namespace: str = Field(pattern=_APPLICATION_ID_PATTERN, min_length=2, max_length=42)
    sensitivity_defaults: SensitivityDefaults = Field(default_factory=SensitivityDefaults)
    context_policy: ApplicationContextPolicy = Field(default_factory=ApplicationContextPolicy)
    cross_application: CrossApplicationDeclaration = Field(
        default_factory=CrossApplicationDeclaration
    )
    mutation_operations: tuple[MutationOperationDeclaration, ...] = Field(default=(), max_length=16)
    federation_exports: tuple[FederationExportDeclaration, ...] = Field(default=(), max_length=16)
    budget_hints: ApplicationBudgetHints = Field(default_factory=ApplicationBudgetHints)
    comparison_domain_ids: tuple[str, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def references_are_unambiguous(self) -> "ApplicationDefinition":
        keys = [(item.operation_id, item.version) for item in self.mutation_operations]
        if len(keys) != len(set(keys)):
            raise ValueError("application_mutation_operations_duplicate")
        if any((item.operation_id, item.version) not in keys
               for item in self.context_policy.sidecar.mutation_operations):
            raise ValueError("sidecar_mutation_operation_undeclared")
        for name, values in (
            ("context_provider_ids", self.context_provider_ids),
            ("tool_ids", self.tool_ids),
            ("comparison_domain_ids", self.comparison_domain_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name}_must_be_unique")
        for capability_id in (*self.context_provider_ids, *self.tool_ids):
            if not re.fullmatch(_CAPABILITY_ID_PATTERN, capability_id):
                raise ValueError("application_capability_id_invalid")
        for domain_id in self.comparison_domain_ids:
            if not re.fullmatch(r"^[a-z][a-z0-9-]{1,40}$", domain_id):
                raise ValueError("application_comparison_domain_id_invalid")
        if self.application_id in self.cross_application.application_ids:
            raise ValueError("application_cannot_declare_itself_cross_application")
        return self


class CapabilityRegistration(BaseModel):
    """Registry metadata for one context provider or tool implementation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["application-capability-v1"] = "application-capability-v1"
    capability_id: str = Field(pattern=_CAPABILITY_ID_PATTERN, min_length=2, max_length=81)
    kind: CapabilityKind
    # `available` means an implementation exists. A feature gate can still
    # disable its use for a given deployment without turning it into a stub.
    available: bool = False
    feature_gate: Literal[
        "memory_enabled",
        "travel_context_enabled",
        "shopping_context_enabled",
        "finance_context_enabled",
        "health_context_enabled",
    ] | None = None
    unavailable_reason: str | None = Field(default=None, min_length=1, max_length=160)
    read_only_context: bool = False
    result_fields: tuple[str, ...] = Field(default=(), max_length=32)
    max_result_bytes: int | None = Field(default=None, ge=1, le=65_536)

    @model_validator(mode="after")
    def availability_is_consistent(self) -> "CapabilityRegistration":
        if self.available and self.unavailable_reason is not None:
            raise ValueError("available_capability_has_unavailable_reason")
        if not self.available and self.unavailable_reason is None:
            raise ValueError("unavailable_capability_requires_reason")
        if self.kind == "context_provider" and (
            self.read_only_context or self.result_fields or self.max_result_bytes is not None
        ):
            raise ValueError("context_provider_has_tool_result_metadata")
        if self.kind == "tool":
            if self.read_only_context and (not self.result_fields or self.max_result_bytes is None):
                raise ValueError("read_context_tool_requires_bounded_result_contract")
            if not self.read_only_context and (self.result_fields or self.max_result_bytes is not None):
                raise ValueError("non_read_context_tool_has_result_contract")
            if len(self.result_fields) != len(set(self.result_fields)):
                raise ValueError("tool_result_fields_must_be_unique")
        return self

    def is_enabled(self, feature_flags: dict[str, bool] | None = None) -> bool:
        """Return whether this implementation is enabled by supplied config."""
        if not self.available:
            return False
        if self.feature_gate is None:
            return True
        return bool((feature_flags or {}).get(self.feature_gate, False))


class ApplicationContextRequest(BaseModel):
    """Resolved manifest metadata paired with the authenticated request scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    definition: ApplicationDefinition
    scope: RequestScope
    context_provider_capabilities: tuple[CapabilityRegistration, ...] = Field(
        default=(), max_length=32
    )
    tool_capabilities: tuple[CapabilityRegistration, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def manifest_matches_scope(self) -> "ApplicationContextRequest":
        if self.definition.application_id != self.scope.application_id:
            raise ValueError("application_definition_scope_mismatch")
        if self.definition.workspace_kind == "unsupported" and self.scope.workspace_id is not None:
            raise ValueError("application_workspace_unsupported")
        if self.definition.workspace_kind == "required" and self.scope.workspace_id is None:
            raise ValueError("application_workspace_required")
        if any(item.kind != "context_provider" for item in self.context_provider_capabilities):
            raise ValueError("application_context_provider_kind_invalid")
        if any(item.kind != "tool" for item in self.tool_capabilities):
            raise ValueError("application_tool_capability_kind_invalid")
        for capabilities in (self.context_provider_capabilities, self.tool_capabilities):
            ids = [item.capability_id for item in capabilities]
            if len(ids) != len(set(ids)):
                raise ValueError("application_context_capability_duplicate")
        return self
