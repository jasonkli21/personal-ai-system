"""Minimal CLI; every ask is an explicit user message, never a database upload."""

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from uuid import UUID, uuid4

from reading_logbook.client import APIError, PlatformClient, UncertainTurn
from reading_logbook.store import Logbook


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="reading-logbook.sqlite3")
    parser.add_argument("--url", default=os.environ.get("PERSONAL_AI_URL"))
    parser.add_argument(
        "--token-file", default=os.environ.get("PERSONAL_AI_TOKEN_FILE")
    )
    parser.add_argument("--workspace", default=os.environ.get("PERSONAL_AI_WORKSPACE"))
    parser.add_argument("--allow-loopback", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("--note", default="")
    sub.add_parser("books")
    start = sub.add_parser("start")
    start.add_argument("title")
    start.add_argument("--key")
    sub.add_parser("list")
    get = sub.add_parser("get")
    get.add_argument("conversation_id")
    for name in ("preview", "ask"):
        command = sub.add_parser(name)
        command.add_argument("conversation_id")
        command.add_argument(
            "content",
            help="Only this text is sent; copy a local note explicitly if desired",
        )
        command.add_argument("--key")
    retrieve = sub.add_parser("retrieve")
    retrieve.add_argument("query")
    retrieve.add_argument("--key", required=True)
    retrieve.add_argument("--external", action="store_true")
    retrieve.add_argument("--tool", action="store_true")
    recover = sub.add_parser("recover")
    recover.add_argument("key")
    args = parser.parse_args(argv)
    book = Logbook(args.db)
    try:
        if args.command == "add":
            result = {"book_id": book.add(args.title, args.note)}
        elif args.command == "books":
            result = book.books()
        else:
            if not args.url or not args.token_file or not args.workspace:
                raise ValueError("url, protected token file and workspace required")
            token_path = Path(args.token_file)
            if stat.S_IMODE(token_path.stat().st_mode) & 0o077:
                raise ValueError("token file must be private (chmod 600)")
            token = token_path.read_text().strip()
            client = PlatformClient(
                args.url, token, args.workspace, allow_loopback=args.allow_loopback
            )
            namespace = json.dumps(
                [client.base_url, client.application, client.workspace]
            )
            if args.command == "retrieve":
                result = client.retrieve(
                    args.query, args.key,
                    sources=("local", "external") if args.external else ("local",),
                    tool=args.tool,
                )
            elif args.command == "list":
                result = client.conversations()
            elif args.command == "get":
                result = client.conversation(args.conversation_id)
            elif args.command == "recover":
                key = str(UUID(args.key))
                operation = book.operation(namespace, key)
                if operation["kind"] == "start":
                    result = client.start(operation["body"]["title"], key)
                else:
                    result = client.status(operation["conversation_id"], key)
                    if result["state"] == "completed":
                        result = client.ask(
                            operation["conversation_id"], operation["body"]
                        )
                    else:
                        print(json.dumps({"key": key, **result}))
                        return 2
                book.completed(namespace, key, result)
            else:
                key = str(UUID(args.key)) if args.key else str(uuid4())
                if args.command == "start":
                    body, kind, conversation_id = {"title": args.title}, "start", None
                else:
                    body = {
                        "content": args.content,
                        "idempotency_key": key,
                        "choice": {"mode": "automatic"},
                    }
                    kind, conversation_id = "turn", str(UUID(args.conversation_id))
                if args.command == "preview":
                    result = client.preview(conversation_id, body)
                else:
                    # Durable journal and visible original key precede any network request.
                    book.remember(namespace, key, kind, conversation_id, body)
                    print(json.dumps({"operation_key": key}), flush=True)
                    if kind == "start":
                        result = client.start(args.title, key)
                    else:
                        result = client.ask(
                            conversation_id,
                            body,
                            provisional=lambda text: print(
                                text, end="", file=sys.stderr, flush=True
                            ),
                        )
                    book.completed(namespace, key, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (APIError, UncertainTurn, OSError, ValueError, KeyboardInterrupt) as error:
        # Exception text can contain URLs/headers from urllib; emit only safe classes/codes.
        code = error.code if isinstance(error, APIError) else type(error).__name__
        print(
            json.dumps(
                {
                    "state": "unconfirmed",
                    "code": code,
                    "recovery": "recover the printed original key; no automatic retry",
                }
            ),
            file=sys.stderr,
        )
        return 2
    finally:
        book.db.close()


if __name__ == "__main__":
    raise SystemExit(main())
