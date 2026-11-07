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
NETWORK = "integration"
NATIVE_LAUNCHER = "/usr/bin/sandbox-exec"
NATIVE_PROFILE = '(version 1)(allow default)(deny network*)(allow network-inbound (local ip "localhost:*"))(allow network-outbound (remote ip "localhost:*"))'
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


def verify_container(container, project, approved_image_id=None):
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
    expected_env = {
        "POSTGRES_DB": "personal_ai_test",
        "POSTGRES_USER": "personal_ai",
        "POSTGRES_PASSWORD": "personal_ai_test_only",
    } if service == "postgres-test" else {}
    env = dict(item.split("=", 1) for item in config.get("Env", []) if "=" in item)
    postgres_override = {key: value for key, value in env.items() if key.startswith("POSTGRES_")}
    safe_env_keys = {
        "postgres-test": {
            "PATH", "GOSU_VERSION", "LANG", "PG_MAJOR", "PG_VERSION", "PG_SHA256",
            "DOCKER_PG_LLVM_DEPS", "PGDATA", *expected_env,
        },
        "dynamodb-local-test": {"PATH", "JAVA_HOME", "LANG", "LC_ALL", "TZ"},
    }
    expected_command = ["postgres"] if service == "postgres-test" else [
        "-jar", "DynamoDBLocal.jar", "-inMemory", "-sharedDb"
    ]
    if service == "dynamodb-local-test" and (
        config.get("Cmd") != expected_command
        or config.get("WorkingDir") != "/home/dynamodblocal"
    ):
        raise Refused("dynamodb_disposable_mode_required")
    # Refuse all volumes, including anonymous mounts inherited from an image.
    if (
        config.get("Image") != image
        or config.get("Cmd") != expected_command
        or (service == "postgres-test" and config.get("Entrypoint") != ["docker-entrypoint.sh"])
        or (service == "dynamodb-local-test" and config.get("Entrypoint") != ["java", "-Djava.library.path=./DynamoDBLocal_lib", "-jar"])
        or approved_image_id is None
        or container.get("Image") != approved_image_id
        or host.get("PortBindings") != expected_ports
        or (host.get("Tmpfs") or {}) != expected_tmpfs
        or host.get("Privileged")
        or host.get("CapAdd")
        or host.get("CapDrop")
        or host.get("Devices")
        or host.get("PidMode")
        or host.get("IpcMode") not in (None, "private")
        or host.get("UsernsMode")
        or host.get("ExtraHosts")
        or host.get("SecurityOpt")
        or host.get("GroupAdd")
        or host.get("ShmSize", 64 * 1024 * 1024) != 64 * 1024 * 1024
        or host.get("PublishAllPorts")
        or host.get("ReadonlyRootfs")
        or host.get("Binds")
        or host.get("NetworkMode") != project + "_" + NETWORK
        or set(container.get("NetworkSettings", {}).get("Networks") or {}) != {project + "_" + NETWORK}
        or (service == "postgres-test" and postgres_override != expected_env)
        or (service == "dynamodb-local-test" and any(key.startswith("POSTGRES_") for key in env))
        or set(env) - safe_env_keys[service]
        or any(
            mount.get("Type") != "tmpfs" or mount.get("Destination") not in expected_tmpfs
            for mount in container.get("Mounts", [])
        )
    ):
        raise Refused("container_specification_drift")
    state = container["State"]
    if state.get("Paused") or state.get("Restarting") or state.get("Dead"):
        raise Refused("container_state_untrusted")
    if state["Running"] and container["NetworkSettings"]["Ports"] != expected_ports:
        raise Refused("runtime_port_drift")
    return service, state.get("Health", {}).get("Status") == "healthy" and state["Running"]


