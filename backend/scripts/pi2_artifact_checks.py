"""PI-1 regressions, then independently built PI-2 server/host/client profiles.

No downloads. Reuse existing dependency files but no .pth/editable hooks, as PI-1.
The client-only interpreter has only the stdlib and its installed client wheel.
"""

import hashlib
import json
import runpy
import shutil
import subprocess
import tarfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
state = runpy.run_path(str(ROOT / "backend/scripts/pi1_artifact_checks.py"))
workspace, python, env, uv = (state[k] for k in ("workspace", "python", "env", "uv"))
client_env = workspace / "client-only"
venv.EnvBuilder(with_pip=False).create(client_env)
client_python = client_env / "bin/python"
artifacts = []
for kind in ("client", "host"):
    directory = ROOT / "examples/reading-logbook" / kind
    files = sorted(
        f
        for f in (directory / "dist").iterdir()
        if f.suffix == ".whl" or f.name.endswith(".tar.gz")
    )
    assert len(files) == 2
    for artifact in files:
        with (
            zipfile.ZipFile(artifact) if artifact.suffix == ".whl" else tarfile.open(artifact)
        ) as archive:
            names = archive.namelist() if artifact.suffix == ".whl" else archive.getnames()
            assert not any(
                "personal_ai/" in name or "personal_ai_reference_apps" in name for name in names
            )
            meta = next(
                n
                for n in names
                if n.endswith("/METADATA" if artifact.suffix == ".whl" else "/PKG-INFO")
            )
            raw = (
                archive.read(meta)
                if artifact.suffix == ".whl"
                else archive.extractfile(meta).read()
            )
            requires = [
                line for line in raw.decode().splitlines() if line.startswith("Requires-Dist:")
            ]
            assert requires == (
                [] if kind == "client" else ["Requires-Dist: personal-ai-backend==0.1.0"]
            )
            # No hidden source imports/sys.path hooks in the HTTP-only distribution.
            if kind == "client":
                for name in names:
                    if name.endswith(".py"):
                        source = (
                            archive.read(name)
                            if artifact.suffix == ".whl"
                            else archive.extractfile(name).read()
                        )
                        assert all(
                            term not in source
                            for term in (b"personal_ai", b"sys.path", b"PYTHONPATH")
                        )
        artifacts.append(
            {
                "artifact": str(artifact.relative_to(ROOT)),
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "members": len(names),
                "requires_dist": requires,
            }
        )
    wheel = next(f for f in files if f.suffix == ".whl")
    subprocess.run(
        [uv, "pip", "install", "--python", str(python), "--no-deps", "--no-index", str(wheel)],
        env=env,
        cwd=workspace,
        check=True,
    )
    if kind == "client":
        subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(client_python),
                "--no-deps",
                "--no-index",
                str(wheel),
            ],
            env=env,
            cwd=workspace,
            check=True,
        )
# PI-1 ends with the legacy bundle restored. Physically remove it before PI-2.
subprocess.run(
    [uv, "pip", "uninstall", "--python", str(python), "personal-ai-reference-apps"],
    env=env,
    cwd=workspace,
    check=True,
)
for row in artifacts:
    print(json.dumps(row), flush=True)
subprocess.run(
    [
        str(client_python),
        "-c",
        "import importlib.util,reading_logbook; assert importlib.util.find_spec('personal_ai') is None; assert importlib.util.find_spec('reading_logbook_host') is None; print('CLIENT_ONLY_ORIGIN='+reading_logbook.__file__)",
    ],
    env=env,
    cwd=workspace,
    check=True,
)
probe = workspace / "pi2_origins.py"
probe.write_text("""import importlib.util,sys,json
from pathlib import Path
from importlib.metadata import distribution
import personal_ai,reading_logbook,reading_logbook_host
assert importlib.util.find_spec("personal_ai_reference_apps") is None
modules = [personal_ai,reading_logbook,reading_logbook_host]
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in modules)
assert not any("personal-ai-system" in p for p in sys.path)
print(json.dumps({"origins":[m.__file__ for m in modules],"sys_path":sys.path,
"entry_points":[str(e) for e in distribution("reading-logbook-host").entry_points]}))
from personal_ai.main import create_app
assert create_app(selected_contributions=()).state.application_registry.application_ids == {"personal_ai"}
""")
subprocess.run([str(python), str(probe)], env=env, cwd=workspace, check=True)
test_root = workspace / "pi2"
tests = test_root / "tests"
tests.mkdir(parents=True)
(test_root / "pytest.ini").write_text(
    "[pytest]\nmarkers =\n    loopback_http: synthetic loopback HTTP fixture\n"
)
for name in ("conftest.py", "test_pi2_http.py", "test_pi2_client.py"):
    shutil.copyfile(ROOT / "backend/tests" / name, tests / name)
doc = workspace / "docs/platform-independence"
doc.mkdir(parents=True)
shutil.copyfile(
    ROOT / "docs/platform-independence/consumer-v1.openapi.json", doc / "consumer-v1.openapi.json"
)
runner = workspace / "pi2_http_checks.py"
shutil.copyfile(ROOT / "backend/scripts/pi2_http_checks.py", runner)
client_runner = workspace / "pi2_client_probe.py"
shutil.copyfile(ROOT / "backend/scripts/pi2_client_probe.py", client_runner)
http_env = {
    **env,
    "PI2_INSTALLED": "1",
    "PI2_CLIENT_PYTHON": str(client_python),
    "PI2_CLIENT_RUNNER": str(client_runner),
}
assert "PYTHONPATH" not in http_env
subprocess.run(
    [str(python), str(runner), "-q", str(tests)], env=http_env, cwd=test_root, check=True
)
# Remove new packages; rerun original core probe with neither host nor references.
subprocess.run(
    [
        uv,
        "pip",
        "uninstall",
        "--python",
        str(python),
        "reading-logbook-host",
        "reading-logbook-client",
    ],
    env=env,
    cwd=workspace,
    check=True,
)
subprocess.run([str(python), str(state["probe"])], env=env, cwd=workspace, check=True)
print("PI2_INSTALLED_HTTP_CLIENT_AND_UNINSTALL=PASS", flush=True)
