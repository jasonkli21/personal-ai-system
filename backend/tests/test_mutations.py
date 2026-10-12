"""Authoritative effect conformance through the installed generic extension seam."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Event, RLock
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationDefinition,
    ApplicationSidecarPolicy,
)
from personal_ai.applications.registry import ApplicationRegistry, default_application_registry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.context.deployment import configured_context_runtime
from personal_ai.context.runtime import (
    ContextPermissionRevalidatorRegistry,
    ContextRuntimeContribution,
    ContextRuntimeContributionCatalog,
    ContextRuntimeRegistry,
)
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
    ContextSourceSnapshot,
)
from personal_ai.entities.conversation import Conversation, Message, MessageRole, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.mutations.contracts import (
    AuthoritativePostState,
    DomainOutcome,
    DomainValidation,
    MutationAdapterContractError,
    MutationCandidateInvalidError,
    MutationCandidateNotApplicableError,
    MutationCandidateRequest,
    MutationError,
    MutationOperationDeclaration,
    MutationProposal,
    MutationUnavailableError,
    OperationRef,
    ProducerProvenance,
    ProposalIntent,
    TypedMutationCandidate,
)
from personal_ai.mutations.outputs import CanonicalOutputResolver
from personal_ai.mutations.service import MutationService
from personal_ai.mutations.transitions import validate_transition
from personal_ai.persistence.postgres.database import PersistenceConflict
from personal_ai.settings import Settings


class MemoryMutationRepository:
    """Serialized contract fake; real-store CAS evidence has a separate opt-in suite."""
    def __init__(self):
        self.lock = RLock()
        self.records = {}
        self.audit = []
        self.fail_after_effect = False

    def get(self, scope, proposal_id):
        with self.lock:
            result = self.records.get((scope.owner_id, proposal_id))
            result = MutationProposal.model_validate_json(result) if result else None
            if result and (result.acting_user_id != scope.acting_user_id
                or result.intent.target.application_id != scope.application_id
                or result.intent.target.workspace_id != scope.workspace_id):
                return None
            return result

    def save(self, proposal, *, expected_revision):
        with self.lock:
            scope = RequestScope(owner_id=proposal.owner_id, acting_user_id=proposal.acting_user_id,
                request_id="repository", application_id=proposal.intent.target.application_id,
                workspace_id=proposal.intent.target.workspace_id)
            current = self.get(scope, proposal.proposal_id)
            validate_transition(current, proposal, expected_revision)
            if self.fail_after_effect and proposal.state == "applied":
                self.fail_after_effect = False
                raise RuntimeError("local_commit_interrupted")
            self.records[proposal.owner_id, proposal.proposal_id] = proposal.model_dump_json()
            self.audit.append(proposal)
            return self.get(scope, proposal.proposal_id)

    def required_operation_contracts(self):
        with self.lock:
            proposals = [MutationProposal.model_validate_json(value) for value in self.records.values()]
        return tuple(sorted({
            (
                proposal.intent.target.application_id,
                proposal.intent.operation.operation_id,
                proposal.intent.operation.version,
                proposal.intent.operation_contract_fingerprint,
            )
            for proposal in proposals
        }))


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str = Field(min_length=1, max_length=100)


def mutation_case(owner="owner"):
    now = [datetime.now(UTC)]
    principal = AuthenticatedPrincipal("google", "alice", owner, None, 0, True)
    scope = RequestScope(owner_id=owner, acting_user_id="google|alice", request_id="request",
                         application_id="synthetic", workspace_id="space")
    target = ContextEntityReference(application_id="synthetic", workspace_id="space",
                                    entity_type="note", entity_id="note-1")
    dependency = ContextPermissionDependency(
        permission_id="synthetic.note", version="epoch-1", purpose="mutation",
        owner_id=scope.owner_id, acting_user_id=scope.acting_user_id,
        source_scope=ApplicationScope(application_id=scope.application_id, workspace_id=scope.workspace_id),
        entity_ref=target, source_revision="v1",
    )

    class Permissions:
        permission_namespaces = ("synthetic.note",)
        epoch = "epoch-1"
        current = True

        def supports(self, dep):
            return dep.permission_id == "synthetic.note"

        def is_current(self, dep):
            return (self.current and dep == dependency and dep.version == self.epoch)

    permissions = Permissions()
    declaration = MutationOperationDeclaration(operation_id="note.rename", version=1,
                                                payload_schema_id="note-title-v1",
                                                entity_types=("note",), sensitivity="personal",
                                                contract_fingerprint="b" * 64)

    class Adapter:
        payload_model = Payload
        allowed = True
        business_valid = True
        domain_version = "v1"
        sends = 0
        effects = 0
        reconciles = 0
        def __init__(self):
            self.receipts = {}
        timeout = False
        mismatch = False
        candidate_mode = "valid"
        block = False
        entered = Event()
        release = Event()
        domain_lock = RLock()

        def authorize(self, request, entity, *, action):
            return (self.allowed and request == scope and entity == target)

        def validate(self, request, proposal):
            return DomainValidation(
                intent_digest=proposal.intent_digest(), validation_id="validation-1", version="validator-v1",
                expected_domain_version=proposal.intent.expected_domain_version,
                valid=self.business_valid and self.domain_version == proposal.intent.expected_domain_version,
                code="valid" if self.business_valid else "business_rule_denied",
                preview=f"Rename {target.entity_id} to {proposal.intent.payload['title']}",
                permission_dependencies=(dependency,), expires_at=proposal.intent.expires_at,
            )

        def candidate_from_output(self, request, output):
            assert request == scope
            assert output.id == output_id
            assert output.status == MessageStatus.COMPLETED
            if self.candidate_mode == "not_applicable":
                raise MutationCandidateNotApplicableError()
            if self.candidate_mode == "invalid":
                raise MutationCandidateInvalidError()
            if self.candidate_mode == "unavailable":
                raise MutationUnavailableError("candidate_source_unavailable")
            if self.candidate_mode == "malformed":
                return {"not": "a typed candidate"}
            return TypedMutationCandidate(
                target=target,
                payload_schema_id="note-title-v1",
                payload={"title": "New title"},
                expected_domain_version="v1",
                rationale="Rename requested in the canonical assistant response",
            )

        def execute(self, request, proposal):
            self.sends += 1
            if self.block:
                self.entered.set()
                assert self.release.wait(5)
            with self.domain_lock:
                key = proposal.domain_operation_key
                if key in self.receipts:
                    return self.receipts[key]
                if not self.authorize(request, proposal.intent.target, action="execute"):
                    result = DomainOutcome(domain_operation_key=key, state="rejected", code="authorization_revoked")
                elif not permissions.is_current(proposal.validation.permission_dependencies[0]):
                    result = DomainOutcome(domain_operation_key=key, state="rejected", code="permission_epoch_stale")
                elif self.domain_version != proposal.intent.expected_domain_version:
                    result = DomainOutcome(domain_operation_key=key, state="rejected", code="domain_version_stale")
                else:
                    self.effects += 1
                    self.domain_version = "v2"
                    result = DomainOutcome(domain_operation_key=key, state="applied", code="committed",
                                           post_state=AuthoritativePostState(target=target,
                                           domain_version="v2", reference_id="domain-receipt-1"))
                self.receipts[key] = result
            if self.timeout:
                raise TimeoutError("ack_lost_after_commit")
            if self.mismatch:
                return result.model_copy(update={"domain_operation_key": uuid4()})
            return result

        def reconcile(self, request, proposal):
            self.reconciles += 1
            return self.receipts.get(proposal.domain_operation_key, DomainOutcome(
                domain_operation_key=proposal.domain_operation_key, state="uncertain", code="no_receipt",
            ))

    adapter = Adapter()
    adapter.declaration = declaration
    definition = ApplicationDefinition(
        application_id="synthetic", display_name="Synthetic", memory_namespace="synthetic",
        workspace_kind="required", mutation_operations=(declaration,),
        context_policy=ApplicationContextPolicy(sidecar=ApplicationSidecarPolicy(
            mutation_operations=(OperationRef(operation_id=declaration.operation_id, version=1),),
        )),
    )
    registry = ApplicationRegistry((definition,))
    catalog = ContextRuntimeContributionCatalog((("synthetic", lambda settings:
        ContextRuntimeContribution({}, permission_revalidators=(permissions,),
            mutation_adapters={("synthetic", "note.rename", 1): adapter})),))
    runtime = configured_context_runtime(Settings(_env_file=None, app_environment="test", ai_provider="fake", ai_model="fake"), catalog=catalog)
    repository = MemoryMutationRepository()
    service = MutationService(repository, registry, runtime,
                              ContextPermissionRevalidatorRegistry(runtime.permission_revalidators),
                              clock=lambda: now[0])
    source = ContextSourceSnapshot(
        provider_id="synthetic.note", source_id="note-1", source_version="v1", item_id="note-1",
        owner_id=scope.owner_id, application_id=scope.application_id, workspace_id=scope.workspace_id,
        content_fingerprint="a" * 64, permission_dependencies=(dependency,),
        expires_at=now[0] + timedelta(minutes=30),
    )
    conversation_id, output_id = uuid4(), uuid4()
    output_content = "The canonical completed assistant output."
    attribution = TurnAttribution(
        fact_source="server_observed",
        execution_origin="automatic_managed",
        provider_id="synthetic.provider",
        model_id="synthetic-model-v1",
        recorded_at=now[0],
        source_snapshots=(source,),
    )
    conversation = Conversation(
        id=conversation_id, owner_id=scope.owner_id, application_id=scope.application_id,
        workspace_id=scope.workspace_id, title="Synthetic output", created_at=now[0],
        updated_at=now[0],
    )
    message = Message(
        id=output_id, conversation_id=conversation_id, owner_id=scope.owner_id,
        application_id=scope.application_id, workspace_id=scope.workspace_id,
        role=MessageRole.ASSISTANT, content=output_content, status=MessageStatus.COMPLETED,
        created_at=now[0], attribution=attribution,
    )
    from personal_ai.storage.errors import ResourceNotFoundError

    class OutputConversations:
        def get(self, *, owner_id, conversation_id):
            if (owner_id, conversation_id) != (scope.owner_id, conversation.id):
                raise ResourceNotFoundError("conversation_not_found")
            return conversation
    class OutputMessages:
        current_message = message
        active = True

        def get(self, *, owner_id, conversation_id, message_id):
            if (owner_id, conversation_id, message_id) != (
                scope.owner_id, conversation.id, self.current_message.id
            ):
                raise ResourceNotFoundError("message_not_found")
            return self.current_message
        def list_active(self, *, owner_id, conversation_id):
            assert (owner_id, conversation_id) == (scope.owner_id, conversation.id)
            return [self.current_message] if self.active else []
    output_conversations = OutputConversations()
    output_messages = OutputMessages()
    output_resolver = CanonicalOutputResolver(output_conversations, output_messages)
    service.output_resolver = output_resolver
    attribution_fingerprint = sha256(json.dumps(
        attribution.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    ).encode()).hexdigest()
    intent = ProposalIntent(
        idempotency_key=uuid4(), target=target, operation=OperationRef(operation_id="note.rename", version=1),
        payload_schema_id="note-title-v1", payload={"title": "New title"},
        expected_domain_version="v1", rationale="Owner requested rename",
        producer=ProducerProvenance(
            provider_id=attribution.provider_id, model_id=attribution.model_id,
            output_message_id=output_id,
            output_fingerprint=sha256(output_content.encode()).hexdigest(),
            attribution_fingerprint=attribution_fingerprint,
            fact_source=attribution.fact_source, execution_origin=attribution.execution_origin,
        ),
        sources=(source,), expires_at=now[0] + timedelta(minutes=10),
        operation_contract_fingerprint=declaration.contract_fingerprint,
    )
    candidate = MutationCandidateRequest(
        idempotency_key=intent.idempotency_key,
        output={"conversation_id": conversation_id, "message_id": output_id},
        operation=intent.operation,
    )
    return {"service": service, "repo": repository, "principal": principal, "scope": scope,
            "adapter": adapter, "permissions": permissions, "intent": intent, "now": now,
            "registry": registry, "runtime": runtime, "catalog": catalog, "definition": definition,
            "candidate": candidate, "message": message, "conversation": conversation,
            "output_resolver": output_resolver, "output_conversations": output_conversations,
            "output_messages": output_messages}


@pytest.fixture
def mutation():
    return mutation_case()


def create(f):
    return f["service"]._create_resolved(f["principal"], f["scope"], f["intent"])


def validated(f):
    p = create(f)
    return f["service"].validate(f["principal"], f["scope"], p.proposal_id)


def confirmed(f):
    p = validated(f)
    return f["service"].confirm(f["principal"], f["scope"], p.proposal_id,
                               binding=p.binding(), confirmation_id=uuid4())


def apply(f, p):
    return f["service"].apply(f["principal"], f["scope"], p.proposal_id,
        binding=p.binding(), confirmation_id=p.confirmation.confirmation_id)


def test_synthetic_registered_effect_and_authoritative_post_state(mutation):
    f = mutation
    p = confirmed(f)
    result = apply(f, p)
    assert result.state == "applied"
    assert result.outcome.post_state.domain_version == "v2"
    assert result.outcome.post_state.reference_id == "domain-receipt-1"
    assert [row.state for row in f["repo"].audit] == [
        "proposed", "validated", "confirmed", "executing", "applied",
    ]
    assert apply(f, p) == result
    assert f["adapter"].sends == f["adapter"].effects == 1


@pytest.mark.parametrize("change,code", [
    ({"operation": OperationRef(operation_id="arbitrary.write", version=1)}, "unsupported"),
    ({"operation": OperationRef(operation_id="note.rename", version=2)}, "unsupported"),
    ({"payload_schema_id": "wrong-schema"}, "schema_unsupported"),
    ({"payload": {"title": "New title", "write_anything": True}}, "extra_forbidden"),
    ({"payload": {"title": 1}}, "string_type"),
])
def test_unsupported_or_untyped_candidate_never_persists(mutation, change, code):
    f = mutation
    with pytest.raises((MutationError, ValidationError), match=code):
        f["service"]._create_resolved(
            f["principal"], f["scope"], f["intent"].model_copy(update=change)
        )
    assert not f["repo"].audit
    assert f["adapter"].sends == 0


def test_metadata_without_implementation_and_policy_denial(mutation):
    f = mutation
    f["runtime"].mutation_adapters = {}
    with pytest.raises(MutationError, match="implementation_unavailable"):
        create(f)
    f["service"].runtime = configured_context_runtime(Settings(_env_file=None, app_environment="test", ai_provider="fake", ai_model="fake"), catalog=f["catalog"])
    definition = f["definition"].model_copy(update={"context_policy": ApplicationContextPolicy()})
    f["service"].registry = ApplicationRegistry((definition,))
    with pytest.raises(MutationError, match="operation_denied"):
        create(f)
    with pytest.raises(ValidationError, match="undeclared"):
        ApplicationDefinition(application_id="synthetic", display_name="Synthetic", memory_namespace="synthetic",
            context_policy=ApplicationContextPolicy(sidecar=ApplicationSidecarPolicy(mutation_operations=(f["intent"].operation,))))
    for app in ("travel", "shopping", "finance", "health"):
        assert default_application_registry().get(app).mutation_operations == ()


def test_invalid_unvalidated_and_mismatched_confirmation(mutation):
    f = mutation
    p = create(f)
    with pytest.raises(MutationError, match="confirmation_invalid"):
        f["service"].confirm(f["principal"], f["scope"], p.proposal_id,
                             binding=p.binding(), confirmation_id=uuid4())
    f["adapter"].business_valid = False
    p = validated(f)
    assert p.state == "rejected"
    with pytest.raises(MutationError, match="confirmation_invalid"):
        f["service"].confirm(f["principal"], f["scope"], p.proposal_id,
                             binding=p.binding(), confirmation_id=uuid4())
    assert f["adapter"].effects == 0


def test_exact_binding_immutable_intent_and_expiry(mutation):
    f = mutation
    p = validated(f)
    for change in ({"expected_domain_version": "v2"}, {"payload": {"title": "changed"}},
                   {"expires_at": p.intent.expires_at + timedelta(seconds=1)}):
        changed = p.model_copy(update={"intent": p.intent.model_copy(update=change)})
        with pytest.raises(MutationError, match="confirmation_invalid"):
            f["service"].confirm(f["principal"], f["scope"], p.proposal_id,
                                 binding=changed.binding(), confirmation_id=uuid4())
        with pytest.raises(PersistenceConflict):
            f["repo"].save(changed.model_copy(update={"revision": 3, "state": "confirmed"}), expected_revision=2)
    f["now"][0] = p.intent.expires_at
    with pytest.raises(MutationError, match="expired"):
        f["service"].confirm(f["principal"], f["scope"], p.proposal_id,
                             binding=p.binding(), confirmation_id=uuid4())
    assert f["repo"].get(f["scope"], p.proposal_id).state == "expired"


def test_stale_domain_version_rejected_at_atomic_effect_boundary(mutation):
    f = mutation
    p = confirmed(f)
    f["adapter"].domain_version = "changed-by-another-user"
    result = apply(f, p)
    assert result.state == "rejected"
    assert result.outcome.code == "domain_version_stale"
    assert f["adapter"].effects == 0


@pytest.mark.parametrize("boundary", ["validate", "confirm", "apply", "read"])
def test_permission_epoch_revocation_and_no_sensitive_reuse(mutation, boundary):
    f = mutation
    p = create(f) if boundary == "validate" else validated(f) if boundary == "confirm" else confirmed(f)
    f["permissions"].epoch = "epoch-2"
    with pytest.raises(MutationError, match="source_denied"):
        if boundary == "apply":
            apply(f, p)
        elif boundary == "confirm":
            f["service"].confirm(f["principal"], f["scope"], p.proposal_id, binding=p.binding(), confirmation_id=uuid4())
        else:
            getattr(f["service"], "load_control_record" if boundary == "read" else boundary)(
                f["principal"], f["scope"], p.proposal_id
            )
    assert f["adapter"].sends == 0


def test_revoked_domain_authorization_before_effect(mutation):
    f = mutation
    p = confirmed(f)
    f["adapter"].allowed = False
    with pytest.raises(MutationError, match="authorization_denied"):
        apply(f, p)
    assert f["adapter"].sends == 0
    assert f["repo"].get(f["scope"], p.proposal_id).state == "rejected"


def test_transient_pre_send_checks_leave_the_confirmed_proposal_retryable(mutation):
    f = mutation
    p = confirmed(f)
    authorize = f["adapter"].authorize

    def authorization_timeout(request, entity, *, action):
        if action == "execute":
            raise TimeoutError("authorization service unavailable")
        return authorize(request, entity, action=action)

    f["adapter"].authorize = authorization_timeout
    with pytest.raises(MutationUnavailableError, match="authority_unavailable"):
        apply(f, p)
    assert f["repo"].get(f["scope"], p.proposal_id).state == "confirmed"
    assert f["adapter"].sends == 0


def test_transient_permission_revalidation_leaves_confirmation_retryable(mutation):
    f = mutation
    p = confirmed(f)

    def permission_timeout(_dependency):
        raise TimeoutError("permission authority unavailable")

    f["permissions"].is_current = permission_timeout
    with pytest.raises(MutationUnavailableError, match="source_authority_unavailable"):
        apply(f, p)
    assert f["repo"].get(f["scope"], p.proposal_id).state == "confirmed"
    assert f["adapter"].sends == 0


def test_missing_runtime_is_retryable_but_explicit_policy_revocation_is_terminal(mutation):
    f = mutation
    p = confirmed(f)
    f["service"].runtime = ContextRuntimeRegistry()
    with pytest.raises(MutationUnavailableError, match="implementation_unavailable"):
        apply(f, p)
    assert f["repo"].get(f["scope"], p.proposal_id).state == "confirmed"
    assert f["adapter"].sends == 0

    f["service"].runtime = f["runtime"]
    f["service"].registry = ApplicationRegistry((
        f["definition"].model_copy(update={"context_policy": ApplicationContextPolicy()}),
    ))
    with pytest.raises(MutationError, match="operation_denied"):
        apply(f, p)
    assert f["repo"].get(f["scope"], p.proposal_id).state == "rejected"
    assert f["adapter"].sends == 0


def test_retained_versioned_adapter_reconciles_after_current_contract_retirement(mutation):
    from personal_ai.mutations.compatibility import (
        MutationRuntimeCompatibilityError,
        require_reconciliation_compatibility,
    )

    f = mutation
    p = confirmed(f)
    f["adapter"].timeout = True
    unknown = apply(f, p)
    assert unknown.state == "uncertain"
    key = (
        "synthetic", "note.rename", 1,
        f["definition"].mutation_operations[0].contract_fingerprint,
    )
    retained_runtime = ContextRuntimeRegistry(mutation_reconciliation_adapters={
        key: f["adapter"],
    })
    require_reconciliation_compatibility(f["repo"], retained_runtime)
    with pytest.raises(MutationRuntimeCompatibilityError, match="contract_missing"):
        require_reconciliation_compatibility(f["repo"], ContextRuntimeRegistry())

    retired_definition = f["definition"].model_copy(update={
        "mutation_operations": (),
        "context_policy": ApplicationContextPolicy(),
    })
    f["service"].registry = ApplicationRegistry((retired_definition,))
    f["service"].runtime = retained_runtime
    result = f["service"].reconcile(f["principal"], f["scope"], p.proposal_id)
    assert result.state == "applied"
    assert f["adapter"].sends == 1


def test_same_version_semantic_change_cannot_reuse_old_confirmation(mutation):
    f = mutation
    p = confirmed(f)
    changed_declaration = f["definition"].mutation_operations[0].model_copy(
        update={"contract_fingerprint": "c" * 64}
    )
    f["service"].registry = ApplicationRegistry((
        f["definition"].model_copy(update={"mutation_operations": (changed_declaration,)}),
    ))
    with pytest.raises(MutationError, match="contract_changed"):
        f["service"].validate(f["principal"], f["scope"], p.proposal_id)
    assert f["adapter"].sends == 0


@pytest.mark.parametrize("field,value", [("owner_id", "other"), ("acting_user_id", "google|bob"),
    ("application_id", "another"), ("workspace_id", "another")])
def test_owner_actor_application_workspace_isolation(mutation, field, value):
    f = mutation
    p = confirmed(f)
    scope = f["scope"].model_copy(update={field: value})
    with pytest.raises(MutationError):
        f["service"].load_control_record(f["principal"], scope, p.proposal_id)
    assert f["adapter"].sends == 0


def test_concurrent_double_click_and_restart_do_not_duplicate_send(mutation):
    f = mutation
    p = confirmed(f)
    f["adapter"].block = True
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(apply, f, p)
        assert f["adapter"].entered.wait(5)
        with pytest.raises(MutationError, match="busy"):
            apply(f, p)
        f["adapter"].release.set()
        assert first.result().state == "applied"
    restarted = MutationService(f["repo"], f["registry"], f["runtime"], f["permissions"], clock=lambda: f["now"][0])
    f["service"] = restarted
    assert apply(f, p).state == "applied"
    assert f["adapter"].sends == f["adapter"].effects == 1


@pytest.mark.parametrize("failure", ["timeout", "mismatch", "local_commit"])
def test_unknown_outcome_reconciles_original_key_after_restart(mutation, failure):
    f = mutation
    p = confirmed(f)
    if failure == "local_commit":
        f["repo"].fail_after_effect = True
        with pytest.raises(RuntimeError, match="local_commit_interrupted"):
            apply(f, p)
        assert f["repo"].get(f["scope"], p.proposal_id).state == "executing"
    else:
        setattr(f["adapter"], failure, True)
        assert apply(f, p).state == "uncertain"
    f["now"][0] += timedelta(minutes=11)  # expiry cannot prevent reconciliation
    f["service"] = MutationService(f["repo"], f["registry"], f["runtime"], f["permissions"], clock=lambda: f["now"][0])
    result = apply(f, p)
    assert result.state == "applied"
    assert result.domain_operation_key == p.domain_operation_key
    assert result.outcome.post_state.domain_version == "v2"
    assert f["adapter"].effects == f["adapter"].sends == 1
    assert f["adapter"].reconciles == 1


def test_crash_before_send_and_absent_receipt_remain_uncertain(mutation):
    f = mutation
    p = confirmed(f)
    f["service"]._save(p, state="executing", execution_attempt_id=uuid4(), lease_until=f["now"][0] + timedelta(seconds=60))
    f["now"][0] += timedelta(seconds=61)
    result = apply(f, p)
    assert result.state == "uncertain"
    assert result.outcome.post_state is None
    assert apply(f, p).state == "uncertain"
    assert f["adapter"].sends == 0


def test_reconciliation_crash_and_revocation_durably_resolve_without_disclosure(mutation):
    f = mutation
    p = confirmed(f)
    f["adapter"].timeout = True
    unknown = apply(f, p)
    reserved = f["service"]._save(unknown, state="reconciling", outcome=None, reconciliation_id=uuid4(),
                                  lease_until=f["now"][0] + timedelta(seconds=60))
    f["permissions"].current = False
    f["now"][0] += timedelta(seconds=61)
    resolved = f["service"].reconcile(f["principal"], f["scope"], reserved.proposal_id)
    public = f["service"]._present(f["principal"], f["scope"], resolved)
    assert public.proposal.intent.payload is None
    assert public.proposal.validation.preview is None
    assert public.proposal.intent.source_refs == ()
    assert f["repo"].get(f["scope"], p.proposal_id).state == "applied"
    assert f["adapter"].sends == 1


def test_producer_identity_and_labels_never_supply_authority(mutation):
    f = mutation
    request = f["candidate"].model_dump(mode="json")
    request["producer"] = {"provider_id": "chatgpt", "model_id": "claimed"}
    request["sources"] = []
    with pytest.raises(ValidationError):
        MutationCandidateRequest.model_validate(request)
    p = f["service"].create_from_output(
        f["principal"], f["scope"], f["candidate"]
    )
    assert p.intent.producer.output_message_id == f["message"].id
    assert p.intent.producer.provider_id == f["message"].attribution.provider_id
    assert p.intent.sources == f["message"].attribution.source_snapshots
    assert p.intent.producer.output_fingerprint == sha256(
        f["message"].content.encode()
    ).hexdigest()
    f["adapter"].allowed = False
    with pytest.raises(MutationError, match="authorization_denied"):
        f["service"].create_from_output(f["principal"], f["scope"], f["candidate"])


@pytest.mark.parametrize(
    "provider_label,model_label",
    [
        (None, None),
        ("user-entered provider", None),
        (None, "user-entered model"),
        ("x" * 150, "user-entered model"),
    ],
)
def test_manual_import_labels_do_not_block_or_claim_mutation_provenance(
    mutation, provider_label, model_label
):
    f = mutation
    original = f["message"].attribution
    manual = TurnAttribution(
        fact_source="user_declared",
        execution_origin="manual_import",
        provider_id=provider_label,
        model_id=model_label,
        recorded_at=original.recorded_at,
        source_snapshots=original.source_snapshots,
    )
    output = f["message"].model_copy(update={"attribution": manual})
    f["output_messages"].current_message = output

    proposal = f["service"].create_from_output(
        f["principal"], f["scope"], f["candidate"]
    )

    assert proposal.intent.producer.execution_origin == "manual_import"
    assert proposal.intent.producer.fact_source == "user_declared"
    assert proposal.intent.producer.provider_id is None
    assert proposal.intent.producer.model_id is None
    assert proposal.intent.producer.endpoint_profile_id is None
    expected_fingerprint = sha256(
        json.dumps(
            manual.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    assert proposal.intent.producer.attribution_fingerprint == expected_fingerprint
    assert proposal.intent.producer.output_message_id == output.id


@pytest.mark.parametrize(
    "mode,error_type",
    [
        ("not_applicable", MutationCandidateNotApplicableError),
        ("invalid", MutationCandidateInvalidError),
        ("malformed", MutationAdapterContractError),
    ],
)
def test_candidate_conversion_rejections_are_stable_and_do_not_persist(
    mutation, mode, error_type
):
    f = mutation
    f["adapter"].candidate_mode = mode

    with pytest.raises(error_type):
        f["service"].create_from_output(
            f["principal"], f["scope"], f["candidate"]
        )

    assert not f["repo"].audit
    assert f["adapter"].sends == 0


def test_candidate_conversion_outage_is_retryable_without_persisting(mutation):
    f = mutation
    f["adapter"].candidate_mode = "unavailable"
    with pytest.raises(MutationUnavailableError):
        f["service"].create_from_output(
            f["principal"], f["scope"], f["candidate"]
        )
    assert not f["repo"].audit

    f["adapter"].candidate_mode = "valid"
    proposal = f["service"].create_from_output(
        f["principal"], f["scope"], f["candidate"]
    )
    assert proposal.proposal_id == f["service"].create_from_output(
        f["principal"], f["scope"], f["candidate"]
    ).proposal_id
    assert len(f["repo"].audit) == 1


@pytest.mark.parametrize("change,code", [
    ({"role": MessageRole.USER}, "mutation_output_not_found"),
    ({"status": MessageStatus.FAILED}, "mutation_output_not_found"),
    ({"application_id": "another"}, "mutation_output_not_found"),
    ({"attribution": None}, "mutation_output_not_found"),
])
def test_candidate_requires_completed_exactly_scoped_canonical_assistant_output(mutation, change, code):
    f = mutation
    f["output_messages"].current_message = f["message"].model_copy(update=change)
    with pytest.raises(MutationError, match=code):
        f["service"].create_from_output(f["principal"], f["scope"], f["candidate"])
    assert not f["repo"].audit


def test_candidate_rejects_superseded_output_and_foreign_output_handle(mutation):
    f = mutation
    f["output_messages"].active = False
    with pytest.raises(MutationError, match="mutation_output_not_active"):
        f["service"].create_from_output(f["principal"], f["scope"], f["candidate"])
    f["output_messages"].active = True
    foreign_output = f["candidate"].model_copy(update={
        "output": f["candidate"].output.model_copy(update={"message_id": uuid4()}),
    })
    with pytest.raises(MutationError, match="mutation_output_not_found"):
        f["service"].create_from_output(f["principal"], f["scope"], foreign_output)
    assert not f["repo"].audit


def test_idempotent_intent_creation_and_changed_intent_conflict(mutation):
    f = mutation
    with ThreadPoolExecutor(max_workers=4) as executor:
        proposals = list(executor.map(lambda _: create(f), range(4)))
    assert len({p.proposal_id for p in proposals}) == 1
    assert len(f["repo"].audit) == 1
    f["intent"] = f["intent"].model_copy(update={"payload": {"title": "different"}})
    with pytest.raises(MutationError, match="idempotency_conflict"):
        create(f)


def test_production_api_dependency_composes_registered_runtime_and_persistence(mutation, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_ai.api import mutations
    from personal_ai.api.dependencies import (
        get_application_registry,
        get_context_runtime_registry,
        get_conversation_repository,
        get_message_repository,
        get_request_scope,
        require_recent_auth,
    )

    f = mutation
    class Factory:
        def mutation_repository(self):
            return f["repo"]
    monkeypatch.setattr(mutations, "persistence_factory", lambda settings: Factory())
    app = FastAPI()
    app.include_router(mutations.router)
    app.dependency_overrides[get_application_registry] = lambda: f["registry"]
    app.dependency_overrides[get_context_runtime_registry] = lambda: f["runtime"]
    app.dependency_overrides[get_conversation_repository] = lambda: f["output_conversations"]
    app.dependency_overrides[get_message_repository] = lambda: f["output_messages"]
    app.dependency_overrides[get_request_scope] = lambda: f["scope"]
    app.dependency_overrides[mutations.get_settings] = lambda: Settings(_env_file=None, ai_provider="fake", ai_model="fake")
    app.dependency_overrides[require_recent_auth] = lambda: f["principal"]
    # Real dependency/controller path; substitute only store, identity and installed registrations.
    client = TestClient(app)
    f["candidate"] = f["candidate"].model_copy(
        update={"idempotency_key": uuid4()}
    )
    response = client.post(
        "/v1/mutations/candidates", json=f["candidate"].model_dump(mode="json")
    )
    assert response.status_code == 201, response.text
    assert response.json()["apply_available"] is False
    assert "sources" not in response.json()["proposal"]["intent"]
    assert "owner_id" not in response.json()["proposal"]
    assert "domain_operation_key" not in response.json()["proposal"]
    proposal_id = response.json()["proposal"]["proposal_id"]
    prefix = f"/v1/mutations/{proposal_id}"
    value = client.post(prefix + "/validate").json()
    assert value["apply_available"] is True
    assert "permission_dependencies" not in value["proposal"]["validation"]
    choice = {"binding": value["binding"], "confirmation_id": str(uuid4())}
    assert client.post(prefix + "/confirm", json=choice).status_code == 200

    authorize = f["adapter"].authorize

    def temporary_authority_failure(request, entity, *, action):
        if action == "execute":
            raise TimeoutError("temporary authority outage")
        return authorize(request, entity, action=action)

    f["adapter"].authorize = temporary_authority_failure
    unavailable = client.post(prefix + "/apply", json=choice)
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "mutation_authority_unavailable"
    assert f["repo"].get(f["scope"], UUID(proposal_id)).state == "confirmed"

    f["adapter"].authorize = authorize
    result = client.post(prefix + "/apply", json=choice)
    assert result.status_code == 200, result.text
    assert result.json()["proposal"]["state"] == "applied"
    assert result.json()["apply_available"] is False
    assert result.json()["proposal"]["intent"]["payload"] is None
    assert result.json()["proposal"]["validation"]["preview"] is None
    assert "execution_attempt_id" not in result.json()["proposal"]
    assert "reconciliation_id" not in result.json()["proposal"]
    assert "lease_until" not in result.json()["proposal"]
    assert "domain_operation_key" not in result.json()["proposal"].get("outcome", {})
    assert client.post(prefix + "/apply", json=choice).json() == result.json()
    assert f["adapter"].sends == 1


def test_validation_receipt_is_bound_to_exact_intent(mutation):
    f = mutation
    p = create(f)
    validate = f["adapter"].validate
    f["adapter"].validate = lambda scope, proposal: validate(scope, proposal).model_copy(
        update={"intent_digest": "b" * 64},
    )
    with pytest.raises(MutationError, match="validation_invalid"):
        f["service"].validate(f["principal"], f["scope"], p.proposal_id)
    assert f["repo"].get(f["scope"], p.proposal_id).state == "proposed"


def test_registered_adapter_enforces_epoch_inside_domain_transaction(mutation):
    f = mutation
    p = confirmed(f)
    f["adapter"].block = True
    with ThreadPoolExecutor(max_workers=1) as executor:
        sent = executor.submit(apply, f, p)
        assert f["adapter"].entered.wait(5)
        f["permissions"].epoch = "epoch-2"
        f["adapter"].release.set()
        assert sent.result().state == "rejected"
    result = f["repo"].get(f["scope"], p.proposal_id)
    assert result.state == "rejected"
    assert result.outcome.code == "permission_epoch_stale"
    assert f["adapter"].effects == 0


def test_repository_rejects_confirmation_shortcut_and_second_execution(mutation):
    from personal_ai.mutations.contracts import Confirmation

    f = mutation
    p = create(f)
    receipt = f["adapter"].validate(f["scope"], p)
    upgraded = p.model_copy(update={"revision": 2, "state": "validated", "validation": receipt})
    upgraded = upgraded.model_copy(update={"confirmation": Confirmation(
        confirmation_id=uuid4(), binding=upgraded.binding(), acting_user_id=p.acting_user_id,
        confirmed_at=f["now"][0],
    )})
    with pytest.raises(PersistenceConflict, match="confirmation_transition"):
        f["repo"].save(upgraded, expected_revision=1)
    result = apply(f, confirmed(f))
    with pytest.raises(PersistenceConflict):
        f["repo"].save(result.model_copy(update={"revision": result.revision + 1,
            "state": "executing", "execution_attempt_id": uuid4()}), expected_revision=result.revision)


def test_application_lifespan_installs_mutation_extension_without_control_flow_edits(mutation, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_ai.api.dependencies import get_context_runtime_registry, get_settings
    from personal_ai.context.deployment import default_context_runtime_catalog
    from personal_ai.main import lifespan

    f = mutation
    class Factory:
        def mutation_repository(self):
            return f["repo"]

    from personal_ai.persistence import factory as persistence_factory_module
    monkeypatch.setattr(persistence_factory_module, "persistence_factory", lambda _settings: Factory())
    monkeypatch.setattr("personal_ai.main.validate_startup_configuration", lambda: None)
    monkeypatch.setattr("personal_ai.main.close_persistence_clients", lambda: None)
    settings = Settings(_env_file=None, ai_provider="fake", ai_model="fake")
    catalog = default_context_runtime_catalog()
    catalog.register("synthetic-mutation", lambda settings: ContextRuntimeContribution(
        {}, permission_revalidators=(f["permissions"],),
        mutation_adapters={("synthetic", "note.rename", 1): f["adapter"]},
    ))
    app = FastAPI(lifespan=lifespan)
    app.state.application_registry = f["registry"]
    app.state.context_runtime_catalog = catalog
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app):
        assert get_context_runtime_registry(type("Request", (), {"app": app})()).mutation_adapters[
            ("synthetic", "note.rename", 1)
        ] is f["adapter"]
        assert app.state.application_registry.get("synthetic").mutation_operations == f["definition"].mutation_operations


def test_post_state_survives_own_version_change_without_redisclosing_old_source(mutation):
    f = mutation
    p = confirmed(f)
    result = apply(f, p)
    # A source revision consumed to produce the patch becomes stale after the write.
    f["permissions"].current = False
    public = f["service"]._present(f["principal"], f["scope"], result)
    assert public.proposal.outcome.post_state.domain_version == "v2"
    assert public.proposal.intent.payload is None
    assert public.proposal.intent.rationale is None
    assert public.proposal.validation.preview is None
    assert f["service"].load_control_record(f["principal"], f["scope"], p.proposal_id).state == "applied"
    f["adapter"].allowed = False
    with pytest.raises(MutationError, match="authorization_denied"):
        f["service"]._present(f["principal"], f["scope"], result)


def test_write_policy_revocation_cannot_prevent_original_key_reconciliation(mutation):
    f = mutation
    p = confirmed(f)
    f["adapter"].timeout = True
    assert apply(f, p).state == "uncertain"
    definition = f["definition"].model_copy(update={"context_policy": ApplicationContextPolicy()})
    f["service"].registry = ApplicationRegistry((definition,))
    resolved = f["service"].reconcile(f["principal"], f["scope"], p.proposal_id)
    assert resolved.state == "applied"
    assert f["service"]._present(f["principal"], f["scope"], resolved).apply_available is False
    assert f["adapter"].sends == 1


def test_scoped_identities_do_not_alias_null_or_delimited_identity_values():
    from personal_ai.mutations.contracts import proposal_identity

    key = uuid4()
    assert proposal_identity("owner", "actor", "synthetic", None, key) != proposal_identity(
        "owner", "actor", "synthetic", "None", key,
    )
    assert proposal_identity("owner:a", "b", "synthetic", None, key) != proposal_identity(
        "owner", "a:b", "synthetic", None, key,
    )


def test_expired_confirmed_proposal_cannot_execute_or_revive(mutation):
    f = mutation
    p = confirmed(f)
    f["now"][0] = p.validation.expires_at
    with pytest.raises(MutationError, match="expired"):
        apply(f, p)
    assert apply(f, p).state == "expired"
    assert f["adapter"].sends == 0
    assert f["service"]._present(f["principal"], f["scope"], apply(f, p)).apply_available is False
