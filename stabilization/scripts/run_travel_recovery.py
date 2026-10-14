"""Own two disposable loopback databases for the actual age/PG restore smoke."""

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn", required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    parts = urlsplit(args.admin_dsn)
    if (
        parts.scheme != "postgresql"
        or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parts.path != "/postgres"
        or not parts.username
        or parts.query
        or parts.fragment
    ):
        parser.error("explicit loopback PostgreSQL /postgres admin URI required")
    directory = Path(__file__).resolve().parents[3] / "personal-travel-app/backend"
    names = [f"suite_travel_{uuid4().hex}_test" for _ in range(2)]
    urls = [
        urlunsplit(parts._replace(path=f"/{name}")).replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
        for name in names
    ]
    env = os.environ.copy()
    env.update(
        DATABASE_URL=urls[0],
        RECOVERY_SOURCE_DATABASE_URL=urls[0],
        RECOVERY_RESTORE_DATABASE_URL=urls[1],
        TRAVEL_DEPLOYMENT_MODE="local",
        TRAVEL_AUTH_MODE="local",
    )
    created = []
    with psycopg.connect(args.admin_dsn, autocommit=True) as connection:
        try:
            for name in names:
                connection.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
                )
                created.append(name)
            with args.log.open("w") as output:
                for arguments in (
                    ("-m", "alembic", "upgrade", "head"),
                    ("-m", "scripts.recovery_smoke"),
                ):
                    result = subprocess.run(
                        [str(directory / ".venv/bin/python"), *arguments],
                        cwd=directory,
                        env=env,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                    if result.returncode:
                        break
            print(
                f"Travel encrypted recovery: exit={result.returncode}; log={args.log}"
            )
            print(args.log.read_text()[-4000:])
            return result.returncode
        finally:
            for name in created:
                connection.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(name)
                    )
                )


if __name__ == "__main__":
    raise SystemExit(main())
