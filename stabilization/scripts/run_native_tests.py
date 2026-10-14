"""Run repository tests in an owned, disposable loopback PostgreSQL database.

Run with backend/.venv/bin/python. Requires CREATEDB on the explicit local test
role. This never truncates a configured application database or prints secrets.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql

PROJECTS = Path(__file__).resolve().parents[3]
REPOSITORIES = {
    "shopping": ("shopping-assistant", "apps/api", "db"),
    "finance": ("personal-finance", "services/api", None),
    "personal-ai": ("personal-ai-system", "backend", "persistence_integration"),
    "tasks": ("personal-ai-system", "backend", None),
    "travel": ("personal-travel-app", "backend", None),
    "health": ("health-app", "services/api", None),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", choices=REPOSITORIES)
    parser.add_argument("--admin-dsn", required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("tests", nargs="*")
    args = parser.parse_intermixed_args()
    parts = urlsplit(args.admin_dsn)
    if (
        parts.scheme != "postgresql"
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.path != "/postgres"
        or not parts.username
        or parts.query
        or parts.fragment
    ):
        parser.error("admin DSN must be an explicit loopback PostgreSQL /postgres URI")
    repo, relative, marker = REPOSITORIES[args.repository]
    root = PROJECTS / repo / relative
    python = root / ".venv/bin/python"
    if args.repository == "tasks":
        python = Path("/tmp/suite-task-integration-venv/bin/python")
    if not python.is_file():
        parser.error("repository virtualenv is unavailable")
    name = f"suite_{uuid4().hex}_test"
    task_dsn = urlunsplit(parts._replace(path=f"/{name}"))
    sqlalchemy_dsn = task_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    env = os.environ.copy()
    env["UV_NO_SYNC"] = "1"
    env["PRIVATE_FILE_DIR"] = f"/private/tmp/{name}_private"
    if args.repository in {"health", "travel", "shopping", "finance"}:
        env["DATABASE_URL"] = sqlalchemy_dsn
    if args.repository == "shopping":
        # Shopping deliberately refuses to test against its configured runtime
        # database. Its fixtures override every domain session factory. Keep the
        # runtime URI separate and synthetic, without creating or using it.
        env["DATABASE_URL"] = urlunsplit(
            parts._replace(path=f"/{name}_unconfigured")
        ).replace("postgresql://", "postgresql+psycopg://", 1)
    if args.repository == "health":
        env.update(
            APP_ENV="test",
            AUTH_MODE="dev",
            LOCAL_OBJECT_STORAGE_ROOT=f"/private/tmp/{name}_objects",
        )
    if args.repository == "travel":
        env["SYNTHETIC_IDENTITY_FIXTURE_PORT"] = str(parts.port or 5432)
    if args.repository == "tasks":
        env["SUITE_TEST_POSTGRES_DSN"] = task_dsn
        env.update(
            APP_ENV="test",
            AUTH_MODE="local",
            DATABASE_URL=sqlalchemy_dsn,
            LOCAL_OBJECT_STORAGE_ROOT=f"/private/tmp/{name}_objects",
        )
        env["PYTHONPATH"] = os.pathsep.join(
            (
                str(PROJECTS / "personal-ai-system/backend/src"),
                str(PROJECTS / "personal-finance/services/api"),
                str(PROJECTS / "shopping-assistant/apps/api/src"),
                str(PROJECTS / "personal-travel-app/backend/src"),
                str(PROJECTS / "health-app/services/api/src"),
            )
        )
    if args.repository == "personal-ai":
        env["PERSISTENCE_TEST_POSTGRES_DSN"] = task_dsn
    else:
        env["TEST_DATABASE_URL"] = sqlalchemy_dsn
    if args.repository == "finance":
        env["STAGE4_RECOVERY_TEST_ADMIN_URL"] = args.admin_dsn.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    command = [str(python), "-m", "pytest", "-q", "--tb=short"]
    if marker:
        command += ["-m", marker]
    command += args.tests
    if args.repository == "tasks" and not args.tests:
        command += ["../stabilization/tests/test_suite_tasks.py"]
    with psycopg.connect(args.admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            with args.log.open("w") as output:
                result = subprocess.run(
                    command,
                    cwd=root,
                    env=env,
                    stdout=output,
                    check=False,
                    stderr=subprocess.STDOUT,
                )
            print(f"{args.repository}: exit={result.returncode}; log={args.log}")
            print(args.log.read_text()[-6500:])
            return result.returncode
        finally:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


if __name__ == "__main__":
    raise SystemExit(main())
