"""Reject phase-coded names on active source, test, command, and documentation surfaces."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASE_PATH = re.compile(
    r"(?i)(?:^|[/._-])(?:pi|hxe|mem|phase|re)[-_]?\d+|(?:^|[/._-])p\d+(?:\.\d+)?(?:$|[/._-])"
)
PHASE_TEXT = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:"
    r"phase[-_ ]?(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)(?:[-_:][A-Za-z0-9][A-Za-z0-9_-]*)?|"
    r"(?:PI|MEM|HXE|RE)[-_ ]?\d+(?:\.\d+)?(?:[-_:][A-Za-z0-9][A-Za-z0-9_-]*)?|"
    r"P(?![0-3](?:\b|_)|50(?:\b|_)|95(?:\b|_))\d{1,2}(?:\.\d+)?(?:[-_:][A-Za-z0-9][A-Za-z0-9_-]*)?|"
    r"pi\d+(?:[-_:][A-Za-z0-9][A-Za-z0-9_-]*)?|"
    r"mem\d+(?:[-_:][A-Za-z0-9][A-Za-z0-9_-]*)?|"
    r"p(?![0-3](?:\b|_)|50(?:\b|_)|95(?:\b|_))\d{1,2}[-_:][A-Za-z0-9][A-Za-z0-9_-]*"
    r")(?![A-Za-z0-9])"
)
PHASE_DECLARATION = re.compile(
    r"(?i)\b(?:class|def)\s+[A-Za-z_]*?(?:PI|MEM|HXE|RE)\d+[A-Za-z0-9_]*"
)

ACTIVE_ROOTS = (
    "backend",
    "adapters",
    "infrastructure",
    "examples",
    "reference-apps",
    "sdk/python",
    "frontend/src",
    ".github/workflows",
)
ACTIVE_ROOT_FILES = (
    "AGENTS.md",
    "CONTRIBUTING.md",
    "Makefile",
    "README.md",
    "SECURITY.md",
)
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "node_modules",
}
TEXT_SUFFIXES = {
    ".env",
    ".example",
    ".json",
    ".md",
    ".mdx",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
def _numbered_doc(prefix: str, number: int, suffix: str, directory: str = "docs") -> str:
    return f"{directory}/{prefix}{number}{suffix}"


HISTORICAL_DOC_PATHS = {
    "docs/implementation-plan.md",
    "docs/personal-ai-system-dynamic-reasoning-engine-prd.md",
    "docs/memory/memory-architecture-and-research-roadmap.md",
    "docs/platform-independence/platform-independence-roadmap.md",
    "docs/platform-independence/pi-cross-phase-gate-registry.md",
    "docs/personal-ai-system-integrated-roadmap-11-03.md",
    "docs/reasoning-engine/personal-ai-system-dynamic-reasoning-engine-prd.md",
    "docs/memory/consolidation-independent-evaluation-plan.md",
    _numbered_doc("hxe-", 1, "-plan-hardening.md", "docs/harness-excellence"),
    _numbered_doc("hxe-", 0, "-detailed-implementation-plan.md"),
    _numbered_doc("hxe-", 1, "-detailed-implementation-plan.md"),
    _numbered_doc("hxe-", 2, "-detailed-implementation-plan.md.md"),
    _numbered_doc("hxe-", 3, "-detailed-implementation-plan.md"),
    _numbered_doc("hxe-", 4, "-detailed-implementation-plan.md"),
    _numbered_doc("hxe-", 5, "-detailed-implementation-plan.md"),
    *{
        _numbered_doc("phase-", 1, suffix)
        for suffix in (
            "-deployment-checklist.md",
            "-implementation-guide.md",
            "-implementation-plan.md",
            "-review-fixes.md",
            "-verification-plan.md",
        )
    },
    *{
        _numbered_doc("phase-", number, suffix)
        for number in (2, 3, 4, 5, 6, 7, 8)
        for suffix in ("-implementation-guide.md", "-implementation-plan.md")
    },
    *{
        _numbered_doc("phase-", 9, suffix)
        for suffix in (
            "-authorization-matrix.md",
            "-implementation-evidence.md",
            "-implementation-plan.md",
            "-operations-runbook.md",
            "-owner-migration.md",
            "-provider-data-register.md",
            "-release-checklist.md",
            "-threat-model.md",
        )
    },
    _numbered_doc("phase-", 16, "-independent-review-2026-10-07.md"),
}
HISTORICAL_DOC_PREFIXES = (
    "docs/personal-ai-chapter-2/",
    "docs/releases/phase-",
    "docs/harness-excellence/2026-",
    "docs/reasoning-engine/re-",
    "docs/memory/mem-",
    "docs/memory/plans/mem-",
    "docs/migrations/phase-",
    "docs/platform-independence/pi-",
)
DATE_IN_PATH = re.compile(r"20\d{2}-\d{2}-\d{2}")
CURRENT_DOC_ROOTS = ("experiments", "stabilization")

# The renamed frozen corpus files are checked by hash before their historical
# identifiers are excluded from the active-text scan.
FROZEN_FIXTURE_SHA256 = {
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/cases-v1.json": "84c0e5a1e990ac5b282a24348e4319406d3ec4188d179099777ab5aa4b5651bf",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/cases-v2.json": "25df654eda27040c3b52695fd6ec695b53238a7cf76b82e1ed4e5d442b55205d",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/manifest-v1.json": "8480771c464c353a8899a36a4c510fe08a3665ff97a0cde7c0b867f5ff0d99bf",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/manifest-v2.json": "ad69387bca873df3e9b3522ff15d222122d49ed572d8a113423cae5fd0af336c",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-2.json": "322dd2f2e6bf7a66a9065bdbf36c8fa50fd37c3537a5ab82279d7139ba54a53f",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-3.json": "431667748921a5a2cc05a19538172830effc3a8a144cfc4645fbb3b2038fb93c",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-4.json": "ccee9fd1fcf6dad10c12d27ebc4dbec64995f5063e80a4313229a0121248ab42",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-5.json": "c37407024e50c801e794b2b88a3341f598a7d1736d8c9e1f4221f07c2c8496a2",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-6.json": "35b42c70c19aac0f44dc7f9a118e0f360472a9077c3a0b3da22d70abe8938bc6",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-7.json": "587a4d2530e428ce32c3dc273c38c3734ad183466e47fc17cb3278800bcc1614",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-8.json": "f28f367c8a884801bb7bb0463929bb98426a57af46090fbd094b5402ac948869",
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-9.json": "a00a8faf9f8a8f7dc17efbc81e07a8053c80415a7735eae362ed43ad95bc6a3e",
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-control-v1.json": "7d2e93b33904ddb81bef6e4f8f3ffff89a51b7d63b85b5e88c21877c4b6c2a9d",
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-knowledge-consumer-v1.json": "ff94f67f8889f13887128003d21e5f1b89078e806c12a1d148c4ac7d1d347066",
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-knowledge-pairs-v1.json": "587e87f11422719e8ad2f512ede7020c0bae937cb555b1035cd8eb386866756e",
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-task-cases-v1.json": "043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18",
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-task-cases-v2.json": "592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1",
}

# Exact path-and-token matches only. This intentionally does not exempt files or
# fixture directories. Construct the compatibility tokens so the checker itself
# does not need a self-exemption for the labels it is designed to detect.
def _compat(prefix: str, number: int, suffix: str = "") -> str:
    return f"{prefix}{number}{suffix}"


EXACT_TEXT_EXCEPTIONS = {
    "backend/src/personal_ai/agents/research/iterative/service.py": {
        _compat("phase", 8, "-run"),
        _compat("phase", 8, "-research-session"),
    },
    "backend/src/personal_ai/auth/directory.py": {_compat("phase", 9, "-owner-v1")},
    "backend/src/personal_ai/evaluation/memory_knowledge.py": {_compat("mem", 1, "-paired-v1")},
    "backend/src/personal_ai/evaluation/memory_knowledge_consumer.py": {
        _compat("mem", 1, "-paired-v1"),
        _compat("mem", 1, "-consumer-v1"),
    },
    "backend/src/personal_ai/evaluation/memory_task_contracts.py": {
        _compat("mem", 0, "-task-case-v1"),
        _compat("mem", 0, "-task-case-v2"),
        _compat("MEM", 0),
        _compat("mem", 0, "-v1"),
        _compat("mem", 0, "-v2"),
        _compat("mem", 0, "-rubric-v1"),
        _compat("mem", 0, "-rubric-v2"),
    },
    "backend/src/personal_ai/evaluation/README.md": {
        _compat("mem", 1, "-paired-v1"),
    },
    "backend/src/personal_ai/evaluation/offline_information_handling.py": {
        _compat("pi", 3, "-local-json-bytes-v1"),
    },
    "backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v36.json": {
        _compat("phase", 13, "-envelope-byte-estimate-v1"),
    },
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-10.json": {
        _compat("pi", 6, "-offline-v2"),
        _compat("pi", 6, "-rubric-v2"),
    },
    "backend/src/personal_ai/llm/execution.py": {
        _compat("pi", 3, "-execution-v1"),
        _compat("pi", 3, "-local-json-bytes-v1"),
    },
    "backend/src/personal_ai/llm/synthetic_reasoning.py": {
        _compat("pi", 3, "-local-json-bytes-v1")
    },
    "backend/src/personal_ai/memory/control_repository.py": {_compat("mem", 2)},
    "backend/src/personal_ai/memory/contracts.py": {
        _compat("mem", 1, "_verified_knowledge")
    },
    "backend/src/personal_ai/evaluation/fixtures/routing/adaptive-observations-v1.json": {
        _compat("p", 19, "-resource-projection-v1"),
        _compat("p", 22, "-selected-executed-route-only-v1"),
    },
    "backend/src/personal_ai/evaluation/fixtures/research/retrieval-baseline-v2.json": {
        _compat("Phase ", 33),
    },
    "backend/src/personal_ai/routing/service.py": {
        _compat("phase", 21, "-root-v1"),
        _compat("phase", 21, "-reselection-v1"),
    },
    "backend/src/personal_ai/usage/observations.py": {
        _compat("p", 19, "-resource-projection-v1")
    },
    "backend/src/personal_ai/workflow/reasoning.py": {
        _compat("pi", 3, "-local-json-bytes-v1")
    },
    "backend/scripts/migrate_local_owner.py": {_compat("phase", 9, "-chat-owner-v2")},
    "backend/scripts/release_evidence_check.py": {
        _compat("P", 8),
        _compat("pi-", 8, "-verification"),
        _compat("pi-", 8, "-review-verification-v2"),
        _compat("pi", 8, "-audit-v1"),
        _compat("pi", 8, "-command-receipts-v2"),
    },
    "backend/scripts/test_release_evidence_check.py": {
        _compat("pi-", 8, "-verification"),
        _compat("pi-", 8, "-review-verification-v2"),
        _compat("pi", 8, "-audit-v1"),
        _compat("pi", 8, "-command-receipts-v2"),
    },
    "backend/src/personal_ai/persistence/postgres/schema_cli.py": {
        _compat("P", 10, "_SCHEMA_POSTGRES_DSN"),
    },
    "backend/src/personal_ai/settings.py": {
        _compat("P", 10, "_CLOUD_ADAPTERS_CONFIGURED"),
        _compat("P", 10, "_NEON_RUNTIME_DSN"),
        _compat("P", 10, "_NEON_POOL_MAX_SIZE"),
        _compat("P", 10, "_DYNAMODB_REGION"),
        _compat("P", 10, "_DYNAMODB_TABLE_NAME"),
        _compat("P", 10, "_DYNAMODB_ROLE_ARN"),
        _compat("P", 10, "_DYNAMODB_IDENTITY_TOKEN_AUDIENCE"),
    },
    "backend/tests/persistence/test_factory.py": {_compat("phase", 9, "-owner-v1")},
    "backend/tests/test_application_scope.py": {_compat("phase", 8, "-run")},
    "backend/tests/test_domains.py": {_compat("phase", 5, "-brave-snippet-v1")},
    "backend/tests/test_memory_task_benchmark.py": {
        _compat("MEM", 0),
        _compat("mem", 0, "-v1"),
        _compat("mem", 0, "-v2"),
    },
    "backend/tests/test_release_verification.py": {
        _compat("P", 36, "-IDENTITY"),
        _compat("phase-", 36),
    },
    "backend/tests/test_settings.py": {
        _compat("P", 10, "_NEON_RUNTIME_DSN"),
        _compat("P", 10, "_CLOUD_ADAPTERS_CONFIGURED"),
        _compat("P", 10, "_NEON_POOL_MAX_SIZE"),
        _compat("P", 10, "_DYNAMODB_ROLE_ARN"),
        _compat("P", 10, "_DYNAMODB_IDENTITY_TOKEN_AUDIENCE"),
    },
    "backend/src/personal_ai/evaluation/verification/__main__.py": {
        _compat("phase-", 36),
        _compat("phase", 36, "-verifier-environment-v1"),
    },
    "backend/src/personal_ai/evaluation/verification/contracts.py": {
        _compat("P", 36),
        _compat("phase", 36, "-external-evidence-v1"),
        _compat("phase", 36, "-matrix-v1"),
    },
    "reference-apps/src/personal_ai_reference_apps/domains/service.py": {
        _compat("phase", 5)
    },
    "reference-apps/src/personal_ai_reference_apps/domains/shopping/module.py": {
        _compat("phase", 5, "-research"),
    },
    "reference-apps/src/personal_ai_reference_apps/domains/travel/module.py": {
        _compat("phase", 5, "-research"),
    },
    "infrastructure/aws/dynamodb/validate_cloud_config.py": {
        _compat("p", 10, "_runtime"),
        _compat("p", 10, "_storage_migration"),
    },
    "infrastructure/neon/neon-role-grants.sql.tmpl": {
        _compat("p", 10, "_runtime"),
        _compat("p", 10, "_storage_migration"),
    },
}

HISTORICAL_PLANNING_LOCK_RE = re.compile(
    r"^backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v(\d+)\.json$"
)


def _excluded(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def active_source_files(root: Path = ROOT) -> list[Path]:
    files = []
    for relative in ACTIVE_ROOTS:
        base = root / relative
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not _excluded(path):
                files.append(path)
    files.extend(root / name for name in ACTIVE_ROOT_FILES if (root / name).is_file())
    return sorted(set(files))


def current_doc_files(root: Path = ROOT) -> list[Path]:
    docs = root / "docs"
    if not docs.is_dir():
        return []
    files = []
    for path in docs.rglob("*.md"):
        relative = path.relative_to(root).as_posix()
        parts = Path(relative).parts
        if any(part in {"archive", "history", "personal-ai-chapter-2"} for part in parts):
            continue
        if relative == "docs/naming-exceptions.md":
            continue
        if (
            relative in HISTORICAL_DOC_PATHS
            or relative.startswith(HISTORICAL_DOC_PREFIXES)
            or DATE_IN_PATH.search(relative)
        ):
            continue
        if _excluded(path):
            continue
        files.append(path)
    # These top-level directories contain maintained developer guides outside
    # docs/. Include them in the same naming contract while leaving dated
    # verification receipts as historical evidence.
    for directory in CURRENT_DOC_ROOTS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            relative = path.relative_to(root).as_posix()
            if DATE_IN_PATH.search(relative) or _excluded(path):
                continue
            files.append(path)
    return sorted(files)


def active_paths(root: Path = ROOT) -> list[str]:
    matches = []
    for path in active_source_files(root):
        relative = path.relative_to(root).as_posix()
        if PHASE_PATH.search(relative):
            matches.append(relative)
    for path in current_doc_files(root):
        relative = path.relative_to(root).as_posix()
        if PHASE_PATH.search(relative):
            matches.append(relative)
    return sorted(matches)


def _matrix_exceptions(root: Path) -> set[str]:
    path = root / "backend/src/personal_ai/evaluation/verification/matrix.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    allowed = {str(value.get("schema_version", ""))}
    for row in value.get("rows", []):
        if isinstance(row, dict):
            allowed.update(
                str(row.get(key, ""))
                for key in ("verification_id", "authority_ref")
                if row.get(key)
            )
    return allowed


def is_allowed_text(relative: str, token: str, line: str, root: Path = ROOT) -> bool:
    normalized = token.casefold()
    if relative == "backend/src/personal_ai/evaluation/verification/matrix.json":
        values = _matrix_exceptions(root)
        return any(
            normalized == match.group(0).casefold()
            and ("authority_ref" in line or "verification_id" in line or "schema_version" in line)
            for value in values
            for match in PHASE_TEXT.finditer(value)
        )
    return normalized in {
        value.casefold() for value in EXACT_TEXT_EXCEPTIONS.get(relative, set())
    }


def _frozen_fixture_hash_errors(path: Path, relative: str) -> list[str]:
    expected = FROZEN_FIXTURE_SHA256.get(relative)
    if expected is None:
        return []
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        return [f"cannot read frozen fixture {relative}: {error}"]
    if actual != expected:
        return [f"frozen fixture bytes changed for {relative}: expected={expected} current={actual}"]
    return []


def visible_text(root: Path = ROOT) -> list[str]:
    errors = []
    files = active_source_files(root) + current_doc_files(root)
    for path in sorted(set(files)):
        relative = path.relative_to(root).as_posix()
        errors.extend(_frozen_fixture_hash_errors(path, relative))
        if relative in FROZEN_FIXTURE_SHA256:
            continue
        historical_lock = HISTORICAL_PLANNING_LOCK_RE.fullmatch(relative)
        if historical_lock and int(historical_lock.group(1)) < 36:
            continue
        if relative == "docs/naming-exceptions.md":
            continue
        if path.suffix == ".lock":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(content.splitlines(), 1):
            if path.suffix == ".py" and PHASE_DECLARATION.search(line):
                errors.append(
                    f"{relative}:{line_number}: phase-coded declaration name: {line.strip()}"
                )
            for match in PHASE_TEXT.finditer(line):
                token = match.group(0)
                if not is_allowed_text(relative, token, line, root):
                    errors.append(
                        f"{relative}:{line_number}: undocumented phase-coded text {token!r}: {line.strip()}"
                    )
    errors.extend(_document_exception_errors(root))
    return errors


def _document_exception_errors(root: Path) -> list[str]:
    path = root / "docs/naming-exceptions.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return [f"cannot read naming compatibility register: {error}"]
    required = {
        "phase" + "8-run",
        "phase" + "8-research-session",
        "phase" + "21-root-v1",
        "phase" + "21-reselection-v1",
        "phase" + "9-owner-v1",
        "phase" + "9-chat-owner-v2",
        "pi" + "3-execution-v1",
        "pi" + "3-local-json-bytes-v1",
        "mem" + "2:",
        "phase" + "5-{provider}-snippet-v1",
        "phase" + "5-research",
        "phase" + "36-matrix-v1",
        "phase" + "36-external-evidence-v1",
        "phase" + "36-verifier-environment-v1",
        "phase" + "13-envelope-byte-estimate-v1",
        "P" + "8-*",
        "pi" + "8-audit-v1",
        "pi" + "8-command-receipts-v2",
        "P" + "10_CLOUD_ADAPTERS_CONFIGURED",
        "P" + "10_NEON_RUNTIME_DSN",
        "P" + "10_NEON_POOL_MAX_SIZE",
        "P" + "10_DYNAMODB_REGION",
        "P" + "10_DYNAMODB_TABLE_NAME",
        "P" + "10_SCHEMA_POSTGRES_DSN",
        "P" + "10_DYNAMODB_ROLE_ARN",
        "P" + "10_DYNAMODB_IDENTITY_TOKEN_AUDIENCE",
        "p" + "10_runtime",
        "p" + "10_storage_migration",
        "p" + "19-resource-projection-v1",
        "P" + "36-*",
        "mem" + "1-paired-v1",
        "mem" + "1_verified_knowledge",
        "p" + "22-selected-executed-route-only-v1",
        "Phase " + "33",
    }
    return [
        f"naming compatibility register is missing required justification for {value!r}"
        for value in sorted(required)
        if value not in text
    ]


def check_tree(root: Path = ROOT) -> list[str]:
    errors = [f"phase-coded active path: {path}" for path in active_paths(root)]
    errors.extend(visible_text(root))
    return errors


def main() -> int:
    errors = check_tree(ROOT)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    print("NAMING_POLICY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
