"""Offline client-only installation from the built wheels and rebuilt sdists."""

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = (ROOT / "sdk/python", ROOT / "examples/project-checklist/client")
PROBE = """
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from personal_ai_sdk import Client
from project_checklist.store import Checklist

for name in ('personal_ai', 'personal_ai_reference_apps', 'reading_logbook',
             'reading_logbook_host', 'project_checklist_host'):
    assert importlib.util.find_spec(name) is None, name
for name in ('personal_ai_sdk', 'project_checklist'):
    assert Path(importlib.util.find_spec(name).origin).is_relative_to(sys.prefix)
client = Client('https://example.invalid', 'synthetic', application='project_checklist')
assert client.diagnostics()['contract_version'] == '1.2.0'
cli = str(Path(sys.executable).with_name('project-checklist'))
assert json.loads(subprocess.check_output([cli, 'preflight']))['token_configured'] is False
subprocess.run([cli, 'add', 'Check the drawings'], check=True, capture_output=True)
subprocess.run([cli, 'finish', '1'], check=True, capture_output=True)
assert Checklist(Path('checklist.sqlite')).items() == [(1, 'Check the drawings', 1)]
"""


def only(directory: Path, pattern: str) -> Path:
    (result,) = directory.glob(pattern)
    return result


def main() -> None:
    uv = sys.argv[1] if len(sys.argv) == 2 else "uv"
    with tempfile.TemporaryDirectory(prefix="hxe0-artifacts-") as tmp:
        root = Path(tmp)
        env = {
            "PATH": os.environ["PATH"],
            "TMPDIR": str(root),
            "UV_CACHE_DIR": str(root / "uv-cache"),
            "UV_OFFLINE": "1",
            "PYTHONNOUSERSITE": "1",
        }

        def run(args, cwd=root):
            subprocess.run(args, cwd=cwd, env=env, check=True)

        rebuilt = root / "rebuilt"
        for package in PACKAGES:
            sdist = only(package / "dist", "*.tar.gz")
            run(
                [
                    uv,
                    "build",
                    "--wheel",
                    "--no-build-isolation",
                    "--python",
                    sys.executable,
                    "--out-dir",
                    str(rebuilt),
                    str(sdist),
                ]
            )
        for mode, wheels in (
            ("wheel", [only(package / "dist", "*.whl") for package in PACKAGES]),
            ("sdist", sorted(rebuilt.glob("*.whl"))),
        ):
            assert len(wheels) == len(PACKAGES)
            work = root / mode
            python = work / "bin/python"
            venv.EnvBuilder(with_pip=False).create(work)
            run(
                [
                    uv,
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    "--python",
                    str(python),
                    *map(str, wheels),
                ]
            )
            run([str(python), "-I", "-c", PROBE], cwd=work)
            print(f"HXE0_CLIENT_INSTALL={mode}:PASS", flush=True)


if __name__ == "__main__":
    main()
