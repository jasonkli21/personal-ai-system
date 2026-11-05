"""Launch the sealed v2 fake-only evaluation from the repository checkout."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def main() -> int:
    if (ROOT / ".env").exists() or (ROOT / "backend/.env").exists():
        raise SystemExit("reasoning_eval_refuses_local_env")
    git = lambda *args: subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=5).strip()
    command = [
        sys.executable, "-B", "-m", "personal_ai.evaluation.reasoning_v2.reasoning_baseline",
        "--commit", git("rev-parse", "HEAD"), "--tree", git("rev-parse", "HEAD^{tree}"),
        "--dirty", "yes" if git("status", "--short", "--", "backend/src/personal_ai/evaluation/reasoning_v2") else "no",
    ]
    env = {"PATH": os.defpath, "PYTHONPATH": str(ROOT / "backend/src"), "PYTHONNOUSERSITE": "1"}
    return subprocess.run(command, cwd=ROOT, env=env, timeout=30, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
