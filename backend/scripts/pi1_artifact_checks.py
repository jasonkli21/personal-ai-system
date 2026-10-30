"""Inspect archives and probe a built wheel outside the checkout, entirely offline.

Reuse the existing virtualenv's dependency files in a fresh virtualenv; exclude
all .pth/editable hooks and platform distributions. Install only the built wheel
with uv --no-index --no-deps. No dependency downloads or source PYTHONPATH.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
artifacts = sorted((ROOT / "backend/dist").glob("personal_ai_backend-0.1.0*"))
assert len(artifacts) == 2
for artifact in artifacts:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            names = archive.namelist()
            metadata = archive.read(
                next(name for name in names if name.endswith("/METADATA"))
            ).decode()
            assert "personal-ai-reference" not in metadata
            assert not any(name.endswith("/entry_points.txt") for name in names)
    else:
        with tarfile.open(artifact) as archive:
            names = archive.getnames()
    forbidden = (
        "personal_ai_reference_apps",
        "personal_ai/context/travel",
        "personal_ai/context/shopping",
        "personal_ai/context/finance",
        "personal_ai/context/health",
        "personal_ai/domains/travel",
        "personal_ai/domains/shopping",
        "personal_ai/domains/providers",
        "personal_ai/domains/service",
        "personal_ai/domains/registry",
        "personal_ai/domains/fixtures",
        "personal_ai/itinerary_proposals",
        "personal_ai/booking_extractions",
        "personal_ai/mutations/shopping",
        "personal_ai/api/domains",
        "personal_ai/api/itinerary_proposals",
        "personal_ai/api/booking_extractions",
        "personal_ai/persistence/postgres/capabilities",
    )
    assert not any(prefix in name for prefix in forbidden for name in names)
    print(
        json.dumps(
            {
                "artifact": str(artifact),
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "file_count": len(names),
            }
        ),
        flush=True,
    )

workspace = Path(tempfile.mkdtemp(prefix="pi1-installed-", dir="/private/tmp"))
venv_dir = workspace / "venv"
venv.EnvBuilder(with_pip=False).create(venv_dir)
source_site = (
    Path(sys.executable).parent.parent
    / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
)
target_site = (
    venv_dir / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
)
copied = []
for path in sorted(source_site.iterdir()):
    if (
        path.suffix == ".pth"
        or path.name.startswith(("personal_ai", "_personal_ai", "__editable__"))
        or path.name == "__pycache__"
    ):
        continue
    target = target_site / path.name
    if path.is_dir():
        shutil.copytree(path, target, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        shutil.copyfile(path, target)
    copied.append(path.name)
(workspace / "dependency-files.json").write_text(json.dumps(copied, indent=2))
env = {
    "PATH": os.environ["PATH"],
    "UV_CACHE_DIR": str(workspace / "uv-cache"),
    "UV_OFFLINE": "true",
    "AI_PROVIDER": "fake",
    "AI_MODEL": "pi1-artifact",
    "PYTHONDONTWRITEBYTECODE": "1",
}
wheel = next(artifact for artifact in artifacts if artifact.suffix == ".whl")
python = venv_dir / "bin/python"
subprocess.run(
    ["uv", "pip", "install", "--python", str(python), "--no-deps", "--no-index", str(wheel)],
    cwd=workspace,
    env=env,
    check=True,
)
probe = workspace / "probe.py"
shutil.copyfile(ROOT / "backend/scripts/pi1_core_probe.py", probe)
print(f"ISOLATED_WORKSPACE={workspace}", flush=True)
subprocess.run([str(python), str(probe)], cwd=workspace, env=env, check=True)
print("CORE_ARTIFACT_PROBE=PASS", flush=True)
core_tests = workspace / "core-tests/tests"
core_tests.mkdir(parents=True)
core_test_files = (
    "test_memory_integration.py",
    "test_memory_disclosure_authorization.py",
    "test_research_routes.py",
    "test_iterative_research_routes.py",
    "test_context_builder.py",
)
for name in (*core_test_files, "conftest.py", "__init__.py", "test_iterative_research.py"):
    shutil.copyfile(ROOT / "backend/tests" / name, core_tests / name)
core_runner = workspace / "core_offline_checks.py"
shutil.copyfile(ROOT / "backend/scripts/pi1_offline_checks.py", core_runner)
subprocess.run(
    [str(python), str(core_runner), "-q", *(str(core_tests / name) for name in core_test_files)],
    cwd=workspace,
    env=env,
    check=True,
)
print("CORE_INSTALLED_MEMORY_RESEARCH_SUMMARY=PASS", flush=True)


reference_wheel = ROOT / "reference-apps/dist/personal_ai_reference_apps-0.1.0-py3-none-any.whl"
with zipfile.ZipFile(reference_wheel) as archive:
    entries = archive.namelist()
    assert not any(name.startswith("personal_ai/") for name in entries)
    points = archive.read(
        next(name for name in entries if name.endswith("/entry_points.txt"))
    ).decode()
    assert "personal_ai_reference_apps" in points
print(
    json.dumps(
        {
            "artifact": str(reference_wheel),
            "sha256": hashlib.sha256(reference_wheel.read_bytes()).hexdigest(),
        }
    ),
    flush=True,
)
subprocess.run(
    [
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
        "--no-deps",
        "--no-index",
        str(reference_wheel),
    ],
    cwd=workspace,
    env=env,
    check=True,
)
reference_probe = workspace / "reference_probe.py"
shutil.copyfile(ROOT / "backend/scripts/pi1_reference_probe.py", reference_probe)
subprocess.run([str(python), str(reference_probe)], cwd=workspace, env=env, check=True)
# Run copied compatibility tests against INSTALLED packages, never source pythonpath.
tests = workspace / "tests"
tests.mkdir()
for name in (
    "conftest.py",
    "test_task_deployment.py",
    "test_mutations.py",
    "test_booking_extractions.py",
    "test_itinerary_proposals.py",
    "test_application_scope.py",
    "test_federation.py",
    "test_applications.py",
    "test_context_runtime_composition.py",
    "test_reference_persistence.py",
):
    shutil.copyfile(ROOT / "backend/tests" / name, tests / name)
(tests / "fixtures").mkdir()
shutil.copyfile(
    ROOT / "backend/tests/fixtures/itinerary-proposal-example.json",
    tests / "fixtures/itinerary-proposal-example.json",
)
runner = workspace / "offline_checks.py"
shutil.copyfile(ROOT / "backend/scripts/pi1_offline_checks.py", runner)
subprocess.run([str(python), str(runner), "-q", str(tests)], cwd=workspace, env=env, check=True)
subprocess.run(
    ["uv", "pip", "uninstall", "--python", str(python), "personal-ai-reference-apps"],
    cwd=workspace,
    env=env,
    check=True,
)
subprocess.run([str(python), str(probe)], cwd=workspace, env=env, check=True)
print("REFERENCE_INSTALLED_COMPATIBILITY_AND_UNINSTALL=PASS", flush=True)
subprocess.run(
    [
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
        "--no-deps",
        "--no-index",
        str(reference_wheel),
    ],
    cwd=workspace,
    env=env,
    check=True,
)
subprocess.run([str(python), str(reference_probe)], cwd=workspace, env=env, check=True)
subprocess.run(
    [
        str(python),
        str(runner),
        "-q",
        str(tests / "test_task_deployment.py"),
        str(tests / "test_mutations.py"),
    ],
    cwd=workspace,
    env=env,
    check=True,
)
print("RESTORED_REFERENCE_ORIGINAL_KEY_COMPATIBILITY=PASS", flush=True)
