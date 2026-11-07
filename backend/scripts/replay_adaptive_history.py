"""Run the historical adaptive experiment or the sealed development controls."""

import json
import os
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = "992118dd43cf7225541b1eb9866374a79fa6ec58"

HISTORICAL_CONFORMANCE_SEAL = "dc525f49295aade18e58c243ec60519b1a371c6d9b7ed89640a1a81f612ad0f1"
CONFORMANCE_SEAL = "103e2973aefc05d59df78acb3b779cdd602ad86c9eead963c12e141841c10bf5"
HISTORICAL_CONFORMANCE_MANIFEST = (
    ROOT / "backend/evaluation/adaptive-development-conformance-v1.json"
)
CONFORMANCE_MANIFEST = ROOT / "backend/evaluation/adaptive-development-conformance-v2.json"


def conformance():
    historical = HISTORICAL_CONFORMANCE_MANIFEST.read_bytes()
    if sha256(historical).hexdigest() != HISTORICAL_CONFORMANCE_SEAL:
        raise ValueError("adaptive_historical_conformance_manifest_changed")
    raw = CONFORMANCE_MANIFEST.read_bytes()
    if sha256(raw).hexdigest() != CONFORMANCE_SEAL:
        raise ValueError("adaptive_conformance_manifest_changed")
    manifest = json.loads(raw)
    if (
        manifest.get("version") != "adaptive-development-source-identity-v2"
        or manifest.get("supersedes_sha256") != HISTORICAL_CONFORMANCE_SEAL
    ):
        raise ValueError("adaptive_conformance_migration_invalid")
    if any(
        sha256((ROOT / path).read_bytes()).hexdigest() != expected
        for path, expected in manifest["sources"].items()
    ):
        raise ValueError("adaptive_conformance_source_changed")
    print(
        json.dumps(
            {
                "protocol": manifest["protocol"],
                "custody": manifest["custody"],
                "promotion": manifest["promotion"],
                "source_seal_sha256": CONFORMANCE_SEAL,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    os.chdir(ROOT)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-B",
            "backend/scripts/offline_test_runner.py",
            "-q",
            "backend/tests/test_reasoning_adaptive.py",
        ],
    )


def main():
    with tempfile.TemporaryDirectory(prefix="adaptive-history-") as tmp:
        with subprocess.Popen(
            ["git", "archive", REVISION],
            cwd=ROOT,
            stdout=subprocess.PIPE,
        ) as archive:
            subprocess.run(["tar", "-x", "-C", tmp], stdin=archive.stdout, check=True)
            if archive.wait() != 0:
                raise RuntimeError("historical_adaptive_revision_unavailable")
        env = {**os.environ, "PYTHONPATH": str(Path(tmp) / "backend/src")}
        subprocess.run(
            [
                sys.executable,
                "-B",
                "backend/scripts/offline_test_runner.py",
                "-qs",
                "backend/tests/test_reasoning_adaptive.py",
                "-k",
                "sealed_evaluation",
            ],
            cwd=tmp,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    if sys.argv[1:] == ["--conformance"]:
        conformance()
    else:
        main()
