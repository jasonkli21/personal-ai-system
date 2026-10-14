"""Isolated native stores for tests that exercise database-global invariants."""

import os
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest

from personal_ai.persistence.postgres import PostgresDatabase


@pytest.fixture
def isolated_postgres_dsn():
    """Create only synthetic databases; never truncate the configured database.

    The opt-in local test role needs CREATEDB. Separate databases preserve real
    cross-connection behavior without leaking global store/health state between
    tests or concurrent test processes.
    """
    dsn = os.environ.get("PERSISTENCE_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("set isolated PERSISTENCE_TEST_POSTGRES_DSN (test role needs CREATEDB)")
    PostgresDatabase(dsn, environment="test")  # Reject cloud endpoints before DDL.
    import psycopg
    from psycopg import sql

    name = f"pai_test_{uuid4().hex}"
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            parts = urlsplit(dsn)
            yield urlunsplit(parts._replace(path=f"/{name}"))
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
