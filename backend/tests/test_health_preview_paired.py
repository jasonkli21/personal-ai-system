"""Exercise the Health journal and signed preview with separate product interpreters."""
# ruff: noqa: F811 - pytest imports fixtures by name

import json
import os
import subprocess
from contextlib import ExitStack, contextmanager
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_bytes
from selectors import EVENT_READ, DefaultSelector
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from personal_ai.api.private_application_plan import PROFILE_PREFIX, RECEIPT_HEADER
from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.memory.dependencies import memory_dependency
from personal_ai.services.external_turns import application_plan
from personal_ai.services.external_turns.application_plan import BoundPreviewMetadata
from tests.app_context_support.application_plan import plan_request
from tests.app_context_support.health_loopback_proof import (
    PROOF_HEADER,
    TRANSACTION_HEADER,
    sign,
    verify,
)
from tests.app_context_support.health_preview import Selection, canonical, digest
from tests.app_context_support.health_receipts import KEY_ID, NONCE_HEADER, decode, encode
from tests.persistence.conftest import isolated_postgres_dsn  # noqa: F401
from tests.persistence.test_shared_application_service_postgres import shared_db  # noqa: F401
from tests.test_health_plan_preview import (  # noqa: F401
    APP,
    AUDIENCE,
    configure_preview,
    prepare,
    setup,
)
from tests.test_travel_plan_paired import bearer_factory

CALLBACK_AUDIENCE = "https://health-fixture.invalid"
PAS_AUDIENCE = "https://pas-fixture.invalid"
REQUIRED = ("R5_HEALTH_PAIRED_CHECKOUT", "R5_HEALTH_PYTHON", "R5_HEALTH_SOCKET_DSN")
pytestmark = pytest.mark.skipif(
    not all(os.environ.get(name) for name in REQUIRED),
    reason="requires the paired Health checkout, locked Python and migrated disposable database",
)


