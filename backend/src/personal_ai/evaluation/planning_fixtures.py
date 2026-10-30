"""Synthetic federation fixture shared by offline planning evaluation and conformance tests."""

from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel

from personal_ai.applications.contracts import ApplicationContextRequest, ApplicationDefinition
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
)
from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import (
    ContextItem,
    ContextProviderCoordinator,
    ContextSelection,
)
from personal_ai.context.runtime import (
    ContextRuntimeContribution,
    compose_context_runtime,
)
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
    ContextSourceReference,
)
from personal_ai.contracts.federation import FederationExportDeclaration, FederationSelection
from personal_ai.federation.broker import (
    FederationCase,
    FederationExportResult,
    federation_contribution,
)
from personal_ai.federation.contracts import FederationGrantIntent
from personal_ai.federation.deployment import install_federation_metadata
from personal_ai.federation.service import FederationPermissionAuthority
from personal_ai.persistence.postgres.federation import validate_transition


def historical_reference_planning_rules() -> tuple[ContextPlanningRule, ...]:
    """Synthetic rule contracts for the named historical reference cases.

    These rules exercise the shared planner without importing optional app
    implementations. They are not production registration or authorization.
    The full rule catalog remains owned by the selected reference package.
    """
    return (
        ContextPlanningRule(
            rule_id="travel.selected-trip:v1",
            category="travel_current_trip",
            phrases=("this trip", "my trip", "trip itinerary", "current itinerary"),
            provider_id="travel.trip_context",
            operation="current",
            fields=("trip_title", "start_date", "end_date", "timezone", "itinerary_overview"),
            max_results=4,
            max_bytes=24_576,
            max_tokens=512,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("trip",),
            priority=20,
            application_ids=("travel",),
            explanation="Synthetic rule for the historical selected-trip planning case.",
        ),
        ContextPlanningRule(
            rule_id="travel.selected-entities:v1",
            category="travel_selected_entities",
            phrases=("selected day", "selected place", "this place", "day itinerary", "reservation"),
            provider_id="travel.trip_context",
            operation="entity",
            fields=(
                "day_date", "day_title", "item_title", "item_type", "item_status",
                "item_schedule", "place_name", "place_category", "place_address",
                "place_source", "place_attribution",
            ),
            max_results=12,
            max_bytes=32_768,
            max_tokens=512,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("day", "itinerary_item", "place", "reservation"),
            priority=25,
            application_ids=("travel",),
            explanation="Synthetic rule for the historical selected-entity planning case.",
        ),
        ContextPlanningRule(
            rule_id="shopping.selected-project-context:v1",
            category="shopping_project_context",
            phrases=("this shopping project", "my shopping project", "project requirements"),
            provider_id="shopping.product_context",
            operation="current",
            fields=("project_title", "project_goal", "requirements", "selected_products"),
            max_results=12,
            max_bytes=24_576,
            max_tokens=768,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            candidate_entity_types=("project", "project_product"),
            required=True,
            priority=25,
            application_ids=("shopping",),
            explanation="Synthetic rule for the historical selected-project planning case.",
        ),
        ContextPlanningRule(
            rule_id="shopping.selected-catalog-evidence:v1",
            category="shopping_selected_catalog_evidence",
            phrases=("compare these selected products", "use selected product evidence"),
            provider_id="shopping.catalog_search",
            operation="search",
            fields=("catalog_observations",),
            max_results=24,
            max_bytes=24_576,
            max_tokens=768,
            timeout_seconds=5,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("project", "project_product"),
            priority=30,
            application_ids=("shopping",),
            explanation="Synthetic rule for the historical selected-products planning case.",
        ),
        ContextPlanningRule(
            rule_id="finance.selected-account:v1",
            category="finance_selected_account",
            phrases=("this finance account", "selected account context"),
            provider_id="finance.account_context",
            operation="current",
            fields=("account_summary", "balance_summary"),
            max_results=4,
            max_bytes=12_288,
            max_tokens=512,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("account",),
            required=True,
            priority=20,
            application_ids=("finance",),
            explanation="Synthetic rule for the historical selected-account planning case.",
        ),
        ContextPlanningRule(
            rule_id="finance.selected-thesis:v1",
            category="finance_selected_thesis",
            phrases=("selected finance thesis", "this thesis note"),
            provider_id="finance.research_context",
            operation="current",
            fields=("research_thesis",),
            max_results=4,
            max_bytes=16_384,
            max_tokens=768,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("issuer",),
            priority=32,
            application_ids=("finance",),
            explanation="Synthetic rule for the historical selected-thesis planning case.",
        ),
    )


