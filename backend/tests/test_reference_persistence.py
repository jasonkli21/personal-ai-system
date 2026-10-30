"""Historical decoder checks against synthetic SQL rows; no database acceptance."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from personal_ai_reference_apps.booking_extractions.repositories import ExtractionRecord
from personal_ai_reference_apps.itinerary_proposals.repositories import ProposalRecord
from personal_ai_reference_apps.persistence.factory import ReferencePersistenceFactory
from personal_ai_reference_apps.persistence.postgres.capabilities import (
    PostgresBookingExtractionRepository,
    PostgresItineraryProposalRepository,
)

from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.storage import ResourceNotFoundError


class Database:
    def __init__(self, payload):
        self.payload = payload
        self.queries = []

    @contextmanager
    def connection(self, **_kwargs):
        yield self

    def execute(self, query, parameters):
        self.queries.append((query, parameters))
        return self

    def fetchone(self):
        return self.payload, 1


@pytest.mark.parametrize("kind", ["proposal", "extraction"])
@pytest.mark.parametrize("scoped", [False, True])
def test_original_sql_payload_decoder_preserves_legacy_null_and_scoped_rows(kind, scoped):
    now = datetime(2026, 10, 30, tzinfo=UTC)
    record_id = uuid4()
    base = {
        "owner_id": "synthetic-owner",
        "request_fingerprint": "a" * 64,
        "state": "pending",
        "created_at": now,
        "execution_deadline": now + timedelta(seconds=30),
        "retained_until": now + timedelta(hours=48),
    }
    if kind == "proposal":
        record = ProposalRecord(
            **base,
            proposal_id=record_id,
            trip_handle="h_trip00001",
            support_mode="context_only",
            proposal_expires_at=now + timedelta(hours=24),
        )
        repository_type = PostgresItineraryProposalRepository
    else:
        record = ExtractionRecord(
            **base,
            extraction_id=record_id,
            idempotency_key=uuid4(),
            source_sha256="b" * 64,
            expires_at=now + timedelta(hours=24),
        )
        repository_type = PostgresBookingExtractionRepository
    payload = record.model_dump(mode="json")
    scope = (
        ApplicationScope(application_id="travel", workspace_id="trip-1")
        if scoped
        else ApplicationScope()
    )
    if scoped:
        payload.update(application_id="travel", workspace_id="trip-1")
    else:
        # Old v1 rows lack scope fields; a nullable legacy workspace remains null.
        payload.pop("application_id", None)
        payload["workspace_id"] = None
    database = Database(payload)
    with application_scope_context(scope):
        decoded = repository_type(database).get("synthetic-owner", record_id)
        assert (
            decoded.application_id == scope.application_id
            and decoded.workspace_id == scope.workspace_id
        )
        assert decoded.request_fingerprint == "a" * 64 and decoded.state == "pending"
        assert (decoded.proposal_id if kind == "proposal" else decoded.extraction_id) == record_id
        assert "workspace_id IS NOT DISTINCT FROM" in database.queries[-1][0]
        with pytest.raises(ResourceNotFoundError):
            repository_type(database).get("foreign-owner", record_id)
    with (
        application_scope_context(ApplicationScope(application_id="shopping")),
        pytest.raises(ResourceNotFoundError),
    ):
        repository_type(database).get("synthetic-owner", record_id)
    assert database.payload == payload


def test_optional_factory_delegates_to_canonical_store_without_core_decoder_hooks():
    sentinel = object()

    class Core:
        database = sentinel

        def memory_repository(self):
            return sentinel

    factory = ReferencePersistenceFactory(Core())
    assert factory.memory_repository() is sentinel
    assert factory.itinerary_proposal_repository().database is sentinel
    assert factory.booking_extraction_repository().database is sentinel
    from personal_ai.persistence.factory import PostgresDynamoPersistenceFactory

    assert not hasattr(PostgresDynamoPersistenceFactory, "booking_extraction_repository")
    assert not hasattr(PostgresDynamoPersistenceFactory, "itinerary_proposal_repository")
