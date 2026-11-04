"""Inspect and repeat-build the dependency-free SDK; input origin stays external."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from email.parser import BytesParser
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_WHEEL = 2_000_000
SDK_FILES = {"__init__.py", "client.py", "py.typed"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect_wheel(path, expected_digest):
    """Inspect inert archive bytes before any installer or package code runs."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_WHEEL:
        raise ValueError("wheel_size_or_type")
    with path.open("rb") as handle:
        raw = handle.read(MAX_WHEEL + 1)
    if len(raw) > MAX_WHEEL:
        raise ValueError("wheel_size_or_type")
    if (
        not isinstance(expected_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        or digest(raw) != expected_digest
    ):
        raise ValueError("wheel_digest")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 32:
            raise ValueError("wheel_inventory")
        prefix = "personal_ai_sdk-0.1.0.dist-info/"
        allowed = {"personal_ai_sdk/" + name for name in SDK_FILES} | {
            prefix + name for name in ("METADATA", "WHEEL", "RECORD", "licenses/LICENSE")
        }
        if set(names) != allowed:
            raise ValueError("wheel_hooks_or_modules")
        if any(
            i.file_size > 1_000_000 or (i.external_attr >> 16) & 0o170000 == 0o120000
            for i in archive.infolist()
        ):
            raise ValueError("wheel_member_size_or_link")
        message = BytesParser().parsebytes(archive.read(prefix + "METADATA"))
        if (
            message.get_all("Name") != ["personal-ai-sdk"]
            or message.get_all("Version") != ["0.1.0"]
            or message.get_all("Requires-Dist")
            or message.get_all("License-Expression") != ["Apache-2.0"]
        ):
            raise ValueError("wheel_metadata")
        license_bytes = archive.read(prefix + "licenses/LICENSE")
        if b"Apache License" not in license_bytes or b"Version 2.0" not in license_bytes:
            raise ValueError("wheel_license")
        return {
            "name": "personal-ai-sdk",
            "version": "0.1.0",
            "sha256": digest(raw),
            "license": "Apache-2.0",
            "runtime_dependencies": [],
            "members": {name: digest(archive.read(name)) for name in sorted(names)},
        }


def clean_env(tmp):
    return {
        "PATH": os.defpath,
        "TMPDIR": str(tmp),
        "UV_OFFLINE": "1",
        "UV_CACHE_DIR": str(tmp / "cache"),
        "PYTHONNOUSERSITE": "1",
        "SOURCE_DATE_EPOCH": "1700000000",
    }


def run(argv, cwd, env, timeout=60):
    from release_process import bounded_run

    result = bounded_run(argv, cwd=cwd, env=env, timeout=timeout)
    if result["exit"] or result["timed_out"] or result["output_cap_reached"]:
        raise ValueError("bounded_child_failed")
    return result


def source():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, timeout=10).decode().strip()

    commit = git("rev-parse", "HEAD")
    return {"commit": commit, "tree": git("rev-parse", f"{commit}^{{tree}}")}


def checkout_state():
    raw = subprocess.check_output(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        cwd=ROOT,
        timeout=10,
    )
    paths = [
        *Path(__file__).parent.glob("release_*.py"),
        Path(__file__).parent / "source_free_sdk_probe.py",
    ]
    return {
        "clean": not bool(raw),
        "status_sha256": digest(raw),
        "tooling_sha256": {p.name: digest(p.read_bytes()) for p in sorted(paths)},
    }


def tool_inventory():
    # Build dependencies are read from the prepared environment, never fetched.
    # List the full prepared distribution inventory to expose transitive inputs;
    # presence is an observation, not independently authenticated provenance.
    result = []
    for dist in metadata.distributions():
        result.append(
            {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "license": dist.metadata.get("License-Expression")
                or dist.metadata.get("License")
                or "UNKNOWN",
                "requires": sorted(dist.requires or []),
                "origin": "UNVERIFIED",
            }
        )
    return sorted(result, key=lambda d: (d["name"].lower(), d["version"]))


