"""Synthetic source hosts with real migrations, sessions and canonical domain records.

Only external IAM/Firebase lookups are replaced. No local development identity is
authorized to sign source tasks. Each host uses the supplied disposable schema.
"""

import base64
import os
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

PROJECTS = Path(__file__).resolve().parents[3]


def encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def task_settings(application, root_key, fingerprint):
    from personal_ai.contracts.task_control import SourceTaskSettings

    settings = SourceTaskSettings(
        base_url="https://pai.example.invalid",
        audience="https://pai.example.invalid",
        service_account=f"{application}@synthetic-project.iam.gserviceaccount.com",
        issuer=f"{application}-test",
        key_id=f"{application}-key",
        private_key=encode(Ed25519PrivateKey.generate().private_bytes_raw()),
        pai_issuer="pai-test",
        pai_key_id="pai-key",
        pai_public_key=encode(root_key.public_key().public_bytes_raw()),
        operation_fingerprint=fingerprint,
    )
    values = settings.model_dump(mode="json")
    values["private_key"] = settings.private_key.get_secret_value()
    return values


def migrate(engine, repository, location, script_folder="migrations"):
    directory = PROJECTS / repository / location
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / script_folder))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def travel_host(engine, tmp_path, fingerprint, root_key=None):
    from fastapi import FastAPI
    from personal_travel.api.dependencies import session_dependency
    from personal_travel.api.middleware import LocalBoundaryMiddleware
    from personal_travel.api.router import api_router
    from personal_travel.auth.contracts import VerifiedPrincipal
    from personal_travel.auth.google_oidc import stable_google_owner_id
    from personal_travel.auth.sessions import create_session
    from personal_travel.config import Settings, get_settings
    from personal_travel.main import app as production_app
    from personal_travel.models.trip import Trip

    migrate(engine, "personal-travel-app", "backend")
    key = root_key or Ed25519PrivateKey.generate()
    settings = Settings(
        _env_file=None,
        travel_auth_mode="google_oidc",
        google_oauth_client_id="synthetic-client",
        google_oauth_client_secret="synthetic-secret",
        google_oauth_redirect_uri="https://testserver/auth/google/callback",
        google_oauth_allowed_email="owner@example.invalid",
        google_oauth_allowed_hosted_domain="example.invalid",
        personal_ai_auth_mode="google_cloud_run_iam",
        personal_ai_base_url="https://pai.example.invalid",
        personal_ai_service_iam_audience="https://pai.example.invalid",
        personal_ai_service_account="travel@synthetic-project.iam.gserviceaccount.com",
        personal_ai_user_id_token_audience="synthetic-client",
        personal_ai_context_enabled=True,
        personal_ai_context_service_iam_audience="https://travel.example.invalid",
        personal_ai_context_service_account="pai@synthetic-project.iam.gserviceaccount.com",
        allowed_hosts="testserver,travel.example.invalid",
        cors_origins="https://testserver",
        task_control=task_settings("travel", key, fingerprint),
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.exception_handlers.update(production_app.exception_handlers)
    app.state.auth_settings_provider = lambda: settings
    app.state.auth_session_factory = factory
    app.add_middleware(
        LocalBoundaryMiddleware,
        hosts=settings.allowed_host_list,
        origins=settings.cors_origin_list,
    )
    app.include_router(api_router)
    owner = stable_google_owner_id("https://accounts.google.com", "synthetic-user")
    with factory() as session, session.begin():
        raw, csrf, _ = create_session(
            session,
            VerifiedPrincipal(
                issuer="https://accounts.google.com",
                subject="synthetic-user",
                owner_id=owner,
                email="owner@example.invalid",
                issued_at=int(time.time()),
                expires_at=int(time.time()) + 3600,
                authenticated_at=int(time.time()),
            ),
            ttl_seconds=3600,
        )
        trip = Trip(
            id=uuid4(),
            owner_id=owner,
            title="Private title excluded from task",
            start_date=date(2026, 10, 14),
            end_date=date(2026, 10, 16),
            timezone="UTC",
            destination="Synthetic destination",
            cross_domain_sharing_allowed=True,
            revision=1,
        )
        session.add(trip)
    old_settings, old_factory = (
        app.state.auth_settings_provider,
        app.state.auth_session_factory,
    )
    old_overrides = app.dependency_overrides.copy()

    def sessions():
        with factory() as session:
            yield session

    app.state.auth_settings_provider = lambda: settings
    app.state.auth_session_factory = factory
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[session_dependency] = sessions
    app.state.task_service_verifier = lambda *args, **kw: None
    try:
        with TestClient(app, base_url="https://testserver") as client:
            client.cookies.set(settings.auth_session_cookie_name, raw)
            client.cookies.set(settings.auth_csrf_cookie_name, csrf)
            client.headers["X-CSRF-Token"] = csrf
            yield SimpleNamespace(
                client=client,
                root_key=key,
                task=settings.task_control,
                entity_id=trip.id,
                entity_type="trip",
                version="1",
                category="trip",
                purpose="shopping_trip_context",
                fields=("destination", "start_date", "end_date"),
                prefix="/v1/shopping-tasks",
                choice={"trip_id": str(trip.id), "expected_trip_revision": 1},
            )
    finally:
        app.state.auth_settings_provider, app.state.auth_session_factory = (
            old_settings,
            old_factory,
        )
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)


