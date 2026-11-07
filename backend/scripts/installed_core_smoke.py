"""Build and exercise installed core profiles using prepared dependencies."""

import argparse
import errno
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

from offline_benchmark_checks import PROFILE

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SANDBOX = "/usr/bin/sandbox-exec"
OPTIONAL = ("personal_ai_reference_apps", "reading_logbook", "reading_logbook_host")
NATIVE_PROBE = """
import errno, subprocess, sys
child = r'''import errno, socket
for family, target in [(socket.AF_INET, ('192.0.2.1', 9)),
                       (socket.AF_INET6, ('2001:db8::1', 9))]:
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        with socket.socket(family, kind) as sock:
            try:
                if kind == socket.SOCK_STREAM:
                    sock.settimeout(2)
                    sock.connect(target)
                else:
                    sock.sendto(b'native-fence-probe', target)
            except OSError as error:
                assert error.errno in (errno.EPERM, errno.EACCES)
            else:
                raise AssertionError('native egress not fenced')
'''
subprocess.run([sys.executable, '-I', '-c', child], check=True, timeout=8)
"""


class SmokeError(RuntimeError):
    pass


def run(command, *, cwd, env, timeout=120, capture=False):
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        start_new_session=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    ) as process:
        try:
            stdout, _ = process.communicate(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        if process.returncode:
            raise SmokeError(f"child {Path(command[0]).name} exited {process.returncode}")
        return stdout


def install_locked_dependencies(requirements, site, target):
    import base64
    import hmac

    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    installed = {}
    for dist in importlib.metadata.distributions(path=[str(site)]):
        installed.setdefault(canonicalize_name(dist.metadata["Name"]), []).append(dist)
    for line in requirements.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        matches = installed.get(canonicalize_name(requirement.name), [])
        if len(matches) != 1 or not requirement.specifier.contains(
            matches[0].version, prereleases=True
        ):
            raise SmokeError(f"offline dependency missing or mismatched: {requirement.name}")
        dist = matches[0]
        if dist.read_text("direct_url.json") or not dist.files:
            raise SmokeError(f"expected a prepared index distribution: {requirement.name}")
        for entry in dist.files:
            if ".." in entry.parts or entry.is_absolute() or entry.suffix == ".pth":
                raise SmokeError(f"unsafe dependency metadata: {requirement.name}")
            if entry.parts[0] in {"sitecustomize.py", "usercustomize.py"}:
                raise SmokeError(f"unexpected startup hook: {requirement.name}")
            source = Path(dist.locate_file(entry))
            if not source.is_file() or source.resolve() != site.resolve() / entry:
                raise SmokeError(f"unsafe or incomplete installed dependency: {requirement.name}")
            if entry.name != "RECORD":
                if not entry.hash:
                    raise SmokeError(f"dependency file has no RECORD hash: {requirement.name}")
                digest = hashlib.new(entry.hash.mode, source.read_bytes()).digest()
                actual = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
                if not hmac.compare_digest(actual, entry.hash.value):
                    raise SmokeError(f"dependency RECORD hash mismatch: {requirement.name}")
            destination = target / entry
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)


def inspect_artifacts(directory, absent):
    archives = sorted((*directory.glob("*.whl"), *directory.glob("*.tar.gz")))
    for artifact in archives:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                names = archive.namelist()
        else:
            with tarfile.open(artifact) as archive:
                names = archive.getnames()
        if len(names) != len(set(names)):
            raise SmokeError("duplicate archive member")
        if any(
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or set(Path(name).parts).intersection(absent)
            or Path(name).suffix == ".pth"
            for name in names
        ):
            raise SmokeError("unexpected archive contents")
        with artifact.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        print(
            json.dumps(
                {
                    "artifact": artifact.name,
                    "sha256": digest,
                    "members": len(names),
                }
            ),
            flush=True,
        )


