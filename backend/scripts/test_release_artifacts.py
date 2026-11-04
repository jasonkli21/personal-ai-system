"""Inert wheel tamper checks and source-free synthetic consumer conformance."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
import venv
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from release_artifacts import (
    ROOT,
    SDK_FILES,
    clean_env,
    digest,
    inspect_wheel,
    install,
    native_fence,
    source,
)
from release_preflight import main as preflight
from release_process import bounded_run


class ArtifactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="artifact-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wheel = self.root / "personal_ai_sdk-0.1.0-py3-none-any.whl"
        prefix = "personal_ai_sdk-0.1.0.dist-info/"
        self.members = {"personal_ai_sdk/" + name: b"" for name in SDK_FILES}
        self.members.update(
            {
                prefix
                + "METADATA": b"Name: personal-ai-sdk\nVersion: 0.1.0\nLicense-Expression: Apache-2.0\n",
                prefix + "WHEEL": b"Wheel-Version: 1.0\n",
                prefix + "RECORD": b"",
                prefix + "licenses/LICENSE": b"Apache License Version 2.0",
            }
        )

    def write(self):
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for name, raw in self.members.items():
                archive.writestr(name, raw)
        return digest(self.wheel.read_bytes())

    def test_closed_sdk_inventory(self):
        result = inspect_wheel(self.wheel, self.write())
        self.assertEqual(result["runtime_dependencies"], [])

    def test_tampered_unpinned_and_symlink_wheels(self):
        pin = self.write()
        with self.wheel.open("ab") as handle:
            handle.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "wheel_digest"):
            inspect_wheel(self.wheel, pin)
        alias = self.root / "alias.whl"
        alias.symlink_to(self.wheel)
        with self.assertRaisesRegex(ValueError, "wheel_size_or_type"):
            inspect_wheel(alias, digest(self.wheel.read_bytes()))

    def test_hooks_extra_packages_paths_and_dependencies_denied(self):
        original = self.members.copy()
        changes = [
            {"evil.pth": b"import os"},
            {"sitecustomize.py": b""},
            {"usercustomize.py": b""},
            {"../outside.py": b""},
            {"personal_ai/__init__.py": b""},
            {"personal_ai_sdk-0.1.0.dist-info/entry_points.txt": b""},
            {
                "personal_ai_sdk-0.1.0.dist-info/METADATA": b"Name: personal-ai-sdk\nVersion: 0.1.0\nLicense-Expression: Apache-2.0\nRequires-Dist: evil\n"
            },
        ]
        for change in changes:
            self.members = {**original, **change}
            pin = self.write()
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                inspect_wheel(self.wheel, pin)

    def test_unknown_name_version_and_license_denied(self):
        key = "personal_ai_sdk-0.1.0.dist-info/METADATA"
        original = self.members[key]
        for old, new in [
            (b"personal-ai-sdk", b"other"),
            (b"0.1.0", b"0.2.0"),
            (b"Apache-2.0", b"UNKNOWN"),
        ]:
            self.members[key] = original.replace(old, new)
            pin = self.write()
            with self.assertRaisesRegex(ValueError, "wheel_metadata"):
                inspect_wheel(self.wheel, pin)

    def test_untrusted_tool_pin_stops_before_installer(self):
        pin = self.write()
        trust = {
            "schema": "sdk-origin-v1",
            "source": source(),
            "origin": "synthetic-operator-fixture",
            "filename": self.wheel.name,
            "sha256": pin,
            "name": "personal-ai-sdk",
            "version": "0.1.0",
            "tools": {"uv_sha256": "a" * 64, "python_sha256": "b" * 64},
        }
        pins = self.root / "pins.json"
        pins.write_text(json.dumps(trust))
        with (
            patch("release_artifacts.native_fence") as fence,
            self.assertRaisesRegex(ValueError, "untrusted_install_toolchain"),
        ):
            install(self.wheel, pins, Path(sys.executable))
        fence.assert_not_called()

    def test_native_fence_has_no_degraded_success(self):
        with (
            patch("release_artifacts.sys.platform", "unsupported"),
            self.assertRaisesRegex(ValueError, "native_fence_unsupported"),
        ):
            native_fence(self.root, clean_env(self.root))
        with (
            patch("release_artifacts.sys.platform", "darwin"),
            patch("release_artifacts.run", side_effect=ValueError("denied")),
            self.assertRaises(ValueError),
        ):
            native_fence(self.root, clean_env(self.root))

    def test_source_free_protocol_and_source_import_negative(self):
        # E1 simulated installed layout, not native installation acceptance.
        target = self.root / "environment"
        venv.EnvBuilder(with_pip=False).create(target)
        python = target / "bin/python"
        site = next((target / "lib").glob("python*/site-packages"))
        sdk = site / "personal_ai_sdk"
        sdk.mkdir()
        for name in SDK_FILES:
            (sdk / name).write_bytes((ROOT / "sdk/python/src/personal_ai_sdk" / name).read_bytes())
        probe = self.root / "unrelated.py"
        probe.write_bytes((ROOT / "backend/scripts/source_free_sdk_probe.py").read_bytes())
        command = [str(python), "-I", str(probe)]
        result = subprocess.run(
            command,
            cwd=self.root,
            env=clean_env(self.root),
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout)["network_attempts"], 0)
        (site / "personal_ai.py").write_text("raise RuntimeError('must not import')")
        result = subprocess.run(
            command,
            cwd=self.root,
            env=clean_env(self.root),
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_preflight_distinguishes_regression_from_missing_evidence(self):
        for child_exit, expected_exit in ((0, 3), (1, 1)):
            measured = {"exit": child_exit, "timed_out": False, "output_cap_reached": False}
            with (
                patch("sys.argv", ["release-preflight", "--measure-synthetic"]),
                patch("release_preflight.bounded_run", return_value=measured),
                redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(preflight(), expected_exit)
            self.assertEqual(json.loads(output.getvalue())["scorecard"]["release"], "NO_GO")

    def test_measurement_timeout_and_output_are_bounded(self):
        env = clean_env(self.root)
        result = bounded_run(
            [sys.executable, "-I", "-c", "import time; time.sleep(5)"],
            cwd=self.root,
            env=env,
            timeout=0.05,
        )
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["exit"], 0)
        result = bounded_run(
            [sys.executable, "-I", "-c", "print('x'*5000000)"], cwd=self.root, env=env, timeout=5
        )
        self.assertTrue(result["output_cap_reached"])
        self.assertLessEqual(result["output_bytes"], 4_000_000)


if __name__ == "__main__":
    unittest.main()
