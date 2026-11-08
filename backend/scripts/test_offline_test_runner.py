"""Scoped negative checks for the shared hermetic test entrypoint."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/scripts/offline_test_runner.py"
MAKEFILE = ROOT / "Makefile"

FENCED_TARGETS = (
    "hermetic-fence-check",
    "reasoning-check",
    "reasoning-orchestrator-check",
    "reasoning-grounded-check",
    "reasoning-adaptive-check",
    "reasoning-adaptive-conformance",
    "synthetic-reasoning-check",
    "memory-episode-check",
    "memory-consolidation-check",
    "memory-navigation-check",
    "memory-research-check",
    "memory-governance-check",
    "workflow-check",
)


def _recipe(target: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:\n((?:\t.*\n)+)", MAKEFILE.read_text(), re.MULTILINE
    )
    assert match, f"missing Make target recipe: {target}"
    return match.group(1)


def test_forbidden_socket_attempt_fails_the_fenced_entrypoint(tmp_path):
    probe = tmp_path / "test_forbidden_egress.py"
    probe.write_text(
        "import socket\n\n"
        "def test_forbidden_egress():\n"
        "    socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER), "-q", str(probe)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 3, (result.returncode, result.stdout, result.stderr)
    assert re.search(r"OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=[1-9]\d*", result.stdout), (
        result.stdout
    )
    assert "PermissionError" in result.stdout + result.stderr


def test_grounded_replay_clock_only_wraps_the_sealed_study(tmp_path):
    probe = tmp_path / "test_reasoning_grounded.py"
    probe.write_text(
        "import sys, time, types\n"
        "clock = types.ModuleType('personal_ai.clock_probe')\n"
        "clock.monotonic = time.monotonic\n"
        "sys.modules[clock.__name__] = clock\n\n"
        "def test_sealed_evaluation():\n"
        "    assert clock.monotonic() == 1000.0\n\n"
        "def test_real_deadline_behavior_remains_live():\n"
        "    before = clock.monotonic()\n"
        "    time.sleep(0.01)\n"
        "    assert clock.monotonic() > before\n",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER), "-q", str(probe)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "2 passed" in result.stdout
    assert "OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=0" in result.stdout


@pytest.mark.parametrize("target", FENCED_TARGETS)
def test_hermetic_targets_route_through_the_network_fence(target):
    recipe = _recipe(target)
    if target == "reasoning-adaptive-conformance":
        assert "replay_adaptive_history.py --conformance" in recipe
        script = (ROOT / "backend/scripts/replay_adaptive_history.py").read_text()
        assert "offline_test_runner.py" in script
    else:
        assert "offline_test_runner.py" in recipe, target


def test_direct_adaptive_conformance_replay_uses_the_network_fence():
    script = (ROOT / "backend/scripts/replay_adaptive_history.py").read_text()
    assert "offline_test_runner.py" in script
