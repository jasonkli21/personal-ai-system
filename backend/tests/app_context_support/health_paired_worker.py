"""A locked Health interpreter with a transient request-affine callback fixture."""

import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from threading import Thread
from types import SimpleNamespace
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from health_api.application.personal_ai_context import read_personal_ai_health_context
from health_api.application.profile_service import (
    CreateProfile,
    create_profile_item,
    update_profile_item,
)
from health_api.application.r5_health_caller import (
    R5OriginalKeys,
    R5PreviewEpochs,
    R5VerifiedCallerTarget,
    bind_r5_preview_request,
    observe_r5_preview,
    r5_create_request,
    reserve_r5_operation_keys,
)
from health_api.application.r5_health_source import (
    R5HealthSelection,
    R5PreviewUnavailable,
    R5SourceAuthority,
    parse_r5_source_request,
    read_r5_health_preference,
    resolve_r5_owner,
)
from health_api.config.settings import Settings
from health_api.domain.schemas import ProfilePayloadV1, ProfileValidity
from health_api.integrations.firebase_auth import FirebaseTokenVerifier, TokenVerificationError
from health_api.integrations.personal_ai_context import HealthContextReadRequest
from health_api.integrations.personal_ai_context_auth import (
    PersonalAIContextAuthorizationError,
    PersonalAIContextIdentityVerifier,
)
from health_api.persistence.models import ProviderIdentity, R5PreviewWireBinding, User
from health_loopback_proof import PROOF_HEADER, TRANSACTION_HEADER, sign, verify
from health_step2_worker import ISSUER, SYNTHETIC_PREFERENCE
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

CALLBACK_AUDIENCE = "https://health-fixture.invalid"
PAS_AUDIENCE = "https://pas-fixture.invalid"
SERVICE = "pas@health-fixture.invalid"


