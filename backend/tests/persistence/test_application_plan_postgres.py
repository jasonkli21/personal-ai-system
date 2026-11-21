"""Native plan-root, owner fence, and independent restore-witness scenarios."""

# ruff: noqa: F811 - pytest imports fixtures by their parameter names

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
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
        self.claims_path = path.with_name(path.name + ".claims")
        self.database = database
        if initialize:
            self.write({"epoch": str(uuid4()), "owner_fence": None})
        self.epoch = self.read()["epoch"]

    def read(self):
        return json.loads(self.path.read_text())

    def write(self, data):
        pending = self.path.with_name(self.path.name + f".{uuid4().hex}.pending")
        with pending.open("x") as output:
            output.write(json.dumps(data))
            output.flush()
            os.fsync(output.fileno())
        pending.replace(self.path)
        self._sync_directory(self.path.parent)

    def record_claim(self, root, owner, attempt, payload):
        record = {
            "epoch": self.epoch,
            "owner": owner,
            "root": str(root),
            "attempt": str(attempt),
            "payload": payload,
        }
        self.claims_path.mkdir(parents=True, exist_ok=True)
        claim_path = self._claim_path(root, owner, self.claims_path)
        pending = self.claims_path / f".{claim_path.name}.{uuid4().hex}.pending"
        with pending.open("x") as output:
            output.write(json.dumps(record, sort_keys=True))
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(pending, claim_path)
        except FileExistsError:
            if json.loads(claim_path.read_text()) != record:
                raise RuntimeError("plan_claim_witness_conflict") from None
        finally:
            pending.unlink(missing_ok=True)
        self._sync_directory(self.claims_path)
        if json.loads(claim_path.read_text()) != record:
            raise RuntimeError("plan_claim_witness_unverified")

    @staticmethod
    def _sync_directory(directory):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _claim_path(root, owner, directory):
        identity = hashlib.sha256(json.dumps([str(root), owner]).encode()).hexdigest()
        return directory / f"{identity}.json"

    def claim_current(self, root, owner, attempt, payload):
        try:
            metadata = self.read()
            claim_path = self._claim_path(root, owner, self.claims_path)
            expected = {
                "epoch": self.epoch,
                "owner": owner,
                "root": str(root),
                "attempt": str(attempt),
                "payload": payload,
            }
            return metadata["epoch"] == self.epoch and json.loads(
                claim_path.read_text()
            ) == expected
        except Exception:  # noqa: BLE001 - missing or inaccessible witness quarantines
            return False

    def current(self):
        try:
            data = self.read()
            if data["epoch"] != self.epoch:
                return False
            for path in sorted(self.claims_path.glob("*.json")):
                record = json.loads(path.read_text())
                if (
                    set(record) != {"epoch", "owner", "root", "attempt", "payload"}
                    or record["epoch"] != self.epoch
                    or self._claim_path(record["root"], record["owner"], self.claims_path)
                    != path
                ):
                    return False
                if query(
                    self.database,
                    "SELECT state,attempt_id::text,payload_sha256 FROM inference_route_roots "
                    "WHERE root_id=%s AND owner_id=%s",
                    (record["root"], record["owner"]),
                ) != [("fenced", record["attempt"], record["payload"])]:
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
        claim_current=witness.claim_current,
    )


def test_native_ambiguous_plan_fence_and_owner_deletion_survive_restore_boundary(
    plan_factory,
    shared_db,
    isolated_postgres_dsn,
    tmp_path,
):
    witness = PlanWitness(tmp_path / "outside-db.json", shared_db)
    older_witness_path = tmp_path / "older-witness.json"
    older_witness_path.write_bytes(witness.path.read_bytes())

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

        # The stale database and a stale witness can agree after joint restore.
        # The independently retained claim and owner tombstone still govern
        # continuity for the restored generation.
        stale = PlanWitness(older_witness_path, older, initialize=False)
        assert stale.current()
        restored = native_attempts(older, stale)
        restored.recovery_current = lambda: stale.current() and witness.current()
        host.plan.service.attempts = restored
        assert not restored.recovery_current()
        assert status(host, target, cid, payload).status_code == 403

        # Loss of the independent copy never promotes the stale agreement.
        witness.path.unlink()
        assert not restored.recovery_current()
        assert status(host, target, cid, payload).status_code == 403
        assert query(older, "SELECT root_id FROM inference_route_roots") == []
        assert len(target.provider.sends()) == 1 and host.generation.sends == []


