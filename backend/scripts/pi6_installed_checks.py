"""Exercise the full PI-6 evaluator from installed wheels outside the checkout."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

from pi6_checks import PROFILE

ROOT = Path(__file__).resolve().parents[2]
PROBE = r"""
def main():
 import importlib.util,json,sys
 from pathlib import Path
 from personal_ai.evaluation.pi6 import evaluate
 from personal_ai.evaluation.pi6_contracts import load_corpus
 assert importlib.util.find_spec('personal_ai_reference_apps') is None
 corpus,manifest=load_corpus()
 assert len(corpus.cases)==32
 core=__import__('personal_ai')
 assert Path(core.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
 result=evaluate(require_native=True)
 assert len(result['rows']) == 68
 assert not result['analysis']['safety_veto']
 if manifest['missing_dependencies']:
     assert result['pi6_offline_evaluation']=='changes_required'
     assert result['analysis']['coverage']['non_measured_arms'] > 0
     missing_rows=[row for row in result['rows']
                   if row['observation']['status']!='measured']
     assert any(row['observation']['ineligibility']=='missing_optional_host'
                for row in missing_rows), json.dumps({
                    'missing_dependencies':manifest['missing_dependencies'],
                    'coverage':result['analysis']['coverage'],
                    'non_measured':[{
                        'family':row['family'],'arm':row['arm'],
                        'status':row['observation']['status'],
                        'ineligibility':row['observation']['ineligibility'],
                        'error':row['observation']['error']}
                        for row in missing_rows]})
     print(json.dumps({'PI6_INSTALLED_CORE_PATH':'PASS','rows':len(result['rows']),
                       'ineligible_dependencies':manifest['missing_dependencies'],
                       'coverage':result['analysis']['coverage']}),flush=True)
 else:
     import reading_logbook,reading_logbook_host
     assert all(Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
                for module in [reading_logbook,reading_logbook_host])
     assert result['analysis']['coverage']['valid'], json.dumps({
         'coverage':result['analysis']['coverage'],
         'evaluation_complete':result['analysis']['evaluation_complete'],
         'native_fence_complete':result['analysis']['native_fence_complete'],
         'non_measured':[{
             'family':row['family'],'arm':row['arm'],
             'status':row['observation']['status'],
             'ineligibility':row['observation']['ineligibility'],
             'error':row['observation']['error'],
             'verdict':row['score']['verdict'],
             'reason':row['score']['reason']}
             for row in result['rows'] if row['observation']['status']!='measured']})
     assert result['analysis']['evaluation_complete']
     assert result['analysis']['native_fence_complete']
     identity=result['runtime_identity']
     assert all(row['package_sha256']!='not_installed' for row in identity['distributions'])
     print(json.dumps({'PI6_INSTALLED_FULL_EVALUATOR':'PASS','rows':len(result['rows']),
                       'analysis':result['analysis'],'runtime_identity':identity}),flush=True)

if __name__ == '__main__':
 main()
"""


def main():
    if sys.platform != "darwin":
        raise SystemExit("PI6 installed probe needs reviewed native fence")
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("offline installer uv required")
    core = sorted((ROOT / "backend/dist").glob("personal_ai_backend-*.whl"))
    client = sorted(
        (ROOT / "examples/reading-logbook/client/dist").glob("reading_logbook_client-*.whl")
    )
    host = sorted((ROOT / "examples/reading-logbook/host/dist").glob("reading_logbook_host-*.whl"))
    if len(core) != 1 or len(client) != 1 or len(host) != 1:
        raise SystemExit("build PI2 wheels before installed PI6 evaluation")
    wheels = [*core, *client, *host]
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            assert not any("personal_ai_reference_apps" in name for name in names)
            assert not any(name.startswith("personal_ai/") for name in names if wheel != core[0])
    with tempfile.TemporaryDirectory(prefix="pi6-installed-") as directory:
        workspace = Path(directory).resolve()
        venv_dir = workspace / "venv"
        venv.EnvBuilder(with_pip=False).create(venv_dir)
        suffix = f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
        source, target = Path(sys.executable).parent.parent / suffix, venv_dir / suffix
        for path in source.iterdir():
            if (
                path.suffix == ".pth"
                or path.name == "__pycache__"
                or path.name.startswith(
                    ("personal_ai", "_personal_ai", "__editable__", "reading_logbook")
                )
            ):
                continue
            if path.is_dir():
                shutil.copytree(
                    path, target / path.name, ignore=shutil.ignore_patterns("__pycache__")
                )
            else:
                shutil.copyfile(path, target / path.name)
        python = venv_dir / "bin/python"
        env = {
            "PATH": os.environ["PATH"],
            "UV_OFFLINE": "1",
            "UV_CACHE_DIR": str(workspace / "cache"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "AI_PROVIDER": "fake",
            "APP_ENVIRONMENT": "test",
        }
        probe = workspace / "probe.py"
        probe.write_text(PROBE)

        def install(paths):
            subprocess.run(
                [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    "--no-index",
                    "--no-deps",
                    *map(str, paths),
                ],
                env=env,
                cwd=workspace,
                check=True,
            )

        def run(label):
            completed = subprocess.run(
                ["/usr/bin/sandbox-exec", "-p", PROFILE, str(python), str(probe)],
                env=env,
                cwd=workspace,
                check=False,
                timeout=420,
                capture_output=True,
                text=True,
            )
            print(
                json.dumps(
                    {
                        "phase": label,
                        "exit_code": completed.returncode,
                        "stdout": completed.stdout[-6000:],
                        "stderr_tail": completed.stderr[-1000:],
                    }
                ),
                flush=True,
            )
            if completed.returncode:
                raise SystemExit(f"PI6 installed evaluator failed during {label}")

        install(core)
        run("core_only")
        install([*client, *host])
        run("client_and_host_wheels")
        print(
            json.dumps(
                {
                    "PI6_INSTALLED_PROBE": "PASS",
                    "network_fence": "native_loopback_only",
                    "dependency_installation": "offline_no_index_no_deps",
                    "wheels": [
                        {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                        for path in wheels
                    ],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
