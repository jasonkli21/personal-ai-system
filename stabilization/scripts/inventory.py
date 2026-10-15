"""Compare fixed baselines with task source; requires Python >=3.12 for domain syntax."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

PROJECTS = Path(__file__).resolve().parents[3]
REPOSITORIES = (
    "personal-ai-system",
    "shopping-assistant",
    "personal-finance",
    "personal-travel-app",
    "health-app",
)
BASELINES = {
    "personal-ai-system": "c029194156c570ec55f8173af969702f0265e57b",
    "shopping-assistant": "2268b944ffa8fe5c2e6f2787c88dea616160e398",
    "personal-finance": "495c21186b68215bf110ab6ab3115cd67190cc67",
    "personal-travel-app": "09584976d46c67c97a19c72d173b2ee88dbcb31c",
    "health-app": "7fb84c76217c772b2bce6715744b8294afafa771",
}
EXCLUDED_USER_FILES = (
    "docs/phase-11-independent-review-2026-10-07.md",
    "docs/phase-12-independent-review-2026-10-07.md",
    "docs/phase-13-independent-review-2026-10-07.md",
    "docs/phase-14-independent-review-2026-10-07.md",
    "docs/phase-15-independent-review-2026-10-07.md",
    "docs/phase-17r-independent-review-2026-10-08.md",
    "docs/personal-ai-chapter-2/litellm-routing-review-handoff-2026-10-08.md",
    "docs/planning/phase-8-independent-review-handoff.md",
    "docs/planning/phase-9-independent-review-handoff.md",
    "docs/shopping-assistant-maintainability-review-handoff.md",
    "docs/reviews/phase-9-independent-review.md",
    "frontend/pnpm-workspace.yaml",
)


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=root)


def category(name: str) -> str:
    if (
        name.endswith(("generated.ts", "schema.d.ts", "task_wire.py"))
        or name == "packages/api-types/src/index.ts"
        or (name.endswith("task_control.py") and "/contracts/" not in name)
    ):
        return "generated_contract"
    if name.startswith("docs/") or name.endswith(".md"):
        return "documentation"
    if "lock" in Path(name).name or name.endswith((".tsbuildinfo", ".lock")):
        return "lock_or_build"
    if name.endswith(".json") or "/fixtures/" in name:
        return "data_or_contract"
    if any(part in {"tests", "test", "e2e"} for part in Path(name).parts):
        return "tests"
    if name.endswith((".py", ".tsx", ".ts")) and any(
        part in {"src", "app", "components", "lib"} for part in Path(name).parts
    ):
        return "production"
    return "configuration_or_tooling"


def inventory(root: Path, names: list[str], *, baseline: bool) -> dict:
    rows = []
    for name in names:
        data = (
            git(root, "show", f"{BASELINES[root.name]}:{name}")
            if baseline
            else (root / name).read_bytes()
        )
        rows.append(
            {
                "path": name,
                "bytes": len(data),
                "nonblank_lines": sum(bool(line.strip()) for line in data.splitlines()),
                "category": category(name),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {
        kind: sorted(
            (row for row in rows if row["category"] == kind),
            key=lambda row: row["bytes"],
            reverse=True,
        )[:15]
        for kind in {row["category"] for row in rows}
    }


def main() -> None:
    report = {}
    for repository in REPOSITORIES:
        root = PROJECTS / repository
        tracked = git(root, "ls-files", "-z").decode().strip("\0").split("\0")
        untracked = (
            git(root, "ls-files", "--others", "--exclude-standard", "-z")
            .decode()
            .strip("\0")
            .split("\0")
        )
        current = sorted(
            name
            for name in set(tracked + untracked)
            if name
            and name not in EXCLUDED_USER_FILES
            and not name.startswith("stabilization/evidence/")
            and not name.startswith("stabilization/archive/")
            and (root / name).is_file()
        )
        baseline_names = (
            git(root, "ls-tree", "-r", "--name-only", BASELINES[repository])
            .decode()
            .splitlines()
        )
        baseline = inventory(root, baseline_names, baseline=True)
        changed = (
            git(root, "diff", "--name-only", BASELINES[repository])
            .decode()
            .splitlines()
        )
        semantic = {"ast_identical": [], "changed": []}
        for name in changed:
            if (
                name in baseline_names
                and name.endswith(".py")
                and (root / name).is_file()
            ):
                before = ast.dump(
                    ast.parse(git(root, "show", f"{BASELINES[root.name]}:{name}"))
                )
                after = ast.dump(ast.parse((root / name).read_bytes()))
                semantic["ast_identical" if before == after else "changed"].append(name)
        identity = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in current
            if name.startswith(
                (
                    "backend/",
                    "services/",
                    "apps/",
                    "migrations/",
                    "packages/",
                    "frontend/",
                )
            )
        }
        report[repository] = {
            "base_revision": BASELINES[repository],
            "branch": git(root, "branch", "--show-current").decode().strip(),
            "source_tree_sha256": hashlib.sha256(
                json.dumps(identity, sort_keys=True).encode()
            ).hexdigest(),
            "baseline": baseline,
            "current": inventory(root, current, baseline=False),
            "tracked_python_comparison": semantic,
            "preserved_user_files": [
                name for name in untracked if name in EXCLUDED_USER_FILES
            ],
        }
    destination = (
        PROJECTS
        / "personal-ai-system/stabilization/evidence/source-inventory.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
