"""PI-6 public HTTP task probes in installed wheels with reference apps absent.

Build first with make pi2-build. Dependencies are copied, never downloaded.
No source PYTHONPATH, editable hooks, runtime patch of auth, or fixture executable.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from pi6_checks import PROFILE

ROOT = Path(__file__).resolve().parents[2]
PROBE = '''
import importlib.util,json
from personal_ai.evaluation.pi6_contracts import load_corpus
assert importlib.util.find_spec('personal_ai_reference_apps') is None
corpus,manifest=load_corpus()
try:
 import reading_logbook
except ImportError:
 print('PI6_INSTALLED_CORE_FIXTURES_NO_HOST=PASS')
else:
 from personal_ai.evaluation.pi6_driver import dispatch
 from personal_ai.evaluation.pi6_scoring import score
 rows=[]
 for case in corpus.cases:
  for arm in ['baseline','candidate']:
   observation=dispatch(case.task,arm)
   scored=score(case,arm,observation)
   assert not scored['veto'] and observation.error=='none'
   rows.append(scored['success'])
 assert importlib.util.find_spec('personal_ai_reference_apps') is None
 print(json.dumps({'PI6_INSTALLED_SIGNED_HTTP_NO_TOYS':'PASS','observations':len(rows),'task_successes':sum(rows)}))
'''


def main():
    if sys.platform != 'darwin':
        raise SystemExit('PI6 installed probe needs reviewed native fence')
    uv = shutil.which('uv')
    if not uv:
        raise SystemExit('offline installer uv required')
    with tempfile.TemporaryDirectory(prefix='pi6-installed-') as directory:
        workspace = Path(directory).resolve()
        venv_dir = workspace / 'venv'
        venv.EnvBuilder(with_pip=False).create(venv_dir)
        suffix = f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'
        source, target = Path(sys.executable).parent.parent / suffix, venv_dir / suffix
        for path in source.iterdir():
            if (path.suffix == '.pth' or path.name == '__pycache__'
                    or path.name.startswith(('personal_ai', '_personal_ai', '__editable__', 'reading_logbook'))):
                continue
            if path.is_dir():
                shutil.copytree(path, target / path.name, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                shutil.copyfile(path, target / path.name)
        python = venv_dir / 'bin/python'
        env = {'PATH': os.environ['PATH'], 'UV_OFFLINE': '1', 'UV_CACHE_DIR': str(workspace / 'cache'),
               'PYTHONDONTWRITEBYTECODE': '1', 'AI_PROVIDER': 'fake', 'APP_ENVIRONMENT': 'test'}
        probe = workspace / 'probe.py'
        probe.write_text(PROBE)
        wheels = [next((ROOT / 'backend/dist').glob('*.whl'))]
        wheels += [next((ROOT / f'examples/reading-logbook/{kind}/dist').glob('*.whl'))
                   for kind in ('client', 'host')]
        def install(paths):
            subprocess.run([uv, 'pip', 'install', '--python', str(python), '--no-index', '--no-deps',
                            *map(str, paths)], env=env, cwd=workspace, check=True)
        def run():
            subprocess.run(['/usr/bin/sandbox-exec', '-p', PROFILE, str(python), str(probe)],
                           env=env, cwd=workspace, check=True, timeout=120)
        install(wheels[:1])
        run()
        install(wheels[1:])
        run()
        print(json.dumps({'PI6_INSTALLED_PROBE':'PASS', 'network_fence':'native_loopback_only',
                          'dependency_installation':'offline_no_index_no_deps'}))


if __name__ == '__main__':
    main()
