"""Example-owned constructors over the canonical persistence factory/database."""

from personal_ai.persistence.factory import (
    persistence_factory as core_persistence_factory,
)

from personal_ai_reference_apps.persistence.postgres.capabilities import (
    PostgresBookingExtractionRepository,
    PostgresItineraryProposalRepository,
)


class ReferencePersistenceFactory:
    def __init__(self, core):
        self.core = core

    def __getattr__(self, name):
        return getattr(self.core, name)

    def itinerary_proposal_repository(self):
        return PostgresItineraryProposalRepository(self.core.database)

    def booking_extraction_repository(self):
        return PostgresBookingExtractionRepository(self.core.database)


def persistence_factory(settings):
    return ReferencePersistenceFactory(core_persistence_factory(settings))
