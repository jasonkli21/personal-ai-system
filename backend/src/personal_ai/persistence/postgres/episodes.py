"""Postgres episode projection transactions, with canonical owner deletion fence."""

from contextlib import contextmanager
from copy import deepcopy

from personal_ai.memory.episode_repository import empty_bucket
from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced


class PostgresEpisodeRepository:
    def __init__(self, database):
        self.database = database

    @contextmanager
    def locked(self, owner_id, namespace):
        from psycopg.types.json import Jsonb

        with self.database.transaction(timeout_seconds=2) as connection:
            assert_owner_unfenced(connection, owner_id)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ("episodes:" + owner_id + ":" + namespace,),
            )
            row = connection.execute(
                "SELECT payload FROM memory_episode_scopes WHERE owner_id=%s AND namespace_digest=%s FOR UPDATE",
                (owner_id, namespace),
            ).fetchone()
            bucket = row[0] if row else empty_bucket()
            original = deepcopy(bucket)
            yield bucket
            if bucket == original:
                return
            if row is None:
                connection.execute("SELECT pg_advisory_xact_lock(%s, %s)", (0x504149, 35))
                if (
                    connection.execute("SELECT count(*) FROM memory_episode_scopes").fetchone()[0]
                    >= 128
                ):
                    raise ValueError("episode_namespace_capacity")
            connection.execute(
                "INSERT INTO memory_episode_scopes(owner_id,namespace_digest,payload) VALUES (%s,%s,%s) "
                "ON CONFLICT(owner_id,namespace_digest) DO UPDATE SET payload=EXCLUDED.payload",
                (owner_id, namespace, Jsonb(bucket)),
            )

    def erase_owner(self, owner_id):
        """Operator erasure only after the existing durable owner fence is installed."""
        from personal_ai.persistence.postgres.owner_lifecycle import lock_owner

        with self.database.transaction(timeout_seconds=2) as connection:
            lock_owner(connection, owner_id)
            if not connection.execute(
                "SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s", (owner_id,)
            ).fetchone():
                raise PermissionError("owner_fence_required")
            connection.execute("DELETE FROM memory_episode_scopes WHERE owner_id=%s", (owner_id,))
