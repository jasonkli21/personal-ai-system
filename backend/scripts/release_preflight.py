"""Read-only preflight and explicitly opted-in bounded synthetic measurement."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from release_artifacts import ROOT, checkout_state, clean_env, source
from release_process import bounded_run
from release_profiles import PROFILES, canonical, template, validate

CANARY = [
    "backend/tests/test_inference_execution.py",
    "backend/tests/test_retrieval_context.py",
    "backend/tests/test_retrieval_integrations.py",
    "backend/tests/test_provider_usage.py",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="offline_development")
    parser.add_argument("--measure-synthetic", action="store_true")
    args = parser.parse_args()
    revision = source()
    manifest = template(revision, args.profile, platform.python_version())
    result = {
        "schema": "release-preflight-v1",
        "manifest": manifest,
        "checkout": checkout_state(),
        "scorecard": validate(manifest, expected=revision, trusted={}, receipts={}),
        "environment": {
            "os": sys.platform,
            "architecture": platform.machine(),
            "os_release": platform.release(),
            "macos_version": platform.mac_ver()[0] or None,
            "python": platform.python_version(),
        },
        "real_task": {
            "status": "BLOCKED",
            "required": [
                "operator-approved pinned native llama.cpp and GGUF hash",
                "effective native egress fence",
                "disposable migrated store",
                "synthetic source and finite resource envelope",
                "independent review",
            ],
        },
        "network": "no application execution by default",
        "measurement": None,
    }
    if args.measure_synthetic:
        with tempfile.TemporaryDirectory(prefix="release-canary-") as tmp:
            env = clean_env(Path(tmp))
            env.update(
                {
                    "AI_PROVIDER": "fake",
                    "APP_ENVIRONMENT": "test",
                    "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                }
            )
            argv = [
                sys.executable,
                "-E",
                "-s",
                "backend/scripts/offline_test_runner.py",
                "-q",
                "--tb=short",
                *CANARY,
            ]
            try:
                result["measurement"] = bounded_run(argv, cwd=ROOT, env=env)
            except (OSError, RuntimeError, subprocess.SubprocessError, ValueError):
                result["measurement"] = {
                    "status": "BLOCKED",
                    "reason": "bounded_runner_or_resource_control_unavailable",
                    "tier": "E1",
                    "resource_envelope": {"e2_resource_status": "BLOCKED"},
                }
            result["measurement"].update(
                {
                    "tier": "E1",
                    "concurrency": 1,
                    "attempts": 1,
                    "setup_seconds": None,
                    "idle_cpu": None,
                    "idle_ram": None,
                    "ttft": None,
                    "model_requests": None,
                    "tokens": None,
                    "scope": "canonical synthetic tests only; no real model utility measurement",
                }
            )
    print(canonical(result).decode())
    # Product/test failures differ from missing release prerequisites.
    measured = result["measurement"]
    if measured and measured.get("status") != "BLOCKED" and (
        measured["exit"] or measured["timed_out"] or measured["output_cap_reached"]
    ):
        return 1
    # Missing evidence is never converted into readiness by a successful test.
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
