"""Bounded PI-5 checks under native offline and Python loopback fences."""

import subprocess
import sys
from pathlib import Path

from pi3_checks import main

FILES = [
    "test_pi5_retrieval.py",
    "test_research_provider.py",
    "test_research_pipeline.py",
    "test_retrieval_phase33.py",
]

if __name__ == "__main__":
    result = main(files=FILES, runner=__file__)
    if result == 0 and "--fenced" not in sys.argv:
        root = Path(__file__).resolve().parents[2]
        result = subprocess.call(
            [
                sys.executable,
                str(root / "backend/scripts/pi2_http_checks.py"),
                "-q",
                "--tb=short",
                str(root / "backend/tests/test_pi5_http.py"),
            ],
            cwd=root,
        )
    raise SystemExit(result)
