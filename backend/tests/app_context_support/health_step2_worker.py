"""One disposable Health process for the Step 2 reservation and projection APIs."""

import json
import os
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

from health_api.application.personal_ai_context import (
    read_personal_ai_health_context,
)
from health_api.application.profile_service import CreateProfile, create_profile_item
from health_api.application.r5_health_caller import R5CallerTarget, reserve_r5_operation_keys
from health_api.application.r5_health_source import (
    R5HealthSelection,
    R5SourceAuthority,
    read_r5_health_preference,
    require_current_r5_source_authority,
    resolve_r5_owner,
)
from health_api.config.settings import Settings
from health_api.domain.schemas import ProfilePayloadV1, ProfileValidity
from health_api.integrations.firebase_auth import VerifiedIdentity
from health_api.integrations.personal_ai_context import HealthContextReadRequest
from health_api.persistence.models import ProviderIdentity, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SYNTHETIC_PREFERENCE = {
    "kind": "preference",
    "category": "preferences",
    "key": "r5_synthetic_presentation_format",
    "label": "Synthetic presentation format",
    "value": {"type": "text", "value": "bullets"},
}
ISSUER = "https://securetoken.google.com/health-fixture"
NETWORK_EVENTS = {
    "socket.connect",
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyaddr",
    "socket.sendto",
    "socket.sendmsg",
}


def main():
    from sqlalchemy.engine import make_url

    attempts = []

    def audit(event, _):
        if event in NETWORK_EVENTS:
            attempts.append(event)
            raise PermissionError("Health source fixture is socket only")

    url = make_url(os.environ["R5_HEALTH_SOCKET_DSN"])
    assert url.host is None and url.query["host"].startswith("/")
    sys.addaudithook(audit)
    settings = Settings(
        app_env="test",
        auth_mode="firebase",
        firebase_project_id="health-fixture",
        personal_ai_context_service_audience="https://health-fixture.invalid",
        personal_ai_context_service_account="pas@health-fixture.invalid",
        personal_ai_context_read_enabled=True,
        personal_ai_r5_preview_enabled=True,
    )
    engine = create_engine(url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    subject = "fixture-" + str(uuid4())
    now = int(datetime.now(UTC).timestamp())
    with sessions() as session, session.begin():
        owner = User(id=uuid4(), display_timezone="UTC")
        session.add(owner)
        session.flush()
        session.add(ProviderIdentity(issuer=ISSUER, subject=subject, user_id=owner.id))
        created = create_profile_item(
            session,
            owner.id,
            CreateProfile(
                id=uuid4(),
                profile=ProfilePayloadV1.model_validate(SYNTHETIC_PREFERENCE),
                validity=ProfileValidity(),
                ai_use_allowed=True,
                cross_domain_use_allowed=True,
            ),
        )
        profile = created.aggregate[0]
    authority = R5SourceAuthority(
        VerifiedIdentity(ISSUER, subject, now, now),
        uuid4(),
        1,
        uuid4(),
        R5HealthSelection(profile.id, profile.revision),
    )
    intent = uuid4()

    def reply(value):
        print(json.dumps(value), flush=True)

    reply(
        {
            "owner": str(owner.id),
            "enrollment_id": str(authority.enrollment_id),
            "installation_id": str(authority.installation_id),
            "object_id": str(profile.id),
            "revision": profile.revision,
        }
    )
    for line in sys.stdin:
        action, values = json.loads(line)
        if action == "reserve":
            target = R5CallerTarget(
                UUID(values["synthetic_pas_owner_uuid"]),
                UUID(values["client_id"]),
                UUID(values["branch_id"]),
                values["destination_digest"],
            )
            keys = reserve_r5_operation_keys(
                sessions,
                settings,
                intent_id=intent,
                request=values["profile_request"].encode(),
                authority=authority,
                target=target,
                create_request_digest=values["local_digest"],
                reauthorize=lambda target=target: (authority, target),
            )
            reply({"create": str(keys.create), "preview": str(keys.preview)})
        elif action == "source":
            raw = values["raw"].encode()
            if values["operation"] == "profile":
                _, response = read_r5_health_preference(
                    sessions,
                    settings,
                    raw,
                    authority,
                    lambda: authority,
                )
            else:
                require_current_r5_source_authority(settings, authority, authority)
                parsed = HealthContextReadRequest.model_validate_json(raw)
                assert parsed.operation == "verify" and parsed.category == "profile_preferences"
                assert parsed.entity_refs[0].object_id == authority.selection.object_id
                with sessions() as session, session.begin():
                    owner_id = resolve_r5_owner(session, authority)
                    response = read_personal_ai_health_context(session, owner_id, parsed)
                require_current_r5_source_authority(settings, authority, authority)
            reply({"body": response.model_dump_json()})
        elif action == "stop":
            reply({"forbidden_network_attempts": attempts})
            break
        else:
            raise ValueError("unknown action")
    engine.dispose()


if __name__ == "__main__":
    main()
