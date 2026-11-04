"""Single-row workflow authority. Every transition and its receipt commit together."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

from personal_ai.contracts.workflow import TERMINAL, RunProgress
from personal_ai.storage.errors import PersistenceConflict

_EVENT_LIMIT = 8
_RUN_LIMIT = 256
_LEASE = timedelta(seconds=5)


class WorkflowFenceLost(RuntimeError):
    pass


class WorkflowRow:
    def __init__(self, run_id, deadline, source_digest, spec, record, now):
        self.run_id = run_id
        self.deadline = deadline
        self.source_digest = source_digest
        self.spec = spec
        self.record = record
        self.now = now

    def event(self, kind, attempt_id=None):
        self.record["cursor"] += 1
        events = self.record["events"]
        events.append({"sequence": self.record["cursor"], "kind": kind, "attempt_id": attempt_id})
        del events[:-_EVENT_LIMIT]

    def terminal(self, state, reason=None):
        self.spec = None
        self.record.update(state=state, reason=reason, fence=None, lease=None)
        self.event(state)

    def expire(self):
        row = self.record
        if row["state"] in TERMINAL:
            return
        if row["lease"] is not None and self.now.timestamp() < row["lease"]:
            return
        attempt = self.pending
        if attempt is not None:
            if attempt["state"] == "dispatched":
                attempt["state"] = "uncertain"
                self.terminal("uncertain", "operator_reconciliation_required")
                return
            # The old fence can no longer advance this reservation to dispatch.
            attempt["state"] = "abandoned"
            self.event("step_abandoned", attempt["attempt_id"])
        if row["cancel_requested"]:
            self.terminal("canceled")
        elif self.now >= self.deadline:
            self.terminal("failed", "deadline")
        elif row["state"] == "running":
            row.update(state="queued", fence=None, lease=None)
            self.event("requeued")

    @property
    def pending(self):
        attempts = self.record["attempts"]
        if attempts and attempts[-1]["state"] in {"reserved", "dispatched"}:
            return attempts[-1]
        return None

    def claim(self):
        self.expire()
        if self.record["state"] != "queued":
            return None
        # Limit recovery to one replacement claim.
        if self.record["claims"] >= 2:
            self.terminal("failed", "claim_budget")
            return None
        fence = str(uuid4())
        self.record.update(
            state="running",
            fence=fence,
            lease=(self.now + _LEASE).timestamp(),
            claims=self.record["claims"] + 1,
        )
        self.event("claimed")
        return fence

    def check(self, fence, *, renew=False):
        row = self.record
        if (
            row["state"] != "running"
            or row["fence"] != fence
            or self.now.timestamp() >= row["lease"]
        ):
            raise WorkflowFenceLost("workflow_fence_lost")
        if renew:
            row["lease"] = (self.now + _LEASE).timestamp()

    def progress(self, cursor):
        events = self.record["events"]
        if type(cursor) is not int or not 0 <= cursor <= self.record["cursor"]:
            raise ValueError("workflow_cursor_invalid")
        return RunProgress(
            run_id=self.run_id,
            state=self.record["state"],
            cancel_requested=self.record["cancel_requested"],
            reason=self.record["reason"],
            cursor=self.record["cursor"],
            gap=cursor < events[0]["sequence"] - 1,
            events=tuple(event for event in events if event["sequence"] > cursor),
            attempts=self.record["attempts"],
        )


class PostgresWorkflowStore:
    def __init__(self, database):
        self.database = database

    def find(self, scope_digest, spec):
        with self.database.transaction(timeout_seconds=2) as connection:
            return self._find(
                connection, scope_digest, spec.original_key, spec.intent_digest(scope_digest)
            )

    @staticmethod
    def _find(connection, scope_digest, original_key, digest):
        existing = connection.execute(
            "SELECT run_id, intent_digest FROM workflow_runs "
            "WHERE scope_digest = %s AND original_key = %s",
            (scope_digest, original_key),
        ).fetchone()
        if existing is None:
            return None
        if existing[1] != digest:
            raise PersistenceConflict("workflow_intent_conflict")
        return existing[0]

    def submit(self, scope_digest, spec, source_digest):
        from psycopg.types.json import Jsonb

        digest = spec.intent_digest(scope_digest)
        with self.database.transaction(timeout_seconds=2) as connection:
            # Serialize the global bounded admission check across all callers.
            connection.execute("SELECT pg_advisory_xact_lock(%s, %s)", (0x504149, 34))
            existing = self._find(connection, scope_digest, spec.original_key, digest)
            if existing is not None:
                return existing
            if connection.execute("SELECT count(*) FROM workflow_runs").fetchone()[0] >= _RUN_LIMIT:
                raise ValueError("workflow_capacity")
            now = connection.execute("SELECT clock_timestamp()").fetchone()[0]
            run_id = uuid4()
            row = WorkflowRow(
                run_id,
                now + timedelta(milliseconds=spec.deadline_ms),
                source_digest,
                spec.model_dump(mode="json"),
                {
                    "state": "queued",
                    "fence": None,
                    "lease": None,
                    "claims": 0,
                    "cursor": 0,
                    "events": [],
                    "attempts": [],
                    "cancel_requested": False,
                    "reason": None,
                },
                now,
            )
            row.event("queued")
            connection.execute(
                "INSERT INTO workflow_runs "
                "(run_id, scope_digest, original_key, intent_digest, source_digest, "
                "spec, deadline, record) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    run_id,
                    scope_digest,
                    spec.original_key,
                    digest,
                    source_digest,
                    Jsonb(row.spec),
                    row.deadline,
                    Jsonb(row.record),
                ),
            )
            return run_id

    @contextmanager
    def locked(self, scope_digest, run_id):
        from psycopg.types.json import Jsonb

        with self.database.transaction(timeout_seconds=2) as connection:
            saved = connection.execute(
                "SELECT deadline, source_digest, spec, record FROM workflow_runs "
                "WHERE scope_digest = %s AND run_id = %s FOR UPDATE",
                (scope_digest, run_id),
            ).fetchone()
            if saved is None:
                raise LookupError("workflow_not_found")
            now = connection.execute("SELECT clock_timestamp()").fetchone()[0]
            row = WorkflowRow(run_id, *saved, now)
            # Avoid a database write on pure observations.
            original = deepcopy(row.record)
            yield row
            if row.record != original:
                connection.execute(
                    "UPDATE workflow_runs SET record = %s, spec = %s WHERE run_id = %s",
                    (Jsonb(row.record), Jsonb(row.spec) if row.spec is not None else None, run_id),
                )