def repeat_build(uv):
    revision = source()
    uv = str(Path(uv).resolve(strict=True))
    outputs = []
    with tempfile.TemporaryDirectory(prefix="release-build-") as tmp:
        root = Path(tmp)
        env = clean_env(root)
        tracked = (
            subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", revision["commit"], "sdk/python"],
                cwd=ROOT,
                timeout=10,
            )
            .decode()
            .splitlines()
        )
        inputs = {}
        for iteration in ("one", "two"):
            work = root / iteration
            package = work / "package"
            package.mkdir(parents=True)
            for name in tracked:
                # Build only the declared package source, not tests, dist or examples.
                relative = Path(name).relative_to("sdk/python")
                if relative.parts[0] not in {"src", "pyproject.toml", "LICENSE"}:
                    continue
                raw = subprocess.check_output(
                    ["git", "show", f"{revision['commit']}:{name}"], cwd=ROOT, timeout=10
                )
                target = package / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                inputs[name] = digest(raw)
            run(
                [
                    uv,
                    "build",
                    "--offline",
                    "--no-build-isolation",
                    "--python",
                    sys.executable,
                    "--out-dir",
                    str(work / "dist"),
                    str(package),
                ],
                root,
                env,
            )
            records = {}
            for path in sorted((work / "dist").iterdir()):
                if path.name == ".gitignore":
                    continue
                raw = path.read_bytes()
                record = {"sha256": digest(raw), "bytes": len(raw)}
                if path.suffix == ".whl":
                    record["inspection"] = inspect_wheel(path, digest(raw))
                records[path.name] = record
            if len(records) != 2 or not any(n.endswith(".tar.gz") for n in records):
                raise ValueError("build_outputs")
            outputs.append(records)
        differences = [
            name
            for name in sorted(set(outputs[0]) | set(outputs[1]))
            if outputs[0].get(name) != outputs[1].get(name)
        ]
        member_differences = {}
        for name in differences:
            left = outputs[0].get(name, {}).get("inspection", {}).get("members", {})
            right = outputs[1].get(name, {}).get("inspection", {}).get("members", {})
            member_differences[name] = [
                n for n in sorted(set(left) | set(right)) if left.get(n) != right.get(n)
            ]
        return {
            "schema": "artifact-build-v1",
            "source": revision,
            "checkout": checkout_state(),
            "release_tool_digests": release_tool_digests(),
            "inputs": inputs,
            "python": platform.python_version(),
            "platform": sys.platform,
            "uv_version": subprocess.check_output([uv, "--version"], env=env, cwd=root, timeout=10)
            .decode()
            .strip(),
            "tool_digests": {
                "uv_sha256": digest(Path(uv).read_bytes()),
                "python_sha256": digest(Path(sys.executable).read_bytes()),
            },
            "build_environment": tool_inventory(),
            "outputs": outputs,
            "source_date_epoch": 1700000000,
            "bitwise_equal": not differences,
            "different_archives": differences,
            "different_wheel_members": member_differences,
            "origin": "BLOCKED: independent toolchain and input pins required",
            "license_review": "BLOCKED: operator must review transitive inventory",
            "scope": "committed SDK only; no backend or optional package acceptance",
        }


def native_fence(root, env):
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("native_fence_unsupported")
    # Reuse the installed-core probe, including a child and TCP/UDP IPv4/IPv6.
    from installed_core_smoke import NATIVE_PROBE

    prefix = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
    run([*prefix, sys.executable, "-I", "-c", NATIVE_PROBE], root, env, timeout=12)
    return prefix


RELEASE_TOOL_NAMES = (
    "release_artifacts.py",
    "release_preflight.py",
    "release_process.py",
    "release_profiles.py",
    "source_free_sdk_probe.py",
)


def release_tool_digests():
    return {
        name: digest((ROOT / "backend/scripts" / name).read_bytes())
        for name in RELEASE_TOOL_NAMES
    }


