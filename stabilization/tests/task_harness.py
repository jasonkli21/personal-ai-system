"""Synthetic Finance → PAI → Shopping API flow with native domain/control records.

Run via scripts/run_native_tests.py tasks. Separate IAM/Firebase certificate lookup
is explicitly faked; Ed25519 signatures, request binding, API handlers, federation,
source consent/revisions, PostgreSQL control state and domain receipts are real.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import httpx2
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loopback_https import LoopbackHTTPS
from personal_ai.api import federation, mutations
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.middleware import AuthenticationMiddleware
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.auth.service_tokens import InvalidServiceToken
from personal_ai.context.deployment import configured_context_runtime
from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry
from personal_ai.contracts.context_references import ContextEntityReference
from personal_ai.federation.contracts import FederationGrantIntent
from personal_ai.federation.deployment import reconcile_federation_runtime_metadata
from personal_ai.federation.service import FederationPermissionAuthority
from personal_ai.mutations import deployment
from personal_ai.mutations.service import MutationService
from personal_ai.persistence.postgres.database import PostgresDatabase
from personal_ai.persistence.postgres.mutations import PostgresMutationRepository
from personal_ai.settings import Settings, get_settings
from source_hosts import health_host, migrate, travel_host
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

PROJECTS = Path(__file__).resolve().parents[3]


def _source_fixture():
    path = PROJECTS / "personal-finance/services/api/tests/test_shopping_tasks.py"
    spec = importlib.util.spec_from_file_location("suite_finance_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public(key):
    return (
        base64.urlsafe_b64encode(
            key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        )
        .decode()
        .rstrip("=")
    )


@pytest.fixture
def flow(request, monkeypatch, tmp_path):
    parameter = getattr(request, "param", "finance")
    use_https = isinstance(parameter, tuple)
    source_name = parameter[0] if use_https else parameter
    network = LoopbackHTTPS(tmp_path) if use_https else None
    if network:
        request.addfinalizer(network.close)
    dsn = os.environ.get("SUITE_TEST_POSTGRES_DSN", "")
    parsed = urlsplit(dsn)
    if not dsn:
        pytest.skip("explicit disposable suite PostgreSQL database required")
    if (
        parsed.hostname not in {"127.0.0.1", "localhost"}
        or not parsed.path.startswith("/suite_")
        or not parsed.path.endswith("_test")
    ):
        pytest.fail("refusing a non-owned/non-local suite database")
    engine = create_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1))
    request.addfinalizer(engine.dispose)
    names = {
        app: f"{app}_suite_{uuid4().hex}"
        for app in (
            {"finance", "shopping", "travel", "health"}
            if use_https
            else {"finance", "shopping", source_name}
        )
    }

    def drop_schemas():
        with engine.begin() as connection:
            for name in names.values():
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))

    request.addfinalizer(drop_schemas)
    with engine.begin() as connection:
        for name in names.values():
            connection.execute(text(f'CREATE SCHEMA "{name}"'))
    engines = {
        app: create_engine(
            dsn.replace("postgresql://", "postgresql+psycopg://", 1),
            connect_args={"options": f"-csearch_path={name}"},
        )
        for app, name in names.items()
    }
    for item in engines.values():
        request.addfinalizer(item.dispose)
    source_fixture = _source_fixture()
    migrate(
        engines["finance"], "personal-finance", "services/api", script_folder="alembic"
    )
    from shopping.integrations.personal_ai.tasks import NOTE_OPERATION_FINGERPRINT

    if source_name == "finance":
        source_generator = source_fixture.task_host.__wrapped__(
            monkeypatch, tmp_path, engines["finance"]
        )
        source, root_key = next(source_generator)
        host = None
    else:
        factory = travel_host if source_name == "travel" else health_host
        source_generator = factory(
            engines[source_name], tmp_path, NOTE_OPERATION_FINGERPRINT
        )
        host = next(source_generator)
        source, root_key = host.client, host.root_key
    request.addfinalizer(source_generator.close)
    from app.db.models import MonthlyDiscretionaryBudget
    from app.integrations.task_client import TaskControlClient
    from shopping.accounts.models import FirebaseOwnerBinding
    from shopping.config import Settings as ShoppingSettings
    from shopping.config import get_settings as get_shopping_settings
    from shopping.integrations.personal_ai.task_auth import PersonalAITaskAuthority
    from shopping.integrations.personal_ai.tasks import OPERATION_FINGERPRINT
    from shopping.main import app as shopping_app
    from shopping.projects.models import DelegatedTaskReceipt, ShoppingProject
    from shopping.projects.schemas import ProjectCreate
    from shopping.projects.service import create_project

    if source_name == "finance":
        source.app.state.settings = source.app.state.settings.__class__(
            **{
                **source.app.state.settings.__dict__,
                "task_settings": source.app.state.settings.task_settings.model_copy(
                    update={"operation_fingerprint": OPERATION_FINGERPRINT}
                ),
            }
        )
    all_clients = {source_name: source}
    all_tasks = {
        source_name: source.app.state.settings.task_settings
        if host is None
        else host.task
    }
    extra_generators = []
    if use_https:
        for additional in {"finance", "travel", "health"} - {source_name}:
            if additional == "finance":
                generator = source_fixture.task_host.__wrapped__(
                    monkeypatch, tmp_path / additional, engines[additional]
                )
                client, _unused_key = next(generator)
                client.app.state.settings = client.app.state.settings.__class__(
                    **{
                        **client.app.state.settings.__dict__,
                        "task_settings": client.app.state.settings.task_settings.model_copy(
                            update={
                                "operation_fingerprint": OPERATION_FINGERPRINT,
                                "pai_public_key": _public(root_key),
                            }
                        ),
                    }
                )
                task = client.app.state.settings.task_settings
            else:
                factory = travel_host if additional == "travel" else health_host
                generator = factory(
                    engines[additional],
                    tmp_path / additional,
                    NOTE_OPERATION_FINGERPRINT,
                    root_key,
                )
                additional_host = next(generator)
                client, task = additional_host.client, additional_host.task
            extra_generators.append(generator)
            request.addfinalizer(generator.close)
            all_clients[additional], all_tasks[additional] = client, task
    cfg = Config(str(PROJECTS / "shopping-assistant/apps/api/alembic.ini"))
    cfg.set_main_option(
        "script_location", str(PROJECTS / "shopping-assistant/apps/api/migrations")
    )
    with engines["shopping"].connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
    owner = uuid4()
    with Session(engines["shopping"]) as session:
        session.add(
            FirebaseOwnerBinding(firebase_uid="synthetic-firebase-user", owner_id=owner)
        )
        session.commit()
        project = create_project(
            session,
            owner,
            ProjectCreate(
                title="Synthetic suite project",
                goal="One confirmed budget",
                budget_target="10.00",
                budget_maximum="100.00",
                budget_currency="USD",
            ),
        )
    shop_settings = ShoppingSettings(
        _env_file=None,
        environment="staging",
        database_url="postgresql+psycopg://synthetic:synthetic@example.neon.tech/synthetic?sslmode=verify-full",
        personal_ai_mode="external",
        cors_origins="https://shopping.example.invalid",
        auth_mode="firebase",
        firebase_project_id="synthetic-project",
        firebase_owner_uid="synthetic-firebase-user",
        local_owner_id=owner,
        personal_ai_context_enabled=True,
        personal_ai_context_service_audience="https://shopping.example.invalid",
        personal_ai_context_service_account="pai@synthetic-project.iam.gserviceaccount.com",
        personal_ai_context_user_audience="synthetic-client",
        personal_ai_context_google_user_subject="synthetic-user",
        personal_ai_context_google_user_email="owner@example.invalid",
        personal_ai_context_identity_mapping_reference="explicit-synthetic-link",
        personal_ai_tasks_enabled=True,
        personal_ai_tasks_delegation_issuer="pai-test",
        personal_ai_tasks_delegation_key_id="pai-key",
        personal_ai_tasks_delegation_public_key=_public(root_key),
        personal_ai_tasks_authority_base_url="https://pai.example.invalid",
        personal_ai_tasks_authority_audience="https://pai.example.invalid",
        personal_ai_tasks_callback_service_account="shopping@synthetic-project.iam.gserviceaccount.com",
    )
    shopping_app.dependency_overrides[get_shopping_settings] = lambda: shop_settings
    request.addfinalizer(
        lambda: shopping_app.dependency_overrides.pop(get_shopping_settings, None)
    )
    sf = sessionmaker(bind=engines["shopping"], expire_on_commit=False)
    for attr in (
        "task_session_factory",
        "conversation_session_factory",
        "research_session_factory",
        "catalog_session_factory",
    ):
        setattr(shopping_app.state, attr, sf)
    monkeypatch.setattr(
        "shopping.integrations.personal_ai.task_auth._verify_token",
        lambda token, **kw: {
            "email": "pai@synthetic-project.iam.gserviceaccount.com",
            "email_verified": True,
        },
    )
    monkeypatch.setattr(
        "shopping.projects.dependencies._firebase_app", lambda project: object()
    )
    monkeypatch.setattr(
        "firebase_admin.auth.get_user",
        lambda uid, **kw: SimpleNamespace(
            uid=uid,
            disabled=False,
            tokens_valid_after_timestamp=0,
            provider_data=[
                SimpleNamespace(provider_id="google.com", uid="synthetic-user")
            ],
        ),
    )

    clients = {}
    sent = []
    lose_ack = {"enabled": False}
    unavailable = {"enabled": False}
    before_execute = {"callback": None}

    def domain_response(request):
        app = request.url.host.split(".")[0]
        body = json.loads(request.content)
        sent.append((app, request.url.path, body.get("action")))
        if app == "shopping" and body.get("action") == "execute":
            callback = before_execute["callback"]
            if callback:
                before_execute["callback"] = None
                callback()
        if (
            app == "shopping"
            and unavailable["enabled"]
            and body.get("action") == "execute"
        ):
            return httpx.Response(
                503, json={"code": "synthetic_destination_unavailable"}
            )
        response = clients[app].request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
        )
        if (
            app == "shopping"
            and body.get("action") == "execute"
            and lose_ack["enabled"]
        ):
            lose_ack["enabled"] = False
            raise httpx.ReadTimeout("synthetic lost acknowledgement")
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )

    original = deployment.domain_client

    def signed_client(settings, endpoint, audience=None):
        result = original(settings, endpoint, audience)
        result.transport = (
            network.transport() if network else httpx.MockTransport(domain_response)
        )
        result.token_fetcher = lambda **kw: (
            "synthetic:" + settings.task_domain_service_account
        )
        return result

    monkeypatch.setattr(deployment, "domain_client", signed_client)
    finance_task = (
        source.app.state.settings.task_settings if host is None else host.task
    )
    source_config = {}
    if source_name == "travel":
        source_config = {
            "travel_federation_enabled": True,
            "travel_context_base_url": "https://travel.example.invalid",
            "travel_context_service_audience": "https://travel.example.invalid",
            "travel_context_service_account": "pai@synthetic-project.iam.gserviceaccount.com",
        }
    elif source_name == "health":
        source_config = {
            "health_federation_enabled": True,
            "health_context_base_url": "https://health.example.invalid",
            "health_context_service_audience": "https://health.example.invalid",
            "health_context_service_account": "pai@synthetic-project.iam.gserviceaccount.com",
            "health_federation_delegation_issuer": "pai-test",
            "health_federation_delegation_key_id": "pai-key",
            "health_federation_delegation_private_key": base64.urlsafe_b64encode(
                root_key.private_bytes_raw()
            )
            .decode()
            .rstrip("="),
        }
    if use_https:
        source_config.update(
            travel_federation_enabled=True,
            travel_context_base_url="https://travel.example.invalid",
            travel_context_service_audience="https://travel.example.invalid",
            travel_context_service_account="pai@synthetic-project.iam.gserviceaccount.com",
            health_federation_enabled=True,
            health_context_base_url="https://health.example.invalid",
            health_context_service_audience="https://health.example.invalid",
            health_context_service_account="pai@synthetic-project.iam.gserviceaccount.com",
            health_federation_delegation_issuer="pai-test",
            health_federation_delegation_key_id="pai-key",
            health_federation_delegation_private_key=base64.urlsafe_b64encode(
                root_key.private_bytes_raw()
            )
            .decode()
            .rstrip("="),
        )
    root_settings_kwargs = source_config
    root_settings = Settings(
        _env_file=None,
        ai_provider="gemini",
        ai_model="synthetic-no-provider",
        app_environment="test",
        auth_mode="google_oidc",
        auth_required=True,
        auth_audience="synthetic-client",
        auth_allowed_emails=("owner@example.invalid",),
        auth_hosted_domain="example.invalid",
        persistence_local_postgres_dsn=dsn,
        finance_context_enabled=source_name == "finance" or use_https,
        finance_context_base_url="https://finance.example.invalid",
        finance_context_service_audience="https://finance.example.invalid",
        finance_context_service_account="pai@synthetic-project.iam.gserviceaccount.com",
        federation_choice_hmac_key="synthetic-choice-signing-key-at-least-32-bytes",
        task_delegation_enabled=True,
        task_delegation_audience="https://pai.example.invalid",
        task_delegation_issuer="pai-test",
        task_delegation_key_id="pai-key",
        task_delegation_private_key=base64.urlsafe_b64encode(
            root_key.private_bytes_raw()
        )
        .decode()
        .rstrip("="),
        task_domain_service_account="pai@synthetic-project.iam.gserviceaccount.com",
        task_source_endpoints={
            name: f"https://{name}.example.invalid" for name in all_clients
        },
        task_callback_accounts={
            "shopping": "shopping@synthetic-project.iam.gserviceaccount.com"
        },
        task_origin_trusts={
            name: {
                "issuer": task.issuer,
                "service_account": task.service_account,
                "key_id": task.key_id,
                "public_key": _public(
                    Ed25519PrivateKey.from_private_bytes(
                        base64.urlsafe_b64decode(
                            task.private_key.get_secret_value()
                            + "=" * (-len(task.private_key.get_secret_value()) % 4)
                        )
                    )
                ),
                "user_issuer": "https://accounts.google.com",
                "user_subject": "synthetic-user",
                "allowed_destinations": ["shopping"],
                "mapping_reference": "explicit-synthetic-link",
            }
            for name, task in all_tasks.items()
        },
        task_shopping_enabled=True,
        task_shopping_base_url="https://shopping.example.invalid",
        task_shopping_audience="https://shopping.example.invalid",
        task_shopping_operation_fingerprint=OPERATION_FINGERPRINT,
        task_shopping_note_operation_fingerprint=NOTE_OPERATION_FINGERPRINT,
        **root_settings_kwargs,
    )

    def service_identity(token, *, audience, service_account):
        if token != "synthetic:" + service_account:
            raise InvalidServiceToken

    monkeypatch.setattr(
        "personal_ai.auth.task_identity.verify_google_service_token", service_identity
    )
    database = PostgresDatabase(dsn, environment="test", min_size=1, max_size=4)
    request.addfinalizer(database.close)
    database.migrate()
    if source_name == "health" or use_https:
        from personal_ai.context import health_federation

        original_health = health_federation.HealthFederationExportClient

        def health_client(**kw):
            kw.update(
                transport=network.transport()
                if network
                else httpx.MockTransport(domain_response),
                service_token_fetcher=lambda **unused: (
                    "synthetic:" + kw["service_account"]
                ),
            )
            return original_health(**kw)

        monkeypatch.setattr(
            health_federation, "HealthFederationExportClient", health_client
        )
    runtime = configured_context_runtime(root_settings)
    registry = deployment.install_task_metadata(
        reconcile_federation_runtime_metadata(default_application_registry(), runtime),
        root_settings,
        runtime,
    )
    service = MutationService(
        PostgresMutationRepository(database),
        registry,
        runtime,
        ContextPermissionRevalidatorRegistry(runtime.permission_revalidators),
        command_resolver=deployment.configured_command_resolver(root_settings, runtime),
    )
    root_app = FastAPI()
    root_app.add_middleware(AuthenticationMiddleware)
    root_app.state.application_registry = registry
    root_app.state.context_runtime_registry = runtime
    root_app.dependency_overrides[get_settings] = lambda: root_settings
    root_app.dependency_overrides[mutations.get_mutation_service] = lambda: service
    root_app.include_router(mutations.router)
    root_app.include_router(federation.router)

    def root_response(request):
        response = clients["pai"].request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )

    def control_response(request):
        response = clients["pai"].request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx2.Response(
            response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )

    shopping_app.state.task_authority_factory = lambda settings, assertion: (
        PersonalAITaskAuthority(
            settings,
            assertion,
            transport=network.transport()
            if network
            else httpx.MockTransport(root_response),
            service_token_fetcher=lambda: (
                "synthetic:shopping@synthetic-project.iam.gserviceaccount.com"
            ),
        )
    )
    if source_name == "finance":
        source.app.state.task_control_client = TaskControlClient(
            finance_task,
            transport=network.transport(httpx2)
            if network
            else httpx2.MockTransport(control_response),
            token_fetcher=lambda audience, account: "synthetic:" + account,
        )
    else:
        from personal_ai.contracts.task_control import SourceTaskControlClient

        source.app.state.task_control_client = SourceTaskControlClient(
            application_id=source_name,
            base_url=finance_task.base_url,
            audience=finance_task.audience,
            issuer=finance_task.issuer,
            key_id=finance_task.key_id,
            private_key=finance_task.private_key.get_secret_value(),
            service_account=finance_task.service_account,
            token_fetcher=lambda audience, account: "synthetic:" + account,
            client_type=httpx.Client,
            transport=network.transport()
            if network
            else httpx.MockTransport(root_response),
        )
    for name, additional_client in all_clients.items():
        if name != source_name:
            from personal_ai.contracts.task_control import SourceTaskControlClient

            task = all_tasks[name]
            additional_client.app.state.task_control_client = SourceTaskControlClient(
                application_id=name,
                base_url=task.base_url,
                audience=task.audience,
                issuer=task.issuer,
                key_id=task.key_id,
                private_key=task.private_key.get_secret_value(),
                service_account=task.service_account,
                token_fetcher=lambda audience, account: "synthetic:" + account,
                client_type=httpx.Client,
                transport=network.transport(),
            )
        clients[name] = additional_client
    with TestClient(shopping_app) as shopping, TestClient(root_app) as pai:
        clients.update(shopping=shopping, pai=pai)
        if network:
            for name, client in clients.items():
                network.start(name, client.app)
        principal = AuthenticatedPrincipal(
            "https://accounts.google.com",
            "synthetic-user",
            "usr_"
            + hashlib.sha256(
                b"https://accounts.google.com\0synthetic-user"
            ).hexdigest()[:32],
            None,
            int(datetime.now(UTC).timestamp()),
            True,
            int(datetime.now(UTC).timestamp()),
        )
        # The grant is an explicit user action. The source command cannot issue it.
        if host is None:
            with Session(engines["finance"]) as session:
                budget = session.scalar(select(MonthlyDiscretionaryBudget))
                budget_id = budget.id
        else:
            budget_id = host.entity_id
        authority = next(
            v
            for v in runtime.permission_revalidators
            if isinstance(v, FederationPermissionAuthority)
        )
        token = bind_verified_principal(principal)
        scope_token = bind_request_scope(
            RequestScope(
                request_id="synthetic-grant-create",
                owner_id=principal.owner_id,
                acting_user_id=f"{principal.issuer}|{principal.subject}",
                application_id="shopping",
                workspace_id=None,
            )
        )
        try:
            grant = authority.create(
                principal,
                FederationGrantIntent(
                    grant_id=uuid4(),
                    owner_id=principal.owner_id,
                    acting_user_id=f"{principal.issuer}|{principal.subject}",
                    source=ApplicationScope(application_id=source_name),
                    destination=ApplicationScope(application_id="shopping"),
                    category=host.category if host else "discretionary_budget",
                    purpose=host.purpose if host else "shopping_discretionary_budget",
                    fields=host.fields if host else ("amount", "currency", "period"),
                    entities=(
                        ContextEntityReference(
                            application_id=source_name,
                            entity_type=host.entity_type
                            if host
                            else "discretionary_budget",
                            entity_id=str(budget_id),
                        ),
                    ),
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                ),
            )
        finally:
            reset_request_scope(scope_token)
            reset_verified_principal(token)
        prefix = host.prefix if host else "/v1/finance/shopping-tasks"
        options = source.get(prefix + "/choices")
        assert options.status_code == 200, options.text
        choice_id = authority._choice_handle(grant)
        assert choice_id in {item["id"] for item in options.json()["choices"]}
        if network:
            request.addfinalizer(network.close)
        yield SimpleNamespace(
            source=source,
            source_name=source_name,
            network=network,
            host=host,
            prefix=prefix,
            root=pai,
            shopping=shopping,
            engines=engines,
            database=database,
            owner=owner,
            project_id=project.id,
            choice_id=choice_id,
            sent=sent,
            lose_ack=lose_ack,
            unavailable=unavailable,
            before_execute=before_execute,
            authority=authority,
            grant=grant,
            principal=principal,
            service=service,
            ShoppingProject=ShoppingProject,
            Receipt=DelegatedTaskReceipt,
        )
