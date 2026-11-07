"""Adversarial tests for offline setup and disposable-store ownership."""

import importlib.util
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from personal_ai.auth import safeguards

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "backend/scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def smoke(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return load_script("installed_core_smoke")


@pytest.fixture
def stores():
    return load_script("local_storage_smoke")


def test_missing_locked_dependency_refuses_without_an_installer(smoke, tmp_path):
    target = tmp_path / "installed"
    target.mkdir()
    with pytest.raises(smoke.SmokeError, match="offline dependency missing or mismatched"):
        smoke.install_locked_dependencies("package-never-installed==42", tmp_path, target)
    assert not list(target.iterdir())


def test_explicit_native_requirement_blocks_when_unavailable(smoke, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(smoke.sys, "platform", "unsupported")
    with pytest.raises(smoke.SmokeError, match="native egress fence is required before build"):
        smoke.smoke(tmp_path, "unreachable-uv", consumer=False, allow_degraded=False)
    assert '"native_egress": "blocked_unverified"' in capsys.readouterr().out


def test_missing_native_launcher_refuses_before_build(smoke, monkeypatch, tmp_path):
    monkeypatch.setattr(smoke.sys, "platform", "darwin")
    monkeypatch.setattr(smoke, "SANDBOX", str(tmp_path / "missing-sandbox"))
    with pytest.raises(smoke.SmokeError, match="native egress fence is required before build"):
        smoke.smoke(tmp_path, "not-dispatched", consumer=True, allow_degraded=False)
    assert not list(tmp_path.iterdir())


def test_changed_same_version_dependency_bytes_refuse(smoke, monkeypatch, tmp_path):
    import base64
    import hashlib
    from types import SimpleNamespace

    package = tmp_path / "package.py"
    package.write_bytes(b"modified same-version package")
    expected = base64.urlsafe_b64encode(hashlib.sha256(b"original package").digest()).rstrip(b"=").decode()
    from pathlib import PurePosixPath

    class HashedPath(PurePosixPath):
        hash = SimpleNamespace(mode="sha256", value=expected)

    entry = HashedPath("package.py")
    class Dist:
        def __init__(self):
            self.metadata = {"Name": "package"}
            self.version = "1.2.3"
            self.files = [entry]
        def read_text(self, _name):
            return None
        def locate_file(self, _entry):
            return package

    monkeypatch.setattr(smoke.importlib.metadata, "distributions", lambda path: [Dist()])
    with pytest.raises(smoke.SmokeError, match="RECORD hash mismatch"):
        smoke.install_locked_dependencies("package==1.2.3", tmp_path, tmp_path / "target")


def test_timeout_kills_owned_child(smoke, tmp_path):
    with pytest.raises(subprocess.TimeoutExpired):
        smoke.run(
            [sys.executable, "-I", "-c", "import time; time.sleep(60)"],
            cwd=tmp_path,
            env={},
            timeout=0.1,
            capture=True,
        )


def test_child_stderr_canary_is_not_copied_to_parent_error(smoke, tmp_path):
    canary = "SYNTHETIC_CHILD_STDERR_CANARY_7801"
    with pytest.raises(smoke.SmokeError) as failure:
        smoke.run(
            [sys.executable, "-I", "-c", f"import sys; print('{canary}', file=sys.stderr); sys.exit(17)"],
            cwd=tmp_path, env={}, capture=True,
        )
    assert canary not in str(failure.value)


def test_interrupt_cleans_only_owned_workspace(tmp_path):
    uv = tmp_path / "uv"
    uv.write_text(
        '#!/bin/sh\n[ -z "$AI_API_KEY$PYTHONPATH$INFERENCE_PROFILE" ] || exit 42\n'
        ': > "$TMPDIR/running"\nexec /bin/sleep 60\n'
    )
    uv.chmod(0o700)
    keep = tmp_path / "untouched"
    keep.write_text("synthetic unrelated file")
    with subprocess.Popen(
        [sys.executable, "-E", "-s", SCRIPTS / "installed_core_smoke.py", "--allow-degraded"],
        env={
            "PATH": str(tmp_path),
            "TMPDIR": str(tmp_path),
            "AI_API_KEY": "synthetic-unused-key",
            "PYTHONPATH": str(tmp_path),
            "INFERENCE_PROFILE": "legacy_gemini",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        try:
            deadline = time.monotonic() + 10
            while not list(tmp_path.glob("installed-local-store-*/running")):
                assert child.poll() is None and time.monotonic() < deadline
                time.sleep(0.02)
            child.terminate()
            _, stderr = child.communicate(timeout=5)
            assert child.returncode == 130, stderr
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    assert not list(tmp_path.glob("installed-local-store-*"))
    assert keep.read_text() == "synthetic unrelated file"


def container_for(stores, service):
    image, guest, port = stores.SERVICES[service]
    binding = {guest: [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
    return {
        "Id": "a" * 64,
        "Config": {
            "Image": image,
            "Cmd": ["postgres"] if service == "postgres-test" else ["-jar", "DynamoDBLocal.jar", "-inMemory", "-sharedDb"],
            "Entrypoint": ["docker-entrypoint.sh"] if service == "postgres-test" else ["java", "-Djava.library.path=./DynamoDBLocal_lib", "-jar"],
            "WorkingDir": "/home/dynamodblocal",
            "Env": (["POSTGRES_DB=personal_ai_test", "POSTGRES_USER=personal_ai", "POSTGRES_PASSWORD=personal_ai_test_only"] if service == "postgres-test" else []),
            "Labels": {
                "com.docker.compose.project": "owned",
                "com.docker.compose.service": service,
                "com.docker.compose.oneoff": "False",
                "com.docker.compose.project.config_files": str(stores.COMPOSE),
                "com.docker.compose.project.working_dir": str(stores.ROOT),
            },
        },
        "HostConfig": {
            "PortBindings": binding,
            "NetworkMode": "owned_integration",
            "Tmpfs": {"/var/lib/postgresql/data": ""} if service == "postgres-test" else {},
            "ShmSize": 64 * 1024 * 1024,
        },
        "State": {"Running": True, "Health": {"Status": "healthy"}},
        "NetworkSettings": {"Ports": binding, "Networks": {"owned_integration": {}}},
        "Mounts": [],
        "Image": "sha256:" + "b" * 64,
    }


@pytest.mark.parametrize("service", ["postgres-test", "dynamodb-local-test"])
def test_only_owned_ephemeral_loopback_services_validate(stores, service):
    container = container_for(stores, service)
    assert stores.verify_container(container, "owned", container["Image"]) == (service, True)
    with pytest.raises(stores.Refused, match="container_ownership_unproven"):
        stores.verify_container(container, "other", container["Image"])
    container["Mounts"] = [{"Type": "volume"}]
    with pytest.raises(stores.Refused, match="container_specification_drift"):
        stores.verify_container(container, "owned", container["Image"])


@pytest.mark.parametrize("mutate", [
    lambda c: c["Config"].update(Entrypoint=["/bin/sh", "-c", "unexpected"]),
    lambda c: c["Config"].update(Cmd=["unsafe"]),
    lambda c: c["Config"].update(Env=["POSTGRES_DB=other"]),
    lambda c: c["HostConfig"].update(CapAdd=["SYS_ADMIN"]),
    lambda c: c["HostConfig"].update(Devices=[{"PathOnHost": "/dev/null"}]),
    lambda c: c["NetworkSettings"].update(Networks={"owned_integration": {}, "evil": {}}),
    lambda c: c.update(Image="sha256:" + "c" * 64),
    lambda c: c["State"].update(Paused=True),
])
def test_effective_container_drift_refuses(stores, mutate):
    container = container_for(stores, "postgres-test")
    mutate(container)
    with pytest.raises(stores.Refused):
        stores.verify_container(container, "owned", "sha256:" + "b" * 64)


def test_same_project_inventory_collision_is_rejected_before_down(stores, monkeypatch):
    harness = object.__new__(stores.LocalStores)
    harness.project = "owned"
    harness.approved_image_ids = {"postgres-test": "sha256:" + "b" * 64}
    calls = []

    def cli(*args):
        calls.append(args)
        if args[0] == "ps":
            return "a" * 64 + "\n" + "c" * 64
        if args[0] == "inspect":
            import json

            first = container_for(stores, "postgres-test")
            second = container_for(stores, "postgres-test")
            second["Id"] = "c" * 64
            return json.dumps([first, second])
        pytest.fail("mutation attempted after colliding inventory")

    monkeypatch.setattr(harness, "run", cli)
    with pytest.raises(stores.Refused, match="duplicate_project_service"):
        harness.perform("down")
    assert [item[0] for item in calls] == ["ps", "inspect"]


def test_down_rechecks_exact_ids_before_mutation(stores, monkeypatch):
    harness = object.__new__(stores.LocalStores)
    harness.project = "owned"
    snapshots = iter([
        {"postgres-test": ("a" * 64, True)},
        {"postgres-test": ("c" * 64, True)},
    ])
    monkeypatch.setattr(harness, "inventory", lambda: next(snapshots))
    monkeypatch.setattr(harness, "network", lambda _found: "b" * 64)
    calls = []
    monkeypatch.setattr(harness, "run", lambda *args: calls.append(args))
    with pytest.raises(stores.Refused, match="disposable_inventory_changed_before_teardown"):
        harness.perform("down")
    assert calls == []


def test_drift_blocks_down_before_mutation(stores, monkeypatch):
    harness = object.__new__(stores.LocalStores)
    harness.project = "owned"
    harness.approved_image_ids = {"postgres-test": "sha256:" + "b" * 64}
    calls = []

    def cli(*args):
        calls.append(args)
        if args[0] == "ps":
            return "a" * 64
        if args[0] == "inspect":
            import json

            container = container_for(stores, "postgres-test")
            container["HostConfig"]["PortBindings"] = {}
            return json.dumps([container])
        pytest.fail("operation attempted against drifted container")

    monkeypatch.setattr(harness, "run", cli)
    with pytest.raises(stores.Refused, match="container_specification_drift"):
        harness.perform("down")
    assert [command[0] for command in calls] == ["ps", "inspect"]


def test_down_uses_verified_ids_and_keeps_volumes(stores, monkeypatch):
    harness = object.__new__(stores.LocalStores)
    monkeypatch.setattr(harness, "inventory", lambda: {"postgres-test": ("a" * 64, True)})
    monkeypatch.setattr(harness, "network", lambda _found: "b" * 64)
    calls = []
    monkeypatch.setattr(harness, "run", lambda *args: calls.append(args))
    harness.perform("down")
    assert calls == [("stop", "a" * 64), ("rm", "a" * 64), ("network", "rm", "b" * 64)]


def test_concurrent_daily_reservation_is_atomic_and_resets_at_utc_boundary(monkeypatch):
    class Clock(datetime):
        instant = datetime(2026, 11, 2, 23, 59, tzinfo=UTC)

        @classmethod
        def now(cls, _timezone=None):
            return cls.instant

    monkeypatch.setattr(safeguards, "datetime", Clock)
    store = safeguards.InMemorySafeguardStore()

    def reserve(_):
        try:
            assert store.reserve_daily("synthetic-owner", 2, 10, 6, 30) == 60
        except safeguards.SafeguardDenied as error:
            assert error.code == "daily_budget_exceeded" and error.retry_after == 60
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(32))) == 3
    assert store.reserve_daily("independent-synthetic-owner", 2, 10, 6, 30) == 60
    Clock.instant = datetime(2026, 11, 3, tzinfo=UTC)
    assert store.reserve_daily("synthetic-owner", 2, 10, 6, 30) == 86_400


def test_up_refuses_image_that_would_allocate_unowned_volume(stores, monkeypatch):
    harness = object.__new__(stores.LocalStores)
    monkeypatch.setattr(harness, "inventory", dict)
    monkeypatch.setattr(harness, "network", lambda _found: None)
    monkeypatch.setattr(harness, "check_ports", lambda _found: None)
    harness.approved_image_ids = {
        "postgres-test": "sha256:" + "a" * 64,
        "dynamodb-local-test": "sha256:" + "b" * 64,
    }
    harness.approved_image_digests = {
        "postgres-test": "sha256:" + "c" * 64,
        "dynamodb-local-test": "sha256:" + "d" * 64,
    }

    def inspect(*args):
        assert args[:2] == ("image", "inspect")
        return '[{"Id":"sha256:' + "a" * 64 + '","RepoDigests":["pgvector/pgvector@sha256:' + "c" * 64 + '"],"Config":{"Volumes":{"/unexpected":{}}}}]'

    monkeypatch.setattr(harness, "run", inspect)
    with pytest.raises(stores.Refused, match="cached_image_declares_unowned_volume"):
        harness.perform("up")