@contextmanager
def health_worker(subject):
    checkout = Path(os.environ["R5_HEALTH_PAIRED_CHECKOUT"]).resolve()
    assert not (checkout / ".env").exists()
    assert not (checkout / "services/api/.env").exists()
    assert (
        subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=checkout, text=True)
        == ""
    ), "run this distributed fixture from a committed Health checkout"
    runner = Path(__file__).parent / "app_context_support/health_paired_worker.py"
    child_env = {key: os.environ[key] for key in ("PATH", "R5_HEALTH_SOCKET_DSN")}
    child_env["PYTHONPATH"] = str(checkout / "services/api/src")
    with (
        subprocess.Popen(
            [os.environ["R5_HEALTH_PYTHON"], "-sB", str(runner)],
            cwd=checkout,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as worker,
        DefaultSelector() as reader,
    ):
        reader.register(worker.stdout, EVENT_READ)

        def read():
            assert reader.select(timeout=6), "Health fixture response timeout"
            line = worker.stdout.readline()
            assert line, "Health worker terminated"
            return json.loads(line)

        def exchange(operation, **values):
            worker.stdin.write(json.dumps([operation, values]) + "\n")
            worker.stdin.flush()
            return read()

        callback_key, forward_key = token_bytes(32), token_bytes(32)
        worker.stdin.write(
            json.dumps(
                {
                    "subject": subject,
                    "callback_key": callback_key.hex(),
                    "forward_key": forward_key.hex(),
                }
            )
            + "\n"
        )
        worker.stdin.flush()
        binding = read()
        try:
            yield exchange, binding, callback_key, forward_key, worker
            if worker.poll() is None:
                stopped = exchange("stop")
                assert stopped["forbidden_network_attempts"] == []
                assert worker.wait(timeout=5) == 0
        finally:
            if worker.poll() is None:
                worker.kill()


class Pair:
    def __init__(self, setup_host, stack, worker, bearer, subject, database):
        self.send, self.health, self.callback_key, forward_key, self.worker = worker
        self.http = stack.enter_context(httpx.Client(trust_env=False, timeout=3))
        self.wrong_endpoint = None
        self.saved_callback = None
        self.callbacks = 0
        self.preview_posts = 0
        self.serializer_calls = 0
        self.transaction = None
        enrollment, installation = str(uuid4()), str(uuid4())
        self.host = setup_host(
            subject=subject,
            bearer_override=bearer,
            database=database,
            reverse_transport=self.callback,
            verify_transaction=lambda request, raw, nonce: (
                len(request.headers.getlist(PROOF_HEADER)) == 1
                and verify(
                    forward_key,
                    PAS_AUDIENCE,
                    request.method,
                    request.url.path,
                    raw,
                    request.headers.get(PROOF_HEADER),
                )
                == nonce
            ),
            health_binding={
                "owner": self.health["owner"],
                "enrollment_id": enrollment,
                "installation_id": installation,
                **self.health["records"][0],
            },
        )
        plan = self.host.target.plan

        def count_serialization(package):
            self.serializer_calls += 1
            return plan.serialize_payload(package)

        self.host.target.plan = replace(plan, serialize_payload=count_serialization)
        self.host.fixture.targets[
            plan.scope.owner_id, APP, None, plan.scope.client_namespace
        ] = self.host.target.plan
        self.client = stack.enter_context(TestClient(self.host.app))
        enrollment_values = {
            "subject": subject,
            "enrollment": enrollment,
            "generation": 1,
            "installation": installation,
            "record": 0,
        }
        assert self.send("enroll", **enrollment_values, consented=False) == {"denied": True}
        assert self.send("enroll", **enrollment_values, consented=True) == {"enrolled": True}
        self.branch_id = uuid4()
        binding = self.host.target.plan.preview_binding(self.host.principal, UUID(int=0))
        self.values = {
            "intent": str(uuid4()),
            "profile_request": canonical(self.host.enrollment.selected.request("profile")).decode(),
            "pas_owner": self.host.principal.owner_id,
            "actor": self.host.enrollment.actor,
            "source_epoch": self.host.enrollment.source_epoch,
            "policy_epoch": self.host.enrollment.policy_epoch,
            "client_namespace": self.host.namespace,
            "branch_id": str(self.branch_id),
            "destination_digest": binding.target_fingerprint,
        }

    def callback(self, request):
        self.callbacks += 1
        worker = self.wrong_endpoint or self.health
        path = self.health["path"]
        assert self.transaction is not None
        proof = sign(
            self.callback_key,
            f"{CALLBACK_AUDIENCE}/{self.transaction}",
            "POST",
            path,
            request.content,
        )
        self.saved_callback = (path, request.content, proof)
        return self.http.post(
            f"http://127.0.0.1:{worker['port']}{path}",
            content=request.content,
            headers={PROOF_HEADER: proof, TRANSACTION_HEADER: self.transaction},
        )

    def post(self, path, headers, body, *, send_proof=True, **authority_changes):
        if not send_proof:
            return self.client.post(path, headers=headers, content=body)
        nonce = headers[NONCE_HEADER]
        proof = self.send("sign", method="POST", path=path, body=body.decode(), nonce=nonce)[
            "proof"
        ]
        self.transaction = nonce
        try:
            if path.endswith("/context-preview"):
                current = self.send(
                    "authorize_preview",
                    **(self.receipt_values | authority_changes),
                    conversation=str(self.conversation),
                    body=body.decode(),
                    path=path,
                )
                if current != {"ok": True}:
                    assert current == {"denied": True}
                    return None
                self.preview_posts += 1
            return self.client.post(path, headers=headers | {PROOF_HEADER: proof}, content=body)
        finally:
            self.transaction = None
            assert self.send("finish") == {"ok": True}

    def reserve(self):
        self.original = self.send("reserve", **self.values)
        assert self.original["pas_owner"] == self.host.principal.owner_id
        self.create_body = json.loads(self.original["request"])
        assert self.original["digest"] == digest(self.create_body)
        assert self.original["create"] != self.original["preview"]
        assert self.send("reserve", **self.values) == self.original

    def create(self):
        op, headers = prepare(self.host, self.create_body)
        initial = self.post(op.path, headers, canonical(self.create_body), send_proof=False)
        assert initial.status_code == 422
        initial = self.post(op.path, headers, canonical(self.create_body))
        assert initial.status_code == 201, initial.text
        # Recover a lost create response with fresh authority for this exact intent.
        _, retry_headers = prepare(self.host, self.create_body)
        repeated = self.post(op.path, retry_headers, canonical(self.create_body))
        assert repeated.status_code == 201 and repeated.content == initial.content
        self.conversation = UUID(repeated.json()["conversation_id"])
        self.branch = configure_preview(self.host, self.conversation, branch_id=self.branch_id)
        self.preview_body = plan_request(UUID(self.original["preview"]))
        self.receipt_values = self.values | {
            "create": self.original["create"],
            "preview": self.original["preview"],
            "receipt_key": self.host.verify_keys[KEY_ID].public_bytes_raw().hex(),
            "witness": True,
        }
        self.create_response = {
            "body": repeated.text,
            "receipt": repeated.headers[RECEIPT_HEADER],
            "request": self.preview_body,
        }

    def bind(self):
        result = self.send("bind_preview", **self.receipt_values, **self.create_response)
        assert result == {
            "conversation": str(self.conversation),
            "digest": digest(self.preview_body),
        }
        assert self.send("bind_preview", **self.receipt_values, **self.create_response) == {
            "denied": True
        }

    def _operation(self, **changes):
        return prepare(
            self.host,
            self.preview_body,
            cid=self.conversation,
            create_key=UUID(self.original["create"]),
            branch=self.branch,
            **changes,
        )

    def preview(self):
        op, headers = self._operation()
        self.result = self.post(op.path, headers, canonical(self.preview_body))
        assert self.result.status_code == 200, self.result.text
        snapshot = self.host.target.memory
        with application_scope_context(ApplicationScope(application_id="personal_ai")):
            lifecycle = self.host.fixture.lifecycle.get_state(
                owner_id=self.host.principal.owner_id,
                memory_id=snapshot.id,
            )
        dependency = memory_dependency(
            snapshot, lifecycle, acting_user_id=self.host.enrollment.actor
        )
        self.epochs = {
            "branch_digest": self.branch,
            "destination": {
                "application": APP,
                "provider": "ChatGPT",
                "model": self.host.target.plan.model,
                "runtime": self.host.target.plan.scope.local_recipient,
                "recipient": self.host.target.plan.scope.model_recipient,
            },
            "source_grants": {
                purpose: grant.version for (_, purpose), grant in self.host.grants.items()
            },
            "memory_grants": {"approved-pas-memory-origin": dependency.version}
            | {
                purpose: grant.dependency(dependency, purpose).version
                for purpose, grant in zip(
                    ("runtime-handoff", "inference-disclosure"),
                    self.host.fixture.disclosures[self.host.target.plan.scope],
                    strict=True,
                )
            },
        }
        _, duplicate = self._operation()
        assert self.post(op.path, duplicate, canonical(self.preview_body)).status_code == 422

    def observe(self, *, response=None, change=None, witness=True, **changes):
        op, headers = self._operation()
        values = self.receipt_values | {
            "epochs": self.epochs,
            "nonce": headers[NONCE_HEADER],
            "conversation": str(self.conversation),
            "digest": digest(self.preview_body),
            "witness": witness,
        }
        result = self.send("observe", **(values | changes))
        if "get" not in result:
            return result
        assert result["get"] == f"{op.path}/{op.key}"
        if response is None:
            self.transaction = headers[NONCE_HEADER]
            try:
                response = self.client.get(
                    result["get"],
                    headers=headers | {PROOF_HEADER: result["proof"]},
                )
            finally:
                self.transaction = None
        self.last_observe = response
        wire = {
            "body": response.text,
            "receipt": response.headers.get(RECEIPT_HEADER),
            "status": response.status_code,
        } | (change or {})
        return self.send("get_response", **wire)

    def continue_denied(self):
        denied = self.client.post(
            f"{PROFILE_PREFIX}/{self.conversation}/continue",
            headers=self.host.headers,
            json=plan_request(UUID(self.original["preview"]), self.result.json()["confirmation"]),
        )
        assert denied.status_code == 422
        self.assert_no_execution()

    def assert_no_execution(self):
        assert self.serializer_calls == 0
        assert not self.host.target.local_payloads
        assert not self.host.target.provider.sends()


def test_two_paired_workers_bind_actual_owner_and_original_key_status(
    setup, monkeypatch, shared_db
):
    bearer = bearer_factory(monkeypatch, datetime.now(UTC))
    with ExitStack() as stack:
        subjects = ("fabricated-one", "fabricated-two")
        workers = [stack.enter_context(health_worker(subject)) for subject in subjects]
        pairs = [
            Pair(setup, stack, worker, bearer, subject, shared_db)
            for worker, subject in zip(workers, subjects, strict=True)
        ]
        first, second = pairs
        for pair in pairs:
            pair.reserve()
            pair.create()
        crossed = first.receipt_values | second.create_response
        assert first.send("bind_preview", **crossed) == {"denied": True}
        legacy = first.receipt_values | first.create_response | {"witness": False}
        assert first.send("bind_preview", **legacy) == {"denied": True}
        wrong_request = first.create_response | {
            "request": first.preview_body | {"idempotency_key": str(uuid4())}
        }
        assert first.send("bind_preview", **first.receipt_values, **wrong_request) == {
            "denied": True
        }
        for pair in reversed(pairs):
            pair.bind()
            pair.preview()
            pair.continue_denied()
        assert first.host.principal.owner_id != second.host.principal.owner_id
        assert first.host.target.memory.owner_id == first.host.principal.owner_id
        assert second.host.target.memory.owner_id == second.host.principal.owner_id

        before = first.send("counts")
        wrong = Selection(UUID(first.health["records"][1]["object_id"]), 1)
        url = f"http://127.0.0.1:{first.health['port']}{first.health['path']}"
        transaction = str(uuid4())
        assert first.send("begin", nonce=transaction) == {"ok": True}
        body = canonical(wrong.request("profile"))
        signed_wrong = sign(
            first.callback_key,
            f"{CALLBACK_AUDIENCE}/{transaction}",
            "POST",
            first.health["path"],
            body,
        )
        assert (
            first.http.post(
                url,
                content=body,
                headers={PROOF_HEADER: signed_wrong, TRANSACTION_HEADER: transaction},
            ).status_code
            == 403
        )
        path, body, consumed = first.saved_callback
        assert (
            first.http.post(
                url,
                content=body,
                headers={PROOF_HEADER: consumed, TRANSACTION_HEADER: transaction},
            ).status_code
            == 403
        )
        assert path == first.health["path"]
        assert first.http.post(url, content=body).status_code == 403
        assert first.send("counts") == before
        valid = canonical(first.host.enrollment.selected.request("profile"))
        valid_proof = sign(
            first.callback_key, f"{CALLBACK_AUDIENCE}/{transaction}", "POST", path, valid
        )
        valid_headers = {PROOF_HEADER: valid_proof, TRANSACTION_HEADER: transaction}
        assert first.http.post(url, content=valid, headers=valid_headers).status_code == 200
        count_after_read = first.send("counts")
        assert count_after_read["protected_reads"] == before["protected_reads"] + 1
        assert first.http.post(url, content=valid, headers=valid_headers).status_code == 403
        assert first.send("counts") == count_after_read
        assert first.send("finish") == {"ok": True}
        current_request = sign(
            first.callback_key,
            f"{CALLBACK_AUDIENCE}/{transaction}",
            "POST",
            path,
            body,
        )
        assert (
            first.http.post(
                url,
                content=body,
                headers={PROOF_HEADER: current_request, TRANSACTION_HEADER: transaction},
            ).status_code
            == 403
        )

        assert first.observe()["metadata"]["source_sensitivity"] == "restricted"
        for dependency in ("source_grants", "destination"):
            posts = first.preview_posts
            assert first.observe(mutate_epochs=dependency) == {"metadata": None}
            assert first.last_observe.status_code == 200
            assert first.preview_posts == posts
            assert first.observe()["metadata"]["source_sensitivity"] == "restricted"
        assert second.observe()["metadata"]["history_turns"] == 1
        assert first.observe(response=second.result) == {"metadata": None}
        assert first.observe(response=first.result, change={"body": first.result.text + " "}) == {
            "metadata": None
        }
        for status in (404, 429, 503):
            assert first.observe(response=httpx.Response(status, content=b"")) == {"metadata": None}
        assert first.observe(response=first.result, change={"timeout": True}) == {"metadata": None}
        assert first.observe(response=httpx.Response(200, content=b"data: partial")) == {
            "metadata": None
        }
        assert first.observe(witness=False) == {"metadata": None}

        first.wrong_endpoint = second.health
        assert first.observe() == {"metadata": None}
        first.wrong_endpoint = None
        assert first.send("relink") == {"ok": True}
        assert first.observe() == {"denied": True}
        assert first.send("restore_link") == {"ok": True}
        assert first.observe(change={"revoke": True}) == {"denied": True}
        assert first.send("restore_session") == {"ok": True}
        assert first.observe()["metadata"]["history_turns"] == 1
        assert first.observe(change={"revoke_source": True}) == {"denied": True}
        second.host.fixture.disclosures.clear()
        assert second.observe() == {"metadata": None}
        second.host.fixture.service._previews.clear()
        assert second.observe() == {"metadata": None}
        assert second.send("forget") == {"ok": True}
        assert second.observe() == {"denied": True}

        print(
            "HEALTH_WORKERS=2 HEALTH_RECORDS=4 PAS_NATIVE_OWNERS=2 "
            "PRIVATE_CONTINUE_HTTP=422,422 SERIALIZER_CALLS=0 RUNTIME_HANDOFF_BYTES=0 FAKE_PROVIDER_POSTS=0"
        )


def test_same_owner_wrong_record_receipt_is_rejected(setup, monkeypatch, shared_db):
    bearer = bearer_factory(monkeypatch, datetime.now(UTC))
    subject = "fabricated-record-owner"
    with ExitStack() as stack:
        worker = stack.enter_context(health_worker(subject))
        pair = Pair(setup, stack, worker, bearer, subject, shared_db)
        pair.reserve()
        pair.create()
        enrollment = pair.host.enrollment
        wrong = Selection(UUID(pair.health["records"][1]["object_id"]), 1)
        # Re-sign a correctly formed create receipt for the wrong record and same owners.
        original = pair.create_response["receipt"]
        statement = json.loads(decode(original.split(".")[0]))
        statement["selection"] = replace(enrollment, selected=wrong).claims()["selection"]
        raw = canonical(statement)
        altered = pair.create_response | {
            "receipt": f"{encode(raw)}.{encode(pair.host.authority.key.sign(raw))}"
        }
        assert pair.send("bind_preview", **pair.receipt_values, **altered) == {"denied": True}
        pair.bind()
        pair.preview()
        receipt = pair.result.headers[RECEIPT_HEADER]
        preview_claims = json.loads(decode(receipt.split(".")[0]))
        for change in (
            {"selection": statement["selection"]},
            {"actual_revision": 2},
            {"aud": "urn:wrong:audience"},
            {"kid": "unknown-key"},
            {"exp": 1},
            {"purpose": "create"},
            {"destination": preview_claims["destination"] | {"recipient": "different"}},
        ):
            candidate = canonical(preview_claims | change)
            crossed = f"{encode(candidate)}.{encode(pair.host.authority.key.sign(candidate))}"
            assert pair.observe(response=pair.result, change={"receipt": crossed}) == {
                "metadata": None
            }


def test_pending_status_refuses_after_initiating_health_worker_dies(setup, monkeypatch, shared_db):
    bearer = bearer_factory(monkeypatch, datetime.now(UTC))
    subject = "fabricated-interruption"
    with ExitStack() as stack:
        worker = stack.enter_context(health_worker(subject))
        pair = Pair(setup, stack, worker, bearer, subject, shared_db)
        pair.reserve()
        pair.create()
        pair.bind()
        pair.preview()
        assert pair.observe()["metadata"]["history_turns"] == 1
        op, headers = pair._operation()
        status_path = f"{op.path}/{op.key}"
        proof = pair.send(
            "sign", method="GET", path=status_path, body="", nonce=headers[NONCE_HEADER]
        )["proof"]
        assert pair.send("counts")["forbidden_network_attempts"] == []
        pair.worker.kill()
        assert pair.worker.wait(timeout=5) < 0
        pair.transaction = headers[NONCE_HEADER]
        denied = pair.client.get(status_path, headers=headers | {PROOF_HEADER: proof})
        assert denied.status_code == 422 and RECEIPT_HEADER not in denied.headers
        assert not pair.host.target.local_payloads and not pair.host.target.provider.sends()


@pytest.mark.parametrize("stage", ["reserve", "bind_preview"])
@pytest.mark.parametrize("change", ["source", "intent"])
def test_health_post_commit_authority_changes_preserve_keys(
    setup, monkeypatch, shared_db, stage, change,
):
    bearer = bearer_factory(monkeypatch, datetime.now(UTC))
    subject = f"commit-{stage}-{change}"
    with ExitStack() as stack:
        worker = stack.enter_context(health_worker(subject))
        pair = Pair(setup, stack, worker, bearer, subject, shared_db)
        if stage == "reserve":
            values = pair.values
        else:
            pair.reserve()
            pair.create()
            values = pair.receipt_values | pair.create_response
        assert pair.send(stage, **values, commit_change=change) == {"denied": True}
        saved = pair.send("journal", intent=values["intent"])
        assert set(saved) == {"create", "preview"}
        assert saved["create"]["bound"]
        assert saved["preview"]["bound"] is (stage == "bind_preview")
        assert saved["create"]["key"] != saved["preview"]["key"]
        if stage == "bind_preview":
            assert saved["create"]["key"] == pair.original["create"]
            assert saved["preview"]["key"] == pair.original["preview"]
            assert pair.send(stage, **values) == {"denied": True}
        elif change == "intent":
            retry = pair.send(stage, **values)
            assert [retry[key] for key in ("create", "preview")] == [
                saved[key]["key"] for key in ("create", "preview")
            ]
        else:
            assert pair.send(stage, **values) == {"denied": True}
        assert pair.send("journal", intent=values["intent"]) == saved
        assert pair.preview_posts == 0
        pair.assert_no_execution()


@pytest.mark.parametrize("change", ["source", "recipient", "intent"])
def test_health_rechecks_authority_at_outgoing_preview_boundary(
    setup, monkeypatch, shared_db, change,
):
    bearer = bearer_factory(monkeypatch, datetime.now(UTC))
    subject = f"before-preview-post-{change}"
    with ExitStack() as stack:
        worker = stack.enter_context(health_worker(subject))
        pair = Pair(setup, stack, worker, bearer, subject, shared_db)
        pair.reserve()
        pair.create()
        pair.bind()
        saved = pair.send("journal", intent=pair.values["intent"])
        operation, headers = pair._operation()
        before = pair.callbacks
        changes = {"recipient_changed": change == "recipient", "witness": change != "intent"}
        if change == "source":
            assert pair.send("revoke_selected_source") == {"ok": True}
        assert pair.post(operation.path, headers, canonical(pair.preview_body), **changes) is None
        assert pair.preview_posts == 0
        assert pair.callbacks == before
        assert pair.send("journal", intent=pair.values["intent"]) == saved
        assert not pair.host.fixture.service._previews
        pair.assert_no_execution()


@pytest.mark.parametrize("method", ["create", "preview", "observe"])
@pytest.mark.parametrize("mapping", ["missing", "revoked"])
def test_pas_private_revalidation_uses_read_only_native_owner(
    setup, monkeypatch, shared_db, method, mapping,
):
    bearer = bearer_factory(monkeypatch, datetime.now(UTC))
    subject = f"revalidation-{method}-{mapping}"
    with ExitStack() as stack:
        worker = stack.enter_context(health_worker(subject))
        pair = Pair(setup, stack, worker, bearer, subject, shared_db)
        pair.reserve()
        if method != "create":
            pair.create()
            pair.bind()
        if method == "observe":
            pair.preview()
        directory = pair.host.directory
        owner = pair.host.principal.owner_id
        require_existing = directory.require_existing
        ensure_active = directory.ensure_active
        counts = {"lookup": 0, "bootstrap": 0}

        def changed_after_ingress(principal):
            require_existing(principal)
            counts["lookup"] += 1
            if counts["lookup"] == 1:
                with shared_db.transaction() as connection:
                    if mapping == "missing":
                        connection.execute("DELETE FROM identity_mappings WHERE owner_id=%s", (owner,))
                    else:
                        connection.execute(
                            "UPDATE identity_mappings SET status='revoked', "
                            "payload=jsonb_set(payload, '{status}', to_jsonb(%s::text)) "
                            "WHERE owner_id=%s",
                            ("revoked", owner),
                        )

        def count_bootstrap(principal, *, correlation_id):
            counts["bootstrap"] += 1
            return ensure_active(principal, correlation_id=correlation_id)

        def native_state():
            with shared_db.connection() as connection:
                return tuple(
                    connection.execute(statement, (owner,)).fetchall()
                    for statement in (
                        "SELECT status, payload FROM identity_mappings WHERE owner_id=%s",
                        "SELECT scope_id FROM scope_namespaces WHERE owner_id=%s ORDER BY scope_id",
                        "SELECT record_id FROM audit_events WHERE owner_id=%s ORDER BY record_id",
                    )
                )

        before = native_state()
        monkeypatch.setattr(directory, "require_existing", changed_after_ingress)
        monkeypatch.setattr(directory, "ensure_active", count_bootstrap)
        protected_reads = pair.callbacks
        if method == "create":
            operation, headers = prepare(pair.host, pair.create_body)
            response = pair.post(operation.path, headers, canonical(pair.create_body))
        elif method == "preview":
            operation, headers = pair._operation()
            response = pair.post(operation.path, headers, canonical(pair.preview_body))
        else:
            assert pair.observe() == {"metadata": None}
            response = pair.last_observe
        assert response.status_code == 422, response.text
        assert RECEIPT_HEADER not in response.headers
        assert pair.callbacks == protected_reads
        assert counts["bootstrap"] == 0
        assert counts["lookup"] == 1
        after = native_state()
        assert after[1:] == before[1:]
        assert [row[0] for row in after[0]] == ([] if mapping == "missing" else ["revoked"])
        pair.assert_no_execution()


@pytest.mark.parametrize("method", ["preview", "observe"])
@pytest.mark.parametrize(
    "change", ["source", "memory", "branch", "enrollment", "operation_expiry", "preview_expiry"]
)
def test_pas_bound_publication_requires_current_authority_after_signing(
    setup, monkeypatch, shared_db, method, change,
):
    bearer = bearer_factory(monkeypatch, datetime.now(UTC))
    subject = f"publication-{method}-{change}"
    with ExitStack() as stack:
        worker = stack.enter_context(health_worker(subject))
        pair = Pair(setup, stack, worker, bearer, subject, shared_db)
        pair.reserve()
        pair.create()
        pair.bind()
        packages = []
        make_package = application_plan.PreparedExecution

        def count_package(**kwargs):
            packages.append(kwargs)
            return make_package(**kwargs)

        monkeypatch.setattr(application_plan, "PreparedExecution", count_package)
        if method == "observe":
            pair.preview()
            cache = tuple(pair.host.fixture.service._previews.values())
            assert len(cache) == 1 and isinstance(cache[0], BoundPreviewMetadata)
            assert {field.name for field in fields(cache[0])} == {
                "binding", "branch_digest", "policy_version", "snapshots", "original_key",
                "expires_at", "confirmation", "attested_body",
            }
            assert cache[0].attested_body == pair.result.content

        authority = pair.host.authority
        signing_key = authority.key
        signed = []
        check_snapshots = application_plan.source_snapshots_current
        preview_clock = pair.host.fixture.service.clock
        after_final_check = []

        class SignThenChange:
            def sign(self, statement):
                signature = signing_key.sign(statement)
                signed.append(statement)
                if change == "source":
                    pair.host.grants.pop((pair.conversation, "source-read"))
                if change == "memory":
                    pair.host.fixture.disclosures.clear()
                return signature

        def check_then_change(snapshots, permissions, *, now):
            result = check_snapshots(snapshots, permissions, now=now)
            if signed and not after_final_check:
                after_final_check.append(result)
                if change == "branch":
                    authority.current_branch = lambda *_: "different branch"
                if change == "enrollment":
                    pair.host.current.clear()
                if change == "operation_expiry":
                    authority.clock = lambda: int(json.loads(signed[0])["iat"]) + 30
                if change == "preview_expiry":
                    pair.host.fixture.service.clock = lambda: preview_clock().replace(
                        microsecond=0
                    ) + timedelta(minutes=2)
            return result

        monkeypatch.setattr(authority, "key", SignThenChange())
        monkeypatch.setattr(application_plan, "source_snapshots_current", check_then_change)
        if method == "preview":
            operation, headers = pair._operation()
            response = pair.post(operation.path, headers, canonical(pair.preview_body))
            assert not pair.host.fixture.service._previews
        else:
            assert pair.observe() == {"metadata": None}
            response = pair.last_observe
            assert tuple(pair.host.fixture.service._previews.values()) == cache
        assert len(signed) == 1
        assert after_final_check == [change not in {"source", "memory"}]
        assert response.status_code == 422, response.text
        assert RECEIPT_HEADER not in response.headers
        assert "selected_context" not in response.json()
        assert packages == []
        pair.assert_no_execution()
