"""Single-host content-free external intent fence. Receipts are never pruned."""

import json
import os
import sqlite3
import stat
from contextlib import closing
from hashlib import sha256
from pathlib import Path


class IntentConflict(ValueError):
    pass


class AttemptJournal:
    CAPACITY = 4096

    def __init__(self, filename):
        path = Path(filename)
        if (
            not path.is_absolute()
            or not path.parent.is_dir()
            or any(p.is_symlink() for p in (path, *path.parents))
        ):
            raise ValueError("journal_unavailable")
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        os.close(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("journal_permissions_invalid")
        self.filename = str(path)
        with closing(self.connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS retrieval_attempts ("
                "scope TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, "
                "state TEXT NOT NULL, PRIMARY KEY(scope, key))"
            )

    def connect(self):
        return sqlite3.connect(self.filename, timeout=0.05)

    @staticmethod
    def scope_key(scope):
        return sha256(
            json.dumps(
                [
                    scope.owner_id,
                    scope.acting_user_id,
                    scope.application_id,
                    scope.workspace_id,
                ]
            ).encode()
        ).hexdigest()

    def reserve(self, scope, query):
        key, namespace = str(query.idempotency_key), self.scope_key(scope)
        fingerprint = sha256(query.model_dump_json().encode()).hexdigest()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT fingerprint, state FROM retrieval_attempts WHERE scope=? AND key=?",
                (namespace, key),
            ).fetchone()
            if row:
                if row[0] != fingerprint:
                    raise IntentConflict("retrieval_intent_conflict")
                return (
                    "external_already_attempted"
                    if row[1] == "completed"
                    else "external_outcome_unknown"
                )
            if db.execute("SELECT count(*) FROM retrieval_attempts").fetchone()[0] >= self.CAPACITY:
                return "quota"
            db.execute(
                "INSERT INTO retrieval_attempts VALUES (?, ?, ?, 'unknown')",
                (namespace, key, fingerprint),
            )
        return None

    def complete(self, scope, query):
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE retrieval_attempts SET state='completed' WHERE scope=? AND key=?",
                (self.scope_key(scope), str(query.idempotency_key)),
            )