def smoke(workspace, uv, *, consumer, allow_degraded):
    env = {
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(workspace),
        "UV_CACHE_DIR": str(workspace / "uv-cache"),
        "UV_OFFLINE": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "AI_PROVIDER": "fake",
        "AI_MODEL": "test-synthetic-model",
        "APP_ENVIRONMENT": "test",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    native = []
    if sys.platform == "darwin" and Path(SANDBOX).is_file():
        try:
            run([SANDBOX, "-p", PROFILE, "/usr/bin/true"], cwd=workspace, env=env, capture=True)
        except SmokeError:
            reason = "sandbox_launcher_rejected"
        else:
            native = [SANDBOX, "-p", PROFILE]
    else:
        reason = "no_reviewed_native_launcher"
    if not native:
        print(json.dumps({"native_egress": "blocked_unverified", "reason": reason}), flush=True)
        if not allow_degraded:
            raise SmokeError("native egress fence is required before build or child dispatch")
    else:
        run(
            [*native, sys.executable, "-I", "-c", NATIVE_PROBE],
            cwd=workspace,
            env=env,
            timeout=8,
        )
    print(
        json.dumps(
            {
                "profile": "local-consumer" if consumer else "offline-core",
                "python": platform.python_version(),
                "platform": f"{platform.system()}-{platform.machine()}",
                "uv": run([uv, "--version"], cwd=workspace, env=env, capture=True).strip(),
                "lock_sha256": hashlib.sha256((BACKEND / "uv.lock").read_bytes()).hexdigest(),
                "dependency_source": "prepared_backend_venv",
                "egress_evidence": "native_fenced" if native else "degraded_unverified",
                "usage_class": "synthetic",
                "billed_cost": "unobserved",
            }
        ),
        flush=True,
    )

    def uv_run(*arguments, **kwargs):
        return run(
            [*native, uv, "--no-config", "--offline", *map(str, arguments)],
            cwd=workspace,
            env=env,
            **kwargs,
        )

    requirements = uv_run(
        "export",
        "--locked",
        "--project",
        BACKEND,
        "--format",
        "requirements-txt",
        "--no-hashes",
        "--no-emit-project",
        "--extra",
        "dev",
        "--group",
        "build",
        capture=True,
    )
    isolated = workspace / "installed"
    venv.EnvBuilder(with_pip=False).create(isolated)
    python = isolated / "bin/python"
    site_suffix = f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    install_locked_dependencies(
        requirements,
        Path(sys.executable).parent.parent / site_suffix,
        isolated / site_suffix,
    )

    def build(source, output, *flags):
        uv_run(
            "build",
            source,
            "--no-build-isolation",
            "--no-sources",
            "--python",
            python,
            "--out-dir",
            output,
            *flags,
        )

    def install(interpreter, *wheels):
        uv_run("pip", "install", "--python", interpreter, "--no-index", "--no-deps", *wheels)

    # Hatchling carries inherited VCS exclusions into the sdist. Preserve
    # those rules so forced artifact modules enter the wheel only once.
    shutil.copyfile(ROOT / ".gitignore", workspace / ".gitignore")
    source = workspace / "core"
    source.mkdir()
    for filename in ("pyproject.toml", "uv.lock"):
        shutil.copyfile(BACKEND / filename, source / filename)
    shutil.copytree(
        BACKEND / "src/personal_ai",
        source / "src/personal_ai",
        ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc"),
    )
    output = workspace / "archives"
    build(source, output)
    inspect_artifacts(output, OPTIONAL)
    rebuilt = workspace / "from-sdist"
    build(next(output.glob("*.tar.gz")), rebuilt, "--wheel")
    inspect_artifacts(rebuilt, OPTIONAL)

    suite = workspace / "suite"
    tests = suite / "backend/tests"
    tests.mkdir(parents=True)
    (suite / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    loopback_http: synthetic HTTP fixture\n"
    )
    runner = suite / "signed_http_checks.py"
    shutil.copyfile(BACKEND / "scripts/signed_http_checks.py", runner)
    for filename in ("test_standalone_core_http.py", "conftest.py", "__init__.py"):
        shutil.copyfile(BACKEND / "tests" / filename, tests / filename)

    def test(*paths, extra_env=None):
        run(
            [*native, python, "-I", runner, "-q", "-s", "--tb=short", *paths],
            cwd=suite,
            env={**env, **(extra_env or {})},
        )

    core_test = "backend/tests/test_standalone_core_http.py"
    install(python, next(output.glob("*.whl")))
    test(core_test)
    install(python, next(rebuilt.glob("*.whl")))
    test(core_test)
    if consumer:
        client_env = workspace / "client-only"
        venv.EnvBuilder(with_pip=False).create(client_env)
        client_python = client_env / "bin/python"
        for name in ("client", "host"):
            package = ROOT / "examples/reading-logbook" / name
            local_source = workspace / name
            shutil.copytree(
                package,
                local_source,
                ignore=shutil.ignore_patterns("dist", "__pycache__"),
            )
            dest = workspace / f"{name}-archives"
            build(local_source, dest)
            inspect_artifacts(dest, ("personal_ai", "personal_ai_reference_apps"))
            wheel = next(dest.glob("*.whl"))
            install(python, wheel)
            if name == "client":
                install(client_python, wheel)
        for filename in (
            "test_signed_http_integration.py",
            "test_standalone_client.py",
            "test_retrieval_http.py",
            "test_retrieval_integrations.py",
            "test_application_lifecycle.py",
        ):
            shutil.copyfile(BACKEND / "tests" / filename, tests / filename)
        docs = suite / "docs/platform-independence"
        docs.mkdir(parents=True)
        contract = "consumer-v1.openapi.json"
        shutil.copyfile(ROOT / "docs/platform-independence" / contract, docs / contract)
        client_runner = suite / "standalone_client_probe.py"
        shutil.copyfile(BACKEND / "scripts/standalone_client_probe.py", client_runner)
        run(
            [
                *native,
                client_python,
                "-I",
                "-c",
                (
                    "from importlib.util import find_spec; import reading_logbook; "
                    "assert find_spec('personal_ai') is None; "
                    "assert find_spec('reading_logbook_host') is None"
                ),
            ],
            cwd=suite,
            env=env,
        )
        test(
            "backend/tests/test_signed_http_integration.py",
            "backend/tests/test_standalone_client.py",
            "backend/tests/test_application_lifecycle.py",
            extra_env={
                "CLIENT_INSTALL_PROBE": "1",
                "CLIENT_INSTALL_PYTHON": str(client_python),
                "CLIENT_INSTALL_RUNNER": str(client_runner),
            },
        )
        uv_run(
            "pip",
            "uninstall",
            "--python",
            python,
            "reading-logbook-client",
            "reading-logbook-host",
        )
        test(core_test)
    if allow_degraded:
        raise SmokeError("degraded_unverified: offline acceptance is blocked")


def interrupt(_number, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--consumer", action="store_true")
    fence = parser.add_mutually_exclusive_group()
    fence.add_argument("--require-native", action="store_true", help=argparse.SUPPRESS)
    fence.add_argument("--allow-degraded", action="store_true",
                       help="development probe only; always exits blocked for acceptance")
    args = parser.parse_args()
    uv = shutil.which("uv")
    if not uv:
        parser.exit(2, "Installed-core checks require uv and the prepared backend virtualenv. See the runbook.\n")
    signal.signal(signal.SIGTERM, interrupt)
    try:
        with tempfile.TemporaryDirectory(prefix="installed-local-store-") as directory:
            smoke(Path(directory), uv, consumer=args.consumer, allow_degraded=args.allow_degraded)
    except (SmokeError, ModuleNotFoundError, OSError, subprocess.TimeoutExpired) as error:
        reason = error if isinstance(error, SmokeError) else type(error).__name__
        if isinstance(error, OSError) and error.errno in {errno.ENOSPC, errno.EDQUOT}:
            reason = "temporary storage exhausted"
        parser.exit(2, f"Installed-core smoke blocked or failed ({reason}). See the runbook.\n")
    except KeyboardInterrupt:
        parser.exit(130, "Installed-core smoke interrupted.\n")


if __name__ == "__main__":
    main()
