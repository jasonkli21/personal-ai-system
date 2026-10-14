"""Deterministic source commands share confirmation and uncertain-effect recovery."""

from uuid import uuid4

import pytest

from personal_ai.mutations.contracts import (
    AuthenticatedCommandRequest,
    MutationError,
    MutationUnavailableError,
    UserCommandProvenance,
)
from tests.test_mutations import mutation_case


def command_case():
    case = mutation_case()
    command = AuthenticatedCommandRequest(
        source_application_id="finance",
        command_id=case["intent"].idempotency_key,
    )
    provenance = UserCommandProvenance(
        source_application_id="finance",
        command_id=command.command_id,
        acting_user_id=case["scope"].acting_user_id,
        command_fingerprint="c" * 64,
    )
    intent = case["intent"].model_copy(update={"producer": provenance})

    class Resolver:
        def resolve(self, principal, scope, request):
            assert principal == case["principal"] and scope == case["scope"]
            assert request == command
            return intent

    case["service"].command_resolver = Resolver()
    return case, command, intent


def test_command_requires_installed_source_authority():
    case, command, _ = command_case()
    case["service"].command_resolver = None
    with pytest.raises(MutationUnavailableError, match="command_resolver_unavailable"):
        case["service"].create_from_command(case["principal"], case["scope"], command)
    assert not case["repo"].records


def test_command_replays_exact_intent_and_recovers_lost_ack_without_resend():
    case, command, _ = command_case()
    service, principal, scope = case["service"], case["principal"], case["scope"]
    proposal = service.create_from_command(principal, scope, command)
    assert service.create_from_command(principal, scope, command) == proposal
    proposal = service.validate(principal, scope, proposal.proposal_id)
    confirmation_id = uuid4()
    proposal = service.confirm(
        principal,
        scope,
        proposal.proposal_id,
        binding=proposal.binding(),
        confirmation_id=confirmation_id,
    )
    case["adapter"].timeout = True
    outcome = service.apply(
        principal,
        scope,
        proposal.proposal_id,
        binding=proposal.binding(),
        confirmation_id=confirmation_id,
    )
    assert outcome.state == "uncertain"
    outcome = service.apply(
        principal,
        scope,
        proposal.proposal_id,
        binding=proposal.binding(),
        confirmation_id=confirmation_id,
    )
    assert outcome.state == "applied"
    assert case["adapter"].sends == case["adapter"].effects == 1
    assert case["adapter"].reconciles == 1
    public = service.read_view(principal, scope, proposal.proposal_id).proposal.intent.producer
    assert public.model_dump() == proposal.intent.producer.model_dump(exclude={"acting_user_id"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_application_id", "health"),
        ("command_id", uuid4()),
        ("acting_user_id", "google|mallory"),
    ],
)
def test_resolver_cannot_change_command_actor_or_source(field, value):
    case, command, intent = command_case()

    class Resolver:
        def resolve(self, *args):
            return intent.model_copy(
                update={
                    "producer": intent.producer.model_copy(update={field: value}),
                }
            )

    case["service"].command_resolver = Resolver()
    with pytest.raises(MutationError, match="command_provenance_denied"):
        case["service"].create_from_command(case["principal"], case["scope"], command)
    assert not case["repo"].records


def test_unverified_identity_cannot_reach_command_resolver():
    case, command, _ = command_case()
    from personal_ai.auth.contracts import AuthenticatedPrincipal

    with pytest.raises(MutationError, match="identity_denied"):
        case["service"].create_from_command(
            AuthenticatedPrincipal.development(),
            case["scope"],
            command,
        )
