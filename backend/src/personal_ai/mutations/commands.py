"""Resolve immutable domain commands using the existing revocable federation seam."""

from hashlib import sha256
from time import monotonic

from personal_ai.auth.scope import ApplicationScope
from personal_ai.contracts.context_references import ContextEntityReference
from personal_ai.contracts.delegated_tasks import (
    COMMAND_READ_FINGERPRINT,
    DelegatedCommandRead,
    DelegatedSourceCommand,
    canonical_bytes,
)
from personal_ai.federation.broker import FederationProvider
from personal_ai.mutations.contracts import (
    MutationError,
    MutationUnavailableError,
    OperationRef,
    ProposalIntent,
    UserCommandProvenance,
)


class SourceCommandResolver:
    """Resolve opaque selectors, never accept browser-supplied authority or payload."""

    def __init__(self, clients, runtime, *, clock):
        self.clients, self.runtime, self.clock = clients, runtime, clock

    def resolve(self, principal, scope, selector):
        client = self.clients.get(selector.source_application_id)
        if client is None:
            raise MutationUnavailableError("mutation_command_source_unavailable")
        request = DelegatedCommandRead(
            destination_application_id=selector.source_application_id,
            command_id=selector.command_id,
        )
        command = DelegatedSourceCommand.model_validate_json(
            client.post(
                "/internal/personal-ai/commands/read",
                request.model_dump(mode="json"),
                principal=principal,
                maximum_bytes=16_384,
                contract_fingerprint=COMMAND_READ_FINGERPRINT,
            )
        )
        if (
            command.source_application_id != selector.source_application_id
            or command.command_id != selector.command_id
            or command.destination_application_id != scope.application_id
            or command.workspace_id != scope.workspace_id
            or command.expires_at <= self.clock()
        ):
            raise MutationError("mutation_command_scope_denied")
        providers = [
            provider
            for provider in self.runtime.provider_factories.values()
            if isinstance(provider, FederationProvider)
            and provider.case.source_application_id == command.source_application_id
            and provider.case.destination_application_id == scope.application_id
        ]
        if not providers:
            raise MutationUnavailableError("mutation_command_federation_unavailable")
        choices = providers[0].authority.resolve_choice_handles(
            principal,
            ApplicationScope(application_id=scope.application_id, workspace_id=scope.workspace_id),
            (command.context_choice_id,),
        )
        choice = choices[0]
        source = ContextEntityReference(
            application_id=command.source_application_id,
            workspace_id=None,
            entity_type=command.source_entity_type,
            entity_id=command.source_entity_id,
        )
        if choice.federation.source.workspace_id is not None or choice.federation.entities != (
            source,
        ):
            raise MutationError("mutation_command_source_denied")
        provider = self.runtime.provider_factories.get(choice.provider_id)
        if provider not in providers:
            raise MutationError("mutation_command_source_denied")
        items = provider.fetch(choice.context_selection(), scope, deadline=monotonic() + 3.0)
        if len(items) != 1 or items[0].source_version != command.expected_source_version:
            raise MutationError("mutation_command_source_stale")
        item = items[0]
        grant = provider.authority.repository.get(scope.owner_id, choice.federation.grant_id)
        if grant is None or not grant.current(self.clock()):
            raise MutationError("mutation_command_source_denied")
        expires_at = min(command.expires_at, grant.expires_at)
        if item.expires_at is None or item.expires_at < expires_at:
            raise MutationError("mutation_command_expiry_denied")
        # Freeze source identity and the original command expiry. Fresh retrieval
        # timestamps cannot create different intent on duplicate submission.
        snapshot = item.authority_snapshot().model_copy(update={"expires_at": expires_at})
        return ProposalIntent(
            idempotency_key=command.command_id,
            target=ContextEntityReference(
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                entity_type="project",
                entity_id=str(command.target_entity_id),
            ),
            operation=OperationRef(
                operation_id=command.operation_id, version=command.operation_version
            ),
            payload_schema_id=command.payload_schema_id,
            payload=command.payload,
            expected_domain_version=command.expected_domain_version,
            rationale=command.rationale,
            producer=UserCommandProvenance(
                source_application_id=command.source_application_id,
                command_id=command.command_id,
                acting_user_id=scope.acting_user_id,
                command_fingerprint=sha256(
                    canonical_bytes(command.model_dump(mode="json"))
                ).hexdigest(),
            ),
            sources=(snapshot,),
            operation_contract_fingerprint=command.operation_contract_fingerprint,
            expires_at=expires_at,
        )
