from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4

import pytest

from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    bind_request_scope,
    reset_request_scope,
)
from personal_ai.context.health_federation import (
    HEALTH_DIETARY_TO_TRAVEL_PROVIDER_ID,
    HEALTH_ERGONOMIC_TO_SHOPPING_PROVIDER_ID,
    HealthDietaryPayload,
    HealthErgonomicPayload,
    HealthFederationExportAdapter,
    HealthFederationPermissionRevalidator,
    HealthFederationRecord,
    HealthFederationRequest,
    HealthFederationResponse,
    HealthFederationSourceReference,
)
from personal_ai.context.providers import ContextEntityReference, ContextPreparationError
from personal_ai.contracts.federation import FederationContextChoice, FederationSelection
from personal_ai.federation.contracts import FederationGrant, FederationGrantIntent


class FakeHealthFederationClient:
    def __init__(self, record: HealthFederationRecord, *, authoritative_empty: bool = False):
        self.record = record
        self.authoritative_empty = authoritative_empty
        self.requests: list[HealthFederationRequest] = []

    def read(self, request: HealthFederationRequest, _scope, *, deadline: float):
        assert deadline > monotonic()
        self.requests.append(request)
        return HealthFederationResponse(
            operation=request.operation,
            complete=True,
            authoritative_empty=(
                request.operation == "read" and self.authoritative_empty
            ),
            item=self.record if request.operation == "read" else self.record.model_copy(update={"payload": None}),
        )


def _record(purpose: str, entity_id: str, value: object = "Synthetic constraint"):
    category, destination, field, _provider_id = {
        "health_dietary_restrictions_to_travel": (
            "dietary_restrictions", "travel", "dietary_restrictions",
            HEALTH_DIETARY_TO_TRAVEL_PROVIDER_ID,
        ),
        "health_ergonomic_constraints_to_shopping": (
            "ergonomic_constraints", "shopping", "ergonomic_constraints",
            HEALTH_ERGONOMIC_TO_SHOPPING_PROVIDER_ID,
        ),
    }[purpose]
    revision = 3
    fingerprint = "a" * 64
    payload = (
        HealthDietaryPayload(dietary_restrictions=value)
        if field == "dietary_restrictions"
        else HealthErgonomicPayload(ergonomic_constraints=value)
    )
    return HealthFederationRecord(
        category=category,
        entity_id=UUID(entity_id),
        source_revision=revision,
        source_version=f"health-object-v1:r{revision}:schema-1",
        payload=payload,
        source_refs=(
            HealthFederationSourceReference(
                kind="record", reference_id=entity_id, fingerprint=fingerprint
            ),
            HealthFederationSourceReference(
                kind="source", reference_id=str(uuid4()), fingerprint=fingerprint
            ),
        ),
        permission_dependencies=(
            {
                "permission_id": f"health_federation:{purpose}:{entity_id}",
                "version": f"health-object-v1:r{revision}:ai1:cross1",
                "purpose": purpose,
                "source_application_id": "health",
                "destination_application_id": destination,
            },
        ),
    )


def _case(purpose: str, *, record: HealthFederationRecord | None = None, empty=False):
    category, destination, field, provider_id = {
        "health_dietary_restrictions_to_travel": (
            "dietary_restrictions", "travel", "dietary_restrictions",
            HEALTH_DIETARY_TO_TRAVEL_PROVIDER_ID,
        ),
        "health_ergonomic_constraints_to_shopping": (
            "ergonomic_constraints", "shopping", "ergonomic_constraints",
            HEALTH_ERGONOMIC_TO_SHOPPING_PROVIDER_ID,
        ),
    }[purpose]
    entity_id = str(record.entity_id) if record is not None else str(uuid4())
    entity = ContextEntityReference(
        entity_type="profile_item",
        entity_id=entity_id,
        application_id="health",
        workspace_id=None,
    )
    source = ApplicationScope(application_id="health")
    target = ApplicationScope(application_id=destination)
    response_record = record or _record(purpose, entity_id, None if empty else "Synthetic constraint")
    client = FakeHealthFederationClient(response_record, authoritative_empty=empty)
    adapter = HealthFederationExportAdapter(client, purpose)
    now = datetime.now(UTC)
    intent = FederationGrantIntent(
        grant_id=uuid4(),
        owner_id="verified-owner",
        acting_user_id="https://accounts.google.com|verified-user",
        source=source,
        destination=target,
        category=category,
        purpose=purpose,
        entities=(entity,),
        fields=(field,),
        expires_at=now + timedelta(minutes=5),
    )
    source_policy = adapter.resolve_source_policy(intent, deadline=monotonic() + 1)
    grant = FederationGrant(
        grant_id=intent.grant_id,
        issuance_id=uuid4(),
        revision=1,
        epoch=1,
        source=source,
        destination=target,
        owner_id=intent.owner_id,
        acting_user_id=intent.acting_user_id,
        category=category,
        purpose=purpose,
        entities=(entity,),
        fields=(field,),
        expires_at=intent.expires_at,
        created_at=now,
        updated_at=now,
        source_policy=source_policy,
        sensitivity="restricted",
        maximum_sensitivity="restricted",
    )
    selection = FederationContextChoice(
        provider_id=provider_id,
        fields=(field,),
        federation=FederationSelection(
            grant_id=grant.grant_id,
            issuance_id=grant.issuance_id,
            revision=grant.revision,
            epoch=grant.epoch,
            source=source,
            category=category,
            purpose=purpose,
            entities=(entity,),
        ),
    ).context_selection()
    scope = RequestScope(
        application_id=destination,
        owner_id=grant.owner_id,
        acting_user_id=grant.acting_user_id,
        request_id="health-federation-test",
    )
    return adapter, client, intent, grant, selection, scope, entity, field