def claim_in_process():
    """A child process commits one exact root and records its independent claim."""
    data = json.loads(sys.stdin.readline())
    start = Path(data["start"])
    deadline = time.monotonic() + 5
    while not start.exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    if not start.exists():
        raise RuntimeError("claim_start_barrier_timeout")
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
    database.close()


def claim_then_exit():
    """A child process commits the exact root and exits before PAS signs."""
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
    attempts = native_attempts(database, witness)
    if not data["write_witness"]:
        # The root transaction has committed when the witness callback begins.
        attempts.record_claim = lambda *_: os._exit(38)
    attempts.claim(preview)
    os._exit(37)


@pytest.mark.parametrize("write_witness", [True, False], ids=["after-witness", "before-witness"])
def test_worker_loss_after_native_claim_preserves_original_key_and_prevents_resend(
    plan_factory,
    shared_db,
    isolated_postgres_dsn,
    tmp_path,
    write_witness,
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
                "write_witness": write_witness,
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
            assert process.returncode == (37 if write_witness else 38), process.stderr
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
        assert restarted.current(recorded[0]) is write_witness
        assert query(other, "SELECT state FROM inference_route_roots") == [("fenced",)]
        with pytest.raises(
            ConversationConflictError, match="continuation_exists_inspect_canonical_state"
        ):
            restarted.claim(recorded[0])
    assert status(host, target, cid, payload).json()["state"] == "unknown"
    assert plan_http(host, target, cid, "continue", payload).status_code == 409
    assert target.local_payloads == target.provider.sends() == host.generation.sends == []


def test_concurrent_native_claim_witnesses_survive_restore(
    plan_factory,
    shared_db,
    isolated_postgres_dsn,
    tmp_path,
):
    witness = PlanWitness(tmp_path / "concurrent-witness.json", shared_db)

    def wire(fixture):
        fixture.host.directory.native = PostgresPrincipalDirectory(shared_db)
        return native_attempts(shared_db, witness)

    host = plan_factory(attempts=wire)
    target = travel(host)
    owner = target.principal.owner_id
    previews = [
        SimpleNamespace(
            target=SimpleNamespace(scope=SimpleNamespace(owner_id=owner)),
            dispatch=SimpleNamespace(attempt_id=uuid4()),
            package=SimpleNamespace(
                fingerprint=hashlib.sha256(f"payload-{index}".encode()).hexdigest()
            ),
            root_id=uuid4(),
            confirmation=hashlib.sha256(f"confirmation-{index}".encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        for index in range(2)
    ]

    with snapshot_database(shared_db, isolated_postgres_dsn) as older:
        start = tmp_path / "claims-start"
        processes = []
        for preview in previews:
            data = {
                "dsn": isolated_postgres_dsn,
                "witness": str(witness.path),
                "start": str(start),
                "owner": owner,
                "root": str(preview.root_id),
                "attempt": str(preview.dispatch.attempt_id),
                "payload": preview.package.fingerprint,
                "confirmation": preview.confirmation,
                "expires_at": preview.expires_at.isoformat(),
            }
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "from tests.persistence.test_application_plan_postgres import claim_in_process; claim_in_process()",
                ],
                cwd=Path(__file__).resolve().parents[2],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process.stdin.write(json.dumps(data) + "\n")
            process.stdin.flush()
            processes.append(process)
        start.touch()
        for process in processes:
            stdout, stderr = process.communicate(timeout=12)
            assert process.returncode == 0, f"{stdout}\n{stderr}"

        attempts = native_attempts(shared_db, witness)
        assert witness.current()
        assert all(attempts.current(preview) for preview in previews)

        missing_path = witness._claim_path(
            previews[0].root_id, owner, witness.claims_path
        )
        missing_path.unlink()
        # A global scan of the remaining witness is consistent, but the exact
        # missing claim cannot authorize this offer.
        assert witness.current()
        assert not attempts.current(previews[0])
        witness.record_claim(
            previews[0].root_id,
            owner,
            previews[0].dispatch.attempt_id,
            previews[0].package.fingerprint,
        )
        assert attempts.current(previews[0])

        witness.database = older
        restored = native_attempts(older, witness)
        assert not witness.current()
        assert not any(restored.current(preview) for preview in previews)
        with pytest.raises(ContextPreparationError, match=NO_AI):
            restored.claim(previews[0])
        assert query(older, "SELECT root_id FROM inference_route_roots") == []
        assert target.provider.sends() == target.local_payloads == host.generation.sends == []


def independent_database(dsn):
    from contextlib import closing

    return closing(PostgresDatabase(dsn, environment="test", min_size=1, max_size=2))
