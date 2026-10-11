"""Canonical FastAPI composition for deployment-installed context contributions."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from personal_ai.api.dependencies import (
    get_application_context,
    get_context_assembler,
    get_external_context_assembler,
    get_global_profile_repository,
    get_provider_usage_accounting,
    get_request_scope,
    get_settings,
    get_summary_repository,
)
from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.scope import RequestScope
from personal_ai.context import (
    ContextAssembler,
    ContextRuntimeContribution,
    ContextRuntimeRegistry,
    compose_context_runtime,
)
from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextItem,
    ContextOperationSpec,
    ContextProviderError,
    ContextProviderSpec,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.entities import Message
from personal_ai.settings import Settings

APPLICATION_ID = "synthetic_fifth"
PROVIDER_ID = "host.selected_record"


class RecordPayload(BaseModel):
    label: str


class SyntheticProvider:
    spec = ContextProviderSpec(
        provider_id=PROVIDER_ID,
        source_class="domain_current",
        source_version="synthetic-v1",
        operations=(ContextOperationSpec(
            operation="current",
            allowed_fields=("label",),
            accepts_entity_refs=True,
            maximum_results=1,
        ),),
    )

    def __init__(self, reference: ContextEntityReference) -> None:
        self.reference = reference
        self.calls = 0

    def validate_selection(self, selection: ContextSelection, inputs) -> None:
        if inputs.scope.application_id != APPLICATION_ID:
            raise ContextProviderError("host_scope_mismatch")
        if selection.entity_refs != (self.reference,):
            raise ContextProviderError("host_entity_not_authorized")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        del selection, deadline
        self.calls += 1
        return (ContextItem(
            source_class="domain_current",
            provider_id=PROVIDER_ID,
            source_id="record-source",
            source_version="revision-1",
            item_id=self.reference.entity_id,
            owner_id=scope.owner_id,
            application_id=scope.application_id,
            workspace_id=scope.workspace_id,
            entity_refs=(self.reference,),
            authority="authoritative",
            observed_at=datetime.now(UTC),
            sensitivity="personal",
            source_refs=(ContextSourceReference(
                kind="record", reference_id=self.reference.entity_id, fingerprint="a" * 64
            ),),
            payload=RecordPayload(label="Synthetic provider reached through FastAPI composition"),
        ),)


def _contribution_rule(rule_id: str, provider_id: str) -> ContextPlanningRule:
    return ContextPlanningRule(
        rule_id=rule_id,
        category="selected_record",
        phrases=("selected record",),
        provider_id=provider_id,
        operation="current",
        fields=("label",),
        explanation="Read a selected record through one installed contribution.",
    )


def test_context_runtime_composes_independent_domain_contributions():
    runtime = compose_context_runtime(
        ContextRuntimeContribution(
            {}, (_contribution_rule("travel.record:v1", "travel.record"),)
        ),
        ContextRuntimeContribution(
            {}, (_contribution_rule("shopping.record:v1", "shopping.record"),)
        ),
    )

    assert {rule.rule_id for rule in runtime.planning_rules} == {
        "travel.record:v1",
        "shopping.record:v1",
    }


def test_context_runtime_rejects_duplicate_provider_rule_and_permission_ownership():
    rule = _contribution_rule("travel.record:v1", "host.selected_record")
    provider = SyntheticProvider(
        ContextEntityReference(
            entity_type="record", entity_id="record-1", application_id=APPLICATION_ID
        )
    )

    with pytest.raises(ValueError, match="context_runtime_provider_id_duplicate"):
        compose_context_runtime(
            ContextRuntimeContribution({PROVIDER_ID: provider}),
            ContextRuntimeContribution({PROVIDER_ID: provider}),
        )
    with pytest.raises(ValueError, match="context_runtime_rule_id_duplicate"):
        compose_context_runtime(
            ContextRuntimeContribution({}, (rule,)),
            ContextRuntimeContribution({}, (rule,)),
        )

    class Revalidator:
        permission_namespaces = ("source_permission:",)

    with pytest.raises(ValueError, match="context_runtime_revalidator_namespace_duplicate"):
        compose_context_runtime(
            ContextRuntimeContribution({}, permission_revalidators=(Revalidator(),)),
            ContextRuntimeContribution({}, permission_revalidators=(Revalidator(),)),
        )


def _app(provider: SyntheticProvider | None):
    scope = RequestScope(
        owner_id="owner-1",
        request_id="runtime-composition-test",
        application_id=APPLICATION_ID,
        workspace_id="workspace-1",
    )
    reference = ContextEntityReference(
        entity_type="record",
        entity_id="selected-record-1",
        application_id=APPLICATION_ID,
        workspace_id=scope.workspace_id,
    )
    base_policy = ApplicationContextPolicy()
    definition = ApplicationDefinition(
        application_id=APPLICATION_ID,
        display_name="Synthetic fifth application",
        memory_namespace=APPLICATION_ID,
        context_provider_ids=(PROVIDER_ID,),
        context_policy=base_policy.model_copy(update={
            "version": "synthetic-context-v1",
            "provider_policies": (*base_policy.provider_policies, ContextProviderPolicy(
                provider_id=PROVIDER_ID,
                operations=(ContextOperationPolicy(
                    operation="current",
                    fields=(ContextFieldPolicy(field="label", sensitivity="personal"),),
                    sensitivity="personal",
                ),),
            )),
            "maximum_model_sensitivity": "sensitive",
        }),
    )
    application_registry = ApplicationRegistry(
        (definition,),
        (CapabilityRegistration(
            capability_id=PROVIDER_ID, kind="context_provider", available=True
        ),),
    )
    rule = ContextPlanningRule(
        rule_id="host.selected-record:v1",
        category="selected_host_record",
        phrases=("use the selected record",),
        provider_id=PROVIDER_ID,
        operation="current",
        fields=("label",),
        max_tokens=256,
        use_candidate_entities=True,
        require_candidate_entities=True,
        explanation="Read the selected record through the registered host provider.",
    )
    runtime = ContextRuntimeRegistry(
        provider_factories={} if provider is None else {PROVIDER_ID: provider},
        planning_rules=(rule,),
    )
    settings = Settings(_env_file=None, ai_provider="fake", ai_model="fixture")
    app = FastAPI()
    app.state.application_registry = application_registry
    app.state.context_runtime_registry = runtime
    app.dependency_overrides.update({
        get_request_scope: lambda: scope,
        get_settings: lambda: settings,
        get_summary_repository: InMemorySummaryRepository,
        get_global_profile_repository: lambda: object(),
        get_provider_usage_accounting: lambda: None,
    })

    @app.get("/synthetic-context")
    def synthetic_context(
        application_context=Depends(get_application_context),  # noqa: B008
        assembler: ContextAssembler = Depends(get_context_assembler),  # noqa: B008
        external_assembler: ContextAssembler = Depends(get_external_context_assembler),  # noqa: B008
    ):
        # The real dependency constructs the runtime; this harness only selects the
        # offline counter so no provider/network call is needed for token counts.
        assembler.counter = EstimatedTokenCounter()
        plan = assembler.plan_context(
            "Use the selected record.",
            application_context,
            candidate_entities=(reference,),
        )
        pending = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            owner_id=scope.owner_id,
            application_id=scope.application_id,
            workspace_id=scope.workspace_id,
            role="user",
            content="Use the selected record.",
            status="completed",
            created_at=datetime.now(UTC),
        )
        assembled = assembler.assemble(
            (),
            pending,
            refresh=False,
            application_context=application_context,
            context_plan=plan,
            emit_manifest=False,
        )
        external_plan = external_assembler.plan_context(
            "Use the selected record.",
            application_context,
            candidate_entities=(reference,),
        )
        external_assembled = external_assembler.assemble(
            (),
            pending,
            refresh=False,
            application_context=application_context,
            context_plan=external_plan,
            emit_manifest=False,
        )
        return {
            "providers": [item.provider_id for item in assembled.source_items],
            "external_providers": [item.provider_id for item in external_assembled.source_items],
            "selections": [item.provider_id for item in plan.selections],
            "shared_composition": (
                external_assembler.context_provider_coordinator
                is assembler.context_provider_coordinator
                and external_assembler.context_planner is assembler.context_planner
            ),
            "implementation_calls": provider.calls if provider else 0,
        }

    return app


def test_synthetic_application_uses_canonical_runtime_dependency_composition():
    provider = SyntheticProvider(ContextEntityReference(
        entity_type="record",
        entity_id="selected-record-1",
        application_id=APPLICATION_ID,
        workspace_id="workspace-1",
    ))
    response = TestClient(_app(provider)).get("/synthetic-context")

    assert response.status_code == 200
    assert response.json() == {
        "providers": [PROVIDER_ID],
        "external_providers": [PROVIDER_ID],
        "selections": [PROVIDER_ID],
        "shared_composition": True,
        "implementation_calls": 2,
    }


def test_declared_capability_without_runtime_implementation_fails_closed():
    response = TestClient(_app(None)).get("/synthetic-context")

    assert response.status_code == 200
    assert response.json()["selections"] == []
    assert response.json()["providers"] == []
    assert response.json()["external_providers"] == []
    assert response.json()["shared_composition"] is True
    assert response.json()["implementation_calls"] == 0
