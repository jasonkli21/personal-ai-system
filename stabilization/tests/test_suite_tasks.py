"""Task behavior and security cases; host/lifecycle setup lives in task_harness."""

import base64
import json
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from task_harness import (
    flow as flow,  # noqa: PLC0414 - pytest discovers imported fixtures
)


def start(flow):
    identifier = uuid4()
    choice = {
        "command_id": str(identifier),
        "period": "2026-10",
        "expected_budget_revision": 1,
        "context_choice_id": flow.choice_id,
        "shopping_project_id": str(flow.project_id),
        "expected_project_revision": 1,
    }
    headers = {"Origin": "https://testserver"}
    result = flow.source.post(
        "/v1/finance/shopping-tasks/commands", json=choice, headers=headers
    )
    assert result.status_code == 201, result.text
    base = f"/v1/finance/shopping-tasks/commands/{identifier}"
    result = flow.source.post(base + "/submit", headers=headers)
    assert result.status_code == 200, result.text
    replay = flow.source.post(base + "/submit", headers=headers)
    assert replay.status_code == 200 and replay.json() == result.json(), replay.text
    result = flow.source.post(base + "/validate", headers=headers)
    assert result.status_code == 200 and result.json()["state"] == "validated", (
        result.text
    )
    confirm = {"confirmation_id": str(uuid4()), "binding": result.json()["binding"]}
    result = flow.source.post(base + "/confirm", json=confirm, headers=headers)
    assert result.status_code == 200 and result.json()["state"] == "confirmed", (
        result.text
    )
    return base, confirm, headers


def test_source_restart_recovers_the_original_confirmation_identity(flow):
    base, confirmation, headers = start(flow)
    observed = flow.source.get(base).json()
    assert observed["state"] == "confirmed"
    assert observed["confirmation_id"] == confirmation["confirmation_id"]
    # A restarted source UI has no local confirmation ID. Server status is its
    # authoritative recovery path; a replacement confirmation must not apply.
    recovered = {
        "confirmation_id": observed["confirmation_id"],
        "binding": observed["binding"],
    }
    applied = flow.source.post(base + "/apply", json=recovered, headers=headers)
    assert applied.status_code == 200 and applied.json()["state"] == "applied"


def test_populated_task_recovery_tables_refuse_destructive_rollback(flow):
    base, confirmation, headers = start(flow)
    assert (
        flow.source.post(base + "/apply", json=confirmation, headers=headers).json()[
            "state"
        ]
        == "applied"
    )
    projects = Path(__file__).resolve().parents[3]
    for name, directory, scripts, revision in (
        (
            "finance",
            projects / "personal-finance/services/api",
            "alembic",
            "0020_verified_session_auth_time",
        ),
        (
            "shopping",
            projects / "shopping-assistant/apps/api",
            "migrations",
            "p9_conversation_generation_leases",
        ),
    ):
        config = Config(str(directory / "alembic.ini"))
        config.set_main_option("script_location", str(directory / scripts))
        with flow.engines[name].begin() as connection:
            config.attributes["connection"] = connection
            with pytest.raises(RuntimeError, match="Cannot discard retained"):
                command.downgrade(config, revision)
    with Session(flow.engines["shopping"]) as session:
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 1


@pytest.mark.parametrize(
    "invalid", ["unlinked", "disabled", "revoked", "unknown_revocation", "wrong_uid"]
)
def test_destination_current_link_and_revocation_are_rechecked(
    flow, monkeypatch, invalid
):
    base, confirmation, headers = start(flow)
    record = SimpleNamespace(
        uid="wrong-owner" if invalid == "wrong_uid" else "synthetic-firebase-user",
        disabled=invalid == "disabled",
        tokens_valid_after_timestamp=(int(time.time()) + 60) * 1000
        if invalid == "revoked"
        else None
        if invalid == "unknown_revocation"
        else 0,
        provider_data=[]
        if invalid == "unlinked"
        else [SimpleNamespace(provider_id="google.com", uid="synthetic-user")],
    )
    monkeypatch.setattr("firebase_admin.auth.get_user", lambda *args, **kwargs: record)
    result = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert result.status_code == 403, result.text
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 0


