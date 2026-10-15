"""Compare shared wire manifests in each repository's own locked interpreter."""

import json
import os
import subprocess
from pathlib import Path

PROJECTS = Path(__file__).resolve().parents[3]
RUNTIMES = (
    ("personal-ai-system", "backend", "src", "personal_ai.contracts.delegated_tasks"),
    (
        "shopping-assistant",
        "apps/api",
        "src",
        "shopping.integrations.personal_ai.task_wire",
    ),
    ("personal-finance", "services/api", ".", "app.integrations.task_wire"),
    ("personal-travel-app", "backend", "src", "personal_travel.clients.task_wire"),
    ("health-app", "services/api", "src", "health_api.integrations.task_wire"),
)


def main() -> None:
    reports = {}
    for repository, directory, source, module in RUNTIMES:
        root = PROJECTS / repository / directory
        environment = os.environ.copy()
        environment.update(
            PYTHONPATH=str(root / source),
            PRIVATE_FILE_DIR="/private/tmp/suite-contracts-private",
        )
        script = (
            "import json, pydantic; from " + module + " import task_manifest; "
            "print(json.dumps({'pydantic':pydantic.__version__,'manifest':task_manifest()},sort_keys=True))"
        )
        result = subprocess.check_output(
            [str(root / ".venv/bin/python"), "-c", script],
            cwd=root,
            env=environment,
            text=True,
        )
        reports[repository] = json.loads(result)
    canonical = reports["personal-ai-system"]["manifest"]
    if any(report["manifest"] != canonical for report in reports.values()):
        raise SystemExit("isolated shared contract mismatch")
    destination = (
        PROJECTS
        / "personal-ai-system/stabilization/evidence/isolated-contracts.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(reports, indent=2, sort_keys=True) + "\n")
    print("All five isolated runtime manifests match")


if __name__ == "__main__":
    main()