def install(wheel, pins, uv, *, expected_source, expected_tool_digests):
    from release_profiles import closed, identity, read_json

    with pins.open("rb") as handle:
        trust = read_json(handle.read(262145))
    closed(trust, "schema source origin filename sha256 name version tools")
    revision = source()
    identity(expected_source)
    if revision != expected_source:
        raise ValueError("expected_source_mismatch")
    checkout = checkout_state()
    if not checkout["clean"]:
        raise ValueError("dirty_checkout")
    actual_tool_digests = release_tool_digests()
    closed(expected_tool_digests, " ".join(RELEASE_TOOL_NAMES))
    if any(
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        for value in expected_tool_digests.values()
    ):
        raise ValueError("invalid_release_tool_pins")
    if expected_tool_digests != actual_tool_digests:
        raise ValueError("release_tool_digest_mismatch")
    probe_bytes = (ROOT / "backend/scripts/source_free_sdk_probe.py").read_bytes()
    if digest(probe_bytes) != expected_tool_digests["source_free_sdk_probe.py"]:
        raise ValueError("release_tool_digest_mismatch")
    identity(trust["source"])
    if trust["source"] != revision:
        raise ValueError("wheel_source_identity")
    if (
        trust["schema"] != "sdk-origin-v1"
        or trust["filename"] != wheel.name
        or trust["name"] != "personal-ai-sdk"
        or trust["version"] != "0.1.0"
        or not isinstance(trust["origin"], str)
        or not 1 <= len(trust["origin"]) <= 256
    ):
        raise ValueError("operator_pins")
    inspection = inspect_wheel(wheel, trust["sha256"])
    uv = str(Path(uv).resolve(strict=True))
    closed(trust["tools"], "uv_sha256 python_sha256")
    if trust["tools"] != {
        "uv_sha256": digest(Path(uv).read_bytes()),
        "python_sha256": digest(Path(sys.executable).read_bytes()),
    }:
        raise ValueError("untrusted_install_toolchain")
    with tempfile.TemporaryDirectory(prefix="unrelated-sdk-consumer-") as tmp:
        root = Path(tmp)
        env = clean_env(root)
        prefix = native_fence(root, env)
        # Copy the inspected bytes: pin again immediately before installation.
        artifact = root / wheel.name
        shutil.copyfile(wheel, artifact)
        inspect_wheel(artifact, trust["sha256"])
        target = root / "environment"
        venv.EnvBuilder(with_pip=False).create(target)
        python = target / "bin/python"
        run(
            [
                *prefix,
                uv,
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--python",
                str(python),
                str(artifact),
            ],
            root,
            env,
        )
        site = next((target / "lib").glob("python*/site-packages"))
        actual = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
        expected = set(inspection["members"])
        permitted = expected | {
            "personal_ai_sdk-0.1.0.dist-info/INSTALLER",
            "personal_ai_sdk-0.1.0.dist-info/REQUESTED",
            "personal_ai_sdk-0.1.0.dist-info/direct_url.json",
            "personal_ai_sdk-0.1.0.dist-info/uv_cache.json",
        }
        if actual - permitted:
            raise ValueError("installed_hooks_or_dependency_leak")
        for name, pin in inspection["members"].items():
            if not name.endswith("/RECORD") and digest((site / name).read_bytes()) != pin:
                raise ValueError("installed_member_digest")
        probe_path = root / "consumer.py"
        probe_path.write_bytes(probe_bytes)
        run([*prefix, str(python), "-I", str(probe_path)], root, env)
    final_checkout = checkout_state()
    if (
        source() != revision
        or not final_checkout["clean"]
        or release_tool_digests() != expected_tool_digests
    ):
        raise ValueError("source_changed")
    return {
        "schema": "source-free-install-v1",
        "status": "NON_ACCEPTANCE",
        "synthetic_install": "PASS",
        "acceptance": "BLOCKED",
        "tier": "E2",
        "source": revision,
        "checkout": final_checkout,
        "tool_digests": actual_tool_digests,
        "wheel": inspection,
        "origin": "OPERATOR_PIN_SUPPLIED",
        "identity": "BLOCKED: installed signed server not exercised",
        "protocol": "E1 synthetic HTTP transport; no sockets or real issuer",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["build", "install"])
    parser.add_argument("--uv", required=True, type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--pins", type=Path)
    parser.add_argument("--expected-commit")
    parser.add_argument("--expected-tree")
    parser.add_argument("--tool-digests", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "install" and (
            args.wheel is None
            or args.pins is None
            or args.expected_commit is None
            or args.expected_tree is None
            or args.tool_digests is None
        ):
            raise ValueError("operator_source_tool_pins_required")
        expected_source = None
        expected_tools = None
        if args.mode == "install":
            from release_profiles import read_json

            expected_source = {"commit": args.expected_commit, "tree": args.expected_tree}
            with args.tool_digests.open("rb") as handle:
                expected_tools = read_json(handle.read(262145))
        result = (
            repeat_build(args.uv)
            if args.mode == "build"
            else install(
                args.wheel.absolute(),
                args.pins,
                args.uv,
                expected_source=expected_source,
                expected_tool_digests=expected_tools,
            )
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ):
        print('{"status":"BLOCKED","reason":"artifact_or_native_prerequisite_failed"}')
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
