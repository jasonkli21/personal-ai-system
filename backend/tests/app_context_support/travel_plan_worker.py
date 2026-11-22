"""Run the normally imported Travel half in its own locked test environment."""

import base64
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from alembic import command
from alembic.config import Config
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_travel.api.routes.private_plan import mount_private_plan_source
from personal_travel.api.schemas.private_plan import PRIVATE_PLAN_SOURCE_PATH
from personal_travel.auth.contracts import VerifiedPrincipal
from personal_travel.auth.private_plan import PrivatePlanTrust
from personal_travel.clients.private_plan import (
    PlanDestination,
    PlanReceipt,
    PlanReceiptError,
    PlanReceiptRegistration,
    PrivatePlanHTTP,
)
from personal_travel.config import Settings
from personal_travel.main import app as ordinary_app
from personal_travel.models.auth import AuthIdentity
from personal_travel.models.private_plan import PrivatePlanIntent
from personal_travel.models.sidecar_anchor import PersonalAISidecarAnchor
from personal_travel.models.trip import Trip
from personal_travel.services.errors import DomainError
from personal_travel.services.private_plan import PrivatePlanCaller, PrivatePlanJournal
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker


@contextmanager
def migrated_database() -> Iterator[Engine]:
    url = make_url(os.environ["TEST_DATABASE_URL"])
    socket = Path(url.query.get("host", ""))
    if url.host or url.port or not socket.is_absolute() or not socket.is_dir():
        raise ValueError("Use a disposable PostgreSQL database on a Unix socket.")
    schema = f"travel_pair_{uuid4().hex}"
    admin = create_engine(url)
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    config = Config("alembic.ini", stdout=sys.stderr)
    config.set_main_option("script_location", str(Path("migrations").resolve()))
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "0022", revision
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


