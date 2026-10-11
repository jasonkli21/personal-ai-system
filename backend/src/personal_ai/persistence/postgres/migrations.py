"""Checksum-pinned SQL migration loading and application."""

from __future__ import annotations

import hashlib
import importlib
from importlib.resources import files


def migration_checksum(version: int, sql: str, *, migration_package=None) -> str:
    """Checksum SQL and the immutable implementation paired with migration 022."""
    checksum_payload = sql.encode("utf-8")
    if version == 22:
        package = migration_package or files("personal_ai.persistence")
        versioned_directory = package.joinpath("migrations_py")
        checksum_payload += b"\0" + versioned_directory.joinpath("__init__.py").read_bytes()
        checksum_payload += (
            b"\0" + versioned_directory.joinpath("022_routing_authorities.py").read_bytes()
        )
    return hashlib.sha256(checksum_payload).hexdigest()


def apply_migrations(database) -> tuple[int, ...]:
    """Apply checksum-pinned SQL migrations under a transaction advisory lock."""
    database.open()
    applied: list[int] = []
    migration_dir = files("personal_ai.persistence").joinpath("migrations")
    migrations = sorted(item for item in migration_dir.iterdir() if item.name.endswith(".sql"))
    for resource in migrations:
        prefix, _, _ = resource.name.partition("_")
        try:
            version = int(prefix)
        except ValueError as error:
            raise RuntimeError("migration_filename_invalid") from error
        sql = resource.read_text(encoding="utf-8")
        checksum = migration_checksum(version, sql)
        with database.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s, %s)", (0x504149, 10))
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version integer PRIMARY KEY, checksum text NOT NULL, "
                "applied_at timestamptz NOT NULL DEFAULT now())"
            )
            row = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE version = %s",
                (version,),
            ).fetchone()
            if row is not None:
                if row[0] != checksum:
                    raise RuntimeError("migration_checksum_mismatch")
                continue
            connection.execute(sql, prepare=False)
            if version == 22:
                migration = importlib.import_module(
                    "personal_ai.persistence.migrations_py.022_routing_authorities"
                )
                migration.migrate_routing_authorities(connection)
            connection.execute(
                "INSERT INTO schema_migrations(version, checksum) VALUES (%s, %s)",
                (version, checksum),
            )
            applied.append(version)
    return tuple(applied)
