"""Read-disabled projection tests; maintenance fixtures are not an owner issuer."""

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
from personal_ai.memory.episode_service import EpisodeRecord, EpisodeService, fingerprint
from personal_ai.memory.episodes import assess_terminal_steps
from personal_ai.memory.knowledge import ProjectSnapshot
from personal_ai.memory.lifecycle.contracts import MemoryLifecycleState


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
    class Authority:
        def __init__(self):
            self.current_project = project

        def project(self, bound, project_id):
            if bound != scope or project_id != "project":
                raise PermissionError
            return self.current_project

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


def seed_episode(rt):
    spec, receipt = example(2)
    candidates = assess_terminal_steps(
        canonical_bytes(spec), canonical_bytes(receipt), expected_scope_digest=SCOPE
    ).candidates
    with rt.service.guard("project", maintenance=True) as (scope, _, bucket, _check):
        for candidate in candidates:
            key = str(candidate.id)
            record = EpisodeRecord(
                candidate=candidate,
                project_digest=fingerprint(rt.authority.current_project.model_dump()),
                observed_at=rt.now,
                expires_at=rt.now + timedelta(days=1),
            )
            bucket["records"][key] = record.model_dump(mode="json")
            bucket["states"][key] = MemoryLifecycleState(
                owner_id=scope.owner_id,
                memory_id=candidate.id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                scope_version=2,
            ).model_dump(mode="json")
        bucket["receipts"][str(rt.run_id)] = "a" * 64
    return candidates


def test_capture_and_selection_stay_disabled_even_with_synthetic_options(runtime):
    rt = runtime
    assert rt.service.capture("project", rt.run_id).status == "disabled"
    assert rt.service.read("project").status == "disabled"
    assert not rt.repository.buckets


def test_authenticated_forget_works_when_project_is_unresolvable(runtime):
    rt = runtime
    candidates = seed_episode(rt)
    rt.authority.project = lambda *_: (_ for _ in ()).throw(LookupError("deleted"))
    assert rt.service.forget("project", candidates[0].id).status == "forgotten"
    bucket = next(iter(rt.repository.buckets.values()))
    assert str(candidates[0].id) not in bucket["records"]
    assert bucket["states"][str(candidates[0].id)]["retrieval_status"] == "forgotten"
    assert bucket["receipts"]


def test_authenticated_purge_without_project_lookup_tombstones_and_erases(runtime):
    rt = runtime
    candidates = seed_episode(rt)
    rt.authority.project = lambda *_: (_ for _ in ()).throw(LookupError("deleted"))
    assert rt.service.purge("project").status == "forgotten"
    bucket = next(iter(rt.repository.buckets.values()))
    assert not bucket["records"]
    assert all(bucket["states"][str(c.id)]["retrieval_status"] == "forgotten" for c in candidates)
    assert bucket["receipts"]


def test_authenticated_forget_remains_available_when_memory_is_disabled(runtime):
    rt = runtime
    candidate = seed_episode(rt)[0]
    rt.service.settings.memory_enabled = False
    assert rt.service.forget("project", candidate.id).status == "forgotten"


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
def test_foreign_scope_cannot_erase_another_namespace(runtime, change):
    rt = runtime
    candidates = seed_episode(rt)
    token = bind_request_scope(rt.scope.model_copy(update=change))
    try:
        assert rt.service.forget("project", candidates[0].id).status == "denied"
    finally:
        reset_request_scope(token)


def test_wrong_client_has_separate_namespace(runtime):
    rt = runtime
    candidates = seed_episode(rt)
    from dataclasses import replace

    token = bind_verified_principal(replace(rt.principal, authorized_party="other"))
    try:
        assert rt.service.forget("project", candidates[0].id).status == "denied"
    finally:
        reset_verified_principal(token)


def test_wrong_project_identity_cannot_reach_or_erase_another_namespace(runtime):
    rt = runtime
    candidate = seed_episode(rt)[0]
    assert rt.service.forget("different-project", candidate.id).status == "denied"
    assert str(candidate.id) in next(iter(rt.repository.buckets.values()))["records"]


def test_capture_stays_disabled_if_host_flags_are_enabled(runtime):
    runtime.service.capture_enabled = True
    runtime.service.selection_enabled = True
    runtime.service.authority = None
    assert runtime.service.capture("project", runtime.run_id).status == "disabled"
    assert runtime.service.read("project").status == "disabled"
    assert not runtime.repository.buckets


def test_repository_rolls_back_before_commit(runtime):
    repo = runtime.repository
    with pytest.raises(RuntimeError), repo.locked("owner", "namespace") as bucket:
        bucket["receipts"]["key"] = "digest"
        raise RuntimeError("crash before commit")
    assert not repo.buckets


def test_unknown_project_and_guess_do_not_allocate_storage(runtime):
    rt = runtime
    assert rt.service.read("foreign", episode_id=UUID(int=999)).status == "disabled"
    assert rt.service.read("project", episode_id=UUID(int=999)).status == "disabled"
    assert not rt.repository.buckets


def test_disabling_capture_and_selection_keeps_explicit_erasure_available(runtime):
    rt = runtime
    candidates = seed_episode(rt)
    identity = candidates[0].id
    rt.service.capture_enabled = rt.service.selection_enabled = False
    assert rt.service.read("project").status == "disabled"
    assert rt.service.forget("project", identity).status == "forgotten"
