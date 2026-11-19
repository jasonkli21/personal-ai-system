"""Native plan-root, owner fence, and independent restore-witness scenarios."""

# ruff: noqa: F811 - pytest imports fixtures by their parameter names

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from personal_ai.context.providers import ContextPreparationError
from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.artifacts import PostgresArtifactMetadataRepository
from personal_ai.persistence.postgres.auth import PostgresPrincipalDirectory
from personal_ai.persistence.postgres.inference_policy import PostgresInferencePolicy
from personal_ai.persistence.postgres.routing_observations import PostgresRoutingDecisionRepository
from personal_ai.services.external_turns.application_plan import NO_AI, PlanAttempts
from personal_ai.storage.errors import ConversationConflictError
from tests.app_context_support.application_plan import plan_http
from tests.persistence.test_shared_application_service_postgres import (
    query,
    shared_db,  # noqa: F401 - pytest fixture
    snapshot_database,
)
from tests.test_application_plan_inference import (
    confirmed,
    plan_factory,  # noqa: F401 - pytest fixture
    shared_factory,  # noqa: F401 - pytest fixture
    travel,
)
from tests.test_chatgpt_bridge_transport import created, delta
from tests.test_shared_application_service import create, status

pytestmark = pytest.mark.persistence_integration


class PlanWitness:
    """Fixture witness file intentionally resides outside both database snapshots."""

    def __init__(self, path, database, *, initialize=True):
        self.path = path
        self.database = database
        if initialize:
            self.write({"epoch": str(uuid4()), "claims": {}, "owner_fence": None})
        self.epoch = self.read()["epoch"]

    def read(self):
        return json.loads(self.path.read_text())

    def write(self, data):
        pending = self.path.with_suffix(".pending")
        pending.write_text(json.dumps(data))
        pending.replace(self.path)

    def record_claim(self, root, owner, attempt, payload):
        data = self.read()
        data["claims"][str(root)] = [owner, str(attempt), payload]
        self.write(data)

    def current(self):
        try:
            data = self.read()
            if data["epoch"] != self.epoch:
                return False
            for root, (owner, attempt, payload) in data["claims"].items():
                if query(
                    self.database,
                    "SELECT state,attempt_id::text,payload_sha256 FROM inference_route_roots "
                    "WHERE root_id=%s AND owner_id=%s",
                    (root, owner),
                ) != [("fenced", attempt, payload)]:
                    return False
            owner = data["owner_fence"]
            return owner is None or query(
                self.database,
                "SELECT owner_id FROM owner_lifecycle_fences WHERE owner_id=%s",
                (owner,),
            ) == [(owner,)]
        except Exception:  # noqa: BLE001 - missing or inaccessible witness quarantines
            return False


def native_attempts(database, witness, cls=PlanAttempts):
    return cls(
        PostgresRoutingDecisionRepository(database),
        PostgresInferencePolicy(database),
        recovery_current=witness.current,
        record_claim=witness.record_claim,
    )


