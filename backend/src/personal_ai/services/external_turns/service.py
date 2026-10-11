"""High-level external-turn service façade."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.auth.dispatch_grants import DispatchGrantSigner
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.external_turns.contracts import (
    ContextPackage,
    ContextPackageExclusionSummary,
    ContextPackageSourceSummary,
    ExternalTurnAuthority,
    PreparedExternalTurn,
    digest,
)
from personal_ai.services.external_turns.disclosure import ExternalTurnDisclosure
from personal_ai.services.external_turns.dispatch import ExternalTurnDispatch
from personal_ai.services.external_turns.preparation import ExternalTurnPreparation
from personal_ai.services.external_turns.reservations import ExternalTurnReservations


class ExternalTurnService(
    ExternalTurnDisclosure, ExternalTurnPreparation, ExternalTurnDispatch, ExternalTurnReservations
):
    def __init__(
        self,
        *,
        chat: ChatTurnService,
        context: ApplicationContextRequest,
        registry: EndpointRegistry,
        authority: ExternalTurnAuthority,
        signer: DispatchGrantSigner | None = None,
        context_assembler=None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        chat.require_context(context)
        self.chat, self.context, self.registry = chat, context, registry
        self.authority, self.signer, self.clock = authority, signer, clock
        self.context_assembler = context_assembler


__all__ = [
    "ContextPackage",
    "ContextPackageExclusionSummary",
    "ContextPackageSourceSummary",
    "ExternalTurnAuthority",
    "ExternalTurnService",
    "PreparedExternalTurn",
    "digest",
]
