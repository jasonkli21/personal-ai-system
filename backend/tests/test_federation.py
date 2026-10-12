"""Federation conformance through shared registration, policy and provider composition."""

from datetime import UTC, datetime, timedelta
from threading import RLock
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
from personal_ai.contracts.federation import FederationExportDeclaration, FederationSelection
from personal_ai.federation.broker import FederationCase, federation_contribution
from personal_ai.federation.contracts import FederationGrant
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

    def save(self, grant, *, expected_revision):
        with self.lock:
            validate_transition(self.get(grant.owner_id, grant.grant_id), grant, expected_revision)
            self.records[grant.owner_id, grant.grant_id] = grant
        return grant


class SourcePolicy:
    permission_namespaces = ("synthetic_policy:", "synthetic_revision:")
    current = True

    def supports(self, dependency):
        return dependency.permission_id.startswith(self.permission_namespaces)

    def is_current(self, dependency):
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
    authority = FederationPermissionAuthority(repository, source_policy)
    grant = FederationGrant(
        grant_id=uuid4(),
        issuance_id=uuid4(),
        revision=1,
        epoch=1,
        source=source,
        destination=destination,
        owner_id="owner",
        acting_user_id="issuer|user",
        category="constraints",
        purpose="planning",
        entities=(entity,),
        fields=("constraint",),
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
        source_policy=policy,
        sensitivity="sensitive",
        maximum_sensitivity="restricted",
    )
    principal = AuthenticatedPrincipal("issuer", "user", "owner", None, 1, True)
    grant = authority.create(principal, grant)
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
        hook = None
        export_allowed = True

        def authorize_export(self, granted, selected, acting_scope, *, deadline):
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
            return (
                ContextItem(
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
                ),
            )

    adapter = Adapter()
    runtime = compose_context_runtime(
        ContextRuntimeContribution({}, permission_revalidators=(source_policy,)),
        federation_contribution((case,), authority, {case.export.provider_id: adapter}),
    )
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
            item = f["adapter"].fetch(granted, selected, acting_scope, deadline=deadline)[0]
            return (
                item.model_copy(
                    update={
                        **source.model_dump(),
                        "entity_refs": (entity,),
                        "permission_dependencies": (policy, revision),
                        "payload": payload_type(**{name: "bounded" for name in selected.fields}),
                    }
                ),
            )

    provider = FederationProvider(case, f["authority"], Adapter())
    item = provider.fetch(selection, scope, deadline=100)[0]
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
        f["adapter"].fetch = lambda *args, updates=updates, **kwargs: tuple(
            item.model_copy(update=updates) for item in original(*args, **kwargs)
        )
        with pytest.raises(ContextPreparationError):
            provider.fetch(f["selection"], f["scope"], deadline=100)
    f["adapter"].fetch = original
    f["repository"].records[("owner", f["grant"].grant_id)] = f["grant"].model_copy(
        update={"maximum_sensitivity": "sensitive"}
    )
    with pytest.raises(ContextPreparationError, match="sensitivity_denied"):
        prepare(f)


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
                "source_policy",
            )
        },
    }
    created = client.post("/v1/federation/grants", json=request)
    assert created.status_code == 201
    grant_id = created.json()["grant_id"]
    assert client.post("/v1/federation/grants", json=request).json()["grant_id"] == grant_id
    bad = client.post("/v1/federation/grants", json={**request, "purpose": "different"})
    assert bad.status_code == 422
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
    app.dependency_overrides[require_recent_auth] = lambda: AuthenticatedPrincipal(
        "issuer", "other", "other", None, 1, True
    )
    assert client.get(f"/v1/federation/grants/{grant_id}").status_code == 404
    assert f["adapter"].calls == 0


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


def test_synthetic_export_uses_configured_production_registration_path(federation, monkeypatch):
    from personal_ai.federation.deployment import (
        configured_federation_contribution,
        reconcile_federation_runtime_metadata,
    )
    from personal_ai.settings import Settings

    f = federation

    class Factory:
        def federation_grant_repository(self):
            return f["repository"]

    monkeypatch.setattr(
        "personal_ai.persistence.factory.persistence_factory", lambda settings: Factory()
    )
    source_contribution = ContextRuntimeContribution(
        {},
        permission_revalidators=(f["source_policy"],),
        export_adapters={f["case"].export.provider_id: f["adapter"]},
    )
    source_runtime = compose_context_runtime(source_contribution)
    installed = configured_federation_contribution(
        Settings(_env_file=None, ai_provider="fake", ai_model="fake"),
        source_runtime,
        cases=(f["case"],),
    )
    runtime = compose_context_runtime(source_contribution, installed)
    registry = reconcile_federation_runtime_metadata(f["registry"], runtime)
    registration = registry.registration(f["scope"].application_id)
    assert next(
        cap
        for cap in registration.context_providers
        if cap.capability_id == f["case"].export.provider_id
    ).available
    f["context"] = f["context"].model_copy(
        update={"context_provider_capabilities": registration.context_providers}
    )
    f["coordinator"] = ContextProviderCoordinator(runtime.provider_factories)
    assert prepare(f).source_version == "variant-v12"
    assert f["adapter"].calls == 1
    assert f["case"] not in INITIAL_FEDERATION_CASES
    with pytest.raises(ValueError, match="registration_invalid"):
        configured_federation_contribution(
            Settings(_env_file=None, ai_provider="fake", ai_model="fake"), source_runtime
        )


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
