"""Opt-in canonical Postgres transactions; never substitute fake evidence."""

# ruff: noqa: F811 - pytest discovers imported fixtures by their parameter names

from concurrent.futures import ThreadPoolExecutor

import pytest

from personal_ai.persistence.postgres.episodes import PostgresEpisodeRepository
from tests.persistence.test_workflow_postgres import database  # noqa: F401
from tests.test_episode_service import runtime, seed_episode  # noqa: F401

pytestmark = pytest.mark.persistence_integration


def test_disabled_episode_capture_and_native_seeded_maintenance(database, runtime):
    rt = runtime
    rt.service.repository = PostgresEpisodeRepository(database)
    assert rt.service.capture("project", rt.run_id).status == "disabled"
    assert rt.service.read("project").status == "disabled"
    # Direct synthetic seeding exercises maintenance without enabling ingestion.
    identity = seed_episode(rt)[0].id
    assert rt.service.forget("project", identity).status == "forgotten"
    assert rt.service.capture("project", rt.run_id).status == "disabled"
    assert rt.service.read("project", episode_id=identity).status == "disabled"
    with rt.service.guard("project", maintenance=True) as (_, _, bucket, _):
        assert str(identity) not in bucket["records"]
        assert bucket["states"][str(identity)]["retrieval_status"] == "forgotten"
        assert bucket["receipts"]


def test_episode_transaction_rollback_and_connection_serialization(database):
    repo = PostgresEpisodeRepository(database)
    namespace = "a" * 64
    with pytest.raises(RuntimeError), repo.locked("owner", namespace) as bucket:
        bucket["receipts"]["counter"] = 99
        raise RuntimeError("before commit")
    with repo.locked("owner", namespace) as bucket:
        assert "counter" not in bucket["receipts"]

    def increment(_):
        with repo.locked("owner", namespace) as bucket:
            bucket["receipts"]["counter"] = bucket["receipts"].get("counter", 0) + 1

    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(increment, range(8)))
    with repo.locked("owner", namespace) as bucket:
        assert bucket["receipts"]["counter"] == 8