def test_native_ambiguous_plan_fence_and_owner_deletion_survive_restore_boundary(
    plan_factory,
    shared_db,
    isolated_postgres_dsn,
    tmp_path,
):
    witness = PlanWitness(tmp_path / "outside-db.json", shared_db)

    def wire(fixture):
        fixture.host.directory.native = PostgresPrincipalDirectory(shared_db)
        return native_attempts(shared_db, witness)

    host = plan_factory(attempts=wire)
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    with snapshot_database(shared_db, isolated_postgres_dsn) as older:
        target.provider.events = [created(), delta()]
        result = plan_http(host, target, cid, "continue", payload)
        assert "event: response.completed" not in result.text
        assert status(host, target, cid, payload).json()["state"] == "unknown"
        assert len(target.provider.sends()) == 1
        owner = target.principal.owner_id
        package, proof = target.proofs[0]
        assert query(
            shared_db,
            "SELECT owner_id,state,attempt_id, payload_sha256 FROM inference_route_roots",
        ) == [(owner, "fenced", proof.claims.application_plan.attempt_id, package.fingerprint)]
        assert query(older, "SELECT root_id FROM inference_route_roots") == []

        PostgresArtifactMetadataRepository(shared_db).fence(owner)
        data = witness.read()
        witness.write(data | {"owner_fence": owner})
        assert witness.current()
        assert status(host, target, cid, payload).status_code == 403
        assert query(
            shared_db,
            "SELECT attempt_id FROM inference_route_roots WHERE owner_id=%s",
            (owner,),
        ) == [(proof.claims.application_plan.attempt_id,)]

        host.directory.native = PostgresPrincipalDirectory(older)
        host.plan.service.attempts = native_attempts(older, witness)
        witness.database = older
        assert not witness.current()
        assert status(host, target, cid, payload).status_code == 403
        assert plan_http(host, target, cid, "continue", payload).status_code == 403
        witness.path.unlink()
        assert status(host, target, cid, payload).status_code == 403
        assert query(older, "SELECT root_id FROM inference_route_roots") == []
        assert len(target.provider.sends()) == 1 and host.generation.sends == []


def claim_then_exit():
    """A second OS process commits the exact root and exits before PAS signs."""
    data = json.load(sys.stdin)
    database = PostgresDatabase(data["dsn"], environment="test", min_size=1, max_size=2)
    witness = PlanWitness(Path(data["witness"]), database, initialize=False)
    preview = SimpleNamespace(
        target=SimpleNamespace(scope=SimpleNamespace(owner_id=data["owner"])),
        dispatch=SimpleNamespace(attempt_id=UUID(data["attempt"])),
        package=SimpleNamespace(fingerprint=data["payload"]),
        root_id=UUID(data["root"]),
        confirmation=data["confirmation"],
        expires_at=datetime.fromisoformat(data["expires_at"]),
    )
    native_attempts(database, witness).claim(preview)
    os._exit(37)


def test_worker_loss_after_native_claim_preserves_original_key_and_prevents_resend(
    plan_factory,
    shared_db,
    isolated_postgres_dsn,
    tmp_path,
):
    witness = PlanWitness(tmp_path / "claim-witness.json", shared_db)
    recorded = []

    class LostWorker(PlanAttempts):
        def claim(self, preview):
            data = {
                "dsn": isolated_postgres_dsn,
                "witness": str(witness.path),
                "owner": preview.target.scope.owner_id,
                "attempt": str(preview.dispatch.attempt_id),
                "payload": preview.package.fingerprint,
                "root": str(preview.root_id),
                "confirmation": preview.confirmation,
                "expires_at": preview.expires_at.isoformat(),
            }
            process = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from tests.persistence.test_application_plan_postgres import claim_then_exit; claim_then_exit()",
                ],
                cwd=Path(__file__).resolve().parents[2],
                input=json.dumps(data),
                text=True,
                capture_output=True,
                timeout=6,
                check=False,
            )
            assert process.returncode == 37, process.stderr
            recorded.append(preview)
            raise ContextPreparationError(NO_AI)

    host = plan_factory(attempts=lambda _: native_attempts(shared_db, witness, LostWorker))
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    response = plan_http(host, target, cid, "continue", payload)
    assert "event: response.completed" not in response.text and len(recorded) == 1
    assert witness.current()
    with independent_database(isolated_postgres_dsn) as other:
        restarted = native_attempts(other, witness)
        assert restarted.current(recorded[0])
        with pytest.raises(
            ConversationConflictError, match="continuation_exists_inspect_canonical_state"
        ):
            restarted.claim(recorded[0])
    assert status(host, target, cid, payload).json()["state"] == "unknown"
    assert plan_http(host, target, cid, "continue", payload).status_code == 409
    assert target.local_payloads == target.provider.sends() == host.generation.sends == []


def independent_database(dsn):
    from contextlib import closing

    return closing(PostgresDatabase(dsn, environment="test", min_size=1, max_size=2))
