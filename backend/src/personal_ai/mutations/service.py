"""One generic controller for confirmed, domain-authorized external effects."""

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4, uuid5

from personal_ai.mutations.contracts import (
    Confirmation,
    DomainOutcome,
    DomainValidation,
    MutationAdapterContractError,
    MutationCandidateInvalidError,
    MutationCandidateNotApplicableError,
    MutationCandidateRequest,
    MutationError,
    MutationProposal,
    MutationUnavailableError,
    ProducerProvenance,
    ProposalIntent,
    ProposalView,
    TypedMutationCandidate,
    proposal_identity,
)
from personal_ai.mutations.registration import operation_adapter
from personal_ai.storage.errors import PersistenceConflict

TERMINAL = {"applied", "rejected", "expired"}


class MutationService:
    def __init__(self, repository, registry, runtime, permissions, *, output_resolver=None, clock=None):
        self.repository = repository
        self.registry = registry
        self.runtime = runtime
        self.permissions = permissions
        self.output_resolver = output_resolver
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _identity(principal, scope):
        if (not principal.authenticated or principal.owner_id != scope.owner_id
            or scope.acting_user_id != f"{principal.issuer}|{principal.subject}"):
            raise MutationError("mutation_identity_denied")

    def _adapter(self, scope, intent, *, require_policy=True):
        if (intent.target.application_id != scope.application_id
            or intent.target.workspace_id != scope.workspace_id):
            raise MutationError("mutation_target_scope_denied")
        definition = self.registry.get(scope.application_id)
        if ((definition.workspace_kind == "unsupported" and scope.workspace_id is not None)
            or (definition.workspace_kind == "required" and scope.workspace_id is None)):
            raise MutationError("mutation_workspace_denied")
        try:
            adapter = operation_adapter(
                self.registry,
                self.runtime,
                scope,
                intent.operation,
                contract_fingerprint=intent.operation_contract_fingerprint,
                require_policy=require_policy,
            )
        except MutationError as error:
            if "implementation_unavailable" in error.code:
                raise MutationUnavailableError(error.code) from error
            raise
        if (intent.payload_schema_id != adapter.declaration.payload_schema_id
            or intent.target.entity_type not in adapter.declaration.entity_types):
            raise MutationError("mutation_schema_unsupported")
        # Validate strictly without coercion/default insertion changing confirmed bytes.
        parsed = adapter.payload_model.model_validate(intent.payload, strict=True)
        if parsed.model_dump(mode="json") != intent.payload:
            raise MutationError("mutation_payload_not_canonical")
        return adapter

    def _authorize(self, adapter, scope, proposal, action):
        try:
            allowed = adapter.authorize(scope, proposal.intent.target, action=action)
        except Exception as error:
            raise MutationUnavailableError("mutation_authority_unavailable") from error
        if allowed is not True:
            raise MutationError("mutation_authorization_denied")

    def _dependencies(self, scope, proposal):
        dependencies = []
        for source in proposal.intent.sources:
            if (source.owner_id != scope.owner_id or not source.permission_dependencies
                or (source.expires_at is not None and source.expires_at <= self.clock())):
                raise MutationError("mutation_source_stale")
            dependencies.extend(source.permission_dependencies)
        if proposal.validation:
            dependencies.extend(proposal.validation.permission_dependencies)
        for dependency in dependencies:
            if (dependency.owner_id is not None and dependency.owner_id != scope.owner_id) or (
                dependency.acting_user_id is not None
                and dependency.acting_user_id != scope.acting_user_id
            ):
                raise MutationError("mutation_source_denied")
            try:
                current = self.permissions.is_current(dependency)
            except Exception as error:
                raise MutationUnavailableError("mutation_source_authority_unavailable") from error
            if current is not True:
                raise MutationError("mutation_source_denied")

    def _load_control_record(self, principal, scope, proposal_id, *, require_policy=True):
        self._identity(principal, scope)
        proposal = self.repository.get(scope, proposal_id)
        if proposal is None or proposal.acting_user_id != scope.acting_user_id:
            raise MutationError("mutation_not_found")
        adapter = self._adapter(scope, proposal.intent, require_policy=require_policy)
        return proposal, adapter

    def load_control_record(self, principal, scope, proposal_id):
        """Internal orchestration read. Callers must not disclose its source-derived fields."""
        proposal, adapter = self._load_control_record(
            principal, scope, proposal_id, require_policy=False
        )
        self._authorize(adapter, scope, proposal, "read")
        if proposal.state in {"proposed", "validated", "confirmed"}:
            self._dependencies(scope, proposal)
        return proposal

    def _present(self, principal, scope, proposal):
        """Capability + implementation + policy + current authority, never UI truth."""
        self._identity(principal, scope)
        if proposal.owner_id != scope.owner_id or proposal.acting_user_id != scope.acting_user_id:
            raise MutationError("mutation_not_found")
        adapter = self._adapter(scope, proposal.intent, require_policy=False)
        self._authorize(adapter, scope, proposal, "read")
        # After an effect, the original target revision can legitimately be stale.
        # Never redisclose derived input/preview through outcome/status reads.
        show_input = proposal.state in {"proposed", "validated", "confirmed"}
        if show_input:
            self._dependencies(scope, proposal)
        available = False
        try:
            current_adapter = self._adapter(scope, proposal.intent)
            self._authorize(current_adapter, scope, proposal, "execute")
            available = bool(
                proposal.state in {"validated", "confirmed"} and proposal.validation
                and proposal.validation.valid and proposal.validation.expires_at > self.clock()
                and proposal.intent.expires_at > self.clock()
            )
        except MutationError:
            pass
        # Client IDs/digests are references, not reusable authorization proofs.
        public = proposal.model_dump(mode="json", exclude={
            "owner_id": True, "acting_user_id": True,
            "domain_operation_key": True, "execution_attempt_id": True,
            "reconciliation_id": True, "lease_until": True,
            "intent": {"sources": True, "operation_contract_fingerprint": True},
            "validation": {"permission_dependencies": True},
            "confirmation": {"acting_user_id": True},
            "outcome": {"domain_operation_key": True},
        })
        public["schema_version"] = "mutation-proposal-view-v1"
        public["intent"]["source_refs"] = [
            ref.model_dump(mode="json") for source in proposal.intent.sources
            for ref in source.source_refs
        ]
        if not show_input:
            public["intent"]["payload"] = None
            public["intent"]["rationale"] = None
            public["intent"]["source_refs"] = []
            if public["validation"]:
                public["validation"]["preview"] = None
        return ProposalView(proposal=public, binding=proposal.binding(), apply_available=available)

    def read_view(self, principal, scope, proposal_id):
        """Disclosure-safe read for routes and other public presentation boundaries."""
        proposal = self.load_control_record(principal, scope, proposal_id)
        return self._present(principal, scope, proposal)

    def _save(self, proposal, **changes):
        candidate = MutationProposal.model_validate(proposal.model_dump() | {
            "revision": proposal.revision + 1, "updated_at": self.clock(), **changes,
        })
        return self.repository.save(candidate, expected_revision=proposal.revision)

    def _expire(self, proposal):
        expiry = min(proposal.intent.expires_at, proposal.validation.expires_at
                     if proposal.validation else proposal.intent.expires_at)
        if self.clock() >= expiry:
            self._save(proposal, state="expired", terminal_code="confirmation_expired")
            raise MutationError("mutation_expired")

    def create_from_output(self, principal, scope, candidate: MutationCandidateRequest):
        """Resolve canonical producer and source authority from a persisted completed output."""
        self._identity(principal, scope)
        if self.output_resolver is None:
            raise MutationUnavailableError("mutation_output_resolver_unavailable")
        candidate = MutationCandidateRequest.model_validate_json(candidate.model_dump_json())
        message = self.output_resolver.resolve(scope, candidate.output)
        attribution = message.attribution
        assert attribution is not None
        if len(attribution.source_snapshots) > 16:
            raise MutationError("mutation_output_source_authority_unavailable")
        definition = self.registry.get(scope.application_id)
        declaration = next(
            (
                item for item in definition.mutation_operations
                if item.operation_id == candidate.operation.operation_id
                and item.version == candidate.operation.version
            ),
            None,
        )
        if declaration is None:
            raise MutationError("mutation_operation_unsupported")
        try:
            adapter = operation_adapter(
                self.registry,
                self.runtime,
                scope,
                candidate.operation,
                contract_fingerprint=declaration.contract_fingerprint,
                require_policy=True,
            )
        except MutationError as error:
            if "implementation_unavailable" in error.code:
                raise MutationUnavailableError(error.code) from error
            raise
        try:
            resolved = adapter.candidate_from_output(scope, message)
        except (
            MutationUnavailableError,
            MutationCandidateNotApplicableError,
            MutationCandidateInvalidError,
        ):
            raise
        except Exception as error:
            raise MutationAdapterContractError(
                "mutation_candidate_adapter_contract_invalid"
            ) from error
        try:
            if not isinstance(resolved, TypedMutationCandidate):
                raise TypeError("mutation_candidate_type_invalid")
            resolved = TypedMutationCandidate.model_validate_json(resolved.model_dump_json())
        except Exception as error:
            raise MutationAdapterContractError(
                "mutation_candidate_adapter_contract_invalid"
            ) from error
        endpoint_profile_id = (
            message.execution.endpoint_profile_id if message.execution is not None else None
        )
        output_fingerprint = sha256(message.content.encode("utf-8")).hexdigest()
        attribution_json = json.dumps(
            attribution.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        producer = ProducerProvenance(
            # Manual-import labels remain bound by attribution_fingerprint but
            # cannot be projected as verified producer identity.
            provider_id=(
                attribution.provider_id
                if attribution.execution_origin != "manual_import"
                else None
            ),
            model_id=(
                attribution.model_id if attribution.execution_origin != "manual_import" else None
            ),
            endpoint_profile_id=(
                endpoint_profile_id
                if attribution.execution_origin != "manual_import"
                else None
            ),
            output_message_id=message.id,
            output_fingerprint=output_fingerprint,
            attribution_fingerprint=sha256(attribution_json.encode("utf-8")).hexdigest(),
            fact_source=attribution.fact_source,
            execution_origin=attribution.execution_origin,
            connection_id=attribution.connection_id,
            connection_revision=attribution.connection_revision,
        )
        intent = ProposalIntent(
            idempotency_key=candidate.idempotency_key,
            target=resolved.target,
            operation=candidate.operation,
            payload_schema_id=resolved.payload_schema_id,
            payload=resolved.payload,
            expected_domain_version=resolved.expected_domain_version,
            rationale=resolved.rationale,
            producer=producer,
            sources=attribution.source_snapshots,
            operation_contract_fingerprint=adapter.declaration.contract_fingerprint,
            expires_at=self.clock() + timedelta(minutes=10),
        )
        return self._create_resolved(principal, scope, intent)

    def _create_resolved(self, principal, scope, intent: ProposalIntent):
        """Create only after a trusted caller has resolved the persisted attribution."""
        self._identity(principal, scope)
        # Reparse to detach mutable dictionaries from callers.
        intent = ProposalIntent.model_validate_json(intent.model_dump_json())
        adapter = self._adapter(scope, intent)
        proposal_id = proposal_identity(scope.owner_id, scope.acting_user_id, scope.application_id,
                                        scope.workspace_id, intent.idempotency_key)
        current = self.repository.get(scope, proposal_id)
        if current:
            if current.intent != intent:
                raise MutationError("mutation_idempotency_conflict")
            return self.load_control_record(principal, scope, proposal_id)
        now = self.clock()
        if not now < intent.expires_at <= now + timedelta(hours=1):
            raise MutationError("mutation_expiry_invalid")
        proposal = MutationProposal(
            proposal_id=proposal_id, owner_id=scope.owner_id, acting_user_id=scope.acting_user_id,
            revision=1, intent=intent, created_at=now, updated_at=now,
            # No caller/model label can lower the classification of derived payloads.
            sensitivity="restricted",
            domain_operation_key=uuid5(proposal_id, "authoritative-domain-operation-v1"),
        )
        self._authorize(adapter, scope, proposal, "propose")
        self._dependencies(scope, proposal)
        try:
            return self.repository.save(proposal, expected_revision=0)
        except PersistenceConflict:
            current = self.repository.get(scope, proposal_id)
            if current is None or current.intent != intent:
                raise MutationError("mutation_idempotency_conflict") from None
            return self.load_control_record(principal, scope, proposal_id)

    def validate(self, principal, scope, proposal_id):
        proposal, adapter = self._load_control_record(principal, scope, proposal_id)
        self._authorize(adapter, scope, proposal, "validate")
        self._dependencies(scope, proposal)
        if proposal.state != "proposed":
            return proposal
        self._expire(proposal)
        receipt = adapter.validate(scope, proposal)
        validation = DomainValidation.model_validate(
            receipt.model_dump() if isinstance(receipt, DomainValidation) else receipt
        )
        if (validation.intent_digest != proposal.intent_digest()
            or validation.expected_domain_version != proposal.intent.expected_domain_version
            or not self.clock() < validation.expires_at <= proposal.intent.expires_at):
            raise MutationError("mutation_validation_invalid")
        candidate = proposal.model_copy(update={"validation": validation})
        self._dependencies(scope, candidate)
        try:
            return self._save(proposal, validation=validation,
                              state="validated" if validation.valid else "rejected",
                              terminal_code=None if validation.valid else validation.code)
        except PersistenceConflict:
            return self.load_control_record(principal, scope, proposal_id)

    def confirm(self, principal, scope, proposal_id, *, binding, confirmation_id):
        proposal, adapter = self._load_control_record(principal, scope, proposal_id)
        self._authorize(adapter, scope, proposal, "confirm")
        self._dependencies(scope, proposal)
        if (not proposal.validation or not proposal.validation.valid
            or binding != proposal.binding()):
            raise MutationError("mutation_confirmation_invalid")
        if proposal.confirmation:
            if proposal.confirmation.confirmation_id != confirmation_id:
                raise MutationError("mutation_confirmation_conflict")
            return proposal
        if proposal.state != "validated":
            raise MutationError("mutation_confirmation_invalid")
        self._expire(proposal)
        confirmation = Confirmation(confirmation_id=confirmation_id, binding=binding,
                                    acting_user_id=scope.acting_user_id, confirmed_at=self.clock())
        try:
            return self._save(proposal, state="confirmed", confirmation=confirmation)
        except PersistenceConflict:
            current = self.load_control_record(principal, scope, proposal_id)
            if (not current.confirmation
                or current.confirmation.confirmation_id != confirmation_id
                or current.confirmation.binding != binding):
                raise MutationError("mutation_confirmation_conflict") from None
            return current

    def apply(self, principal, scope, proposal_id, *, confirmation_id, binding):
        proposal, adapter = self._load_control_record(
            principal, scope, proposal_id, require_policy=False
        )
        if (not proposal.confirmation or proposal.confirmation.confirmation_id != confirmation_id
            or binding != proposal.binding() or proposal.confirmation.binding != binding):
            raise MutationError("mutation_confirmation_invalid")
        if proposal.state in TERMINAL:
            self._authorize(adapter, scope, proposal, "read")
            return proposal
        if proposal.state in {"executing", "reconciling", "uncertain"}:
            # Never issue another physical mutation, even after a crash/timeout.
            return self.reconcile(principal, scope, proposal_id)
        if proposal.state != "confirmed":
            raise MutationError("mutation_confirmation_invalid")
        self._expire(proposal)
        try:
            adapter = self._adapter(scope, proposal.intent)
            self._authorize(adapter, scope, proposal, "execute")
            self._dependencies(scope, proposal)
        except MutationUnavailableError:
            # No effect was reserved or sent; keep the exact confirmed binding retryable.
            raise
        except MutationError as error:
            self._save(proposal, state="rejected", terminal_code=error.code)
            raise
        try:
            reserved = self._save(proposal, state="executing", execution_attempt_id=uuid4(),
                                  lease_until=self.clock() + timedelta(seconds=60))
        except PersistenceConflict:
            raise MutationError("mutation_busy") from None
        # All errors after reservation may follow an effect. Do not infer rejection.
        try:
            outcome = adapter.execute(scope, reserved)
        except Exception:  # noqa: BLE001 - unknown effect or unavailable authority
            outcome = None
        result = self._finish(reserved, outcome)
        self._authorize(adapter, scope, result, "read")
        return result

    def _finish(self, proposal, outcome):
        try:
            outcome = DomainOutcome.model_validate(
                outcome.model_dump() if isinstance(outcome, DomainOutcome) else outcome
            )
            if (outcome.domain_operation_key != proposal.domain_operation_key
                or (outcome.post_state and outcome.post_state.target != proposal.intent.target)):
                raise ValueError("mutation_receipt_mismatch")
        except (ValueError, TypeError):
            outcome = DomainOutcome(domain_operation_key=proposal.domain_operation_key,
                                    state="uncertain", code="domain_outcome_unknown")
        return self._save(proposal, state=outcome.state, outcome=outcome, lease_until=None,
                          terminal_code=outcome.code if outcome.state == "rejected" else None)

    def reconcile(self, principal, scope, proposal_id):
        proposal, adapter = self._load_control_record(
            principal, scope, proposal_id, require_policy=False
        )
        self._authorize(adapter, scope, proposal, "reconcile")
        if proposal.state in TERMINAL:
            return self.load_control_record(principal, scope, proposal_id)
        if proposal.state not in {"executing", "reconciling", "uncertain"}:
            raise MutationError("mutation_reconciliation_invalid")
        if proposal.lease_until and proposal.lease_until > self.clock():
            raise MutationError("mutation_busy")
        if proposal.state in {"executing", "reconciling"}:
            proposal = self._finish(proposal, None)
        try:
            reserved = self._save(proposal, state="reconciling", reconciliation_id=uuid4(),
                                  outcome=None, lease_until=self.clock() + timedelta(seconds=60))
        except PersistenceConflict:
            raise MutationError("mutation_busy") from None
        try:
            outcome = adapter.reconcile(scope, reserved)
        except Exception:  # noqa: BLE001 - unknown effect or unavailable authority
            outcome = None
        result = self._finish(reserved, outcome)
        # Current domain read authority permits the post-state reference; original
        # source-derived payload is suppressed by present(), even after expiry.
        self._authorize(adapter, scope, result, "read")
        return result
