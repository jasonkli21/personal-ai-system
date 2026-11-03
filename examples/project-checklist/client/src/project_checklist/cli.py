"""Small checklist CLI and redacted, credential-free SDK preflight."""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from personal_ai_sdk import (
    CONSUMER_VERSION,
    APIError,
    CapabilityUnavailable,
    Client,
    ContractMismatch,
    UncertainTurn,
)

from .store import Checklist

APP = "project_checklist"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("checklist.sqlite"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--workspace")
    parser.add_argument("--contract-version", default=CONSUMER_VERSION)
    parser.add_argument("--synthetic-loopback", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    commands.add_parser("items")
    commands.add_parser("add").add_argument("title")
    commands.add_parser("finish").add_argument("item", type=int)
    create = commands.add_parser("create")
    create.add_argument("key")
    create.add_argument("title")
    commands.add_parser("conversations")
    commands.add_parser("detail").add_argument("conversation")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("conversation")
    for operation in ("send", "recover"):
        commands.add_parser(operation).add_argument("key")
    args = parser.parse_args()
    try:
        return run(args)
    except (APIError, UncertainTurn, CapabilityUnavailable) as error:
        parser.exit(1, f"{error}\n")
    except (ValueError, OSError, sqlite3.Error) as error:
        # Only SDK-defined codes should cross this boundary. SQLite and local
        # exceptions can include private paths or user-supplied values.
        code = (
            "contract_incompatible"
            if isinstance(error, ContractMismatch)
            else "invalid_local_request"
        )
        parser.exit(2, code + "\n")


def run(args) -> int:
    if args.command == "preflight":
        print(
            json.dumps(
                {
                    "contract_supported": CONSUMER_VERSION,
                    "token_configured": bool(os.environ.get("CHECKLIST_USER_ID_TOKEN")),
                    "workspace_configured": args.workspace is not None,
                    "remote_authority": "unverified",
                    "retrieval": "unavailable",
                    "memory": "unavailable",
                    "evidence": "E0",
                }
            )
        )
        return 0
    if args.command in {"items", "add", "finish", "prepare", "send", "recover"}:
        store = Checklist(args.db)
    target = json.dumps([args.base_url.rstrip("/"), APP, args.workspace])
    match args.command:
        case "add":
            result = store.add(args.title)
        case "finish":
            store.finish(args.item)
            result = {"updated": args.item}
        case "items":
            result = store.items()
        case "prepare":
            result = store.prepare(target, args.conversation, sys.stdin.read(20_001))
        case _:
            client = Client(
                args.base_url,
                os.environ.get("CHECKLIST_USER_ID_TOKEN", ""),
                application=APP,
                workspace=args.workspace,
                contract_version=args.contract_version,
                allow_loopback=args.synthetic_loopback,
            )
            match args.command:
                case "create":
                    result = client.create(args.title, args.key)
                case "conversations":
                    result = client.list()
                case "detail":
                    result = client.detail(args.conversation)
                case "send" | "recover":
                    result = store.turn(
                        client, target, args.key, recover=args.command == "recover"
                    )
    print(json.dumps(result))
    return 0
