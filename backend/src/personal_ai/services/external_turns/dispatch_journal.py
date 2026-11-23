"""Local canonical journal for the isolated synthetic private dispatch profile."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from personal_ai.contracts.private_dispatch import Binding, canonical, parse


@dataclass(frozen=True, repr=False)
class JournalRow:
    binding: Binding
    claims: bytes
    signature: str
    expires: int
    state: str
    payload_hash: str
    body_hash: str | None
    message_id: str | None
    terminal: bytes | None
    terminal_signature: str | None
    result: str | None
    committed_at: int | None


class SyntheticDispatchJournal:
    """Fixture SQL only. Always compose with an independent live continuity witness."""

    def __init__(self, directory: Path):
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir() or directory.stat().st_mode & 0o077:
            raise ValueError("dispatch journal requires a private directory")
        self._path = directory / "dispatch.sqlite"
        if self._path.is_symlink():
            raise ValueError("dispatch journal cannot use a symlink")
        self._path.touch(mode=0o600, exist_ok=True)
        if not self._path.is_file() or self._path.stat().st_mode & 0o077:
            raise ValueError("dispatch journal requires a private file")
        with self._connection() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS attempts (
                    scope_key TEXT PRIMARY KEY, root TEXT NOT NULL UNIQUE,
                    attempt TEXT NOT NULL UNIQUE, binding BLOB NOT NULL, claims BLOB NOT NULL,
                    signature TEXT NOT NULL, expires INTEGER NOT NULL,
                    state TEXT NOT NULL DEFAULT 'unknown' CHECK (
                        state IN ('unknown', 'claimed', 'send_started', 'completed', 'quarantined')
                    ),
                    payload_hash TEXT NOT NULL, body_hash TEXT,
                    message_id TEXT UNIQUE REFERENCES canonical_messages(message_id),
                    terminal BLOB, terminal_signature TEXT, committed_at INTEGER
                )
                """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS canonical_messages (
                    message_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL UNIQUE
                        REFERENCES attempts(scope_key), result TEXT NOT NULL
                )
                """)

    @contextmanager
    def _connection(self, *, write=False):
        db = sqlite3.connect(self._path, timeout=2)
        try:
            with db:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("PRAGMA synchronous=FULL")
                if write:
                    db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def seal(self, key, binding, claims, signature, expires, payload_hash):
        with self._connection(write=True) as db:
            return db.execute("""
                INSERT INTO attempts (
                    scope_key, root, attempt, binding, claims, signature, expires, payload_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(scope_key) DO NOTHING
                """, (key, binding.root, binding.attempt, canonical(binding), claims,
                      signature, expires, payload_hash)).rowcount == 1

    def claim(self, key, body_hash):
        with self._connection(write=True) as db:
            return db.execute("""
                UPDATE attempts SET state='claimed', body_hash=?
                WHERE scope_key=? AND state='unknown' AND body_hash IS NULL
                """, (body_hash, key)).rowcount == 1

    def mark_started(self, key):
        with self._connection(write=True) as db:
            if db.execute("""
                UPDATE attempts SET state='send_started'
                WHERE scope_key=? AND state='claimed'
                """, (key,)).rowcount != 1:
                raise ValueError("dispatch claim lost")

    def complete(self, key, terminal, signature, result, *, message_id, authorize):
        with self._connection(write=True) as db:
            row = self._read(db, key)
            if row is None or row.state not in {"send_started", "completed"}:
                raise ValueError("dispatch send-start state lost")
            if row.state == "completed":
                if (row.message_id, row.terminal, row.terminal_signature, row.result) != (
                    message_id, terminal, signature, result,
                ):
                    db.execute("UPDATE attempts SET state='quarantined' WHERE scope_key=?", (key,))
                return
            committed_at = authorize()
            db.execute("INSERT INTO canonical_messages VALUES (?, ?, ?)", (message_id, key, result))
            db.execute("""
                UPDATE attempts
                SET state='completed', message_id=?, terminal=?, terminal_signature=?,
                    committed_at=?
                WHERE scope_key=?
                """, (message_id, terminal, signature, committed_at, key))

    def read(self, key):
        with self._connection() as db:
            return self._read(db, key)

    @staticmethod
    def _read(db, key):
        row = db.execute("""
            SELECT a.binding, a.claims, a.signature, a.expires, a.state,
                a.payload_hash, a.body_hash, a.message_id, a.terminal,
                a.terminal_signature, m.result, a.committed_at
            FROM attempts a
            LEFT JOIN canonical_messages m ON m.message_id=a.message_id AND m.scope_key=a.scope_key
            WHERE a.scope_key=?
            """, (key,)).fetchone()
        if row is None:
            return None
        return JournalRow(parse(row[0], Binding), *row[1:])
