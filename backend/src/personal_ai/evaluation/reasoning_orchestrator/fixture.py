"""Hermetic benchmark host over the canonical workflow row transitions."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from time import monotonic

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    RequestScope,
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.persistence.postgres.workflows import WorkflowRow
from personal_ai.reasoning.orchestration import HARD_LIMIT, ScopeCeilings
from personal_ai.retrieval.service import RetrievalService
from personal_ai.settings import Settings
from personal_ai.storage.errors import PersistenceConflict
from personal_ai.workflow.reasoning import ReasoningHost
from personal_ai.workflow.service import WorkflowService

CEILINGS = ScopeCeilings(
    application=HARD_LIMIT, workspace=HARD_LIMIT, user=HARD_LIMIT,
    operator_effort="max", application_effort="max", workspace_effort="max",
    user_effort="max", endpoint_effort="max", allow_direct_pin=True,
)


class FixtureStore:
    """Transaction double for evaluation. Native PostgreSQL evidence is separate."""

    def __init__(self):
        self.rows = {}
        self.intents = {}
        self.lock = RLock()

    def find_intent(self, scope, key, digest):
        with self.lock:
            found = self.intents.get((scope, key))
            if found is None:
                return None
            run_id, previous = found
            if previous != digest:
                raise PersistenceConflict("workflow_intent_conflict")
            return run_id

    def submit(self, scope, plan, source, *, monotonic_deadline):
        digest = plan.intent_digest(scope)
        with self.lock:
            existing = self.find_intent(scope, plan.original_key, digest)
            if existing is not None:
                return existing
            left = int((monotonic_deadline - monotonic()) * 1000)
            if left <= 0:
                raise TimeoutError("workflow_submission_deadline")
            row = WorkflowRow.new(plan, source, datetime.now(UTC), deadline_ms=left)
            self.rows[(scope, row.run_id)] = row
            self.intents[(scope, plan.original_key)] = (row.run_id, digest)
            return row.run_id

    @contextmanager
    def locked(self, scope, run_id):
        with self.lock:
            try:
                row = deepcopy(self.rows[(scope, run_id)])
            except KeyError:
                raise LookupError("workflow_not_found") from None
            row.now = datetime.now(UTC)
            yield row
            self.rows[(scope, run_id)] = row


@contextmanager
def synthetic_service(fixture, *, store=None, enabled=True, ceilings=CEILINGS, authority=lambda: None):
    principal = AuthenticatedPrincipal(
        "https://accounts.google.com", "benchmark-actor", "synthetic-owner", None, 1, True,
        audience="workflow-fixture", authorized_party="workflow-fixture",
        expires_at=int(datetime.now(UTC).timestamp()) + 3600,
    )
    scope = RequestScope(
        owner_id=principal.owner_id, acting_user_id=f"{principal.issuer}|{principal.subject}",
        application_id="personal_ai", request_id="workflow-fixture",
    )
    registry = default_application_registry()
    context = ApplicationContextRequest(scope=scope, definition=registry.registration("personal_ai").definition)
    settings = Settings(
        _env_file=None, app_environment="test", ai_provider="fake", ai_model="unused",
        inference_profile="offline_fake", inference_cost_mode="offline_fake",
    )
    service = WorkflowService(
        store if store is not None else FixtureStore(),
        RetrievalService(settings, scope, None, request_authority=authority),
        lambda: registry, enabled=enabled, reasoning_host=ReasoningHost(context, ceilings, fixture),
    )
    bound_principal = bind_verified_principal(principal)
    bound_scope = bind_request_scope(scope)
    try:
        yield service
    finally:
        reset_request_scope(bound_scope)
        reset_verified_principal(bound_principal)