class LocalStores:
    def __init__(self, project, socket_path, docker_config, approved_image_ids, approved_image_digests):
        docker = shutil.which("docker")
        if not docker:
            raise Refused("docker_cli_missing")
        if not socket_path.is_absolute() or not stat.S_ISSOCK(socket_path.stat().st_mode):
            raise Refused("local_docker_unix_socket_required")
        self.project = project
        self.approved_image_ids = approved_image_ids
        self.approved_image_digests = approved_image_digests
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
                service_name = (container.get("Config", {}).get("Labels") or {}).get(
                    "com.docker.compose.service"
                )
                service, ready = verify_container(
                    container, self.project, self.approved_image_ids.get(service_name)
                )
                if service in found:
                    raise Refused("duplicate_project_service")
                found[service] = (container["Id"], ready)
        return found

    def network(self, found):
        name = self.project + "_" + NETWORK
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
            or not network.get("Internal")
            or network.get("Attachable")
            or labels.get("com.docker.compose.project") != self.project
            or labels.get("com.docker.compose.network") != NETWORK
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
                image_id = metadata.get("Id")
                if not re.fullmatch("sha256:[0-9a-f]{64}", image_id or ""):
                    raise Refused("local_image_identity_unproven")
                if self.approved_image_ids.get(name) != image_id:
                    raise Refused("local_image_id_not_operator_approved")
                repo_digests = metadata.get("RepoDigests") or []
                approved_digest = self.approved_image_digests.get(name)
                if (
                    not approved_digest
                    or not re.fullmatch("sha256:[0-9a-f]{64}", approved_digest)
                    or not any(digest.endswith("@" + approved_digest) for digest in repo_digests)
                ):
                    raise Refused("local_image_registry_digest_not_approved")
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
            # Re-read the exact IDs immediately before mutation. A mismatch means
            # preserve every resource and require operator inspection.
            initial = found
            initial_network = network
            found = self.inventory()
            network = self.network(found)
            if found != initial or network != initial_network:
                raise Refused("disposable_inventory_changed_before_teardown")
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
        if sys.platform != "darwin" or not Path(NATIVE_LAUNCHER).is_file():
            raise Refused("native_host_egress_fence_unavailable")
        env = {**self.env, **TEST_ENV, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        probe = [sys.executable, "-I", "-c", """import errno, socket
s = socket.socket()
s.settimeout(2)
try:
    s.connect(("192.0.2.1", 9))
except OSError as error:
    assert error.errno in (errno.EPERM, errno.EACCES)
else:
    raise AssertionError("egress allowed")
"""]
        probe_result = subprocess.run(
            [NATIVE_LAUNCHER, "-p", NATIVE_PROFILE, *probe],
            cwd=ROOT / "backend", env=env, capture_output=True, text=True,
            timeout=8, check=False,
        )
        if probe_result.returncode != 0:
            raise Refused("native_host_egress_fence_unproven")
        prefix = [NATIVE_LAUNCHER, "-p", NATIVE_PROFILE]
        command = [sys.executable, "-m", "personal_ai.persistence.local_stack", "--test"]
        if action == "bootstrap":
            command += ["bootstrap"]
        else:
            command += ["ready"]
        subprocess.run([*prefix, *command], cwd=ROOT / "backend", env=env, check=True, timeout=45)
        if action == "smoke":
            subprocess.run(
                [*prefix,
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
    parser.add_argument(
        "--approved-image", action="append", default=[], metavar="SERVICE=sha256:ID",
        help="operator-reviewed local image config ID, required for doctor/up",
    )
    parser.add_argument(
        "--approved-image-digest", action="append", default=[], metavar="SERVICE=sha256:DIGEST",
        help="operator-reviewed repository digest that must match the local image",
    )
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{32}", args.session):
        parser.exit(2, "Local storage refused: invalid_session_nonce\n")
    try:
        approved = {}
        for entry in args.approved_image:
            service, separator, image_id = entry.partition("=")
            if not separator or service not in SERVICES or not re.fullmatch("sha256:[0-9a-f]{64}", image_id):
                raise Refused("invalid_approved_image_id")
            if service in approved:
                raise Refused("duplicate_approved_image_id")
            approved[service] = image_id
        approved_digests = {}
        for entry in args.approved_image_digest:
            service, separator, digest = entry.partition("=")
            if not separator or service not in SERVICES or not re.fullmatch("sha256:[0-9a-f]{64}", digest):
                raise Refused("invalid_approved_image_digest")
            if service in approved_digests:
                raise Refused("duplicate_approved_image_digest")
            approved_digests[service] = digest
        with tempfile.TemporaryDirectory(prefix="local-storage-") as config:
            LocalStores(
                "local-storage-" + args.session, args.socket, config, approved, approved_digests
            ).perform(args.action)
    except (Refused, OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        reason = error if isinstance(error, Refused) else type(error).__name__
        parser.exit(2, f"Local storage refused: {reason}\n")
    print(
        json.dumps(
            {
                "profile": "local-persistent-disposable",
                "action": args.action,
                "status": "complete",
                "physical_sends": "prohibited_by_configuration_not_observed",
                "provider_usage": "not_measured",
            }
        )
    )


if __name__ == "__main__":
    main()
