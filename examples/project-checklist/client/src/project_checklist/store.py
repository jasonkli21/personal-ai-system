"""SQLite checklist records and caller-owned immutable continuation intents."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from personal_ai_sdk import Client, Continuation


class Checklist:
    def __init__(self, path: Path):
        self._path = path
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS turns (
                    key TEXT PRIMARY KEY, target TEXT NOT NULL,
                    conversation TEXT NOT NULL, body TEXT NOT NULL,
                    submitted INTEGER NOT NULL DEFAULT 0
                );
            """)

    def _connect(self):
        return sqlite3.connect(self._path)

    def add(self, title: str) -> int:
        with closing(self._connect()) as db, db:
            return db.execute("INSERT INTO items(title) VALUES (?)", (title,)).lastrowid

    def items(self) -> list[tuple[int, str, int]]:
        with closing(self._connect()) as db:
            return db.execute(
                "SELECT id, title, done FROM items ORDER BY id"
            ).fetchall()

    def finish(self, item: int) -> None:
        with closing(self._connect()) as db, db:
            db.execute("UPDATE items SET done = 1 WHERE id = ?", (item,))

    def prepare(self, target: str, conversation: str, content: str) -> str:
        """Journal explicitly supplied content and commit before any HTTP operation."""
        conversation = str(UUID(conversation))
        if not 0 < len(content) <= 20_000:
            raise ValueError("invalid_content_length")
        key = str(uuid4())
        body: Continuation = {
            "idempotency_key": key,
            "content": content,
            "choice": {"mode": "automatic"},
        }
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO turns(key, target, conversation, body) VALUES (?, ?, ?, ?)",
                (key, target, conversation, json.dumps(body)),
            )
        return key

    def turn(self, client: Client, target: str, key: str, *, recover: bool):
        key = str(UUID(key))
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT conversation, body, submitted FROM turns WHERE key = ? AND target = ?",
                (key, target),
            ).fetchone()
            if row is None:
                raise ValueError("original_intent_not_found")
            conversation, raw_body, submitted = row
            if not recover:
                claimed = db.execute(
                    "UPDATE turns SET submitted = 1 WHERE key = ? AND submitted = 0",
                    (key,),
                ).rowcount
                if not claimed:
                    raise ValueError("use_recover_for_original_key")
            elif not submitted:
                raise ValueError("original_intent_not_submitted")
        if recover:
            status = client.status(conversation, key)
            if status["state"] != "completed":
                return status
        return client.continue_turn(
            conversation, cast(Continuation, json.loads(raw_body))
        )
