"""Connect the private source slice to the existing PAS context seams."""

from dataclasses import replace

from pydantic import BaseModel, ConfigDict

from personal_ai.auth.scope import (
    ApplicationScope,
    current_request_scope,
    current_verified_principal,
)
from personal_ai.context.providers import (
    ContextFieldSensitivity,
    ContextItem,
    ContextOperationSpec,
    ContextPreparationError,
    ContextProviderError,
    ContextProviderSpec,
)
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
    ContextSourceReference,
)

from .client import TurnBudget
from .source import namespace, record_id, source_version
from .wire import SCHEMA, ProtocolError


class Itinerary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    title: str | None = None
    platform: str | None = None


class Workout(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    title: str | None = None
    duration_minutes: int | None = None


PAYLOADS = {"itinerary_leg": Itinerary, "workout": Workout}


def permission_dependency(result):
    record, grant = result.value, result.grant
    partition = namespace(grant.source_id, grant.app, grant.workspace, grant.owner, grant.kind)
    return ContextPermissionDependency(
        source_scope=ApplicationScope(application_id=grant.app, workspace_id=grant.workspace),
        entity_ref=ContextEntityReference(
            entity_type=grant.kind, entity_id=record_id(partition, record.record_ref, record.source_revision),
            application_id=grant.app, workspace_id=grant.workspace,
        ),
        source_revision=record.source_revision,
        permission_id=grant.id, version=grant.dependency_version, purpose=grant.purpose,
        owner_id=grant.owner, acting_user_id=grant.actor,
    )


def context_item(result):
    record, grant = result.value, result.grant
    dependency = permission_dependency(result)
    return ContextItem(
        source_class="domain_current", provider_id=grant.source_id, source_id=grant.source_id,
        source_version=source_version(record.source_revision), item_id=dependency.entity_ref.entity_id,
        owner_id=grant.owner, application_id=grant.app, workspace_id=grant.workspace,
        entity_refs=(dependency.entity_ref,), authority="authoritative",
        observed_at=record.observed_at, effective_at=record.effective_at,
        expires_at=result.expires_at, sensitivity=result.sensitivity,
        source_refs=(ContextSourceReference(kind="record", reference_id=dependency.entity_ref.entity_id),),
        field_sensitivity=tuple(
            ContextFieldSensitivity(field=field, sensitivity=label)
            for field, label in result.field_sensitivity
        ),
        permission_dependencies=(dependency,),
        payload=PAYLOADS[grant.kind].model_validate(record.content_projection),
    )


class DisclosureAuthority:
    """Request-local witnesses identify what to recheck. They confer no authority."""

    def __init__(self, client):
        self.client = client
        self._witnesses = {}

    def bind(self, results, principal, scope, budget, caller):
        for result in results:
            self._witnesses[permission_dependency(result)] = result, principal, scope, budget, caller

    def is_current(self, dependency):
        witness = self._witnesses.get(dependency)
        if witness is None:
            return False
        result, principal, scope, budget, caller = witness
        if current_verified_principal() != principal or current_request_scope() != scope:
            return False
        try:
            budget.check()
            self.client.revalidate(result, principal, scope, caller)
            budget.check()
            return True
        except (ProtocolError, TimeoutError):
            return False


class SourceProvider:
    def __init__(self, source_id, schema, client, intent, counter, disclosure, caller, *, query=""):
        self.spec = ContextProviderSpec(
            provider_id=source_id, source_class="domain_current", source_version=SCHEMA,
            operations=(ContextOperationSpec(
                operation="search", allowed_fields=tuple(schema.field_types), maximum_results=10,
            ),),
        )
        self.client = client
        self.intent = intent
        self.counter = counter
        self.disclosure = disclosure
        self.caller = caller
        self.kind = schema.kind
        self.query = query

    def validate_selection(self, selection, inputs):
        if selection.provider_id != self.intent.source_id or inputs.application_context is None:
            raise ContextPreparationError("context_provider_scope_mismatch")

    def fetch(self, selection, scope, *, deadline):
        budget = TurnBudget(
            deadline, self.counter, max_bytes=selection.max_bytes,
            max_tokens=selection.max_tokens or 16_384, max_results=selection.max_results,
        )
        principal = current_verified_principal()
        try:
            page = self.client.read(
                "search", principal, scope, replace(self.intent, fields=("title",)), budget,
                caller=self.caller, record_kind=self.kind,
                query=self.query, limit=selection.max_results,
            )
            projections = tuple(
                self.client.read(
                    "fetch", principal, scope, replace(self.intent, fields=selection.fields), budget,
                    caller=self.caller, record_ref=hit.record_ref, source_revision=hit.source_revision,
                )
                for hit in page.value.items
            )
            # A later fetch can invalidate any earlier projection or the search page.
            self.client.revalidate(page, principal, scope, self.caller)
            for result in projections:
                self.client.revalidate(result, principal, scope, self.caller)
            budget.check()
            items = tuple(context_item(result) for result in projections)
            self.disclosure.bind(projections, principal, scope, budget, self.caller)
            return items
        except ProtocolError as error:
            code = "context_source_failed" if error.code == "source_unavailable" else error.code
            raise ContextProviderError(code) from error
