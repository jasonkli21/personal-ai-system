"""Check active paths and visible labels for implementation milestone names."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASE_PATH = re.compile(r"(?:^|[/._-])(?:pi|hxe|mem|phase)[-_]?\d+", re.IGNORECASE)
PHASE_TEXT = re.compile(r"\b(?:phase\s*\d+|PI-\d+|MEM-\d+|HXE-\d+)\b", re.IGNORECASE)
FROZEN_PATHS = {
    "backend/tests/test_pi6.py",
    "backend/scripts/pi6_checks.py",
    "backend/scripts/pi6_installed_checks.py",
    "backend/src/personal_ai/evaluation/pi6.py",
    "backend/src/personal_ai/evaluation/pi6_audit.py",
    "backend/src/personal_ai/evaluation/pi6_contracts.py",
    "backend/src/personal_ai/evaluation/pi6_driver.py",
    "backend/src/personal_ai/evaluation/pi6_http.py",
    "backend/src/personal_ai/evaluation/pi6_scoring.py",
}
VISIBLE_TEXT_PATHS = (
    "frontend/src",
    "adapters/mcp_source/README.md",
    "adapters/mcp_source/pyproject.toml",
    "Makefile",
    "README.md",
)


def active_paths() -> list[str]:
    matches: list[str] = []
    for base in (ROOT / "backend", ROOT / "adapters", ROOT / "infrastructure"):
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in FROZEN_PATHS or "/fixtures/pi6/" in f"/{relative}/" or "/fixtures/memory/" in f"/{relative}/":
                continue
            if PHASE_PATH.search(relative):
                matches.append(relative)
    return matches


def visible_text() -> list[str]:
    errors: list[str] = []
    for name in VISIBLE_TEXT_PATHS:
        target = ROOT / name
        paths = target.rglob("*") if target.is_dir() else (target,)
        for path in paths:
            if not path.is_file():
                continue
            try:
                content = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for line_number, line in enumerate(content.splitlines(), 1):
                if PHASE_TEXT.search(line):
                    errors.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    return errors


def main() -> int:
    paths = active_paths()
    labels = visible_text()
    if paths or labels:
        for item in paths:
            print(f"phase-coded active path: {item}", file=sys.stderr)
        for item in labels:
            print(f"phase-coded visible text: {item}", file=sys.stderr)
        return 1
    print("NAMING_POLICY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
