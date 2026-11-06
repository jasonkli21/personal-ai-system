"""Inert wheel tamper checks and source-free synthetic consumer conformance."""

import io
import json
import signal
import subprocess
import sys
import tempfile
import time
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
    release_tool_digests,
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

    def test_dirty_checkout_stops_before_installer(self):
        pin = self.write()
        pins = self.root / "pins.json"
        pins.write_text(
            json.dumps(
                {
                    "schema": "sdk-origin-v1",
                    "source": source(),
                    "origin": "synthetic-operator-fixture",
                    "filename": self.wheel.name,
                    "sha256": pin,
                    "name": "personal-ai-sdk",
                    "version": "0.1.0",
                    "tools": {"uv_sha256": "a" * 64, "python_sha256": "b" * 64},
                }
            )
        )
        with (
            patch("release_artifacts.checkout_state", return_value={"clean": False}),
            patch("release_artifacts.native_fence") as fence,
            self.assertRaisesRegex(ValueError, "dirty_checkout"),
        ):
            install(
                self.wheel,
                pins,
                Path(sys.executable),
                expected_source=source(),
                expected_tool_digests=release_tool_digests(),
            )
        fence.assert_not_called()

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
            patch("release_artifacts.checkout_state", return_value={"clean": True}),
            patch("release_artifacts.native_fence") as fence,
            self.assertRaisesRegex(ValueError, "untrusted_install_toolchain"),
        ):
            install(
                self.wheel,
                pins,
                Path(sys.executable),
                expected_source=source(),
                expected_tool_digests=release_tool_digests(),
            )
        fence.assert_not_called()

    def test_install_requires_exact_external_source_and_tooling_pins(self):
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
        expected_tools = release_tool_digests()
        wrong_source = {**source(), "tree": "0" * 40}
        with patch("release_artifacts.native_fence") as fence:
            with self.assertRaisesRegex(ValueError, "expected_source_mismatch"):
                install(
                    self.wheel,
                    pins,
                    Path(sys.executable),
                    expected_source=wrong_source,
                    expected_tool_digests=expected_tools,
                )
            for name in ("source_free_sdk_probe.py", "release_artifacts.py"):
                altered = {**expected_tools, name: "0" * 64}
                with (
                    patch("release_artifacts.checkout_state", return_value={"clean": True}),
                    self.assertRaisesRegex(ValueError, "release_tool_digest_mismatch"),
                ):
                    install(
                        self.wheel,
                        pins,
                        Path(sys.executable),
                        expected_source=source(),
                        expected_tool_digests=altered,
                    )
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
        with (
            patch("sys.argv", ["release-preflight", "--measure-synthetic"]),
            patch("release_preflight.bounded_run", side_effect=RuntimeError("control unavailable")),
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(preflight(), 3)
        measurement = json.loads(output.getvalue())["measurement"]
        self.assertEqual(measurement["status"], "BLOCKED")
        self.assertEqual(measurement["resource_envelope"]["e2_resource_status"], "BLOCKED")

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
        self.assertIsNone(result["per_invocation_peak_rss_bytes"])
        self.assertEqual(result["resource_envelope"]["e2_resource_status"], "BLOCKED")
        expected_as = "ENFORCED" if sys.platform.startswith("linux") else "UNAVAILABLE_ON_HOST"
        self.assertEqual(result["resource_envelope"]["address_space_limit_status"], expected_as)
        result = bounded_run(
            [sys.executable, "-I", "-c", "print('x'*5000000)"], cwd=self.root, env=env, timeout=5
        )
        self.assertTrue(result["output_cap_reached"])
        self.assertEqual(result["output_bytes"], 4_000_000)

    def test_stdout_observations_are_explicitly_untrusted(self):
        result = bounded_run(
            [
                sys.executable,
                "-I",
                "-c",
                "print('999 passed'); print('OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=0'); print('{\"protocol\":\"PASS\"}')",
            ],
            cwd=self.root,
            env=clean_env(self.root),
            timeout=5,
        )
        self.assertEqual(result["exit"], 0)
        self.assertEqual(result["test_counts_display_untrusted"], {"passed": 999})
        self.assertEqual(result["reported_network_attempts_display_untrusted"], 0)
        self.assertNotIn("test_counts", result)
        self.assertNotIn("python_network_attempts", result)

    def test_child_observes_declared_finite_limits_and_resource_gate_stays_blocked(self):
        code = (
            "import resource, sys; "
            "assert resource.getrlimit(resource.RLIMIT_FSIZE)[0] == 4000000; "
            "assert resource.getrlimit(resource.RLIMIT_CPU)[0] == 120; "
            "data=bytearray(2_000_000)"
        )
        result = bounded_run(
            [sys.executable, "-I", "-c", code],
            cwd=self.root,
            env=clean_env(self.root),
            timeout=5,
        )
        self.assertEqual(result["exit"], 0)
        self.assertEqual(result["resource_envelope"]["e2_resource_status"], "BLOCKED")

    def test_supervisor_signal_stops_owned_child_group(self):
        for number in (signal.SIGTERM, signal.SIGINT):
            pid_file = self.root / f"pids-{number}"
            child_marker = self.root / f"child-stopped-{number}"
            grandchild_marker = self.root / f"grandchild-stopped-{number}"
            grandchild_ready = self.root / f"grandchild-ready-{number}"
            grandchild = (
                "import pathlib, signal, time\n"
                "def stop(*_):\n"
                f"    pathlib.Path({str(grandchild_marker)!r}).write_text('stopped')\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGTERM, stop)\n"
                f"pathlib.Path({str(grandchild_ready)!r}).write_text('ready')\n"
                "time.sleep(60)"
            )
            child = (
                "import os, pathlib, signal, subprocess, sys, time\n"
                "def stop(*_):\n"
                f"    pathlib.Path({str(child_marker)!r}).write_text('stopped')\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGTERM, stop)\n"
                f"p=subprocess.Popen([sys.executable, '-I', '-c', {grandchild!r}])\n"
                f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()) + ',' + str(p.pid))\n"
                "time.sleep(60)"
            )
            supervisor = (
                "import sys; sys.path.insert(0, 'backend/scripts'); "
                "from release_process import bounded_run; "
                f"import json; print(json.dumps(bounded_run([sys.executable, '-I', '-c', {child!r}], "
                f"cwd={str(self.root)!r}, env={clean_env(self.root)!r}, timeout=30)))"
            )
            proc = subprocess.Popen(
                [sys.executable, "-I", "-c", supervisor], cwd=ROOT, stdout=subprocess.PIPE
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not grandchild_ready.exists():
                time.sleep(0.01)
            self.assertTrue(
                pid_file.exists() and grandchild_ready.exists(), "process tree did not start"
            )
            self.assertEqual(len(pid_file.read_text().split(",")), 2)
            proc.send_signal(number)
            output, _ = proc.communicate(timeout=3)
            self.assertEqual(proc.returncode, 0, output.decode(errors="replace"))
            result = json.loads(output)
            self.assertIn(result["process_group_cleanup"], {"STOPPED", "BLOCKED_SIGNAL_PERMISSION"})
            self.assertTrue(child_marker.exists(), "owned child did not receive TERM")
            self.assertTrue(grandchild_marker.exists(), "owned grandchild did not receive TERM")

    def test_concurrent_supervisors_do_not_signal_each_others_groups(self):
        def launch(name):
            ready = self.root / f"{name}-ready"
            stopped = self.root / f"{name}-stopped"
            child = (
                "import pathlib, signal, time\n"
                "def stop(*_):\n"
                f"    pathlib.Path({str(stopped)!r}).write_text('stopped')\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGTERM, stop)\n"
                f"pathlib.Path({str(ready)!r}).write_text('ready')\n"
                "time.sleep(60)"
            )
            supervisor = (
                "import sys; sys.path.insert(0, 'backend/scripts'); "
                "from release_process import bounded_run; "
                f"bounded_run([sys.executable, '-I', '-c', {child!r}], "
                f"cwd={str(self.root)!r}, env={clean_env(self.root)!r}, timeout=30)"
            )
            process = subprocess.Popen([sys.executable, "-I", "-c", supervisor], cwd=ROOT)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not ready.exists():
                time.sleep(0.01)
            self.assertTrue(ready.exists(), f"{name} child did not start")
            return process, stopped

        first, first_stopped = launch("first")
        second, second_stopped = launch("second")
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=3)
        self.assertTrue(first_stopped.exists())
        self.assertFalse(second_stopped.exists())
        second.send_signal(signal.SIGTERM)
        second.wait(timeout=3)
        self.assertTrue(second_stopped.exists())


if __name__ == "__main__":
    unittest.main()