@pytest.mark.parametrize(
    "purpose",
    (
        "health_dietary_restrictions_to_travel",
        "health_ergonomic_constraints_to_shopping",
    ),
)
def test_health_federation_exports_only_the_exact_granted_field(purpose: str) -> None:
    adapter, client, _intent, grant, selection, scope, entity, field = _case(purpose)

    assert adapter.authorize_export(grant, selection, scope, deadline=monotonic() + 1)
    exported = adapter.fetch(grant, selection, scope, deadline=monotonic() + 1)

    assert exported.complete is True
    assert exported.authoritative_empty_entities == ()
    assert len(exported.items) == 1
    item = exported.items[0]
    assert item.entity_refs == (entity,)
    assert item.field_sensitivity[0].field == field
    assert item.source_version == "health-object-v1:r3:schema-1"
    assert item.permission_dependencies == (grant.source_policy,)
    assert [request.operation for request in client.requests] == ["verify", "verify", "read"]


def test_health_federation_translates_explicit_empty_result_without_inventing_an_item() -> None:
    adapter, _client, _intent, grant, selection, scope, entity, _field = _case(
        "health_dietary_restrictions_to_travel", empty=True
    )

    exported = adapter.fetch(grant, selection, scope, deadline=monotonic() + 1)

    assert exported.items == ()
    assert exported.complete is True
    assert exported.authoritative_empty_entities == (entity,)


@pytest.mark.parametrize("mismatch", ("entity", "permission", "purpose", "revision", "source_ref"))
def test_health_federation_rejects_mismatched_source_identity(mismatch: str) -> None:
    purpose = "health_dietary_restrictions_to_travel"
    entity_id = str(uuid4())
    record = _record(purpose, entity_id)
    updates = {
        "entity": {"entity_id": uuid4()},
        "permission": {
            "permission_dependencies": (
                record.permission_dependencies[0].model_copy(
                    update={"permission_id": "health_federation:wrong:" + entity_id}
                ),
            )
        },
        "purpose": {
            "permission_dependencies": (
                record.permission_dependencies[0].model_copy(update={"purpose": "wrong"}),
            )
        },
        "revision": {"source_version": "health-object-v1:r4:schema-1"},
        "source_ref": {
            "source_refs": (
                record.source_refs[0].model_copy(update={"reference_id": str(uuid4())}),
                record.source_refs[1],
            )
        },
    }
    mismatch_record = record.model_copy(update=updates[mismatch])
    with pytest.raises(ContextPreparationError):
        _case(purpose, record=mismatch_record)


def test_health_permission_revalidator_rechecks_the_same_complete_dependency() -> None:
    _adapter, client, _intent, grant, _selection, scope, entity, _field = _case(
        "health_dietary_restrictions_to_travel"
    )
    revalidator = HealthFederationPermissionRevalidator(client)
    token = bind_request_scope(scope)
    try:
        assert revalidator.supports(grant.source_policy)
        assert revalidator.is_current(grant.source_policy)
        assert str(client.requests[-1].entity_id) == entity.entity_id
    finally:
        reset_request_scope(token)


def test_health_federation_stays_unregistered_when_identity_gate_is_off() -> None:
    from personal_ai.context.health import configured_health_context_contribution
    from personal_ai.settings import Settings

    contribution = configured_health_context_contribution(
        Settings(_env_file=None, app_environment="test", ai_provider="fake", ai_model="fake")
    )
    assert contribution.provider_factories == {}
    assert contribution.export_adapters == {}
    assert contribution.permission_revalidators == ()
