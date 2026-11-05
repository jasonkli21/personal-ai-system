"""Single-row workflow authority. Every transition and its receipt commit together."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from time import monotonic
from uuid import uuid4

from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.contracts.reasoning_workflow import ReasoningProgress
from personal_ai.contracts.workflow import TERMINAL, RunProgress
from personal_ai.reasoning.grounded_receipts import GroundedProgress
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
        if self.reasoning:
            reason = {
                "operator_reconciliation_required": "uncertain_effect",
                "deadline": "budget_exhausted",
                "claim_budget": "budget_exhausted",
                "step_unavailable": "internal_failure",
            }.get(reason, reason)
            if state == "canceled":
                reason = "cancelled"
            self.record.pop("checkpoints", None)
        if self.grounded:
            reason = {
                "operator_reconciliation_required": "uncertain_effect",
                "deadline": "budget_exhausted",
                "claim_budget": "budget_exhausted",
                "step_unavailable": "internal_failure",
            }.get(reason, reason)
            if state == "canceled":
                reason = "cancelled"
        self.spec = None
        self.record.update(state=state, reason=reason, fence=None, lease=None)
        self.event(state)

    def expire(self):
        row = self.record
        if row["state"] in TERMINAL:
            return
        if (
            row["lease"] is not None and self.now.timestamp() < row["lease"]
            and not ((self.reasoning or self.grounded) and self.now >= self.deadline)
        ):
            return
        attempt = self.pending
        if attempt is not None:
            if attempt["state"] == "dispatched":
                binding = attempt.get("operation_binding") or {}
                if self.reasoning and binding.get("tool_id") == "reasoning.verify.v1":
                    # Registered verifiers are deterministic, local predicates. Charge
                    # the call conservatively and allow only the normal fenced recovery.
                    attempt["resources"]["verifier_calls"] = 1
                    attempt["state"] = "failed"
                    self.event("step_failed", attempt["attempt_id"])
                    verifier_failed = True
                elif self.grounded and binding.get("tool_id") == "reasoning.grounded.verify.v1":
                    # The call is a pure predicate, but its candidate only lived
                    # in the lost claim. Finish without reconstructing evidence.
                    attempt["state"] = "failed"
                    self.event("step_failed", attempt["attempt_id"])
                    self.terminal("canceled" if row["cancel_requested"] else "failed",
                                  "deadline" if self.now >= self.deadline else "ephemeral_state_lost")
                    return
                else:
                    attempt["state"] = "uncertain"
                    self.terminal("uncertain", "operator_reconciliation_required")
                    return
            else:
                verifier_failed = False
            if not verifier_failed:
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
    def reasoning(self):
        return self.record.get("reasoning")

    @property
    def grounded(self):
        return self.record.get("grounded")

    def reserve(self, step, operation_binding, *, resources=None):
        if self.pending is not None:
            raise ValueError("workflow_attempt_pending")
        attempt_id = str(uuid4())
        attempt = {
            "attempt_id": attempt_id, "step": step, "state": "reserved",
            "operation_binding": operation_binding,
        }
        if resources is not None:
            attempt["resources"] = resources
        self.record["attempts"].append(attempt)
        self.event("reserved", attempt_id)
        return attempt_id

    def succeed(self, attempt_id):
        if self.pending is None or self.pending["state"] != "dispatched" or (
            self.pending["attempt_id"] != attempt_id
        ):
            raise ValueError("workflow_attempt_not_dispatched")
        self.pending["state"] = "succeeded"
        self.event("step_succeeded", attempt_id)

    @property
    def pending(self):
        attempts = self.record["attempts"]
        if attempts and attempts[-1]["state"] in {"reserved", "dispatched"}:
            return attempts[-1]
        return None

    def dispatch(self, attempt_id, operation_binding):
        attempt = self.pending
        if (
            attempt is None
            or attempt["attempt_id"] != attempt_id
            or attempt["state"] != "reserved"
            or attempt.get("operation_binding") != operation_binding
        ):
            raise ValueError("workflow_attempt_binding_changed")
        attempt["state"] = "dispatched"
        if self.reasoning:
            resources = attempt["resources"]
            if operation_binding["tool_id"] == "reasoning.inference.v1":
                resources["physical_attempts"] = None
            else:
                # Dispatching a local predicate consumes its finite budget even if
                # the process dies before recording the deterministic result.
                resources["verifier_calls"] = 1
        if self.grounded:
            attempt["resources"]["observed_calls"] = None
            if operation_binding["tool_id"] == "reasoning.grounded.verify.v1":
                attempt["resources"]["verifier_calls_charged"] = 1
        self.event("dispatched", attempt_id)

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
        facts = {
            "run_id": self.run_id,
            "state": self.record["state"],
            "cancel_requested": self.record["cancel_requested"],
            "reason": self.record["reason"],
            "cursor": self.record["cursor"],
            "gap": cursor < events[0]["sequence"] - 1,
            "events": tuple(event for event in events if event["sequence"] > cursor),
            "attempts": self.record["attempts"],
        }
        if self.grounded:
            state = self.record["state"]
            return GroundedProgress(
                **facts, **self.grounded, source_digest=self.source_digest,
                plan_digest=self.record["plan_digest"], verification=self.record.get("verification"),
                outcome=(
                    "complete" if state == "succeeded" else
                    self.record.get("outcome", "unavailable") if state in TERMINAL else "pending"
                ),
            )
        if not self.reasoning:
            return RunProgress(**facts)
        state = self.record["state"]
        return ReasoningProgress(
            **facts, **self.reasoning, plan_digest=self.record["plan_digest"],
            phase="terminal" if state in TERMINAL else self.record.get("phase", "planning"),
            outcome=(
                "complete" if state == "succeeded" else
                self.record.get("outcome", "unavailable") if state in TERMINAL else "pending"
            ),
        )

    @classmethod
    def new(cls, spec, source_digest, now, *, deadline_ms):
        record = {
            "state": "queued", "fence": None, "lease": None, "claims": 0,
            "cursor": 0, "events": [], "attempts": [], "cancel_requested": False, "reason": None,
        }
        if spec.schema_version == "reasoning-run-v1":
            record["reasoning"] = spec.model_dump(include={
                "policy", "catalog", "strategy", "strategy_version", "selection", "requested_effort", "effort",
            })
            record["plan_digest"] = sha256(canonical_bytes(spec.model_dump(mode="json"))).hexdigest()
            record["checkpoints"] = []
        if spec.schema_version == "reasoning-grounded-plan-v1":
            record["grounded"] = spec.model_dump(include={
                "source_policy", "strategy_version", "requested_effort", "effort",
            })
            record["plan_digest"] = sha256(canonical_bytes(spec.model_dump(mode="json"))).hexdigest()
        row = cls(
            uuid4(), now + timedelta(milliseconds=deadline_ms), source_digest,
            spec.model_dump(mode="json"), record, now,
        )
        row.event("queued")
        return row


class PostgresWorkflowStore:
    def __init__(self, database):
        self.database = database

    def find(self, scope_digest, spec):
        return self.find_intent(scope_digest, spec.original_key, spec.intent_digest(scope_digest))

    def find_intent(self, scope_digest, original_key, digest):
        with self.database.transaction(timeout_seconds=2) as connection:
            return self._find(connection, scope_digest, original_key, digest)

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

    def submit(self, scope_digest, spec, source_digest, *, monotonic_deadline=None):
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
            deadline_ms = spec.deadline_ms
            if monotonic_deadline is not None:
                deadline_ms = min(deadline_ms, int((monotonic_deadline - monotonic()) * 1000))
                if deadline_ms <= 0:
                    raise TimeoutError("workflow_submission_deadline")
            row = WorkflowRow.new(spec, source_digest, now, deadline_ms=deadline_ms)
            connection.execute(
                "INSERT INTO workflow_runs "
                "(run_id, scope_digest, original_key, intent_digest, source_digest, "
                "spec, deadline, record) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    row.run_id,
                    scope_digest,
                    spec.original_key,
                    digest,
                    source_digest,
                    Jsonb(row.spec),
                    row.deadline,
                    Jsonb(row.record),
                ),
            )
            return row.run_id

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

    def terminal_evidence(self, scope_digest, run_id):
        """Minimal canonical receipt read; no spec, query, result or event-tail copy."""
        with self.database.transaction(timeout_seconds=2) as connection:
            row = connection.execute(
                "SELECT original_key,intent_digest,source_digest,record FROM workflow_runs "
                "WHERE scope_digest=%s AND run_id=%s",
                (scope_digest, run_id),
            ).fetchone()
            if row is None:
                raise LookupError("workflow_not_found")
            if row[3].get("reasoning") or row[3].get("grounded"):
                raise LookupError("workflow_episode_unavailable")
            from personal_ai.memory.episodes import TerminalReceiptEnvelope

            return (
                TerminalReceiptEnvelope(
                    scope_digest=scope_digest,
                    run_id=run_id,
                    original_key=row[0],
                    intent_digest=row[1],
                    source_digest=row[2],
                    state=row[3]["state"],
                    cancel_requested=row[3]["cancel_requested"],
                    attempts=row[3]["attempts"],
                )
                .model_dump_json()
                .encode()
            )
