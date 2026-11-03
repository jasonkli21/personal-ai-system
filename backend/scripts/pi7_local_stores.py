"""Operator commands for the existing disposable Compose integration services."""

import argparse
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.persistence.yml"
SERVICES = {
    "postgres-test": ("pgvector/pgvector:0.8.1-pg17", "5432/tcp", 54330),
    "dynamodb-local-test": ("amazon/dynamodb-local:2.6.1", "8000/tcp", 8001),
}
POSTGRES_DATA = "/var/lib/postgresql/data"
TEST_ENV = {
    "PERSISTENCE_TEST_POSTGRES_DSN": "postgresql://personal_ai:personal_ai_test_only@127.0.0.1:54330/personal_ai_test",
    "PERSISTENCE_TEST_DYNAMODB_ENDPOINT": "http://127.0.0.1:8001",
    "AWS_ACCESS_KEY_ID": "local",
    "AWS_SECRET_ACCESS_KEY": "local",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_EC2_METADATA_DISABLED": "true",
}


class Refused(RuntimeError):
    pass


def verify_container(container, project):
    config = container["Config"]
    host = container["HostConfig"]
    labels = config.get("Labels") or {}
    service = labels.get("com.docker.compose.service")
    if (
        labels.get("com.docker.compose.project") != project
        or labels.get("com.docker.compose.project.config_files") != str(COMPOSE)
        or labels.get("com.docker.compose.project.working_dir") != str(ROOT)
        or labels.get("com.docker.compose.oneoff", "").lower() != "false"
        or service not in SERVICES
        or not re.fullmatch("[0-9a-f]{64}", container["Id"])
    ):
        raise Refused("container_ownership_unproven")
    image, guest, port = SERVICES[service]
    expected_ports = {guest: [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
    expected_tmpfs = {POSTGRES_DATA: ""} if service == "postgres-test" else {}
    if service == "dynamodb-local-test" and (
        config.get("Cmd") != ["-jar", "DynamoDBLocal.jar", "-inMemory", "-sharedDb"]
        or config.get("WorkingDir") != "/home/dynamodblocal"
    ):
        raise Refused("dynamodb_disposable_mode_required")
    # Refuse all volumes, including anonymous mounts inherited from an image.
    if (
        config.get("Image") != image
        or host.get("PortBindings") != expected_ports
        or (host.get("Tmpfs") or {}) != expected_tmpfs
        or host.get("Privileged")
        or host.get("Binds")
        or host.get("NetworkMode") != project + "_default"
        or any(
            mount.get("Type") != "tmpfs" or mount.get("Destination") not in expected_tmpfs
            for mount in container.get("Mounts", [])
        )
    ):
        raise Refused("container_storage_or_port_drift")
    state = container["State"]
    if state["Running"] and container["NetworkSettings"]["Ports"] != expected_ports:
        raise Refused("runtime_port_drift")
    return service, state.get("Health", {}).get("Status") == "healthy" and state["Running"]


class LocalStores:
    def __init__(self, project, socket_path, docker_config):
        docker = shutil.which("docker")
        if not docker:
            raise Refused("docker_cli_missing")
        if not socket_path.is_absolute() or not stat.S_ISSOCK(socket_path.stat().st_mode):
            raise Refused("local_docker_unix_socket_required")
        self.project = project
        self.env = {"PATH": os.environ["PATH"], "DOCKER_CONFIG": docker_config}
        self.docker = [docker, "--host", f"unix://{socket_path}"]
        self.compose = [
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            "/dev/null",
            "-f",
            str(COMPOSE),
            "-p",
            project,
            "--profile",
            "integration",
        ]

    def run(self, *args, timeout=120):
        result = subprocess.run(
            [*self.docker, *args],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise Refused("docker_command_failed")
        return result.stdout

    def inventory(self):
        ids = self.run(
            "ps",
            "-aq",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={self.project}",
        ).splitlines()
        if len(ids) > len(SERVICES) or any(not re.fullmatch("[0-9a-f]{64}", item) for item in ids):
            raise Refused("unexpected_project_containers")
        found = {}
        if ids:
            containers = json.loads(self.run("inspect", *ids))
            if {item["Id"] for item in containers} != set(ids):
                raise Refused("container_inventory_changed")
            for container in containers:
                service, ready = verify_container(container, self.project)
                if service in found:
                    raise Refused("duplicate_project_service")
                found[service] = (container["Id"], ready)
        return found

    def network(self, found):
        name = self.project + "_default"
        identifiers = self.run(
            "network",
            "ls",
            "-q",
            "--no-trunc",
            "--filter",
            f"name=^{name}$",
        ).splitlines()
        if not identifiers:
            return None
        if len(identifiers) != 1 or not re.fullmatch("[0-9a-f]{64}", identifiers[0]):
            raise Refused("unexpected_project_network")
        identifier = identifiers[0]
        (network,) = json.loads(self.run("network", "inspect", identifier))
        labels = network.get("Labels") or {}
        if (
            network["Id"] != identifier
            or network["Name"] != name
            or network["Driver"] != "bridge"
            or network["Scope"] != "local"
            or labels.get("com.docker.compose.project") != self.project
            or labels.get("com.docker.compose.network") != "default"
            or set(network.get("Containers") or {})
            - {identifier for identifier, _ in found.values()}
        ):
            raise Refused("network_ownership_unproven")
        return identifier

    def check_ports(self, found):
        for name, (_, _, port) in SERVICES.items():
            if name not in found:
                with socket.socket() as probe:
                    try:
                        probe.bind(("127.0.0.1", port))
                    except OSError as error:
                        raise Refused("loopback_port_unavailable") from error

    def perform(self, action):
        if action == "doctor":
            self.run("compose", "version")
            self.run("version", "--format", "{{.Server.Version}}")
        found = self.inventory()
        network = self.network(found)
        if action in {"doctor", "up"}:
            self.check_ports(found)
            for name, (image, _, _) in SERVICES.items():
                (metadata,) = json.loads(self.run("image", "inspect", image))
                declared_volumes = set(metadata["Config"].get("Volumes") or {})
                allowed_volumes = {POSTGRES_DATA} if name == "postgres-test" else set()
                if declared_volumes - allowed_volumes:
                    raise Refused("cached_image_declares_unowned_volume")
        if action == "up":
            self.run(
                *self.compose,
                "up",
                "--detach",
                "--wait",
                "--wait-timeout",
                "90",
                "--pull",
                "never",
                "--no-build",
                "--no-recreate",
                *SERVICES,
            )
            found = self.inventory()
            if not self.network(found):
                raise Refused("network_ownership_unproven")
            if found.keys() != SERVICES.keys() or not all(ready for _, ready in found.values()):
                raise Refused("owned_stores_not_ready")
        elif action == "down":
            ids = [identifier for identifier, _ in found.values()]
            if ids:
                self.run("stop", *ids)
                self.run("rm", *ids)
            if network:
                self.run("network", "rm", network)
        elif action in {"bootstrap", "smoke"}:
            if found.keys() != SERVICES.keys() or not all(ready for _, ready in found.values()):
                raise Refused("owned_stores_not_ready")
            if not network:
                raise Refused("network_ownership_unproven")
            self.run_store_command(action)

    def run_store_command(self, action):
        env = {**self.env, **TEST_ENV, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        command = [sys.executable, "-m", "personal_ai.persistence.local_stack", "--test"]
        if action == "bootstrap":
            command += ["bootstrap"]
        else:
            command += ["ready"]
        subprocess.run(command, cwd=ROOT / "backend", env=env, check=True, timeout=45)
        if action == "smoke":
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "anyio.pytest_plugin",
                    "-m",
                    "persistence_integration",
                    "tests/persistence",
                ],
                cwd=ROOT / "backend",
                env=env,
                check=True,
                timeout=180,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("doctor", "up", "bootstrap", "smoke", "down"))
    parser.add_argument("--session", required=True, help="unique 32-character lowercase hex nonce")
    parser.add_argument("--socket", type=Path, default=Path("/var/run/docker.sock"))
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{32}", args.session):
        parser.exit(2, "PI-7 stores refused: invalid_session_nonce\n")
    try:
        with tempfile.TemporaryDirectory(prefix="pi7-docker-") as config:
            LocalStores("pi7-" + args.session, args.socket, config).perform(args.action)
    except (Refused, OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        reason = error if isinstance(error, Refused) else type(error).__name__
        parser.exit(2, f"PI-7 stores refused: {reason}\n")
    print(
        json.dumps(
            {
                "profile": "local-persistent-disposable",
                "action": args.action,
                "status": "complete",
                "provider_usage": "none",
            }
        )
    )


if __name__ == "__main__":
    main()