@pytest.mark.parametrize("flow", ["finance", ("finance", "https")], indirect=True)
def test_budget_flow_commits_once_replays_and_recovers_lost_ack(flow):
    base, confirmation, headers = start(flow)
    flow.lose_ack["enabled"] = flow.network is None
    first = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert first.status_code == 200 and first.json()["state"] == (
        "uncertain" if flow.network is None else "applied"
    ), first.text
    recovered = flow.source.post(base + "/reconcile", headers=headers)
    assert recovered.status_code == 200 and recovered.json()["state"] == "applied", (
        recovered.text
    )
    assert (
        flow.source.post(base + "/apply", json=confirmation, headers=headers).json()
        == recovered.json()
    )
    with Session(flow.engines["shopping"]) as session:
        project = session.get(flow.ShoppingProject, flow.project_id)
        assert project.revision == 2 and str(project.budget_target) == "50.00"
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 1
    assert flow.network is not None or (
        flow.sent.count(("shopping", "/v1/integrations/personal-ai/tasks", "execute"))
        == 1
    )
    assert "acting_user_id" not in json.dumps(recovered.json())
    assert "source_dependencies" not in json.dumps(recovered.json())


def test_revoked_source_consent_prevents_effect(flow):
    base, confirmation, headers = start(flow)
    changed = flow.source.put(
        "/v1/finance/discretionary-budgets/2026-10",
        headers=headers,
        json={
            "expected_revision": 1,
            "amount": "50.00",
            "currency": "USD",
            "share_with_shopping": False,
        },
    )
    assert changed.status_code == 200
    result = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert result.status_code in {403, 409}, result.text
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 0
    assert not any(action == "execute" for _, _, action in flow.sent)


def test_revoked_grant_prevents_reserved_effect(flow):
    base, confirmation, headers = start(flow)
    flow.authority.revoke(
        flow.principal,
        flow.grant.grant_id,
        expected_revision=flow.grant.revision,
        expected_issuance_id=flow.grant.issuance_id,
    )
    result = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert result.status_code in {403, 409}, result.text
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 0
    assert not any(action == "execute" for _, _, action in flow.sent)


def test_grant_revoked_after_reservation_is_rejected_by_destination_callback(flow):
    base, confirmation, headers = start(flow)

    def revoke_before_receiver():
        flow.authority.revoke(
            flow.principal,
            flow.grant.grant_id,
            expected_revision=flow.grant.revision,
            expected_issuance_id=flow.grant.issuance_id,
        )

    flow.before_execute["callback"] = revoke_before_receiver
    result = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert result.status_code == 200 and result.json()["state"] == "rejected", (
        result.text
    )
    assert any(action == "execute" for _, _, action in flow.sent)
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1


def test_source_revision_change_requires_new_user_choice(flow):
    base, confirmation, headers = start(flow)
    result = flow.source.put(
        "/v1/finance/discretionary-budgets/2026-10",
        headers=headers,
        json={
            "expected_revision": 1,
            "amount": "60.00",
            "currency": "USD",
            "share_with_shopping": True,
        },
    )
    assert result.status_code == 200
    result = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert result.status_code in {403, 409}, result.text
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 0


def test_stale_destination_preserves_normal_domain_write(flow):
    from shopping.projects.schemas import ProjectPatch
    from shopping.projects.service import patch_project

    base, confirmation, headers = start(flow)
    with Session(flow.engines["shopping"]) as session:
        patch_project(
            session,
            flow.owner,
            flow.project_id,
            ProjectPatch(
                expected_version=1, budget_target="25.00", budget_currency="USD"
            ),
        )

    result = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert result.status_code == 200 and result.json()["state"] == "rejected", (
        result.text
    )
    assert result.json()["outcome_code"] == "revision_conflict"
    with Session(flow.engines["shopping"]) as session:
        project = session.get(flow.ShoppingProject, flow.project_id)
        assert project.revision == 2 and str(project.budget_target) == "25.00"
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 1


