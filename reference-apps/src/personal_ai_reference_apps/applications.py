"""Reference manifests preserve the historical application contracts."""

from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationDefinition,
    ApplicationSidecarPolicy,
    CapabilityKind,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
    ContextSensitivity,
    ExternalDisclosurePolicy,
)
from personal_ai.applications.registry import (
    ApplicationContribution,
    ApplicationContributionCatalog,
)


def proposal_context_policies():
    def fields(names, sensitivity):
        return tuple(
            ContextFieldPolicy(field=name, sensitivity=sensitivity) for name in names
        )

    return (
        ContextProviderPolicy(
            provider_id="booking.document_extraction",
            operations=(
                ContextOperationPolicy(
                    operation="current",
                    fields=fields(("document_text", "media_type"), "sensitive"),
                    sensitivity="sensitive",
                ),
            ),
        ),
        ContextProviderPolicy(
            provider_id="travel.itinerary_context",
            operations=(
                ContextOperationPolicy(
                    operation="current",
                    fields=fields(("itinerary_context",), "sensitive"),
                    sensitivity="sensitive",
                ),
            ),
        ),
    )


def legacy_shared_policy():
    shared = ApplicationContextPolicy()
    return shared.model_copy(
        update={
            "provider_policies": (
                *shared.provider_policies,
                *proposal_context_policies(),
            )
        }
    )


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
    shared = legacy_shared_policy()
    return ApplicationContextPolicy(
        version=version,
        provider_policies=(*shared.provider_policies, *declarations),
        maximum_model_sensitivity=(
            maximum_model_sensitivity or shared.maximum_model_sensitivity
        ),
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
                sensitivity=(
                    "restricted" if field in restricted_fields else sensitivity
                ),
                model_disclosure=field not in restricted_fields,
            )
            for field in fields
        ),
        sensitivity=sensitivity,
    )


def _reference_metadata():
    """Build initial manifests with common chat context and comparison modules."""
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
        _capability(
            "travel.itinerary_action", "tool", reason="travel_actions_unavailable"
        ),
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
        _capability(
            "shopping.product_action", "tool", reason="shopping_actions_unavailable"
        ),
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
        _capability(
            "finance.account_action", "tool", reason="finance_actions_unavailable"
        ),
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
        _capability(
            "health.record_action", "tool", reason="health_actions_unavailable"
        ),
    )
    definitions = (
        ApplicationDefinition(
            application_id="personal_ai",
            display_name="Personal AI",
            workspace_kind="optional",
            memory_namespace="personal_ai",
            context_policy=ApplicationContextPolicy(
                version="personal-ai-context-policy-v2",
                provider_policies=legacy_shared_policy().provider_policies,
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
            context_provider_ids=(
                "shopping.product_context",
                "shopping.catalog_search",
            ),
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
    from personal_ai_reference_apps.federation import (
        install_reference_federation_metadata as install_federation_metadata,
    )

    definitions, capabilities = install_federation_metadata(definitions, capabilities)
    return definitions, capabilities


def reference_application_registry(*, contribution_catalog=None):
    """Explicit legacy profile for historical in-process consumers/tests."""
    from personal_ai.applications.registry import default_application_registry

    catalog = ApplicationContributionCatalog(
        (name, lambda name=name: application_contribution(name))
        for name in ("travel", "shopping", "finance", "health")
    )
    registry = default_application_registry(contribution_catalog=catalog)
    return (
        registry
        if contribution_catalog is None
        else contribution_catalog.extend(registry)
    )


def application_contribution(application_id):
    definitions, metadata = _reference_metadata()
    definition = next(
        item for item in definitions if item.application_id == application_id
    )
    declared = {*definition.context_provider_ids, *definition.tool_ids}
    capabilities = tuple(item for item in metadata if item.capability_id in declared)
    modules = {}
    if application_id == "travel":
        from personal_ai_reference_apps.domains.travel.module import TravelModule

        modules["travel"] = TravelModule()
    elif application_id == "shopping":
        from personal_ai_reference_apps.domains.shopping.module import ShoppingModule

        modules["shopping"] = ShoppingModule()
    routers, handlers, extensions = (), {}, {}
    if application_id in {"travel", "shopping"}:
        from personal_ai.domains.contracts import DomainContractError

        from personal_ai_reference_apps.api.domains import router as domains_router
        from personal_ai_reference_apps.domains.providers import DomainProviderError
        from personal_ai_reference_apps.errors import (
            domain_contract_error,
            domain_provider_error,
        )

        routers = (domains_router,)
        handlers = {
            DomainContractError: domain_contract_error,
            DomainProviderError: domain_provider_error,
        }
    if application_id == "travel":
        from personal_ai_reference_apps.api.booking_extractions import (
            router as extraction_router,
        )
        from personal_ai_reference_apps.api.itinerary_proposals import (
            router as proposal_router,
        )
        from personal_ai_reference_apps.booking_extractions.repositories import (
            ExtractionError,
        )
        from personal_ai_reference_apps.errors import (
            booking_extraction_error,
            itinerary_proposal_error,
        )
        from personal_ai_reference_apps.itinerary_proposals.contracts import (
            ProposalError,
        )

        routers = (*routers, proposal_router, extraction_router)
        handlers.update(
            {
                ProposalError: itinerary_proposal_error,
                ExtractionError: booking_extraction_error,
            }
        )
        extensions = {"personal_ai": proposal_context_policies()}
    return ApplicationContribution(
        definitions=(definition,),
        capabilities=capabilities,
        comparison_modules=modules,
        routers=routers,
        exception_handlers=handlers,
        context_policy_extensions=extensions,
    )


def travel_application():
    return application_contribution("travel")


def shopping_application():
    return application_contribution("shopping")


def finance_application():
    return application_contribution("finance")


def health_application():
    return application_contribution("health")
