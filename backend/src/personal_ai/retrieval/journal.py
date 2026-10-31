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
    MAX_SCOPES = 32
    MAX_PAGES = 32768  # 128 MiB at the required 4 KiB SQLite page size.

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
            db.execute("CREATE TABLE IF NOT EXISTS retrieval_scopes (scope TEXT PRIMARY KEY)")
            db.execute("INSERT OR IGNORE INTO retrieval_scopes SELECT DISTINCT scope FROM retrieval_attempts")

    def admit_scopes(self, scopes):
        """Reserve equal lifetime allocations for all operator-configured scopes.

        Previously admitted scopes remain allocated after grant removal. Operators
        cannot recycle identities by editing a manifest or deleting receipts.
        """
        namespaces = {self.scope_key(scope) for scope in scopes}
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            retained = {row[0] for row in db.execute("SELECT scope FROM retrieval_scopes")}
            if len(retained | namespaces) > self.MAX_SCOPES:
                return False
            db.executemany("INSERT OR IGNORE INTO retrieval_scopes VALUES (?)",
                           [(namespace,) for namespace in sorted(namespaces)])
        return True

    def connect(self):
        db = sqlite3.connect(self.filename, timeout=0.05)
        if db.execute("PRAGMA page_size").fetchone()[0] != 4096:
            db.close()
            raise ValueError("journal_page_size_invalid")
        db.execute(f"PRAGMA max_page_count={self.MAX_PAGES}")
        return db

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
            admitted = db.execute("SELECT 1 FROM retrieval_scopes WHERE scope=?", (namespace,)).fetchone()
            if not admitted:
                if db.execute("SELECT count(*) FROM retrieval_scopes").fetchone()[0] >= self.MAX_SCOPES:
                    return "quota"
                db.execute("INSERT INTO retrieval_scopes VALUES (?)", (namespace,))
            # Capacity is scoped to one authenticated owner/actor/app/workspace tuple.
            # One scope must not consume the lifetime allowance of every other scope.
            if db.execute(
                "SELECT count(*) FROM retrieval_attempts WHERE scope=?", (namespace,)
            ).fetchone()[0] >= self.CAPACITY:
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
