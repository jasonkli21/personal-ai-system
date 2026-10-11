"""Protected local state and concurrency/crash-recovery tests."""

import base64
import hashlib
import json
import multiprocessing
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from personal_ai.llm.chatgpt.oauth import ISSUER, SCOPES, OAuthFailure, VerifiedTokens
from personal_ai.local_bridge.lifecycle import CredentialLifecycle
from personal_ai.local_bridge.store import (
    DispatchReceipt,
    LocalStoreError,
    ProtectedLocalStore,
    Registration,
)


class FakeOAuth:
    def __init__(self):
        self.calls = []
        self.subject = "synthetic-subject"
        self.scopes = tuple(SCOPES)
        self.expires_at = int(time.time()) + 3600
        self.refresh_error = None
        self.revoke_confirmed = True
        self.revoke_results = None

    def discovery(self):
        return {}

    def tokens(self, *, rotated=False):
        return VerifiedTokens(
            ISSUER,
            self.subject,
            "synthetic-access",
            "synthetic-new-refresh" if rotated else "synthetic-refresh",
            "synthetic-id-token",
            self.scopes,
            self.expires_at,
            0,
            "Synthetic Person",
            "person@example.test",
        )

    def exchange(self, **kwargs):
        self.calls.append(("exchange", kwargs))
        return self.tokens()

    def refresh(self, **kwargs):
        self.calls.append(("refresh", kwargs))
        time.sleep(0.02)
        if self.refresh_error:
            raise self.refresh_error
        self.expires_at = int(time.time()) + 3600
        return self.tokens(rotated=True)

    def revoke(self, **kwargs):
        self.calls.append(("revoke", kwargs))
        if self.revoke_results is not None:
            return self.revoke_results.pop(0)
        return self.revoke_confirmed


def connected_lifecycle(tmp_path):
    store = ProtectedLocalStore(tmp_path / "local-runtime")
    oauth = FakeOAuth()
    lifecycle = CredentialLifecycle(store, oauth)
    attempt_id, url = lifecycle.begin("http://127.0.0.1:54321/auth/callback")
    query = parse_qs(urlsplit(url).query)
    safe = lifecycle.complete(
        attempt_id,
        {
            "state": query["state"][0],
            "code": "synthetic-code",
            "client_id": "oaiapp_synthetic",
        },
    )
    return lifecycle, oauth, safe


def test_local_host_and_issued_registration_persist_but_are_absent_from_safe_state(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    assert safe.state == "connected" and safe.plan_permission
    assert safe.revision == 1
    output = str(asdict(safe))
    assert not any(
        secret in output
        for secret in (
            "synthetic-subject",
            "oaiapp_synthetic",
            "synthetic-access",
            "synthetic-refresh",
            "synthetic-id-token",
            "synthetic-code",
        )
    )
    store = ProtectedLocalStore(lifecycle.store.directory)
    with store.transaction() as tx:
        host = tx.state.host_id
    restarted = CredentialLifecycle(store, oauth)
    attempt, url = restarted.begin(
        "http://127.0.0.1:54322/auth/callback", connection_id=safe.connection_id
    )
    query = parse_qs(urlsplit(url).query)
    assert query["ext_agent_host_id"] == [host]
    assert query["client_id"] == ["oaiapp_synthetic"]
    assert "agent_name_hint" not in query
    assert "id_token_hint" not in query
    assert "synthetic-id-token" not in url
    assert (
        restarted.complete(attempt, {"state": query["state"][0], "code": "synthetic-code"}).revision
        == 2
    )


def test_pkce_state_nonce_are_fresh_and_callback_consumed_once(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    attempt, url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback", connection_id=safe.connection_id
    )
    query = parse_qs(urlsplit(url).query)
    assert query["nonce"][0] != oauth.calls[0][1]["nonce"]
    callback = {"state": query["state"][0], "code": "synthetic-code"}
    lifecycle.complete(attempt, callback)
    verifier = oauth.calls[-1][1]["verifier"]
    assert query["code_challenge"] == [
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    ]
    with pytest.raises(OAuthFailure, match="oauth_state_invalid"):
        lifecycle.complete(attempt, callback)


@pytest.mark.parametrize(
    "callback,code",
    [
        ({"state": "foreign", "code": "synthetic-code"}, "oauth_state_invalid"),
        ({"error": "access_denied"}, "oauth_consent_denied"),
        ({"client_id": "oaiapp_foreign", "code": "synthetic-code"}, "oauth_callback_invalid"),
    ],
)
def test_callback_mismatch_or_denial_keeps_existing_session(tmp_path, callback, code):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    attempt, url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback", connection_id=safe.connection_id
    )
    values = {"state": parse_qs(urlsplit(url).query)["state"][0], **callback}
    with pytest.raises(OAuthFailure, match=code):
        lifecycle.complete(attempt, values)
    assert lifecycle.connections() == (safe,)
    assert len(oauth.calls) == 1