def test_unavailable_destination_preserves_uncertainty_and_never_resends(flow):
    base, confirmation, headers = start(flow)
    flow.unavailable["enabled"] = True
    first = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert first.status_code == 200 and first.json()["state"] == "uncertain", first.text
    repeated = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert repeated.status_code == 200 and repeated.json()["state"] == "uncertain", (
        repeated.text
    )
    assert repeated.json()["proposal_id"] == first.json()["proposal_id"]
    assert repeated.json()["confirmation_id"] == first.json()["confirmation_id"]
    flow.unavailable["enabled"] = False
    observed = flow.source.post(base + "/reconcile", headers=headers)
    assert observed.status_code == 200 and observed.json()["state"] == "uncertain", (
        observed.text
    )
    assert observed.json()["outcome_code"] == "no_receipt"
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 0
    assert (
        flow.sent.count(("shopping", "/v1/integrations/personal-ai/tasks", "execute"))
        == 1
    )


@pytest.mark.parametrize(
    "invalid",
    [
        "issuer",
        "audience",
        "key",
        "key_id",
        "subject",
        "expired",
        "stale_auth",
        "workspace",
        "destination",
        "contract",
    ],
)
def test_invalid_source_delegation_fails_before_native_effect(flow, invalid):
    from personal_ai.contracts.delegated_tasks import (
        control_request_binding,
        sign_delegated_user,
    )

    task = flow.source.app.state.settings.task_settings
    key = Ed25519PrivateKey.from_private_bytes(
        base64.urlsafe_b64decode(
            task.private_key.get_secret_value()
            + "=" * (-len(task.private_key.get_secret_value()) % 4)
        )
    )
    now = int(time.time())
    payload = {"source_application_id": "finance", "command_id": str(uuid4())}
    destination = "travel" if invalid == "destination" else "shopping"
    workspace = str(uuid4()) if invalid == "workspace" else None
    if invalid == "contract":
        payload["schema_version"] = "unsupported-task-command-v999"
    frame = control_request_binding(
        "POST",
        "/v1/mutations/commands",
        destination,
        workspace,
        payload,
        origin_application_id="finance",
    )
    assertion = sign_delegated_user(
        user_issuer="https://accounts.google.com",
        user_subject="different-user" if invalid == "subject" else "synthetic-user",
        authenticated_at=now - 120 if invalid == "expired" else now,
        private_key=Ed25519PrivateKey.generate() if invalid == "key" else key,
        issuer="wrong-issuer" if invalid == "issuer" else task.issuer,
        audience="https://wrong.invalid" if invalid == "audience" else task.audience,
        key_id="wrong-key" if invalid == "key_id" else task.key_id,
        request_body=frame,
        now=now - 120 if invalid == "expired" else now,
    )
    if invalid == "stale_auth":
        header, claims, _signature = assertion.split(".")
        body = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
        body["auth_time"] = now - 600
        claims = (
            base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )
        signing = f"{header}.{claims}"
        assertion = (
            signing
            + "."
            + base64.urlsafe_b64encode(key.sign(signing.encode())).decode().rstrip("=")
        )
    headers = {
        "Authorization": "Bearer synthetic:" + task.service_account,
        "X-Origin-Application-ID": "finance",
        "X-Application-ID": destination,
        "X-User-Delegation": assertion,
    }
    if workspace:
        headers["X-Workspace-ID"] = workspace
    response = flow.root.post("/v1/mutations/commands", json=payload, headers=headers)
    assert response.status_code in {400, 401, 403, 422}, response.text
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 0
    assert not any(action == "execute" for _, _, action in flow.sent)


def test_confirmation_tamper_never_dispatches(flow):
    base, confirmation, headers = start(flow)
    result = flow.source.post(
        base + "/apply", json=confirmation | {"binding": "0" * 64}, headers=headers
    )
    assert result.status_code == 409, result.text
    with Session(flow.engines["shopping"]) as session:
        assert session.get(flow.ShoppingProject, flow.project_id).revision == 1
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 0
    assert not any(action == "execute" for _, _, action in flow.sent)


