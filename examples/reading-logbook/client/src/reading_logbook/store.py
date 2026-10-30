"""Consumer-owned books/notes and retry journal; no credentials are persisted."""

import json
import os
import sqlite3
from pathlib import Path


class Logbook:
    def __init__(self, path):
        path = Path(path)
        # Create privately before SQLite opens; existing databases retain contents.
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(path, 0o600)
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY, title TEXT NOT NULL, note TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations(namespace TEXT, key TEXT, kind TEXT NOT NULL,
                conversation_id TEXT, body TEXT NOT NULL, state TEXT NOT NULL, result TEXT,
                PRIMARY KEY(namespace,key));
        """)

    def add(self, title, note):
        if not 0 < len(title) <= 200 or len(note) > 20000:
            raise ValueError("book text exceeds local limits")
        with self.db:
            return self.db.execute(
                "INSERT INTO books(title,note) VALUES (?,?)", (title, note)
            ).lastrowid

    def books(self):
        return [
            dict(zip(("id", "title", "note"), row))
            for row in self.db.execute("SELECT * FROM books ORDER BY id")
        ]

    def remember(self, namespace, key, kind, conversation_id, body):
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO operations VALUES (?,?,?,?,?,'unknown',NULL)",
                (namespace, key, kind, conversation_id, encoded),
            )
            existing = self.operation(namespace, key)
            if (
                existing["body"] != body
                or existing["kind"] != kind
                or existing["conversation_id"] != conversation_id
            ):
                raise ValueError("operation key already used for different input")

    def operation(self, namespace, key):
        row = self.db.execute(
            "SELECT kind,conversation_id,body,state,result FROM operations WHERE namespace=? AND key=?",
            (namespace, key),
        ).fetchone()
        if row is None:
            raise ValueError("unknown local operation key")
        return {
            "kind": row[0],
            "conversation_id": row[1],
            "body": json.loads(row[2]),
            "state": row[3],
            "result": json.loads(row[4]) if row[4] is not None else None,
        }

    def completed(self, namespace, key, result):
        with self.db:
            self.db.execute(
                "UPDATE operations SET state='completed',result=? WHERE namespace=? AND key=?",
                (json.dumps(result), namespace, key),
            )