def health_host(engine, tmp_path, fingerprint, root_key=None):
    from health_api.application.profile_service import (
        CreateProfile,
        create_profile_item,
    )
    from health_api.config.settings import Settings
    from health_api.domain.schemas import ProfilePayloadV1, ProfileValidity
    from health_api.integrations.firebase_auth import VerifiedIdentity

    # Apps normally have separate process environments. Isolate Health's
    # development app construction from Shopping's AUTH_MODE=local vocabulary.
    previous_auth_mode = os.environ.get("AUTH_MODE")
    os.environ["AUTH_MODE"] = "dev"
    try:
        from health_api.main import create_app
    finally:
        if previous_auth_mode is None:
            os.environ.pop("AUTH_MODE", None)
        else:
            os.environ["AUTH_MODE"] = previous_auth_mode
    from health_api.persistence.models import ProviderIdentity, User

    migrate(engine, "health-app", "")
    key = root_key or Ed25519PrivateKey.generate()
    settings = Settings(
        _env_file=None,
        app_env="test",
        auth_mode="firebase",
        firebase_project_id="synthetic-project",
        local_object_storage_root=tmp_path / "health-objects",
        task_google_subject="synthetic-user",
        personal_ai_federation_export_enabled=True,
        personal_ai_context_service_audience="https://health.example.invalid",
        personal_ai_context_service_account="pai@synthetic-project.iam.gserviceaccount.com",
        personal_ai_federation_delegation_issuer="pai-test",
        personal_ai_federation_delegation_key_id="pai-key",
        personal_ai_federation_delegation_public_key=encode(
            key.public_key().public_bytes_raw()
        ),
        task_control=task_settings("health", key, fingerprint),
    )

    class SyntheticFirebase:
        def verify(self, token):
            assert token == "synthetic-firebase-token"
            return VerifiedIdentity(
                "https://securetoken.google.com/synthetic-project",
                "synthetic-firebase-user",
                auth_time=int(time.time()),
                issued_at=int(time.time()),
            )

        def resolve_google_delegation(self, subject, authenticated_at):
            assert type(authenticated_at) is int
            return self.resolve_google_provider_uid(subject)

        def resolve_google_provider_uid(self, subject):
            assert subject == "synthetic-user"
            return "synthetic-firebase-user"

    owner = uuid4()
    with Session(engine) as session:
        session.add(User(id=owner, display_timezone="UTC"))
        session.flush()
        session.add(
            ProviderIdentity(
                issuer="https://securetoken.google.com/synthetic-project",
                subject="synthetic-firebase-user",
                user_id=owner,
            )
        )
        session.flush()
        aggregate = create_profile_item(
            session,
            owner,
            CreateProfile(
                id=uuid4(),
                profile=ProfilePayloadV1.model_validate(
                    {
                        "kind": "constraint",
                        "category": "constraints",
                        "key": "ergonomic_constraints",
                        "label": "Synthetic constraint",
                        "value": {"type": "text", "value": "Adjustable height"},
                    }
                ),
                validity=ProfileValidity(),
                ai_use_allowed=True,
                cross_domain_use_allowed=True,
                notes="Private note excluded from task",
            ),
        ).aggregate
        session.commit()
        entity_id, revision = aggregate[0].id, aggregate[0].revision
    app = create_app(
        settings=settings, engine=engine, identity_verifier=SyntheticFirebase()
    )
    app.state.task_service_verifier = lambda *args: {
        "email": "pai@synthetic-project.iam.gserviceaccount.com",
        "email_verified": True,
    }
    from health_api.integrations.personal_ai_context_auth import (
        PersonalAIContextIdentityVerifier,
    )

    original = PersonalAIContextIdentityVerifier._google_claims
    PersonalAIContextIdentityVerifier._google_claims = staticmethod(
        app.state.task_service_verifier
    )
    try:
        with TestClient(app, base_url="https://testserver") as client:
            client.headers["Authorization"] = "Bearer synthetic-firebase-token"
            yield SimpleNamespace(
                client=client,
                root_key=key,
                task=settings.task_control,
                entity_id=entity_id,
                entity_type="profile_item",
                version=f"health-object-v1:r{revision}:schema-1",
                category="ergonomic_constraints",
                purpose="health_ergonomic_constraints_to_shopping",
                fields=("ergonomic_constraints",),
                prefix="/shopping-tasks",
                choice={
                    "object_id": str(entity_id),
                    "expected_source_version": f"health-object-v1:r{revision}:schema-1",
                },
            )
    finally:
        PersonalAIContextIdentityVerifier._google_claims = staticmethod(original)