def test_original_result_remains_observable_after_source_revocation(flow):
    base, confirmation, headers = start(flow)
    applied = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert applied.status_code == 200 and applied.json()["state"] == "applied", (
        applied.text
    )
    result = flow.source.put(
        "/v1/finance/discretionary-budgets/2026-10",
        headers=headers,
        json={
            "expected_revision": 1,
            "amount": "50.00",
            "currency": "USD",
            "share_with_shopping": False,
        },
    )
    assert result.status_code == 200
    observed = flow.source.get(base)
    assert observed.status_code == 200 and observed.json() == applied.json(), (
        observed.text
    )
    repeated = flow.source.post(base + "/submit", headers=headers)
    assert repeated.status_code == 200 and repeated.json() == applied.json(), (
        repeated.text
    )
    assert (
        flow.sent.count(("shopping", "/v1/integrations/personal-ai/tasks", "execute"))
        == 1
    )


def test_concurrent_source_command_submission_replays_one_record(flow):
    from concurrent.futures import ThreadPoolExecutor

    from app.db.models import DelegatedSourceCommand

    key = uuid4()
    body = {
        "command_id": str(key),
        "period": "2026-10",
        "expected_budget_revision": 1,
        "context_choice_id": flow.choice_id,
        "shopping_project_id": str(flow.project_id),
        "expected_project_revision": 1,
    }

    def submit(_):
        return flow.source.post(
            "/v1/finance/shopping-tasks/commands",
            json=body,
            headers={"Origin": "https://testserver"},
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert all(result.status_code == 201 for result in results), [
        result.text for result in results
    ]
    assert all(result.json() == results[0].json() for result in results)
    with Session(flow.engines["finance"]) as session:
        assert (
            session.scalar(select(func.count()).select_from(DelegatedSourceCommand))
            == 1
        )


@pytest.mark.parametrize(
    "flow",
    ["travel", "health", ("travel", "https"), ("health", "https")],
    indirect=True,
)
def test_context_note_flow_has_one_effect_and_recovers_lost_ack(flow):
    identifier = uuid4()
    headers = {"Origin": "https://testserver"}
    choice = dict(
        flow.host.choice,
        command_id=str(identifier),
        context_choice_id=flow.choice_id,
        shopping_project_id=str(flow.project_id),
        expected_project_revision=1,
    )
    created = flow.source.post(flow.prefix + "/commands", json=choice, headers=headers)
    assert created.status_code == 201, created.text
    assert "Private" not in json.dumps(created.json())
    base = flow.prefix + f"/commands/{identifier}"
    for action in ("submit", "validate"):
        result = flow.source.post(base + "/" + action, headers=headers)
        assert result.status_code == 200, result.text
    confirmation = {
        "confirmation_id": str(uuid4()),
        "binding": result.json()["binding"],
    }
    confirmed = flow.source.post(base + "/confirm", json=confirmation, headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    flow.lose_ack["enabled"] = flow.network is None
    applied = flow.source.post(base + "/apply", json=confirmation, headers=headers)
    assert applied.status_code == 200 and applied.json()["state"] == (
        "uncertain" if flow.network is None else "applied"
    ), applied.text
    recovered = flow.source.post(base + "/reconcile", headers=headers)
    assert recovered.status_code == 200 and recovered.json()["state"] == "applied", (
        recovered.text
    )
    assert (
        flow.source.post(base + "/submit", headers=headers).json() == recovered.json()
    )
    with Session(flow.engines["shopping"]) as session:
        project = session.get(flow.ShoppingProject, flow.project_id)
        assert project.revision == 2
        assert project.notes.count("User-authorized") == 1
        assert str(project.budget_target) == "10.00"
        assert session.scalar(select(func.count()).select_from(flow.Receipt)) == 1
    if flow.network is None:
        assert (
            flow.sent.count(
                ("shopping", "/v1/integrations/personal-ai/tasks", "execute")
            )
            == 1
        )