class Repository:
    def __init__(self):
        self.records = {}
        self.lock = RLock()
        self.audit = []

    def record_access(self, selection, scope, result):
        self.audit.append((selection.provider_id, scope.owner_id, result))

    def get(self, owner_id, grant_id):
        return self.records.get((owner_id, grant_id))

    def list_destination(self, owner_id, destination):
        return tuple(
            grant
            for (grant_owner, _), grant in self.records.items()
            if grant_owner == owner_id
            and grant.destination == destination
            and grant.state == "active"
        )

    def save(self, grant, *, expected_revision):
        with self.lock:
            validate_transition(self.get(grant.owner_id, grant.grant_id), grant, expected_revision)
            self.records[grant.owner_id, grant.grant_id] = grant
        return grant


class SourcePolicy:
    permission_namespaces = ("synthetic_policy:", "synthetic_revision:")
    current = True
    calls = 0

    def supports(self, dependency):
        return dependency.permission_id.startswith(self.permission_namespaces)

    def is_current(self, dependency):
        self.calls += 1
        return self.current and self.supports(dependency)


class Payload(BaseModel):
    constraint: str


def synthetic_federation():
    now = datetime.now(UTC)
    source = ApplicationScope(application_id="synthetic_source", workspace_id="source-space")
    destination = ApplicationScope(
        application_id="synthetic_destination", workspace_id="destination-space"
    )
    scope = RequestScope(
        **destination.model_dump(),
        owner_id="owner",
        acting_user_id="issuer|user",
        request_id="request",
    )
    entity = ContextEntityReference(
        **source.model_dump(), entity_type="variant", entity_id="variant-2"
    )
    policy = ContextPermissionDependency(
        permission_id="synthetic_policy:owner",
        version="7",
        purpose="planning",
        owner_id="owner",
        acting_user_id="issuer|user",
        source_scope=source,
    )
    revision = ContextPermissionDependency(
        permission_id="synthetic_revision:variant-2",
        version="12",
        purpose="planning",
        entity_ref=entity,
        source_revision="variant-v12",
        owner_id="owner",
        acting_user_id="issuer|user",
        source_scope=source,
    )
    repository, source_policy = Repository(), SourcePolicy()
    authority = FederationPermissionAuthority(
        repository, source_policy, choice_hmac_key=b"synthetic-federation-choice-key-32"
    )
    principal = AuthenticatedPrincipal("issuer", "user", "owner", None, 1, True)
    case = FederationCase(
        source.application_id,
        destination.application_id,
        FederationExportDeclaration(
            category="constraints",
            provider_id="federation.synthetic",
            fields=("constraint",),
            sensitivity="restricted",
        ),
    )

    class Adapter:
        calls = 0
        authorize_calls = 0
        hook = None
        export_allowed = True
        membership_active = True

        def resolve_source_policy(self, intent, *, deadline):
            assert intent.source == source and intent.category == case.export.category
            return policy.model_copy(
                update={"owner_id": intent.owner_id, "acting_user_id": intent.acting_user_id}
            )

        def authorize_export(self, granted, selected, acting_scope, *, deadline):
            self.authorize_calls += 1
            return (
                self.export_allowed
                and self.membership_active
                and selected.federation.category == granted.category
                and set(selected.fields) <= set(granted.fields)
                and set(selected.federation.entities) <= set(granted.entities)
            )

        def fetch(self, grant, selection, scope, *, deadline):
            self.calls += 1
            if self.hook:
                self.hook()
            item = ContextItem(
                provider_id="synthetic.export",
                source_class="domain_current",
                source_id="variant-2",
                source_version="variant-v12",
                item_id="variant-2:12",
                owner_id="owner",
                **source.model_dump(),
                entity_refs=(entity,),
                sensitivity="sensitive",
                authority="authoritative",
                source_refs=(
                    ContextSourceReference(
                        kind="record", reference_id="variant-2:12", fingerprint="a" * 64
                    ),
                ),
                permission_dependencies=(policy, revision),
                observed_at=now,
                expires_at=now + timedelta(minutes=30),
                payload=Payload(constraint="narrow export"),
            )
            return FederationExportResult(items=(item,), complete=True)

    adapter = Adapter()
    runtime = compose_context_runtime(
        ContextRuntimeContribution({}, permission_revalidators=(source_policy,)),
        federation_contribution((case,), authority, {case.export.provider_id: adapter}),
    )
    intent = FederationGrantIntent(
        grant_id=uuid4(),
        source=source,
        destination=destination,
        owner_id="owner",
        acting_user_id="issuer|user",
        category="constraints",
        purpose="planning",
        entities=(entity,),
        fields=("constraint",),
        expires_at=now + timedelta(hours=1),
    )
    grant = authority.create(principal, intent)
    definitions, capabilities = install_federation_metadata(
        (
            ApplicationDefinition(
                application_id=source.application_id,
                display_name="Source",
                memory_namespace="synthetic_source",
            ),
            ApplicationDefinition(
                application_id=destination.application_id,
                display_name="Destination",
                memory_namespace="synthetic_destination",
            ),
        ),
        (),
        (case,),
        implemented_provider_ids=(case.export.provider_id,),
    )
    registry = ApplicationRegistry(definitions, capabilities)
    registration = registry.registration(scope.application_id)
    definition = registration.definition.model_copy(
        update={
            "context_policy": registration.definition.context_policy.model_copy(
                update={"maximum_model_sensitivity": "restricted"}
            )
        }
    )
    context = ApplicationContextRequest(
        definition=definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
    )
    hint = FederationSelection(
        **{name: getattr(grant, name) for name in FederationSelection.model_fields}
    )
    selection = ContextSelection(
        provider_id=case.export.provider_id,
        operation="entity",
        fields=("constraint",),
        federation=hint,
    )
    coordinator = ContextProviderCoordinator(runtime.provider_factories)
    return locals()


