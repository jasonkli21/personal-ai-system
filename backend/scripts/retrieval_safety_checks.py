"""Bounded retrieval checks under native offline and Python loopback fences."""

import subprocess
import sys
from pathlib import Path

from provider_isolation_checks import main

FILES = [
    "test_retrieval_integrations.py",
    "test_retrieval_context.py",
    "test_research_provider.py",
    "test_research_pipeline.py",
    "test_retrieval_query_planning.py",
]

if __name__ == "__main__":
    result = main(files=FILES, runner=__file__)
    if result == 0 and "--fenced" not in sys.argv:
        root = Path(__file__).resolve().parents[2]
        result = subprocess.call(
            [
                sys.executable,
                str(root / "backend/scripts/signed_http_checks.py"),
                "-q",
                "--tb=short",
                str(root / "backend/tests/test_retrieval_http.py"),
            ],
            cwd=root,
        )
    raise SystemExit(result)
