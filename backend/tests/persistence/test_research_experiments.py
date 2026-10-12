"""Real-store immutable replay, race, namespace and retention acceptance (deferred)."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from personal_ai.auth.scope import ApplicationScope
from personal_ai.evaluation.retrieval_contracts import (
    ResearchExperimentSummary,
    RetrievalMeasurements,
)
from personal_ai.persistence.postgres import PersistenceConflict, PostgresDatabase
from personal_ai.persistence.postgres.research_experiments import (
    PostgresResearchExperimentRepository,
)

pytestmark = pytest.mark.persistence_integration


def summary(owner):
    now = datetime.now(UTC)
    metrics = RetrievalMeasurements(
        constraint_retention=1, evidence_recall=1, evidence_precision=1,
        freshness_compliance=1, source_diversity=1, exact_support=1,
        calls=1, retrieved_bytes=100, packed_tokens=100, latency_ms=1,
    )
    return ResearchExperimentSummary(
        id=uuid4(), owner_id=owner, evaluation_run_id=uuid4(), case_id="case",
        task_family="literal", source_profile="synthetic-public-v1", strategy_id="compact-extractive-v1",
        configuration_sha256="a"*64, fixture_sha256="b"*64, baseline_sha256="c"*64,
        tested_revision="a"*40, baseline=metrics, candidate=metrics,
        created_at=now, expires_at=now+timedelta(days=1),
    )


def test_immutable_concurrent_replay_namespace_truncation_and_expiry():
    dsn = os.environ.get("PERSISTENCE_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("isolated PostgreSQL/pgvector environment is deferred")
    database = PostgresDatabase(dsn, environment="test", min_size=1, max_size=8)
    owner = "phase33-" + str(uuid4())
    repository = PostgresResearchExperimentRepository(database)
    record = summary(owner)
    try:
        database.migrate()
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(repository.save, [record]*4))
        assert results == [record]*4
        assert repository.get(owner_id=owner, scope=ApplicationScope(), record_id=record.id) == record
        with pytest.raises(LookupError):
            repository.get(owner_id="other", scope=ApplicationScope(), record_id=record.id)
        with pytest.raises(LookupError):
            repository.get(owner_id=owner, scope=ApplicationScope(workspace_id="other"), record_id=record.id)
        with pytest.raises(PersistenceConflict):
            repository.save(record.model_copy(update={"strategy_id": "different-v1"}))
        repository.save(summary(owner))
        rows, complete = repository.scan(owner_id=owner, scope=ApplicationScope(), limit=1)
        assert len(rows) == 1 and not complete
        assert repository.expire(owner_id=owner, now=record.expires_at+timedelta(days=1), limit=1) == 1
    finally:
        with database.transaction() as connection:
            connection.execute("DELETE FROM research_experiments WHERE owner_id=%s", (owner,))
            connection.execute("DELETE FROM scope_namespaces WHERE owner_id=%s", (owner,))
        database.close()