class TravelFixture:
    def __init__(self, engine, *, identity, trust, service_verifier, trips, receipt_public_key):
        self.sessions = sessionmaker(engine, autoflush=False, expire_on_commit=False)
        self.identity = identity
        self.trust = trust
        self.receipt_public_key = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(receipt_public_key)
        )
        self.registration = None
        self.settings = Settings(_env_file=None, personal_ai_plan_enabled=True)
        self.app = FastAPI()
        mount_private_plan_source(
            self.app,
            settings=self.settings,
            trust=trust,
            sessions=self.sessions,
            verify_service=service_verifier,
        )
        with self.sessions.begin() as session:
            session.add(AuthIdentity(**identity))
            for record in trips:
                session.add(
                    Trip(
                        id=UUID(record["id"]),
                        owner_id=identity["owner_id"],
                        title=record["title"],
                        revision=record["revision"],
                        start_date=date(2026, 11, 22),
                        end_date=date(2026, 11, 23),
                        timezone="UTC",
                    )
                )

    def pas(self, request):
        print(
            json.dumps(
                {
                    "pas_request": {
                        "path": request.url.path,
                        "method": request.method,
                        "headers": dict(request.headers),
                        "content": request.content.decode(),
                    },
                }
            ),
            flush=True,
        )
        for line in sys.stdin:
            method, arguments = json.loads(line)
            if method == "pas_response":
                return httpx.Response(**arguments)
            assert method in {"source", "remove_anchor"}
            print(json.dumps({"result": self.operation(method, arguments)}), flush=True)
        raise RuntimeError("PAS response pipe closed")

    def operation(self, method, arguments):
        if method == "register_destination":
            assert self.registration is None
            destination = PlanDestination.model_validate(arguments)
            self.registration = PlanReceiptRegistration(self.receipt_public_key, destination)
            return None
        if method == "source":
            result = self.client.post(PRIVATE_PLAN_SOURCE_PATH, **arguments)
            return {
                "status": result.status_code,
                "headers": dict(result.headers),
                "body": result.text,
            }
        for key in {
            "trip_id",
            "create_key",
            "conversation_id",
            "original_key",
        } & arguments.keys():
            arguments[key] = UUID(arguments[key])
        if method == "remove_anchor":
            with self.sessions.begin() as session:
                anchor = session.get(PersonalAISidecarAnchor, arguments["conversation_id"])
                session.delete(anchor)
            return None
        if method == "intent_state":
            with self.sessions() as session:
                intent = session.scalar(
                    select(PrivatePlanIntent).where(
                        PrivatePlanIntent.original_key == arguments["original_key"]
                    )
                )
                return intent.state
        if "receipt" in arguments:
            body, signature = arguments["receipt"]
            arguments["receipt"] = PlanReceipt(body.encode(), signature)
        bearer = arguments.pop("bearer", None)
        if method == "change_trip":
            with self.sessions.begin() as session:
                trip = session.get(Trip, arguments["trip_id"])
                assert trip is not None
                if "owner_id" in arguments:
                    trip.owner_id = arguments["owner_id"]
                if "revision" in arguments:
                    trip.revision = arguments["revision"]
            return None
        now = int(datetime.now(UTC).timestamp())
        principal = VerifiedPrincipal(**self.identity, issued_at=now, expires_at=now + 60)
        with self.sessions() as session:
            journal = PrivatePlanJournal(
                session,
                settings=self.settings,
                trust=self.trust,
                principal=principal,
                receipts=self.registration,
            )
            match method:
                case "reserve_create":
                    create = journal.reserve_create(**arguments)
                    return {
                        "newly_reserved": create.newly_reserved,
                        "conversation_id": str(create.conversation_id)
                        if create.conversation_id
                        else None,
                    }
                case "bind_created_conversation":
                    return str(journal.bind_created_conversation(**arguments))
                case "create" | "preview" | "inspect_original_status":
                    caller = PrivatePlanCaller(
                        journal,
                        PrivatePlanHTTP(
                            "https://pas.invalid",
                            bearer=bearer,
                            transport=httpx.MockTransport(self.pas),
                        ),
                    )
                    if method == "create":
                        return str(caller.create(**arguments))
                    if method == "inspect_original_status":
                        return caller.inspect_original_status(**arguments)
                    preview = caller.preview(**arguments)
                    return preview.model_dump(mode="json") if preview else None
                case "reserve_preview":
                    return journal.reserve_preview(**arguments)
                case "record_preview":
                    return journal.record_preview(**arguments).model_dump(mode="json")
                case "record_preview_unknown":
                    return journal.record_preview_unknown(**arguments)
                case "original_status":
                    status = journal.original_status(**arguments)
                    return (
                        {
                            "conversation_id": str(status.conversation_id),
                            "original_key": str(status.original_key),
                        }
                        if status
                        else None
                    )
        raise ValueError("Unknown test operation")


def main():
    outbound = []

    def network_audit(event, _):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
            outbound.append(event)
            raise PermissionError("Travel test networking disabled")

    sys.addaudithook(network_audit)
    config = json.loads(sys.stdin.readline())
    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(config.pop("service_public_key")))
    trust = config.pop("trust")
    trust["delegation_public_key"] = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(trust["delegation_public_key"])
    )

    def verify_service(token, *, audience, expected_service_account):
        try:
            body, signature = map(base64.urlsafe_b64decode, token.split("."))
            public_key.verify(signature, body)
            if json.loads(body) != {"aud": audience, "account": expected_service_account}:
                raise ValueError("Wrong fabricated service identity")
        except InvalidSignature:
            raise ValueError("Invalid fabricated service signature") from None

    with migrated_database() as engine:
        fixture = TravelFixture(
            engine, trust=PrivatePlanTrust(**trust), service_verifier=verify_service, **config
        )
        with (
            TestClient(ordinary_app, base_url="http://localhost") as ordinary,
            TestClient(fixture.app) as fixture.client,
        ):
            assert ordinary.get("/health").status_code == 200
            assert ordinary.post(PRIVATE_PLAN_SOURCE_PATH, json={}).status_code == 404
            print(json.dumps({"ready": True}), flush=True)
            for line in sys.stdin:
                method, arguments = json.loads(line)
                try:
                    result = {"result": fixture.operation(method, arguments)}
                except DomainError as error:
                    result = {"error": error.status_code}
                except PlanReceiptError:
                    result = {"error": "receipt_unavailable"}
                except httpx.HTTPError:
                    result = {"error": "ambiguous"}
                print(json.dumps(result), flush=True)
    assert not outbound, outbound


if __name__ == "__main__":
    main()
