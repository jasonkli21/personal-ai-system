"""Run the frozen fake-only benchmark with a scrubbed environment and deadline."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEATBELT = [
    "/usr/bin/sandbox-exec",
    "-p",
    "(version 1)(allow default)(deny network*)",
]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=5).strip()


def main():
    if (ROOT / ".env").exists() or (ROOT / "backend/.env").exists():
        raise SystemExit("reasoning_eval_refuses_local_env")
    command = [
        sys.executable,
        "-B",
        "-m",
        "personal_ai.evaluation.reasoning_baseline",
        "--commit",
        git("rev-parse", "HEAD"),
        "--tree",
        git("rev-parse", "HEAD^{tree}"),
        "--dirty",
        "yes" if git("status", "--short") else "no",
    ]
    env = {"PATH": os.defpath, "PYTHONPATH": str(ROOT / "backend/src"), "PYTHONNOUSERSITE": "1"}
    try:
        if (
            sys.platform == "darwin"
            and subprocess.run(
                [*SEATBELT, "/usr/bin/true"],
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            ).returncode
            == 0
        ):
            command = [*SEATBELT, *command, "--native-fence"]
        return subprocess.run(command, cwd=ROOT, env=env, timeout=30, check=False).returncode
    except subprocess.TimeoutExpired:
        print("reasoning_eval_process_deadline", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