def test_identity_mismatch_never_overwrites_selected_account(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    attempt, url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback", connection_id=safe.connection_id
    )
    oauth.subject = "different-account"
    with pytest.raises(OAuthFailure, match="oauth_account_mismatch"):
        lifecycle.complete(
            attempt, {"state": parse_qs(urlsplit(url).query)["state"][0], "code": "synthetic-code"}
        )
    assert lifecycle.connections() == (safe,)


def test_issued_client_retained_when_code_exchange_fails_without_claiming_identity(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    attempt, url = lifecycle.begin("http://127.0.0.1:54321/auth/callback")

    def invalid(**kwargs):
        raise OAuthFailure("invalid_grant")

    oauth.exchange = invalid
    with pytest.raises(OAuthFailure):
        lifecycle.complete(
            attempt,
            {
                "state": parse_qs(urlsplit(url).query)["state"][0],
                "code": "expired",
                "client_id": "oaiapp_another",
            },
        )
    with lifecycle.store.transaction() as tx:
        registrations = list(tx.state.registrations.values())
        assert registrations[-1].client_id == "oaiapp_another"
        assert registrations[-1].credentials is None and registrations[-1].subject is None
    assert lifecycle.connections()[0] == safe


def test_rotating_refresh_is_serialized_across_instances_and_atomically_replaces_set(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    with lifecycle.store.transaction() as tx:
        tx.state.registrations[safe.connection_id].credentials.expires_at = 1
        tx.save()
    second = CredentialLifecycle(ProtectedLocalStore(lifecycle.store.directory), oauth)
    with ThreadPoolExecutor(max_workers=2) as pool:
        snapshots = list(pool.map(lambda c: c.snapshot(safe.connection_id), [lifecycle, second]))
    assert len([c for c in oauth.calls if c[0] == "refresh"]) == 1
    assert snapshots[0] == snapshots[1]
    with lifecycle.store.transaction() as tx:
        registration = tx.state.registrations[safe.connection_id]
        assert registration.credentials.refresh_token == "synthetic-new-refresh"
        assert not registration.refresh_pending
        assert registration.revision == safe.revision  # Token rotation isn't an account change.


@pytest.mark.parametrize(
    "code,uncertain,cleared",
    [
        ("invalid_grant", False, True),
        ("refresh_token_reused", False, True),
        ("invalid_client", False, False),
        ("oauth_unavailable", False, False),
        ("oauth_unavailable", True, False),
    ],
)
def test_refresh_failure_distinguishes_revocation_temporary_and_uncertain(
    tmp_path, code, uncertain, cleared
):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    with lifecycle.store.transaction() as tx:
        tx.state.registrations[safe.connection_id].credentials.expires_at = 1
        tx.save()
    oauth.refresh_error = OAuthFailure(code, uncertain=uncertain)
    with pytest.raises(OAuthFailure):
        lifecycle.snapshot(safe.connection_id)
    with lifecycle.store.transaction() as tx:
        registration = tx.state.registrations[safe.connection_id]
        assert (registration.credentials is None) is cleared
        assert registration.refresh_pending is uncertain
        expected_state = (
            "reauth"
            if uncertain or cleared
            else "configuration_error"
            if code == "invalid_client"
            else "unavailable"
        )
        assert registration.state == expected_state
    if uncertain or cleared:
        with pytest.raises(OAuthFailure):
            lifecycle.snapshot(safe.connection_id)
        assert len([c for c in oauth.calls if c[0] == "refresh"]) == 1


def test_crash_during_rotation_requires_reauth_without_io(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    with lifecycle.store.transaction() as tx:
        tx.state.registrations[safe.connection_id].refresh_pending = True
        tx.save()
    restarted = CredentialLifecycle(ProtectedLocalStore(lifecycle.store.directory), oauth)
    with pytest.raises(OAuthFailure, match="bridge_refresh_uncertain"):
        restarted.snapshot(safe.connection_id)
    assert not [c for c in oauth.calls if c[0] == "refresh"]


def test_failed_post_rotation_persistence_keeps_durable_uncertainty_fence(tmp_path, monkeypatch):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    with lifecycle.store.transaction() as tx:
        tx.state.registrations[safe.connection_id].credentials.expires_at = 1
        tx.save()
    original = lifecycle.store._write

    def fail_latest_credentials(state):
        credentials = state.registrations[safe.connection_id].credentials
        if credentials and credentials.refresh_token == "synthetic-new-refresh":
            raise LocalStoreError("local_store_unavailable")
        original(state)

    monkeypatch.setattr(lifecycle.store, "_write", fail_latest_credentials)
    with pytest.raises(LocalStoreError):
        lifecycle.snapshot(safe.connection_id)
    restarted = CredentialLifecycle(ProtectedLocalStore(lifecycle.store.directory), oauth)
    with pytest.raises(OAuthFailure, match="bridge_refresh_uncertain"):
        restarted.snapshot(safe.connection_id)
    assert len([call for call in oauth.calls if call[0] == "refresh"]) == 1


def test_receipt_capacity_failure_does_not_evict_uncertain_sends(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    now = int(time.time())
    with lifecycle.store.transaction() as tx:
        tx.state.receipts = {
            f"{index:064x}": DispatchReceipt(
                fingerprint="a" * 64,
                status="send_started",
                connection_id=safe.connection_id,
                connection_revision=safe.revision,
                created_at=now,
                updated_at=now,
                proof_expires_at=now + 60,
            )
            for index in range(4096)
        }
        tx.save()
    with pytest.raises(LocalStoreError, match="local_store_capacity"):
        lifecycle.store.claim(
            "f" * 64, "b" * 64, safe.connection_id, safe.revision, now + 60, now=now
        )
    with lifecycle.store.transaction() as tx:
        assert len(tx.state.receipts) == 4096
        assert tx.state.receipts["0" * 64].status == "send_started"


def test_pre_send_claim_is_recoverable_after_process_crash_without_reopening_sends(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    identity, fingerprint = "a" * 64, "b" * 64
    token = lifecycle.store.claim(
        identity, fingerprint, safe.connection_id, safe.revision, int(time.time()) + 60
    )
    with lifecycle.store._claim_fds_lock:
        descriptor = lifecycle.store._claim_fds[token]
    # Simulate process exit: the OS lock is released, while the durable record remains.
    lifecycle.store._release_pre_send(descriptor, token)
    restarted = ProtectedLocalStore(lifecycle.store.directory)
    next_token = restarted.claim(
        identity, fingerprint, safe.connection_id, safe.revision, int(time.time()) + 60
    )
    restarted.mark_send_started(
        identity,
        fingerprint,
        safe.connection_id,
        safe.revision,
        next_token,
        expires_at=int(time.time()) + 60,
        now=int(time.time()),
    )
    with restarted.transaction() as tx:
        assert tx.state.receipts[identity].status == "send_started"


def test_settled_receipts_are_reclaimed_after_retention_and_proof_expiry(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    now = 1_000_000
    for index in range(4097):
        identity = f"{index:064x}"
        fingerprint = hashlib.sha256(identity.encode()).hexdigest()
        token = lifecycle.store.claim(
            identity,
            fingerprint,
            safe.connection_id,
            safe.revision,
            now + 60,
            now=now,
        )
        lifecycle.store.mark_send_started(
            identity,
            fingerprint,
            safe.connection_id,
            safe.revision,
            token,
            expires_at=now + 60,
            now=now,
        )
        lifecycle.store.settle(identity, "success", now=now)
        now += 86401
    with lifecycle.store.transaction() as tx:
        assert len(tx.state.receipts) == 1
        assert next(iter(tx.state.receipts.values())).status == "success"


def test_collected_terminal_receipt_cannot_replay_expired_proof_after_clock_rollback(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    identity, fingerprint = "c" * 64, "d" * 64
    now = 1_000_000
    token = lifecycle.store.claim(
        identity, fingerprint, safe.connection_id, safe.revision, now + 60, now=now
    )
    lifecycle.store.mark_send_started(
        identity,
        fingerprint,
        safe.connection_id,
        safe.revision,
        token,
        expires_at=now + 60,
        now=now,
    )
    lifecycle.store.settle(identity, "success", now=now)
    lifecycle.store.maintain(now=now + 86460)
    with lifecycle.store.transaction() as tx:
        assert identity not in tx.state.receipts
    with pytest.raises(LocalStoreError, match="dispatch_authority_expired"):
        lifecycle.store.claim(
            identity, fingerprint, safe.connection_id, safe.revision, now + 60, now=now + 1
        )


def test_stale_unknown_receipts_compact_to_durable_non_resend_fences(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    now = 2_000_000
    uncertain = {f"{index:064x}" for index in range(2)}
    with lifecycle.store.transaction() as tx:
        tx.state.receipts = {
            f"{index:064x}": DispatchReceipt(
                fingerprint=hashlib.sha256(f"{index}".encode()).hexdigest(),
                status="send_started" if index < 2 else "success",
                connection_id=safe.connection_id,
                connection_revision=safe.revision,
                created_at=now - 86402,
                updated_at=now - 86402,
                proof_expires_at=now - 2,
                terminal_at=None if index < 2 else now - 86402,
            )
            for index in range(4096)
        }
        tx.save()

    assert lifecycle.store.maintain(now=now) == 4096
    with lifecycle.store.transaction() as tx:
        assert not tx.state.receipts
    assert len(list((lifecycle.store.directory / "send-fences").iterdir())) == 2

    new_identity, new_fingerprint = "f" * 64, "e" * 64
    token = lifecycle.store.claim(
        new_identity,
        new_fingerprint,
        safe.connection_id,
        safe.revision,
        now + 60,
        now=now,
    )
    lifecycle.store.release_pre_send(new_identity, new_fingerprint, token)

    old_identity = min(uncertain)
    old_fingerprint = hashlib.sha256(f"{int(old_identity, 16)}".encode()).hexdigest()
    with pytest.raises(LocalStoreError, match="dispatch_already_claimed"):
        lifecycle.store.claim(
            old_identity,
            old_fingerprint,
            safe.connection_id,
            safe.revision,
            now + 60,
            now=now,
        )
    assert lifecycle.store.reconcile(
        old_identity,
        old_fingerprint,
        safe.connection_id,
        safe.revision,
    ) == "unknown"


@pytest.mark.parametrize("confirmed", [True, False])
def test_disconnect_stops_locally_clears_tokens_retains_mapping_and_reports_revocation(
    tmp_path, confirmed
):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    oauth.revoke_confirmed = confirmed
    disconnected = lifecycle.disconnect(safe.connection_id)
    assert disconnected.state == "disconnected"
    assert disconnected.remote_revocation == ("confirmed" if confirmed else "unconfirmed")
    with lifecycle.store.transaction() as tx:
        registration = tx.state.registrations[safe.connection_id]
        assert registration.client_id == "oaiapp_synthetic" and registration.credentials is None
    with pytest.raises(OAuthFailure):
        lifecycle.snapshot(safe.connection_id)


def test_disconnect_retries_transient_revocation_without_allowing_inference(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    oauth.revoke_results = [False, False, True]
    disconnected = lifecycle.disconnect(safe.connection_id)
    assert disconnected.remote_revocation == "confirmed"
    assert len([call for call in oauth.calls if call[0] == "revoke"]) == 3
    with pytest.raises(OAuthFailure):
        lifecycle.snapshot(safe.connection_id)


def test_identity_only_registration_cannot_get_inference_credential(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    oauth.scopes = ("openid", "profile", "email")
    attempt, url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback", connection_id=safe.connection_id
    )
    safe = lifecycle.complete(
        attempt, {"state": parse_qs(urlsplit(url).query)["state"][0], "code": "synthetic-code"}
    )
    assert safe.state == "permission_required" and not safe.plan_permission
    with pytest.raises(OAuthFailure, match="bridge_permission_required"):
        lifecycle.snapshot(safe.connection_id)


def test_enable_plan_usage_is_explicit_reconsent_after_identity_only_signin(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    oauth.scopes = ("openid", "profile", "email")
    attempt, url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback", connection_id=safe.connection_id
    )
    identity_only = lifecycle.complete(
        attempt, {"state": parse_qs(urlsplit(url).query)["state"][0], "code": "synthetic-code"}
    )
    assert identity_only.state == "permission_required"
    enable_attempt, enable_url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback",
        connection_id=safe.connection_id,
        enable_plan_usage=True,
    )
    query = parse_qs(urlsplit(enable_url).query)
    assert query["prompt"] == ["consent"]
    assert set(query["scope"][0].split()) == set(SCOPES)
    oauth.scopes = tuple(SCOPES)
    enabled = lifecycle.complete(
        enable_attempt,
        {"state": query["state"][0], "code": "synthetic-code"},
    )
    assert enabled.state == "connected" and enabled.plan_permission
    assert enabled.account_label.startswith("person@example.test · ")
    assert "synthetic-subject" not in str(asdict(enabled))


def test_identical_email_registrations_have_distinct_safe_labels():
    first = Registration(
        connection_id="11111111-1111-4111-8111-111111111111",
        client_id="oaiapp_first",
        account_email="person@example.test",
    )
    second = Registration(
        connection_id="22222222-2222-4222-8222-222222222222",
        client_id="oaiapp_second",
        account_email="person@example.test",
    )
    assert (
        CredentialLifecycle._safe(first).account_label
        != CredentialLifecycle._safe(second).account_label
    )


def test_invalid_client_enters_nonretrying_configuration_error(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    with lifecycle.store.transaction() as tx:
        tx.state.registrations[safe.connection_id].credentials.expires_at = 1
        tx.save()
    oauth.refresh_error = OAuthFailure("invalid_client")
    with pytest.raises(OAuthFailure, match="invalid_client"):
        lifecycle.snapshot(safe.connection_id)
    with pytest.raises(OAuthFailure, match="bridge_client_configuration"):
        lifecycle.snapshot(safe.connection_id)
    assert len([call for call in oauth.calls if call[0] == "refresh"]) == 1
    with lifecycle.store.transaction() as tx:
        assert tx.state.registrations[safe.connection_id].state == "configuration_error"


def test_v1_state_migration_preserves_unknown_send_fence_and_credentials(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    state_path = lifecycle.store.directory / "state.json"
    legacy = json.loads(state_path.read_text())
    legacy["schema_version"] = 1
    legacy.pop("clock_high_water", None)
    registration = legacy["registrations"][safe.connection_id]
    registration.pop("account_name", None)
    registration.pop("account_email", None)
    identity, fingerprint = "a" * 64, "b" * 64
    legacy["receipts"] = {identity: {"fingerprint": fingerprint, "status": "unknown"}}
    state_path.write_text(json.dumps(legacy))
    os.chmod(state_path, 0o600)
    migrated = ProtectedLocalStore(lifecycle.store.directory)
    with migrated.transaction() as tx:
        receipt = tx.state.receipts[identity]
        assert tx.state.schema_version == 3
        assert receipt.status == "send_started"
        assert receipt.fingerprint == fingerprint
        assert (
            tx.state.registrations[safe.connection_id].credentials.refresh_token
            == "synthetic-refresh"
        )
    with pytest.raises(LocalStoreError, match="dispatch_already_claimed"):
        migrated.claim(
            identity, fingerprint, safe.connection_id, safe.revision, int(time.time()) + 60
        )


def test_v2_state_migration_preserves_receipt_details(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    state_path = lifecycle.store.directory / "state.json"
    legacy = json.loads(state_path.read_text())
    legacy["schema_version"] = 2
    identity, fingerprint = "c" * 64, "d" * 64
    legacy["receipts"] = {
        identity: {
            "fingerprint": fingerprint,
            "status": "send_started",
            "origin": "http://localhost:3000",
            "connection_id": safe.connection_id,
            "connection_revision": safe.revision,
            "created_at": 100,
            "updated_at": 100,
            "proof_expires_at": 220,
            "terminal_at": None,
            "acknowledged_at": None,
            "claim_token": None,
        }
    }
    state_path.write_text(json.dumps(legacy))
    os.chmod(state_path, 0o600)

    migrated = ProtectedLocalStore(lifecycle.store.directory)
    with migrated.transaction() as tx:
        assert tx.state.schema_version == 3
        assert tx.state.receipts[identity].status == "send_started"
        assert tx.state.receipts[identity].origin == "http://localhost:3000"
    with pytest.raises(LocalStoreError, match="dispatch_already_claimed"):
        migrated.claim(
            identity, fingerprint, safe.connection_id, safe.revision, int(time.time()) + 60
        )


def test_unsafe_store_permissions_symlinks_and_corruption_fail_explicitly(tmp_path):
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o755)
    with pytest.raises(LocalStoreError):
        ProtectedLocalStore(unsafe)
    linked = tmp_path / "linked"
    linked.symlink_to(unsafe, target_is_directory=True)
    with pytest.raises(LocalStoreError):
        ProtectedLocalStore(linked)
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    path = lifecycle.store.directory / "state.json"
    assert path.stat().st_mode & 0o777 == 0o600
    os.chmod(path, 0o644)
    with pytest.raises(LocalStoreError):
        lifecycle.snapshot(safe.connection_id)
    os.chmod(path, 0o600)
    path.write_text('{"access_token":"do-not-echo-corrupt-data"}')
    with pytest.raises(LocalStoreError) as captured:
        lifecycle.connections()
    assert "do-not-echo" not in str(captured.value)


def test_local_credentials_cannot_be_created_in_a_repository_or_managed_runtime(
    tmp_path, monkeypatch
):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    with pytest.raises(LocalStoreError, match="local_store_in_repository"):
        ProtectedLocalStore(checkout / "credentials")
    monkeypatch.setenv("K_SERVICE", "managed-api")
    with pytest.raises(LocalStoreError, match="managed_runtime_forbidden"):
        ProtectedLocalStore(tmp_path / "managed")


def test_disconnect_invalidates_an_already_started_reauthorization_attempt(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    attempt, url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback", connection_id=safe.connection_id
    )
    lifecycle.disconnect(safe.connection_id)
    with pytest.raises(OAuthFailure, match="oauth_state_invalid"):
        lifecycle.complete(
            attempt, {"state": parse_qs(urlsplit(url).query)["state"][0], "code": "synthetic-code"}
        )


def test_expired_attempt_and_earliest_refresh_constraints_fail_without_exchange(tmp_path):
    lifecycle, oauth, safe = connected_lifecycle(tmp_path)
    attempt, url = lifecycle.begin(
        "http://127.0.0.1:54321/auth/callback", connection_id=safe.connection_id
    )
    now = int(time.time())
    lifecycle.clock = lambda: now + 181
    with pytest.raises(OAuthFailure, match="oauth_state_invalid"):
        lifecycle.complete(
            attempt, {"state": parse_qs(urlsplit(url).query)["state"][0], "code": "synthetic-code"}
        )
    lifecycle.clock = time.time
    with lifecycle.store.transaction() as tx:
        credentials = tx.state.registrations[safe.connection_id].credentials
        credentials.expires_at = 1
        credentials.earliest_refresh_at = now + 600
        tx.save()
    with pytest.raises(OAuthFailure, match="bridge_refresh_not_available"):
        lifecycle.snapshot(safe.connection_id)
    assert not [call for call in oauth.calls if call[0] == "refresh"]


def claim_in_process(path, identity, connection_id, revision, result):
    try:
        store = ProtectedLocalStore(Path(path))
        now = int(time.time())
        token = store.claim(identity, "b" * 64, connection_id, revision, now + 60, now=now)
        store.mark_send_started(
            identity,
            "b" * 64,
            connection_id,
            revision,
            token,
            expires_at=now + 60,
            now=now,
        )
        result.put("claimed")
    except LocalStoreError as error:
        result.put(error.code)


def test_physical_send_claim_is_single_use_across_real_processes_and_restart(tmp_path):
    lifecycle, _, safe = connected_lifecycle(tmp_path)
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    processes = [
        context.Process(
            target=claim_in_process,
            args=(
                str(lifecycle.store.directory),
                "a" * 64,
                safe.connection_id,
                safe.revision,
                results,
            ),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    assert sorted(results.get(timeout=2) for _ in processes) == [
        "claimed",
        "dispatch_already_claimed",
    ]
    restarted = ProtectedLocalStore(lifecycle.store.directory)
    with pytest.raises(LocalStoreError, match="dispatch_already_claimed"):
        restarted.claim(
            "a" * 64, "c" * 64, safe.connection_id, safe.revision, int(time.time()) + 60
        )
    with restarted.transaction() as tx:
        assert tx.state.receipts["a" * 64].status == "send_started"
