"""Bounded Psycopg pools and connection/transaction primitives."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from time import monotonic
from typing import Any
from urllib.parse import parse_qs, urlsplit

from personal_ai.storage.errors import PersistenceConflict  # noqa: F401 - compatibility re-export


class PersistenceUnavailable(RuntimeError):
    """A persistence dependency did not complete within its configured bound."""


class PersistenceRecordNotFound(LookupError):
    """An identifier does not resolve inside the caller's authorized scope."""


class _DeadlineConnection:
    """Apply a caller's remaining budget to every statement in a transaction."""

    def __init__(self, connection, *, deadline, statement_timeout_ms, lock_timeout_ms):
        self._connection = connection
        self._deadline = deadline
        self._statement_timeout_ms = statement_timeout_ms
        self._lock_timeout_ms = lock_timeout_ms

    def _remaining_ms(self):
        remaining = None if self._deadline is None else self._deadline - monotonic()
        if remaining is not None and remaining <= 0:
            raise TimeoutError("postgres operation deadline exceeded")
        return remaining

    def execute(self, query, params=None, **kwargs):
        remaining = self._remaining_ms()
        statement_ms = self._statement_timeout_ms
        lock_ms = self._lock_timeout_ms
        if remaining is not None:
            remaining_ms = max(1, int(remaining * 1000))
            statement_ms = min(statement_ms, remaining_ms)
            lock_ms = min(lock_ms, remaining_ms)
        self._connection.execute(
            "SELECT set_config('statement_timeout', %s, true), "
            "set_config('lock_timeout', %s, true)",
            (f"{statement_ms}ms", f"{lock_ms}ms"),
        )
        self._remaining_ms()
        try:
            return self._connection.execute(query, params, **kwargs)
        except Exception as error:
            if getattr(error, "sqlstate", None) in {"57014", "55P03"}:
                raise TimeoutError("postgres operation timed out") from error
            raise

    def check_deadline(self):
        self._remaining_ms()

    def __getattr__(self, name):
        return getattr(self._connection, name)


