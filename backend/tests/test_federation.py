"""Federation conformance through shared registration, policy and provider composition."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, RLock
from time import monotonic
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from personal_ai.applications.contracts import ApplicationContextRequest, ApplicationDefinition
from personal_ai.applications.registry import ApplicationRegistry, default_application_registry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    bind_request_scope,
    reset_request_scope,
)
from personal_ai.context.providers import (
    ContextItem,
    ContextPreparationError,
    ContextProviderCoordinator,
    ContextProviderInputs,
    ContextSelection,
)
from personal_ai.context.runtime import (
    ContextPermissionRevalidatorRegistry,
    ContextRuntimeContribution,
    compose_context_runtime,
)
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
    ContextSourceReference,
)
from personal_ai.contracts.execution import ContinuationRequestPayload
from personal_ai.contracts.federation import FederationExportDeclaration, FederationSelection
from personal_ai.federation.broker import (
    FederationCase,
    FederationExportResult,
    federation_contribution,
)
from personal_ai.federation.contracts import FederationGrant, FederationGrantIntent
from personal_ai.federation.deployment import INITIAL_FEDERATION_CASES, install_federation_metadata
from personal_ai.federation.service import FederationPermissionAuthority
from personal_ai.persistence.postgres.database import PersistenceConflict
from personal_ai.persistence.postgres.federation import validate_transition


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


@pytest.fixture
def federation():
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

        def resolve_source_policy(self, intent, *, deadline):
            assert intent.source == source and intent.category == case.export.category
            return policy.model_copy(
                update={"owner_id": intent.owner_id, "acting_user_id": intent.acting_user_id}
            )

        def authorize_export(self, granted, selected, acting_scope, *, deadline):
            self.authorize_calls += 1
            return (
                self.export_allowed
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


def prepare(f):
    return (
        f["coordinator"]
        .prepare(f["context"], (f["selection"],), ContextProviderInputs(f["scope"]))
        .items[0]
    )


def test_registered_synthetic_export_preserves_exact_authority(federation):
    f = federation
    item = prepare(f)
    assert item.sensitivity == "restricted"
    assert item.source_version == "variant-v12"
    assert item.source_refs[0].reference_id == "variant-2:12"
    assert item.federation.entities == (f["entity"],)
    assert item.authority_snapshot().federation == item.federation
    assert item.permission_dependencies[-1] == f["grant"].dependency()
    assert item.application_id == f["scope"].application_id
    assert f["adapter"].calls == 1
    assert len(INITIAL_FEDERATION_CASES) == 4
    assert "synthetic_source" not in default_application_registry().application_ids


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "owner",
        "actor",
        "source_workspace",
        "destination_workspace",
        "purpose",
        "category",
        "field",
        "entity",
        "revision",
        "epoch",
        "expired",
        "revoked",
        "source_policy",
    ],
)
def test_denied_before_source_call(federation, failure):
    f = federation
    selection, hint = f["selection"], f["hint"]
    if failure == "missing":
        f["repository"].records.clear()
    elif failure in ("owner", "actor", "destination_workspace"):
        name, value = {
            "owner": ("owner_id", "other"),
            "actor": ("acting_user_id", "delegate"),
            "destination_workspace": ("workspace_id", "other"),
        }[failure]
        f["scope"] = f["scope"].model_copy(update={name: value})
        f["context"] = f["context"].model_copy(update={"scope": f["scope"]})
    elif failure == "source_workspace":
        hint = hint.model_copy(
            update={"source": hint.source.model_copy(update={"workspace_id": "other"})}
        )
    elif failure in ("purpose", "category", "revision", "epoch"):
        hint = hint.model_copy(update={failure: 2 if failure in ("revision", "epoch") else "other"})
    elif failure == "entity":
        hint = hint.model_copy(
            update={"entities": (f["entity"].model_copy(update={"entity_id": "other"}),)}
        )
    elif failure == "field":
        selection = selection.model_copy(update={"fields": ("secret",)})
    elif failure == "expired":
        f["authority"].clock = lambda: f["grant"].expires_at
    elif failure == "revoked":
        f["authority"].revoke(f["principal"], f["grant"].grant_id, expected_revision=1)
    else:
        f["source_policy"].current = False
    f["selection"] = selection.model_copy(update={"federation": hint})
    with pytest.raises(ContextPreparationError):
        prepare(f)
    assert f["adapter"].calls == 0
    if failure != "field":
        assert f["repository"].audit[-1][2].startswith("context_federation_")


def test_revocation_during_read_prevents_return(federation):
    f = federation
    f["adapter"].hook = lambda: f["authority"].revoke(
        f["principal"], f["grant"].grant_id, expected_revision=1
    )
    with pytest.raises(ContextPreparationError):
        prepare(f)
    assert f["adapter"].calls == 1


def test_epoch_change_and_terminal_revocation(federation):
    f = federation
    previous = f["grant"]
    changed = previous.model_copy(update={"revision": 2, "epoch": 2})
    f["repository"].save(changed, expected_revision=1)
    with pytest.raises(ContextPreparationError):
        prepare(f)
    with pytest.raises(PersistenceConflict):
        f["repository"].save(changed, expected_revision=1)
    revoked = f["authority"].revoke(f["principal"], previous.grant_id, expected_revision=2)
    with pytest.raises(PersistenceConflict):
        f["repository"].save(
            revoked.model_copy(
                update={"revision": 4, "epoch": 4, "state": "active", "revocation_id": None}
            ),
            expected_revision=3,
        )
    with pytest.raises(ValidationError):
        FederationGrant.model_validate({**previous.model_dump(), "re_delegation": True})


def test_derived_history_and_summary_reuse_revocation(federation):
    from personal_ai.applications.contracts import ManualImportReusePolicy
    from personal_ai.context.contracts import ConversationSummary, fingerprint
    from personal_ai.context.history import (
        conversation_context_messages,
        memory_extraction_context_reason,
        summary_authority_snapshot,
    )
    from personal_ai.entities import Message
    from personal_ai.entities.turn_execution import TurnAttribution

    f = federation
    item = prepare(f)
    conversation_id, user_id = uuid4(), uuid4()
    common = dict(
        conversation_id=conversation_id,
        owner_id="owner",
        status="completed",
        created_at=f["now"],
        **f["destination"].model_dump(),
    )
    user = Message(**common, id=user_id, role="user", content="question")
    assistant = Message(
        **common,
        id=uuid4(),
        role="assistant",
        parent_message_id=user_id,
        content="derived",
        attribution=TurnAttribution(
            fact_source="server_observed",
            execution_origin="automatic_managed",
            provider_id="fake",
            model_id="fake",
            recorded_at=f["now"],
            effective_context_sensitivity="restricted",
            source_snapshots=(item.authority_snapshot(),),
        ),
    )
    messages = (user, assistant)
    summary = ConversationSummary(
        **{key: value for key, value in common.items() if key != "status"},
        id=uuid4(),
        content="summary",
        source_message_ids=(user.id, assistant.id),
        source_fingerprint=fingerprint(messages),
        covers_through_message_id=assistant.id,
        source_token_count=5,
        summary_token_count=2,
        model="fake",
    )
    revalidator = ContextPermissionRevalidatorRegistry((f["source_policy"], f["authority"]))
    token = bind_request_scope(f["scope"])
    try:
        assert all(
            revalidator.is_current(dep)
            for dep in summary_authority_snapshot(summary, messages).permission_dependencies
        )
        assert memory_extraction_context_reason(assistant) is not None
        assert (
            conversation_context_messages(
                messages,
                manual_import_reuse=ManualImportReusePolicy(),
                permission_revalidator=revalidator,
                check_source_permissions=True,
            )
            == messages
        )
        f["authority"].revoke(f["principal"], f["grant"].grant_id, expected_revision=1)
        assert (
            conversation_context_messages(
                messages,
                manual_import_reuse=ManualImportReusePolicy(),
                permission_revalidator=revalidator,
                check_source_permissions=True,
            )
            == ()
        )
        assert not all(
            revalidator.is_current(dep)
            for dep in summary_authority_snapshot(summary, messages).permission_dependencies
        )
    finally:
        reset_request_scope(token)


def test_artifact_permission_reuse_denied_before_body_read(federation):
    from personal_ai.artifacts.contracts import ArtifactUnavailable
    from personal_ai.artifacts.local import (
        InMemoryArtifactMetadataRepository,
        InMemoryArtifactStore,
    )
    from personal_ai.artifacts.service import ArtifactService

    f = federation
    item = prepare(f)
    revalidator = ContextPermissionRevalidatorRegistry((f["source_policy"], f["authority"]))
    store = InMemoryArtifactStore()
    service = ArtifactService(
        InMemoryArtifactMetadataRepository(), store, permission_revalidator=revalidator
    )
    token = bind_request_scope(f["scope"])
    try:
        ref = service.write(
            {"derived": "value"},
            owner_id="owner",
            scope=f["destination"],
            kind="export",
            identity="id",
            schema_version="test",
            permission_dependencies=item.permission_dependencies,
            required=True,
        )
        assert service.read(ref.artifact_id, owner_id="owner", scope=f["destination"]) == {
            "derived": "value"
        }
        reads = store.read_calls
        f["authority"].revoke(f["principal"], f["grant"].grant_id, expected_revision=1)
        with pytest.raises(ArtifactUnavailable):
            service.read(ref.artifact_id, owner_id="owner", scope=f["destination"])
        assert store.read_calls == reads
    finally:
        reset_request_scope(token)


def test_federation_uses_fastapi_automatic_and_external_assembler_dependencies(federation):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from personal_ai.api.dependencies import (
        get_context_assembler,
        get_external_context_assembler,
        get_global_profile_repository,
        get_provider_usage_accounting,
        get_settings,
        get_summary_repository,
    )
    from personal_ai.context.repositories import InMemorySummaryRepository
    from personal_ai.context.tokens import EstimatedTokenCounter
    from personal_ai.entities import Message
    from personal_ai.settings import Settings

    f = federation
    app = FastAPI()
    app.state.context_runtime_registry = f["runtime"]
    app.dependency_overrides.update(
        {
            get_settings: lambda: Settings(_env_file=None, ai_provider="fake", ai_model="fake"),
            get_summary_repository: InMemorySummaryRepository,
            get_global_profile_repository: lambda: object(),
            get_provider_usage_accounting: lambda: None,
        }
    )

    @app.get("/context")
    def context(
        automatic=Depends(get_context_assembler),  # noqa: B008
        external=Depends(get_external_context_assembler),  # noqa: B008
    ):
        token = bind_request_scope(f["scope"])
        try:
            assert automatic.context_provider_coordinator is external.context_provider_coordinator
            assert automatic.permission_revalidator is external.permission_revalidator
            external.counter = EstimatedTokenCounter()
            plan = external.plan_context(
                "plan", f["context"], explicit_context_selections=(f["selection"],)
            )
            user = Message(
                id=uuid4(),
                conversation_id=uuid4(),
                owner_id="owner",
                **f["destination"].model_dump(),
                role="user",
                status="completed",
                content="plan",
                created_at=f["now"],
            )
            built = external.assemble(
                (), user, application_context=f["context"], context_plan=plan, refresh=False
            )
            return {
                "source_items": len(built.source_items),
                "sensitivity": built.manifest.effective_sensitivity,
            }
        finally:
            reset_request_scope(token)

    assert TestClient(app).get("/context").json() == {
        "source_items": 1,
        "sensitivity": "restricted",
    }


def test_sidecar_package_and_finalize_use_the_same_grant(federation):
    from personal_ai.applications.contracts import ExternalDisclosurePolicy
    from personal_ai.auth.scope import application_scope_context
    from personal_ai.context import ContextAssembler
    from personal_ai.context.tokens import EstimatedTokenCounter
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice
    from personal_ai.contracts.federation import FederationContextChoice
    from personal_ai.entities import Conversation
    from personal_ai.routing.registry import EndpointRegistry
    from personal_ai.services.chat.service import ChatTurnService
    from personal_ai.services.external_turns import ExternalTurnService
    from personal_ai.services.external_turns.authority import PrincipalBoundExternalTurnAuthority
    from personal_ai.settings import Settings
    from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository
    from personal_ai.storage.errors import ConversationConflictError

    f = federation
    policy = f["context"].definition.context_policy
    sidecar_policy = policy.sidecar.model_copy(
        update={
            "manual_external_disclosure": ExternalDisclosurePolicy(maximum_sensitivity="restricted")
        }
    )
    policy = policy.model_copy(
        update={"external_execution_modes": ("manual_external",), "sidecar": sidecar_policy}
    )
    context = f["context"].model_copy(
        update={"definition": f["context"].definition.model_copy(update={"context_policy": policy})}
    )
    revalidator = ContextPermissionRevalidatorRegistry(f["runtime"].permission_revalidators)
    assembler = ContextAssembler(
        Settings(_env_file=None, ai_provider="fake", ai_model="fake"),
        EstimatedTokenCounter(),
        context_provider_coordinator=f["coordinator"],
        permission_revalidator=revalidator,
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    token = bind_request_scope(f["scope"])
    try:
        with application_scope_context(f["destination"]):
            conversation = conversations.create(
                Conversation(
                    id=uuid4(),
                    owner_id="owner",
                    title="federation",
                    created_at=f["now"],
                    updated_at=f["now"],
                )
            )
            chat = ChatTurnService(
                conversations,
                messages,
                None,
                owner_id="owner",
                model="fake",
                application_context=context,
                context_assembler=assembler,
            )

            class Membership:
                def is_member(self, principal, application_id, workspace_id):
                    return (
                        principal == f["principal"]
                        and application_id == f["destination"].application_id
                        and workspace_id == f["destination"].workspace_id
                    )

            external_authority = PrincipalBoundExternalTurnAuthority(
                principal=f["principal"],
                conversations=conversations,
                messages=messages,
                permission_revalidator=revalidator,
                workspace_authorizer=Membership(),
            )
            service = ExternalTurnService(
                chat=chat,
                context=context,
                registry=EndpointRegistry([]),
                authority=external_authority,
                context_assembler=assembler,
            )
            request = ContinuationRequest(
                content="plan",
                idempotency_key=uuid4(),
                choice=ExecutionChoice(mode="manual_external"),
                federation_context=(
                    FederationContextChoice(
                        provider_id=f["selection"].provider_id,
                        fields=f["selection"].fields,
                        federation=f["hint"],
                    ),
                ),
            )
            prepared = service.prepare(conversation.id, request)
            assert prepared.context_package.effective_sensitivity == "restricted"
            assert prepared.context_package.schema_version == "context-package-v2"
            assert "grant_versions" not in prepared.context_package.model_dump()
            assert any(
                source.category == "synthetic_source → synthetic_destination: constraints"
                for source in prepared.context_package.included_sources
            )
            assert prepared.reservation.source_snapshots[0].federation is not None
            f["authority"].revoke(f["principal"], f["grant"].grant_id, expected_revision=1)
            with pytest.raises(ConversationConflictError):
                service._recheck(conversation.id, prepared.reservation, request.choice)
    finally:
        reset_request_scope(token)


@pytest.mark.parametrize("case", INITIAL_FEDERATION_CASES)
def test_four_initial_cases_use_identical_narrow_broker_contract(federation, case):
    from pydantic import create_model

    from personal_ai.federation.broker import FederationProvider

    f = federation
    source = ApplicationScope(application_id=case.source_application_id)
    destination = ApplicationScope(application_id=case.destination_application_id)
    entity = f["entity"].model_copy(update=source.model_dump())
    policy = f["policy"].model_copy(update={"source_scope": source})
    revision = f["revision"].model_copy(update={"source_scope": source, "entity_ref": entity})
    grant = f["grant"].model_copy(
        update={
            "source": source,
            "destination": destination,
            "category": case.export.category,
            "fields": case.export.fields,
            "entities": (entity,),
            "source_policy": policy,
            "sensitivity": case.export.sensitivity,
            "maximum_sensitivity": case.export.sensitivity,
        }
    )
    f["repository"].records[("owner", grant.grant_id)] = grant
    hint = FederationSelection(
        **{name: getattr(grant, name) for name in FederationSelection.model_fields}
    )
    selection = ContextSelection(
        provider_id=case.export.provider_id,
        operation="entity",
        fields=case.export.fields,
        federation=hint,
    )
    scope = f["scope"].model_copy(update=destination.model_dump())

    class Adapter:
        def resolve_source_policy(self, intent, *, deadline):
            return policy

        def authorize_export(self, granted, selected, acting_scope, *, deadline):
            return (
                granted == grant
                and selected.fields == case.export.fields
                and selected.federation.entities == (entity,)
            )

        def fetch(self, granted, selected, acting_scope, *, deadline):
            assert granted == grant and selected.fields == case.export.fields
            payload_type = create_model(
                "NarrowExport", **{name: (str, ...) for name in selected.fields}
            )
            original = f["adapter"].fetch(granted, selected, acting_scope, deadline=deadline)
            item = original.items[0]
            return FederationExportResult(items=(
                item.model_copy(
                    update={
                        **source.model_dump(),
                        "entity_refs": (entity,),
                        "permission_dependencies": (policy, revision),
                        "payload": payload_type(**{name: "bounded" for name in selected.fields}),
                    }
                ),
            ), complete=True)

    provider = FederationProvider(case, f["authority"], Adapter())
    item = provider.fetch(selection, scope, deadline=monotonic() + 100)[0]
    assert item.federation.source == source and item.federation.destination == destination
    assert item.federation.category == case.export.category
    assert item.payload.model_dump().keys() == set(case.export.fields)
    assert item.sensitivity == max(
        ("sensitive", case.export.sensitivity), key={"sensitive": 2, "restricted": 3}.get
    )
    assert not provider.case.export.provider_id.endswith("synthetic")


def test_production_composition_keeps_all_four_exports_unavailable():
    from personal_ai.context.deployment import configured_context_runtime
    from personal_ai.settings import Settings

    runtime = configured_context_runtime(
        Settings(_env_file=None, ai_provider="fake", ai_model="fake")
    )
    registry = default_application_registry()
    for case in INITIAL_FEDERATION_CASES:
        registration = registry.registration(case.destination_application_id)
        capability = next(
            value
            for value in registration.context_providers
            if value.capability_id == case.export.provider_id
        )
        assert capability.available is False
        assert runtime.provider_factories[case.export.provider_id].adapter is None
        assert case.export in registry.get(case.source_application_id).federation_exports


def test_source_overfetch_missing_revision_and_redelegation_fail_closed(federation):
    f = federation
    original = f["adapter"].fetch
    provider = f["runtime"].provider_factories[f["case"].export.provider_id]
    baseline = prepare(f)

    class ExtraPayload(BaseModel):
        constraint: str
        secret: str

    for updates in (
        {"payload": ExtraPayload(constraint="narrow", secret="forbidden")},
        {"permission_dependencies": (f["policy"],)},
        {"federation": baseline.federation},
        {"sensitivity": "unknown"},
    ):
        f["adapter"].fetch = lambda *args, updates=updates, **kwargs: FederationExportResult(
            items=tuple(
                item.model_copy(update=updates)
                for item in original(*args, **kwargs).items
            ),
            complete=True,
        )
        with pytest.raises(ContextPreparationError):
            provider.fetch(f["selection"], f["scope"], deadline=monotonic() + 100)
    f["adapter"].fetch = original
    f["repository"].records[("owner", f["grant"].grant_id)] = f["grant"].model_copy(
        update={"maximum_sensitivity": "sensitive"}
    )
    with pytest.raises(ContextPreparationError, match="sensitivity_denied"):
        prepare(f)


def test_federation_export_requires_authoritative_completeness(federation):
    f = federation
    provider = f["runtime"].provider_factories[f["case"].export.provider_id]
    original = f["adapter"].fetch
    item = original(
        f["grant"], f["selection"], f["scope"], deadline=monotonic() + 100
    ).items[0]

    f["adapter"].fetch = lambda *args, **kwargs: FederationExportResult(
        items=(), complete=True, authoritative_empty_entities=(f["entity"],)
    )
    assert provider.fetch(f["selection"], f["scope"], deadline=monotonic() + 100) == ()

    f["adapter"].fetch = lambda *args, **kwargs: FederationExportResult(
        items=(item,), complete=False, continuation="next-page"
    )
    with pytest.raises(ContextPreparationError, match="export_incomplete"):
        provider.fetch(f["selection"], f["scope"], deadline=monotonic() + 100)

    second_entity = ContextEntityReference(
        **f["source"].model_dump(), entity_type="variant", entity_id="variant-3"
    )
    second_intent = f["intent"].model_copy(
        update={"grant_id": uuid4(), "entities": (f["entity"], second_entity)}
    )
    second_grant = f["authority"].create(f["principal"], second_intent)
    second_hint = FederationSelection(
        **{
            name: getattr(second_grant, name)
            for name in FederationSelection.model_fields
        }
    )
    second_selection = f["selection"].model_copy(update={"federation": second_hint})
    f["adapter"].fetch = lambda *args, **kwargs: FederationExportResult(
        items=(item,), complete=True
    )
    with pytest.raises(ContextPreparationError, match="export_incomplete"):
        provider.fetch(second_selection, f["scope"], deadline=monotonic() + 100)

    bounded_selection = f["selection"].model_copy(update={"max_results": 1})
    f["adapter"].fetch = lambda *args, **kwargs: FederationExportResult(
        items=(item, item.model_copy(update={"item_id": "variant-2:13"})), complete=True
    )
    with pytest.raises(ContextPreparationError, match="export_incomplete"):
        provider.fetch(bounded_selection, f["scope"], deadline=monotonic() + 100)

    f["adapter"].fetch = lambda *args, **kwargs: FederationExportResult(
        items=(item,), complete=False
    )
    with pytest.raises(ContextPreparationError, match="export_incomplete"):
        provider.fetch(f["selection"], f["scope"], deadline=monotonic() + 100)
    f["adapter"].fetch = original


def test_builder_rechecks_permissions_after_token_counting(federation):
    from personal_ai.context.builder import (
        SOURCE_CLASSES,
        ContextBuilder,
        ContextBuildItem,
        ContextBuildPolicy,
    )
    from personal_ai.context.contracts import ContextError
    from personal_ai.context.tokens import FakeTokenCounter
    from personal_ai.llm.client import ChatMessage

    f = federation

    class Revalidator:
        current = True

        def supports(self, dependency):
            return True

        def is_current(self, dependency):
            return self.current and self.supports(dependency)

    revalidator = Revalidator()

    class RevokingCounter(FakeTokenCounter):
        calls = 0

        def count(self, messages):
            result = super().count(messages)
            self.calls += 1
            if self.calls == 4:
                revalidator.current = False
            return result

    item = prepare(f)
    entry = ContextBuildItem.from_context_item(item, required=True)
    builder = ContextBuilder(
        RevokingCounter(),
        permission_revalidator=ContextPermissionRevalidatorRegistry((revalidator,)),
    )
    policy = ContextBuildPolicy(
        global_input_tokens=1000,
        source_max_tokens={category: 1000 for category in SOURCE_CLASSES},
    )
    with pytest.raises(ContextError, match="source_authority_changed"):
        builder.build((ChatMessage(role="user", content="plan"),), (entry,), policy)


def test_absent_federation_keeps_legacy_permission_serialization_stable():
    legacy = {
        "permission_id": "source",
        "version": "1",
        "purpose": "planning",
        "source_application_id": None,
        "destination_application_id": None,
    }
    assert ContextPermissionDependency.model_validate(legacy).model_dump(mode="json") == legacy


def test_registered_grant_api_idempotency_revocation_and_owner_isolation(federation):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_ai.api.dependencies import require_recent_auth
    from personal_ai.api.federation import authority_dependency, router

    f = federation
    app = FastAPI()
    app.include_router(router)
    app.state.application_registry = f["registry"]
    app.dependency_overrides.update(
        {require_recent_auth: lambda: f["principal"], authority_dependency: lambda: f["authority"]}
    )
    client = TestClient(app)
    request = {
        "idempotency_key": str(uuid4()),
        **{
            name: value
            for name, value in f["grant"].model_dump(mode="json").items()
            if name
            in (
                "source",
                "destination",
                "category",
                "purpose",
                "fields",
                "entities",
                "expires_at",
            )
        },
    }
    created = client.post("/v1/federation/grants", json=request)
    assert created.status_code == 201
    assert created.json()["source_policy"] == f["policy"].model_dump(mode="json")
    grant_id = created.json()["grant_id"]
    assert client.post("/v1/federation/grants", json=request).json()["grant_id"] == grant_id
    bad = client.post("/v1/federation/grants", json={**request, "purpose": "different"})
    assert bad.status_code == 409
    for _ in range(2):
        revoked = client.post(
            f"/v1/federation/grants/{grant_id}/revoke",
            json={"expected_revision": 1, "expected_issuance_id": created.json()["issuance_id"]},
        )
        assert revoked.status_code == 200
        assert revoked.json()["epoch"] == 2 and revoked.json()["state"] == "revoked"
    assert client.post("/v1/federation/grants", json=request).json()["state"] == "revoked"
    assert (
        client.post("/v1/federation/grants", json={**request, "re_delegation": True}).status_code
        == 422
    )
    assert client.post(
        "/v1/federation/grants",
        json={**request, "source_policy": f["policy"].model_dump(mode="json")},
    ).status_code == 422
    app.dependency_overrides[require_recent_auth] = lambda: AuthenticatedPrincipal(
        "issuer", "other", "other", None, 1, True
    )
    assert client.get(f"/v1/federation/grants/{grant_id}").status_code == 404
    assert f["adapter"].calls == 0


def test_destination_host_lists_only_current_grant_choices_without_permission_metadata(federation):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_ai.api.dependencies import get_request_scope, require_recent_auth
    from personal_ai.api.federation import choice_authority_dependency, router

    f = federation
    f["authority"].create(f["principal"], f["intent"])
    app = FastAPI()
    app.include_router(router)
    app.state.application_registry = f["registry"]
    app.dependency_overrides.update(
        {
            require_recent_auth: lambda: f["principal"],
            get_request_scope: lambda: f["scope"],
            choice_authority_dependency: lambda: f["authority"],
        }
    )

    source_checks_before_list = f["source_policy"].calls
    export_checks_before_list = f["adapter"].authorize_calls
    response = TestClient(app).get("/v1/federation/grants/choices")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    payload = response.json()
    assert len(payload["choices"]) == 1
    option = payload["choices"][0]
    assert option["category_label"] == "Synthetic Source · constraints"
    assert set(option) == {"id", "category_label"}
    assert len(option["id"]) == 43
    assert str(f["grant"].grant_id) not in response.text
    assert str(f["grant"].issuance_id) not in response.text
    assert "synthetic_source" not in response.text
    assert "variant-2" not in response.text
    assert "permission_id" not in response.text
    assert "source_revision" not in response.text
    assert f["source_policy"].calls == source_checks_before_list
    assert f["adapter"].authorize_calls == export_checks_before_list


def test_opaque_choice_handles_bind_owner_destination_issuance_and_current_grant(federation):
    f = federation
    source_checks_before_resolve = f["source_policy"].calls
    export_checks_before_resolve = f["adapter"].authorize_calls
    handle = f["authority"].current_choices(f["principal"], f["destination"])[0]["id"]
    choices = f["authority"].resolve_choice_handles(
        f["principal"], f["destination"], (handle,)
    )
    assert f["source_policy"].calls == source_checks_before_resolve
    assert f["adapter"].authorize_calls == export_checks_before_resolve
    assert len(choices) == 1
    assert choices[0].federation.grant_id == f["grant"].grant_id
    assert choices[0].fields == f["grant"].fields

    with pytest.raises(ValueError, match="federation_choice_invalid"):
        f["authority"].resolve_choice_handles(
            f["principal"],
            ApplicationScope(
                application_id=f["destination"].application_id,
                workspace_id="another-destination",
            ),
            (handle,),
        )
    other_owner = f["principal"].__class__("issuer", "other", "other-owner", None, 1, True)
    with pytest.raises(ValueError, match="federation_choice_invalid"):
        f["authority"].resolve_choice_handles(other_owner, f["destination"], (handle,))

    revoked = f["authority"].revoke(
        f["principal"],
        f["grant"].grant_id,
        expected_revision=f["grant"].revision,
        expected_issuance_id=f["grant"].issuance_id,
    )
    with pytest.raises(ValueError, match="federation_choice_invalid"):
        f["authority"].resolve_choice_handles(f["principal"], f["destination"], (handle,))

    f["repository"].records.pop((revoked.owner_id, revoked.grant_id))
    recreated = f["authority"].create(f["principal"], f["intent"])
    current_handle = f["authority"].current_choices(f["principal"], f["destination"])[0]["id"]
    assert recreated.issuance_id != f["grant"].issuance_id
    assert current_handle != handle
    with pytest.raises(ValueError, match="federation_choice_invalid"):
        f["authority"].resolve_choice_handles(f["principal"], f["destination"], (handle,))


def test_api_continuation_resolves_opaque_handles_before_shared_context_use(federation):
    from personal_ai.api.federation_choices import resolve_continuation_payload

    f = federation
    source_checks_before_resolve = f["source_policy"].calls
    export_checks_before_resolve = f["adapter"].authorize_calls
    handle = f["authority"].current_choices(f["principal"], f["destination"])[0]["id"]
    payload = ContinuationRequestPayload(
        content="Use the selected constraints.",
        idempotency_key=uuid4(),
        federation_choice_ids=(handle,),
    )
    internal = resolve_continuation_payload(
        payload, f["principal"], f["scope"], f["runtime"]
    )
    assert internal.federation_context[0].federation.grant_id == f["grant"].grant_id
    assert f["source_policy"].calls == source_checks_before_resolve
    assert f["adapter"].authorize_calls == export_checks_before_resolve

    selection = internal.explicit_context_selections[0]
    f["coordinator"].prepare(
        f["context"], (selection,), ContextProviderInputs(f["scope"])
    )
    assert f["source_policy"].calls > 0
    assert f["adapter"].authorize_calls > 0

    with pytest.raises(ValidationError):
        ContinuationRequestPayload.model_validate(
            {
                "content": "Use the selected constraints.",
                "idempotency_key": str(uuid4()),
                "choice": {"mode": "automatic"},
                "federation_context": [
                    internal.federation_context[0].model_dump(mode="json")
                ],
            }
        )

def test_concurrent_identical_grant_create_returns_canonical_record(federation, monkeypatch):
    f = federation
    barrier = Barrier(2)
    save = f["repository"].save

    def synchronized_save(grant, *, expected_revision):
        barrier.wait(timeout=5)
        return save(grant, expected_revision=expected_revision)

    monkeypatch.setattr(f["repository"], "save", synchronized_save)
    intent = f["intent"].model_copy(update={"grant_id": uuid4()})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(lambda _: f["authority"].create(f["principal"], intent), range(2))
        )
    assert results[0] == results[1]
    assert results[0].issuance_id == results[1].issuance_id


def test_concurrent_revoke_retries_return_same_terminal_record(federation, monkeypatch):
    f = federation
    barrier = Barrier(2)
    save = f["repository"].save

    def synchronized_save(grant, *, expected_revision):
        barrier.wait(timeout=5)
        return save(grant, expected_revision=expected_revision)

    monkeypatch.setattr(f["repository"], "save", synchronized_save)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda _: f["authority"].revoke(
                    f["principal"],
                    f["grant"].grant_id,
                    expected_revision=1,
                    expected_issuance_id=f["grant"].issuance_id,
                ),
                range(2),
            )
        )
    assert results[0] == results[1]
    assert results[0].state == "revoked" and results[0].revision == 2


def test_source_policy_epoch_change_blocks_existing_grant(federation):
    f = federation
    f["source_policy"].is_current = lambda dep: dep.version != "7"
    with pytest.raises(ContextPreparationError, match="source_policy_denied"):
        prepare(f)
    assert f["adapter"].calls == 0


def test_memory_or_cached_derived_projection_rechecks_shared_dependencies(federation):
    from personal_ai.context.builder import (
        SOURCE_CLASSES,
        ContextBuilder,
        ContextBuildItem,
        ContextBuildPolicy,
    )
    from personal_ai.context.tokens import FakeTokenCounter
    from personal_ai.llm.client import ChatMessage

    f = federation
    item = prepare(f)
    entry = ContextBuildItem(
        source_class="ai_memory",
        provider_id="ai_memory",
        source_id="memory",
        item_id="memory",
        content="derived memory",
        authority="derived",
        sensitivity="restricted",
        permission_dependencies=item.permission_dependencies,
    )
    builder = ContextBuilder(
        FakeTokenCounter(),
        permission_revalidator=ContextPermissionRevalidatorRegistry(
            f["runtime"].permission_revalidators
        ),
    )
    policy = ContextBuildPolicy(
        global_input_tokens=1000, source_max_tokens={category: 1000 for category in SOURCE_CLASSES}
    )
    token = bind_request_scope(f["scope"])
    try:
        assert builder.build(
            (ChatMessage(role="user", content="plan"),), (entry,), policy
        ).included_item_ids == ("memory",)
        f["authority"].revoke(f["principal"], f["grant"].grant_id, expected_revision=1)
        result = builder.build((ChatMessage(role="user", content="plan"),), (entry,), policy)
        assert result.included_item_ids == () and result.excluded_items == (
            ("memory", "permission_revoked"),
        )
    finally:
        reset_request_scope(token)


def test_direct_assembler_denies_grant_before_counter_or_source(federation):
    from personal_ai.context import ContextAssembler
    from personal_ai.entities import Message
    from personal_ai.settings import Settings

    f = federation

    class NoCalls:
        def count(self, messages):
            pytest.fail("counter invoked before grant authorization")

    f["repository"].records.clear()
    assembler = ContextAssembler(
        Settings(_env_file=None, ai_provider="fake", ai_model="fake"),
        NoCalls(),
        context_provider_coordinator=f["coordinator"],
    )
    user = Message(
        id=uuid4(),
        conversation_id=uuid4(),
        owner_id="owner",
        **f["destination"].model_dump(),
        role="user",
        status="completed",
        content="plan",
        created_at=f["now"],
    )
    with pytest.raises(ContextPreparationError, match="grant_denied"):
        assembler.assemble(
            (), user, application_context=f["context"], context_selections=(f["selection"],)
        )
    assert f["adapter"].calls == 0


def test_current_export_eligibility_is_required_for_fresh_and_derived_reuse(federation):
    f = federation
    token = bind_request_scope(f["scope"])
    try:
        dependency = f["grant"].dependency()
        assert f["authority"].is_current(dependency)
        assert f["source_policy"].is_current(f["policy"])
        f["adapter"].export_allowed = False
        assert f["grant"].state == "active" and f["grant"].epoch == 1
        assert not f["authority"].is_current(dependency)
        with pytest.raises(ContextPreparationError, match="source_policy_denied"):
            prepare(f)
        assert f["adapter"].calls == 0
    finally:
        reset_request_scope(token)


def test_source_adapter_requires_registered_export_authorization(federation):
    f = federation

    class RetrievalOnly:
        def fetch(self, *args, **kwargs):
            pytest.fail("retrieval-only source adapter used")

    with pytest.raises(ValueError, match="authorization_contract_required"):
        federation_contribution(
            (f["case"],), f["authority"], {f["case"].export.provider_id: RetrievalOnly()}
        )


def test_synthetic_export_uses_real_startup_contribution_catalog(federation, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_ai.api.dependencies import get_settings
    from personal_ai.context.deployment import default_context_runtime_catalog
    from personal_ai.federation.service import FederationPermissionAuthority
    from personal_ai.main import lifespan
    from personal_ai.settings import Settings

    f = federation
    monkeypatch.setattr(
        "personal_ai.main.validate_startup_configuration", lambda: None
    )
    monkeypatch.setattr("personal_ai.main.close_persistence_clients", lambda: None)
    class Factory:
        def federation_grant_repository(self):
            return f["repository"]
        def mutation_repository(self):
            class EmptyMutationRepository:
                def required_operation_contracts(self):
                    return ()
            return EmptyMutationRepository()

    monkeypatch.setattr(
        "personal_ai.persistence.factory.persistence_factory", lambda _settings: Factory()
    )
    settings = Settings(_env_file=None, ai_provider="fake", ai_model="fake")
    source_contribution = ContextRuntimeContribution(
        {},
        permission_revalidators=(f["source_policy"],),
        export_adapters={f["case"].export.provider_id: f["adapter"]},
        federation_cases=(f["case"],),
    )
    catalog = default_context_runtime_catalog()
    catalog.register("synthetic-five", lambda _settings: source_contribution)

    app = FastAPI(lifespan=lifespan)
    app.state.application_registry = f["registry"]
    app.state.context_runtime_catalog = catalog
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app):
        runtime = app.state.context_runtime_registry
        registry = app.state.application_registry
        registration = registry.registration(f["scope"].application_id)
        assert next(
            cap
            for cap in registration.context_providers
            if cap.capability_id == f["case"].export.provider_id
        ).available
        provider = runtime.provider_factories[f["case"].export.provider_id]
        authority = next(
            item
            for item in runtime.permission_revalidators
            if isinstance(item, FederationPermissionAuthority)
        )
        assert provider.adapter is f["adapter"]
        assert provider.authority is authority
        assert f["source_policy"] in authority.source_permissions.validators

    f["context"] = f["context"].model_copy(
        update={"context_provider_capabilities": registration.context_providers}
    )
    f["coordinator"] = ContextProviderCoordinator(runtime.provider_factories)
    assert prepare(f).source_version == "variant-v12"
    assert f["adapter"].calls == 1
    assert f["case"] not in INITIAL_FEDERATION_CASES

    unavailable = ContextRuntimeContribution(
        {},
        permission_revalidators=(f["source_policy"],),
        federation_cases=(f["case"],),
    )
    unavailable_catalog = default_context_runtime_catalog()
    unavailable_catalog.register("synthetic-five", lambda _settings: unavailable)
    unavailable_app = FastAPI(lifespan=lifespan)
    unavailable_app.state.application_registry = f["registry"]
    unavailable_app.state.context_runtime_catalog = unavailable_catalog
    unavailable_app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(unavailable_app):
        unavailable_provider = unavailable_app.state.context_runtime_registry.provider_factories[
            f["case"].export.provider_id
        ]
        unavailable_capability = next(
            cap
            for cap in unavailable_app.state.application_registry
            .registration(f["scope"].application_id).context_providers
            if cap.capability_id == f["case"].export.provider_id
        )
        assert unavailable_provider.adapter is None
        assert unavailable_capability.available is False


@pytest.mark.parametrize("change", ("expiry", "revocation"))
def test_grant_changed_during_export_authorization_denies_before_source_read(federation, change):
    f = federation

    def authorize(grant, selection, scope, *, deadline):
        if change == "expiry":
            f["authority"].clock = lambda: f["grant"].expires_at
        else:
            f["authority"].revoke(f["principal"], grant.grant_id, expected_revision=1)
        return True

    f["adapter"].authorize_export = authorize
    with pytest.raises(ContextPreparationError, match="grant_denied"):
        prepare(f)
    assert f["adapter"].calls == 0


def test_recreated_grant_cannot_reauthorize_old_selection_or_dependency(federation):
    from personal_ai.federation.contracts import FederationGrantConflict

    f = federation
    old_dependency = f["grant"].dependency()
    f["repository"].records.clear()  # Simulate physical purge of grant authority.
    replacement = f["grant"].model_copy(update={"issuance_id": uuid4()})
    replacement = f["authority"].create(f["principal"], replacement)
    assert replacement.grant_id == f["grant"].grant_id
    assert replacement.revision == f["grant"].revision == 1
    with pytest.raises(ContextPreparationError, match="scope_denied"):
        prepare(f)
    assert f["adapter"].calls == 0
    token = bind_request_scope(f["scope"])
    try:
        assert not f["authority"].is_current(old_dependency)
    finally:
        reset_request_scope(token)
    with pytest.raises(FederationGrantConflict, match="issuance_conflict"):
        f["authority"].revoke(
            f["principal"],
            replacement.grant_id,
            expected_revision=1,
            expected_issuance_id=f["grant"].issuance_id,
        )
    assert f["repository"].get("owner", replacement.grant_id).state == "active"


def test_issuance_identity_cannot_change_inside_an_existing_grant_lifetime(federation):
    f = federation
    with pytest.raises(PersistenceConflict):
        f["repository"].save(
            f["grant"].model_copy(update={"revision": 2, "epoch": 2, "issuance_id": uuid4()}),
            expected_revision=1,
        )
