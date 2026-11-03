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
    return load_script("pi7_local_smoke")


@pytest.fixture
def stores():
    return load_script("pi7_local_stores")


def test_missing_locked_dependency_refuses_without_an_installer(smoke, tmp_path):
    target = tmp_path / "installed"
    target.mkdir()
    with pytest.raises(smoke.SmokeError, match="offline dependency missing or mismatched"):
        smoke.install_locked_dependencies("package-never-installed==42", tmp_path, target)
    assert not list(target.iterdir())


def test_explicit_native_requirement_blocks_when_unavailable(smoke, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(smoke.sys, "platform", "unsupported")
    with pytest.raises(smoke.SmokeError, match="native egress fence is required"):
        smoke.smoke(tmp_path, "unreachable-uv", consumer=False, require_native=True)
    assert '"native_egress": "blocked_unverified"' in capsys.readouterr().out


def test_timeout_kills_owned_child(smoke, tmp_path):
    with pytest.raises(subprocess.TimeoutExpired):
        smoke.run(
            [sys.executable, "-I", "-c", "import time; time.sleep(60)"],
            cwd=tmp_path,
            env={},
            timeout=0.1,
            capture=True,
        )


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
        [sys.executable, "-E", "-s", SCRIPTS / "pi7_local_smoke.py"],
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
            while not list(tmp_path.glob("pi7-local-*/running")):
                assert child.poll() is None and time.monotonic() < deadline
                time.sleep(0.02)
            child.terminate()
            _, stderr = child.communicate(timeout=5)
            assert child.returncode == 130, stderr
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    assert not list(tmp_path.glob("pi7-local-*"))
    assert keep.read_text() == "synthetic unrelated file"


def container_for(stores, service):
    image, guest, port = stores.SERVICES[service]
    binding = {guest: [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
    return {
        "Id": "a" * 64,
        "Config": {
            "Image": image,
            "Cmd": ["-jar", "DynamoDBLocal.jar", "-inMemory", "-sharedDb"],
            "WorkingDir": "/home/dynamodblocal",
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
            "NetworkMode": "owned_default",
            "Tmpfs": {"/var/lib/postgresql/data": ""} if service == "postgres-test" else {},
        },
        "State": {"Running": True, "Health": {"Status": "healthy"}},
        "NetworkSettings": {"Ports": binding},
        "Mounts": [],
    }


@pytest.mark.parametrize("service", ["postgres-test", "dynamodb-local-test"])
def test_only_owned_ephemeral_loopback_services_validate(stores, service):
    container = container_for(stores, service)
    assert stores.verify_container(container, "owned") == (service, True)
    with pytest.raises(stores.Refused, match="container_ownership_unproven"):
        stores.verify_container(container, "other")
    container["Mounts"] = [{"Type": "volume"}]
    with pytest.raises(stores.Refused, match="container_storage_or_port_drift"):
        stores.verify_container(container, "owned")


def test_drift_blocks_down_before_mutation(stores, monkeypatch):
    harness = object.__new__(stores.LocalStores)
    harness.project = "owned"
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
    with pytest.raises(stores.Refused, match="container_storage_or_port_drift"):
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

    def inspect(*args):
        assert args[:2] == ("image", "inspect")
        return '[{"Config":{"Volumes":{"/unexpected":{}}}}]'

    monkeypatch.setattr(harness, "run", inspect)
    with pytest.raises(stores.Refused, match="cached_image_declares_unowned_volume"):
        harness.perform("up")
