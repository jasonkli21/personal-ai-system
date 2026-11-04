"""E1 host lease tests; the fixture is not a deployed issuer or source registry."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    RequestScope,
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.evaluation.episode_candidates import SCOPE, example
from personal_ai.memory.episode_repository import InMemoryEpisodeRepository
from personal_ai.memory.episode_service import EpisodeEvidence, EpisodeService
from personal_ai.memory.knowledge import ProjectSnapshot


@pytest.fixture
def runtime():
    now = datetime.now(UTC)
    scope = RequestScope(
        owner_id="owner",
        acting_user_id="issuer|subject",
        application_id="reader",
        workspace_id="workspace",
        request_id="request",
    )
    principal = AuthenticatedPrincipal(
        "issuer",
        "subject",
        "owner",
        None,
        1,
        True,
        audience="audience",
        authorized_party="client",
        expires_at=int((now + timedelta(hours=1)).timestamp()),
    )
    project = ProjectSnapshot(
        project_id="project", revision="one", branch="main", permission_version="one"
    )
    spec, receipt = example(2)
    evidence = EpisodeEvidence(
        original_spec=canonical_bytes(spec),
        receipt_envelope=canonical_bytes(receipt),
        scope_digest=SCOPE,
        project=project,
        observed_at=now,
        expires_at=now + timedelta(days=1),
        classification="synthetic_public",
    )

    class Authority:
        active = True

        def __init__(self):
            self.current_project = project

        @contextmanager
        def lease(self, bound, project_id):
            if bound != scope or project_id != "project":
                raise PermissionError
            yield

        def project(self, bound, project_id):
            if bound != scope or project_id != "project":
                raise PermissionError
            return self.current_project

        def resolve(self, bound, project_id, run_id):
            if not self.active or run_id != UUID(int=2):
                raise PermissionError
            return evidence

        def current(self, bound, current_project, record):
            return self.active and current_project == project

    authority, repository = Authority(), InMemoryEpisodeRepository()
    service = EpisodeService(
        SimpleNamespace(memory_enabled=True, app_environment="test"),
        repository,
        authority,
        capture=True,
        selection=True,
        profile="synthetic_local",
        clock=lambda: now,
    )
    a, b = bind_request_scope(scope), bind_verified_principal(principal)
    try:
        yield SimpleNamespace(
            service=service,
            authority=authority,
            repository=repository,
            now=now,
            scope=scope,
            principal=principal,
            run_id=UUID(int=2),
        )
    finally:
        reset_request_scope(a)
        reset_verified_principal(b)


def test_capture_search_fetch_forget_and_replay(runtime):
    rt = runtime
    assert rt.service.capture("project", rt.run_id).status == "saved"
    found = rt.service.read("project", limit=1)
    assert found.status == "found" and found.truncated
    identity = found.items[0].candidate.id
    assert rt.service.read("project", episode_id=identity).items == found.items
    assert rt.service.forget("project", identity).status == "forgotten"
    assert rt.service.forget("project", identity).status == "forgotten"
    assert rt.service.capture("project", rt.run_id).status == "replayed"
    assert rt.service.read("project", episode_id=identity).status == "denied"
    assert all(str(identity) not in b["records"] for b in rt.repository.buckets.values())


def test_source_withdrawal_erases_projection_without_resurrection(runtime):
    rt = runtime
    rt.service.capture("project", rt.run_id)
    rt.authority.active = False
    assert not rt.service.read("project").items
    assert rt.service.purge("project").status == "forgotten"
    rt.authority.active = True
    assert rt.service.capture("project", rt.run_id).status == "replayed"
    assert not rt.service.read("project").items
    assert all(not b["records"] and b["receipts"] for b in rt.repository.buckets.values())


def test_expiry_and_branch_revision_are_hard_filters(runtime):
    rt = runtime
    rt.service.capture("project", rt.run_id)
    rt.authority.current_project = rt.authority.current_project.model_copy(
        update={"branch": "other"}
    )
    assert not rt.service.read("project").items
    rt.service.clock = lambda: rt.now + timedelta(days=2)
    assert not rt.service.read("project").items


@pytest.mark.parametrize(
    "change",
    [
        {"owner_id": "foreign"},
        {"application_id": "other"},
        {"workspace_id": "other"},
        {"acting_user_id": None},
        {"acting_user_id": "issuer|other"},
    ],
)
def test_foreign_scope_guesses_are_denied(runtime, change):
    rt = runtime
    rt.service.capture("project", rt.run_id)
    identity = rt.service.read("project").items[0].candidate.id
    token = bind_request_scope(rt.scope.model_copy(update=change))
    try:
        assert rt.service.read("project", episode_id=identity).status == "denied"
        assert rt.service.forget("project", identity).status == "denied"
    finally:
        reset_request_scope(token)


def test_wrong_client_has_separate_namespace(runtime):
    rt = runtime
    rt.service.capture("project", rt.run_id)
    from dataclasses import replace

    token = bind_verified_principal(replace(rt.principal, authorized_party="other"))
    try:
        assert not rt.service.read("project").items
    finally:
        reset_verified_principal(token)


@pytest.mark.parametrize(
    "attribute,value", [("capture_enabled", False), ("profile", "production"), ("authority", None)]
)
def test_capture_profiles_fail_closed(runtime, attribute, value):
    setattr(runtime.service, attribute, value)
    assert runtime.service.capture("project", runtime.run_id).status in {"disabled", "denied"}
    assert not runtime.repository.buckets


def test_repository_rolls_back_before_commit(runtime):
    repo = runtime.repository
    with pytest.raises(RuntimeError), repo.locked("owner", "namespace") as bucket:
        bucket["receipts"]["key"] = "digest"
        raise RuntimeError("crash before commit")
    assert not repo.buckets


def test_lost_ack_reconciles_original_run_without_second_capture(runtime):
    rt = runtime
    original = rt.repository.locked
    crash = True

    @contextmanager
    def lost_ack(*args):
        nonlocal crash
        with original(*args) as bucket:
            yield bucket
        if crash:
            crash = False
            raise RuntimeError("lost ack after commit")

    rt.repository.locked = lost_ack
    assert rt.service.capture("project", rt.run_id).status == "unavailable"
    assert rt.service.capture("project", rt.run_id).status == "replayed"
    assert len(rt.service.read("project").items) == 2


def test_retained_capacity_denies_new_capture_without_pruning(runtime):
    rt = runtime
    assert rt.service.capture("project", rt.run_id).status == "saved"
    bucket = next(iter(rt.repository.buckets.values()))
    bucket["receipts"].pop(str(rt.run_id))
    bucket["receipts"].update({str(i): "retained" for i in range(128)})
    assert rt.service.capture("project", rt.run_id).status == "capacity"
    assert len(next(iter(rt.repository.buckets.values()))["receipts"]) == 128


def test_unknown_project_and_guess_do_not_allocate_storage(runtime):
    rt = runtime
    assert rt.service.read("foreign", episode_id=UUID(int=999)).status == "denied"
    assert rt.service.read("project", episode_id=UUID(int=999)).status == "denied"
    assert not rt.repository.buckets


def test_disabling_capture_and_selection_keeps_explicit_erasure_available(runtime):
    rt = runtime
    rt.service.capture("project", rt.run_id)
    identity = rt.service.read("project").items[0].candidate.id
    rt.service.capture_enabled = rt.service.selection_enabled = False
    assert rt.service.read("project").status == "disabled"
    assert rt.service.forget("project", identity).status == "forgotten"