def federation_planning_rows():
    """Measure explicit broker selection/currentness; no domain credentials or model."""
    from personal_ai.auth.scope import bind_request_scope, reset_request_scope
    from personal_ai.context.assembler import ContextAssembler
    from personal_ai.context.providers import ContextPreparationError
    from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry
    from personal_ai.context.tokens import EstimatedTokenCounter
    from personal_ai.entities import Message
    from personal_ai.settings import Settings

    rows = []
    for state in (
        "active", "revoked", "expired", "source_revoked", "grant_epoch_changed",
        "consent_revoked", "membership_revoked",
    ):
        f = synthetic_federation()
        settings = Settings(
            _env_file=None,
            ai_provider="fake",
            ai_model="synthetic",
            max_context_tokens=8192,
            max_response_tokens=100,
            summary_trigger_tokens=1000,
            max_summary_tokens=512,
        )
        assembler = ContextAssembler(
            settings,
            EstimatedTokenCounter(),
            context_provider_coordinator=f["coordinator"],
            permission_revalidator=ContextPermissionRevalidatorRegistry(
                f["runtime"].permission_revalidators
            ),
        )
        selection = f["selection"].model_copy(update={"max_tokens": 256})
        plan = assembler.plan_context(
            "Use the explicitly selected constraints",
            f["context"],
            explicit_context_selections=(selection,),
        )
        if state == "revoked":
            f["authority"].revoke(f["principal"], f["grant"].grant_id, expected_revision=1)
        elif state == "source_revoked":
            f["source_policy"].current = False
        elif state == "grant_epoch_changed":
            key = ("owner", f["grant"].grant_id)
            f["repository"].records[key] = f["grant"].model_copy(
                update={"revision": f["grant"].revision + 1, "epoch": f["grant"].epoch + 1}
            )
        elif state == "consent_revoked":
            f["adapter"].export_allowed = False
        elif state == "membership_revoked":
            f["adapter"].membership_active = False
        elif state == "expired":
            f["repository"].records["owner", f["grant"].grant_id] = f["grant"].model_copy(
                update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
            )
        pending = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            owner_id=f["scope"].owner_id,
            application_id=f["scope"].application_id,
            workspace_id=f["scope"].workspace_id,
            role="user",
            content="Use the explicitly selected constraints",
            status="completed",
            created_at=datetime.now(UTC),
        )
        token = bind_request_scope(f["scope"])
        try:
            result = assembler.assemble(
                (),
                pending,
                refresh=False,
                application_context=f["context"],
                context_plan=plan,
                emit_manifest=False,
            )
            row = {
                "failure_class": "none",
                "source_support_proxy": bool(result.source_items),
                "selected_source_count": len(plan.selections),
                "selected_item_count": len(result.source_items),
                "assembled_bytes": sum(len(m.content.encode()) for m in result.messages),
                "estimated_input_tokens": result.budget.selected_total,
                "effective_sensitivity": result.manifest.effective_sensitivity,
            }
        except ContextPreparationError as error:
            row = {
                "failure_class": "expected_policy_or_source_exclusion",
                "reason": error.code,
                "source_support_proxy": False,
                "assembled_bytes": None,
                "estimated_input_tokens": None,
                "effective_sensitivity": "unknown",
            }
        finally:
            reset_request_scope(token)
        rows.append(
            {
                "id": f"cross-app-{state}",
                "family": "federation",
                "application_id": f["scope"].application_id,
                "provider_calls": f["adapter"].calls,
                "trace": plan.planning_trace.model_dump(mode="json"),
                **row,
            }
        )
    return rows