def main():
    attempts = []

    def audit(event, args):
        denied = event in {
            "socket.getaddrinfo",
            "socket.gethostbyname",
            "socket.gethostbyaddr",
            "socket.sendto",
            "socket.sendmsg",
            "socket.connect",
        }
        if event == "socket.bind":
            denied = args[1][0] != "127.0.0.1"
        if denied:
            attempts.append(event)
            raise PermissionError("Health fixture permits only its numeric loopback listener")

    url = make_url(os.environ["R5_HEALTH_SOCKET_DSN"])
    assert url.host is None and url.query["host"].startswith("/")
    sys.addaudithook(audit)
    config = json.loads(sys.stdin.readline())
    subject = config["subject"]
    worker_id = str(uuid4())
    path = f"/callback/{worker_id}"
    callback_key = bytes.fromhex(config["callback_key"])
    settings = Settings(
        app_env="test",
        auth_mode="firebase",
        firebase_project_id="health-fixture",
        personal_ai_context_service_audience=CALLBACK_AUDIENCE,
        personal_ai_context_service_account=SERVICE,
        personal_ai_context_read_enabled=True,
        personal_ai_r5_preview_enabled=True,
    )
    engine = create_engine(url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    uid = f"fixture-{uuid4()}"
    now = int(datetime.now(UTC).timestamp())
    with sessions() as session, session.begin():
        owner = User(id=uuid4(), display_timezone="UTC")
        session.add(owner)
        session.flush()
        session.add(ProviderIdentity(issuer=ISSUER, subject=uid, user_id=owner.id))
        objects = [
            create_profile_item(
                session,
                owner.id,
                CreateProfile(
                    id=uuid4(),
                    profile=ProfilePayloadV1.model_validate(SYNTHETIC_PREFERENCE),
                    validity=ProfileValidity(),
                    ai_use_allowed=True,
                    cross_domain_use_allowed=True,
                ),
            ).aggregate[0]
            for _ in range(2)
        ]
    authority = None
    active = None
    google_subject = subject
    linked_uid = uid
    revoked = False
    lost = False
    seen = set()
    protected_reads = 0
    firebase = FirebaseTokenVerifier("health-fixture", timeout_seconds=1, max_in_flight=2)

    def verify_firebase(token, *, app, check_revoked):
        if active is None or token != active["firebase_token"] or revoked or not check_revoked:
            raise TokenVerificationError
        return {"iss": ISSUER, "aud": "health-fixture", "sub": uid, "iat": now, "auth_time": now}

    def linked(provider, provider_subject, *, app):
        if provider != "google.com" or provider_subject != google_subject:
            raise TokenVerificationError
        return SimpleNamespace(
            uid=linked_uid,
            disabled=False,
            provider_data=(SimpleNamespace(provider_id=provider, uid=provider_subject),),
        )

    class FirebaseError(Exception):
        pass

    firebase._sdk = lambda: (
        SimpleNamespace(
            get_app=lambda _: None, exceptions=SimpleNamespace(FirebaseError=FirebaseError)
        ),
        SimpleNamespace(
            verify_id_token=verify_firebase,
            get_user_by_provider_uid=linked,
            InvalidIdTokenError=TokenVerificationError,
            ExpiredIdTokenError=TokenVerificationError,
            RevokedIdTokenError=TokenVerificationError,
            UserDisabledError=TokenVerificationError,
            UserNotFoundError=TokenVerificationError,
            CertificateFetchError=FirebaseError,
        ),
    )

    def current():
        if active is None or authority is None:
            return None
        try:
            identity = firebase.verify(active["firebase_token"])
            if firebase.resolve_google_provider_uid(subject) != identity.subject:
                return None
        except (TokenVerificationError, ValueError):
            return None
        return R5SourceAuthority(
            identity,
            authority.enrollment_id,
            authority.enrollment_generation,
            authority.installation_id,
            authority.selection,
        )

    def source(raw):
        nonlocal protected_reads
        request = HealthContextReadRequest.model_validate_json(raw)
        if request.operation == "profile":
            parse_r5_source_request(raw, authority.selection)
            protected_reads += 1
            _, response = read_r5_health_preference(sessions, settings, raw, authority, current)
            return response.model_dump_json().encode()
        if (
            request.operation != "verify"
            or request.category != "profile_preferences"
            or request.fields != ("permission_version",)
            or request.max_results != 1
            or len(request.entity_refs) != 1
            or request.entity_refs[0].object_type != "profile_item"
            or request.entity_refs[0].object_id != authority.selection.object_id
            or current() != authority
        ):
            raise R5PreviewUnavailable
        protected_reads += 1
        with sessions() as session, session.begin():
            owner_id = resolve_r5_owner(session, authority)
            response = read_personal_ai_health_context(session, owner_id, request)
        if current() != authority:
            raise R5PreviewUnavailable
        return response.model_dump_json().encode()

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            try:
                size = int(self.headers.get("content-length", "0"))
                if self.path != path or not 0 < size <= 4096 or active is None or authority is None:
                    raise R5PreviewUnavailable
                raw = self.rfile.read(size)
                proofs = self.headers.get_all(PROOF_HEADER, [])
                transactions = self.headers.get_all(TRANSACTION_HEADER, [])
                if len(proofs) != 1 or transactions != [active["transaction"]]:
                    raise R5PreviewUnavailable
                proof = proofs[0]
                nonce = verify(
                    callback_key,
                    f"{CALLBACK_AUDIENCE}/{transactions[0]}",
                    "POST",
                    self.path,
                    raw,
                    proof,
                )
                if nonce is None or nonce in seen or current() != authority:
                    raise R5PreviewUnavailable
                seen.add(nonce)
                # The fixture HMAC stands in for Google service claims. The existing
                # broad-read verifier still enforces the separate service and Firebase checks.
                verified_service = PersonalAIContextIdentityVerifier()
                verified_service._google_claims = lambda token, audience: (
                    {"email": SERVICE, "email_verified": True}
                    if token == proof and audience == CALLBACK_AUDIENCE
                    else {}
                )
                verified_service.verify(
                    service_token=proof,
                    user_token=active["firebase_token"],
                    settings=settings,
                    user_verifier=firebase,
                )
                response = source(raw)
            except (ValueError, PersonalAIContextAuthorizationError):
                self.send_error(403)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    class NumericLoopbackServer(ThreadingHTTPServer):
        def server_bind(self):
            TCPServer.server_bind(self)
            self.server_name, self.server_port = self.server_address

    server = NumericLoopbackServer(("127.0.0.1", 0), Callback)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    def reply(value):
        print(json.dumps(value, default=str), flush=True)

    def initialize(values):
        nonlocal authority
        if authority is not None:
            raise R5PreviewUnavailable
        identity = firebase.verify(active["firebase_token"])
        if firebase.resolve_google_provider_uid(values["subject"]) != identity.subject:
            raise R5PreviewUnavailable
        profile = objects[values["record"]]
        authority = R5SourceAuthority(
            identity,
            UUID(values["enrollment"]),
            values["generation"],
            UUID(values["installation"]),
            R5HealthSelection(profile.id, profile.revision),
        )

    def get_context(values):
        target = R5VerifiedCallerTarget(
            values["pas_owner"],
            values["client_namespace"],
            UUID(values["branch_id"]),
            values["destination_digest"],
            values["actor"],
            values["source_epoch"],
            values["policy_epoch"],
        )
        assert values["actor"] == f"https://accounts.google.com|{subject}"
        return {
            "intent_id": UUID(values["intent"]),
            "source_request": values["profile_request"].encode(),
            "authority": authority,
            "target": target,
            "reauthorize": lambda: (live, target) if (live := current()) is not None else None,
        }

    reply(
        {
            "owner": owner.id,
            "records": [
                {"object_id": profile.id, "revision": profile.revision} for profile in objects
            ],
            "port": server.server_port,
            "path": path,
        }
    )
    for line in sys.stdin:
        operation, values = json.loads(line)
        transient = operation in {"enroll", "reserve", "bind_preview", "observe"}
        if transient and (active is not None or lost):
            reply({"denied": True})
            continue
        if transient:
            active = {"firebase_token": uuid4().hex, "transaction": None}
        try:
            if operation == "enroll":
                if values.get("consented") is not True:
                    raise R5PreviewUnavailable
                initialize(values)
                reply({"enrolled": True})
            elif operation == "reserve":
                context = get_context(values)
                context["request"] = context.pop("source_request")
                original = reserve_r5_operation_keys(
                    sessions, settings, **context, current_intent=lambda _: True
                )
                with sessions() as session:
                    wire = session.get(R5PreviewWireBinding, original.create)
                    assert wire is not None
                    wire_metadata = {"pas_owner": wire.pas_owner_id, "digest": wire.request_digest}
                reply(
                    asdict(original)
                    | {"request": r5_create_request(original).decode(), **wire_metadata}
                )
            elif operation in {"sign", "begin"}:
                if active is not None or lost:
                    raise R5PreviewUnavailable
                active = {"firebase_token": uuid4().hex, "transaction": values["nonce"]}
                if current() != authority or authority is None:
                    active = None
                    raise R5PreviewUnavailable
                if operation == "sign":
                    reply(
                        {
                            "proof": sign(
                                bytes.fromhex(config["forward_key"]),
                                PAS_AUDIENCE,
                                values["method"],
                                values["path"],
                                values["body"].encode(),
                                nonce=values["nonce"],
                            )
                        }
                    )
                else:
                    reply({"ok": True})
            elif operation == "finish":
                active = None
                reply({"ok": True})
            elif operation in {"bind_preview", "observe"}:
                context = get_context(values)
                original = R5OriginalKeys(UUID(values["create"]), UUID(values["preview"]))
                keys = {
                    "offline-preview-key": Ed25519PublicKey.from_public_bytes(
                        bytes.fromhex(values["receipt_key"])
                    )
                }
                if operation == "bind_preview":
                    conversation, digest = bind_r5_preview_request(
                        sessions,
                        settings,
                        **context,
                        original=original,
                        receipt_keys=keys,
                        create_response=values["body"].encode(),
                        create_receipt=values["receipt"],
                        request=values["request"],
                        current_intent=lambda pair, bound=original, live=values["witness"]: (
                            pair == bound and live
                        ),
                    )
                    reply({"conversation": conversation, "digest": digest})
                else:
                    epochs = R5PreviewEpochs(**values["epochs"])

                    def get_status(path, nonce=values["nonce"], scope=active):
                        scope["transaction"] = nonce
                        reply(
                            {
                                "get": path,
                                "proof": sign(
                                    bytes.fromhex(config["forward_key"]),
                                    PAS_AUDIENCE,
                                    "GET",
                                    path,
                                    b"",
                                    nonce=nonce,
                                ),
                            }
                        )
                        action, response = json.loads(sys.stdin.readline())
                        assert action == "get_response"
                        if response.get("timeout"):
                            raise TimeoutError
                        if response.get("revoke"):
                            nonlocal revoked
                            revoked = True
                        if response.get("revoke_source"):
                            with sessions() as session, session.begin():
                                update_profile_item(
                                    session,
                                    owner.id,
                                    authority.selection.object_id,
                                    authority.selection.revision,
                                    {"cross_domain_use_allowed": False},
                                )
                        return response["status"], response["body"].encode(), response["receipt"]

                    result = observe_r5_preview(
                        sessions,
                        settings,
                        **context,
                        original=original,
                        receipt_keys=keys,
                        conversation_id=UUID(values["conversation"]),
                        request_digest=values["digest"],
                        current_epochs=lambda key, bound=original.preview, live=values["witness"], snapshot=epochs: (
                            snapshot if key == bound and live else None
                        ),
                        get_status=get_status,
                    )
                    reply({"metadata": None if result is None else asdict(result)})
            elif operation in {"relink", "restore_link"}:
                linked_uid = uid if operation == "restore_link" else str(uuid4())
                reply({"ok": True})
            elif operation in {"revoke", "restore_session"}:
                revoked = operation == "revoke"
                reply({"ok": True})
            elif operation == "forget":
                active = None
                lost = True
                reply({"ok": True})
            elif operation == "counts":
                reply({"protected_reads": protected_reads, "forbidden_network_attempts": attempts})
            elif operation == "stop":
                reply({"forbidden_network_attempts": attempts, "protected_reads": protected_reads})
                break
            else:
                raise AssertionError("unknown Health fixture operation")
        except (R5PreviewUnavailable, TokenVerificationError):
            reply({"denied": True})
        finally:
            if transient:
                active = None
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=2)
    engine.dispose()


if __name__ == "__main__":
    main()