class PostgresDatabase:
    """Psycopg 3 pools with explicit local endpoint and time bounds."""

    def __init__(
        self,
        dsn: str,
        *,
        environment: str = "local",
        min_size: int = 1,
        max_size: int = 8,
        connect_timeout: int = 5,
        statement_timeout_ms: int = 5_000,
        lock_timeout_ms: int = 2_000,
        pool_timeout: float = 5,
        prepare_threshold: int | None = 5,
    ) -> None:
        if not dsn.strip():
            raise ValueError("postgres_dsn_required")
        if not 0 <= min_size <= max_size <= 16 or max_size < 1:
            raise ValueError("postgres_pool_bounds_invalid")
        if not 1 <= connect_timeout <= 30 or not 1 <= statement_timeout_ms <= 120_000:
            raise ValueError("postgres_timeout_bounds_invalid")
        self._dsn = dsn
        self._environment = environment
        self._min_size, self._max_size = min_size, max_size
        self._connect_timeout = connect_timeout
        self._statement_timeout_ms = statement_timeout_ms
        self._lock_timeout_ms = lock_timeout_ms
        self._pool_timeout = pool_timeout
        self._prepare_threshold = prepare_threshold
        self._pool = None
        self._async_pool = None
        self._validate_endpoint()

    def _validate_endpoint(self) -> None:
        parsed = urlsplit(self._dsn)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
            raise ValueError("postgres_dsn_invalid")
        host = parsed.hostname.rstrip(".").lower()
        local_hosts = {"localhost", "127.0.0.1", "::1", "postgres", "postgres-test"}
        if self._environment in {"staging", "production"} and host in local_hosts:
            raise ValueError("local_postgres_endpoint_forbidden")
        if self._environment in {"local", "test"} and host not in local_hosts:
            raise ValueError("cloud_postgres_endpoint_forbidden")
        if self._environment in {"staging", "production"}:
            query = parse_qs(parsed.query)
            if query.get("sslmode") != ["verify-full"]:
                raise ValueError("postgres_tls_verification_required")

    def open(self) -> None:
        if self._pool is not None:
            return
        try:
            from psycopg.conninfo import make_conninfo
            from psycopg_pool import ConnectionPool
        except ImportError as error:  # pragma: no cover - packaging failure
            raise RuntimeError("psycopg_pool_required") from error
        options = (
            f"-c statement_timeout={self._statement_timeout_ms} "
            f"-c lock_timeout={self._lock_timeout_ms}"
        )
        conninfo = make_conninfo(
            self._dsn,
            connect_timeout=self._connect_timeout,
            options=options,
            application_name="personal-ai",
        )
        self._pool = ConnectionPool(
            conninfo,
            min_size=self._min_size,
            max_size=self._max_size,
            timeout=self._pool_timeout,
            kwargs={"prepare_threshold": self._prepare_threshold},
            open=True,
        )

    async def open_async(self) -> None:
        if self._async_pool is not None:
            return
        try:
            from psycopg.conninfo import make_conninfo
            from psycopg_pool import AsyncConnectionPool
        except ImportError as error:  # pragma: no cover - packaging failure
            raise RuntimeError("psycopg_pool_required") from error
        options = (
            f"-c statement_timeout={self._statement_timeout_ms} "
            f"-c lock_timeout={self._lock_timeout_ms}"
        )
        conninfo = make_conninfo(
            self._dsn,
            connect_timeout=self._connect_timeout,
            options=options,
            application_name="personal-ai",
        )
        self._async_pool = AsyncConnectionPool(
            conninfo,
            min_size=self._min_size,
            max_size=self._max_size,
            timeout=self._pool_timeout,
            kwargs={"prepare_threshold": self._prepare_threshold},
            open=False,
        )
        await self._async_pool.open()

    @contextmanager
    def connection(
        self,
        *,
        timeout_seconds: float | None = None,
        deadline: float | None = None,
        snapshot: bool = False,
    ) -> Iterator[Any]:
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise TimeoutError("postgres operation deadline exceeded")
            relative_deadline = monotonic() + timeout_seconds
            deadline = relative_deadline if deadline is None else min(deadline, relative_deadline)
        remaining = None if deadline is None else deadline - monotonic()
        if remaining is not None and remaining <= 0:
            raise TimeoutError("postgres operation deadline exceeded")
        pool_timeout = (
            self._pool_timeout if remaining is None else min(self._pool_timeout, remaining)
        )
        self.open()
        try:
            with (
                self._pool.connection(timeout=pool_timeout) as raw_connection,
                raw_connection.transaction(),
            ):
                if snapshot:
                    raw_connection.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                    )
                connection = _DeadlineConnection(
                    raw_connection,
                    deadline=deadline,
                    statement_timeout_ms=self._statement_timeout_ms,
                    lock_timeout_ms=self._lock_timeout_ms,
                )
                yield connection
                connection.check_deadline()
        except Exception as error:
            if deadline is not None and monotonic() >= deadline:
                raise TimeoutError("postgres operation deadline exceeded") from error
            if _is_connection_error(error):
                raise PersistenceUnavailable("postgres_unavailable") from error
            raise

    @contextmanager
    def transaction(
        self,
        *,
        timeout_seconds: float | None = None,
        deadline: float | None = None,
        snapshot: bool = False,
    ) -> Iterator[Any]:
        """Alias that makes transaction-group intent explicit at call sites."""
        with self.connection(
            timeout_seconds=timeout_seconds, deadline=deadline, snapshot=snapshot
        ) as connection:
            yield connection

    @asynccontextmanager
    async def aconnection(self):
        await self.open_async()
        async with (
            self._async_pool.connection(timeout=self._pool_timeout) as connection,
            connection.transaction(),
        ):
            yield connection

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    async def close_async(self) -> None:
        if self._async_pool is not None:
            await self._async_pool.close()
            self._async_pool = None

    def migrate(self) -> tuple[int, ...]:
        """Apply the checksum-pinned migration sequence."""
        from .migrations import apply_migrations

        return apply_migrations(self)


def _is_connection_error(error: Exception) -> bool:
    return error.__class__.__name__ in {
        "OperationalError",
        "PoolTimeout",
        "ConnectionTimeout",
        "ConnectionFailure",
    }
