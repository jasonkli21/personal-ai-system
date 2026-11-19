"""Isolated consumer composition. The regular API and loopback factories never mount it."""

import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Annotated
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, Request
from fastapi.routing import APIRoute
from starlette.routing import Match

from personal_ai.api import dependencies as deps
from personal_ai.api.routes import _request_id, _sse_response
from personal_ai.auth.application_clients import client_binding_namespace
from personal_ai.auth.dispatch_grants import (
    ApplicationPlanScope,
    DispatchGrantSigner,
    DispatchGrantVerifier,
    LocalChatScope,
)
from personal_ai.auth.scope import (
    ApplicationScope,
    application_scope_context,
    current_verified_principal,
)
from personal_ai.context import ContextAssembler
from personal_ai.context.contracts import fingerprint
from personal_ai.context.planner import ContextPlanner, ContextPlanningRule
from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry, ContextRuntimeRegistry
from personal_ai.entities import Conversation, Message
from personal_ai.llm.chatgpt.oauth import ISSUER, REQUIRED_USAGE_SCOPES
from personal_ai.llm.chatgpt.responses import PROVIDER, serialize
from personal_ai.llm.external import CHATGPT_PLAN_PROFILE
from personal_ai.local_bridge.application_plan import PairedApplicationRuntime
from personal_ai.local_bridge.lifecycle import CredentialLifecycle
from personal_ai.local_bridge.runtime import (
    CompatibilityGate,
    LocalChatGPTBridge,
    LocalChatInstallation,
)
from personal_ai.local_bridge.store import Credentials, ProtectedLocalStore, Registration
from personal_ai.memory.contracts import Memory, MemoryCandidate, identity, normalize
from personal_ai.memory.dependencies import MemoryPermissionRevalidator
from personal_ai.memory.lifecycle.repositories import InMemoryMemoryLifecycleRepository
from personal_ai.memory.repositories import InMemoryMemoryRepository
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.external_turns.application_plan import (
    MAX_CONTEXT_TOKENS,
    ApplicationPlanService,
    PlanAttempts,
    PlanContinuation,
    PlanTarget,
)
from personal_ai.services.external_turns.plan_memory import ApplicationPlanMemory, MemoryDisclosure
from personal_ai.storage.async_io import sync_call
from tests.test_chatgpt_bridge_transport import ProviderFixture
from tests.test_chatgpt_local_lifecycle import FakeOAuth

from .shared import RUNTIME, plan_source_recipients

MODEL = "account-visible-model"
PRIVATE_HEADER = b"x-pas-user-plan"
PROMPT = "Summarize my app records using my saved preference."


class PlanSelectionRoute(APIRoute):
    def matches(self, scope):
        result = super().matches(scope)
        if (PRIVATE_HEADER, b"1") not in scope.get("headers", ()):
            return Match.NONE, {}
        return result


class MemoryRoots:
    def __init__(self):
        self.rows = {}
        self.lock = RLock()

    @contextmanager
    def transaction(self, *, owner_id):
        with self.lock:
            yield self

    def current_time(self, _connection):
        return datetime.now(UTC)

    def open_root(self, connection, *, root_id, owner_id, payload, plan, deadline):
        row = self.rows.setdefault((root_id, owner_id), (payload, plan, deadline, 0, "open", None))
        if row[:2] != (payload, plan):
            raise LookupError("routing_conflict")
        return row

    def root(self, connection, root_id, owner_id):
        return self.rows.get((root_id, owner_id))

    def change_root(self, connection, *, root_id, owner_id, candidate, state, attempt_id):
        key = root_id, owner_id
        self.rows[key] = (*self.rows[key][:3], candidate, state, attempt_id)


class ApplicationPlanFixture:
    def __init__(self, host, runtime_directory, *, attempts: Callable | None = None):
        self.host, self.runtime_directory = host, runtime_directory
        self.targets = {}
        self.disclosures = {}
        self.disclosure_epochs = {}
        self.recovery_available = True
        self.settings = host.settings
        self.memories = InMemoryMemoryRepository(host.messages)
        self.lifecycle = InMemoryMemoryLifecycleRepository(self.memories, host.messages)
        reader = MemoryPermissionRevalidator(
            self.settings,
            self.memories,
            host.messages,
            self.lifecycle,
            application_registry=host.app.state.application_registry,
        )
        self.memory = ApplicationPlanMemory(
            reader,
            current_scope=lambda: self.service.current_target().scope,
            current_disclosures=lambda scope: self.disclosures.get(scope, ()),
            source_rights=self.memory_source_rights,
        )
        self.roots = MemoryRoots()
        self.claim_witness = {}
        repository = (
            attempts(self)
            if attempts
            else PlanAttempts(
                self.roots,
                self.roots,
                recovery_current=self.recovery_current,
                record_claim=self.record_claim,
            )
        )
        self.authority = repository
        self.private = Ed25519PrivateKey.generate()
        self.signer = DispatchGrantSigner(issuer="fixture-pas", key_id="app-plan", key=self.private)
        self.service = ApplicationPlanService(
            signer=self.signer,
            target_for_request=self.target_for,
            memory=self.memory,
            attempts=repository,
        )
        prior_recovery = host.directory.recovery_current
        host.directory.recovery_current = lambda: prior_recovery() and repository.recovery_current()
        host.controls.plan_recipients = self.source_recipients
        host.app.dependency_overrides.update(
            {
                deps.get_memory_repository: lambda: None,
                deps.get_context_permission_revalidator: lambda: (
                    ContextPermissionRevalidatorRegistry((host.permissions, reader, self.memory))
                ),
            }
        )
        self.mount()

    def record_claim(self, root, owner, attempt, payload):
        with self.roots.lock:
            self.claim_witness[root, owner] = attempt, payload

    def recovery_current(self):
        with self.roots.lock:
            return self.recovery_available and all(
                (row := self.roots.rows.get(key)) is not None
                and (row[5], row[0]) == expected
                and row[4] == "fenced"
                for key, expected in self.claim_witness.items()
            )

    def target_for(self, scope, client):
        return self.targets.get((scope.owner_id, scope.application_id, scope.workspace_id, client))

    def source_recipients(self, owner, app, workspace, client):
        target = self.targets.get((owner, app, workspace, client))
        return (target.scope.local_recipient, target.scope.model_recipient) if target else ()

    def memory_source_rights(self, scope, origin):
        principal = current_verified_principal()
        return (
            principal is not None
            and principal.owner_id == scope.owner_id
            and self.host.controls.is_member(principal, origin.application_id, origin.workspace_id)
        )

    def share_memory(self, target, memory):
        scope = target.plan.scope
        assert memory.owner_id == scope.owner_id
        principal = self.host.identify(target.control)
        self.host.directory.ensure_active(principal, correlation_id="memory-control")
        assert (principal.owner_id, principal.audience, principal.authorized_party) == (
            scope.owner_id,
            "owner-control",
            "owner-control",
        )
        epoch = self.disclosure_epochs.get(scope, 0) + 1
        self.disclosure_epochs[scope] = epoch
        origin = ApplicationScope(
            application_id=memory.application_id, workspace_id=memory.workspace_id
        )
        self.disclosures[scope] = tuple(
            MemoryDisclosure(
                scope, origin, memory.id, recipient, epoch, self.host.now + timedelta(minutes=2)
            )
            for recipient in (scope.local_recipient, scope.model_recipient)
        )

    def mount(self):
        host = self.host
        service = self.service
        channel_tokens = MAX_CONTEXT_TOKENS // 2

        def plan_assembler(
            context: Annotated[ContextAssembler, Depends(deps.get_external_context_assembler)],
            runtime: Annotated[ContextRuntimeRegistry, Depends(deps.get_context_runtime_registry)],
        ):
            rules = (
                *(
                    rule.model_copy(update={"max_tokens": channel_tokens})
                    for rule in runtime.planning_rules
                ),
                ContextPlanningRule(
                    rule_id="application-plan-memory:v1",
                    category="personal_recall",
                    phrases=("saved preference",),
                    provider_id="ai_memory",
                    operation="search",
                    fields=("content",),
                    max_results=1,
                    max_bytes=4096,
                    max_tokens=channel_tokens,
                    timeout_seconds=1,
                    required=True,
                    explanation="Use the explicitly shared PAS memory.",
                ),
            )
            return ContextAssembler(
                context.settings.model_copy(
                    update={
                        "max_context_tokens": 10240,
                        "memory_max_context_tokens": channel_tokens,
                    }
                ),
                context.counter,
                context_provider_coordinator=context.context_provider_coordinator,
                permission_revalidator=context.permission_revalidator,
                context_planner=ContextPlanner(rules, max_total_tokens=MAX_CONTEXT_TOKENS),
            )

        async def preview(
            conversation_id: UUID,
            incoming: PlanContinuation,
            chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
            assembler: Annotated[ContextAssembler, Depends(plan_assembler)],
        ):
            target = await sync_call(service.current_target)
            token = plan_source_recipients.set(
                (target.scope.local_recipient, target.scope.model_recipient)
            )
            try:
                return await sync_call(service.preview, chat, assembler, conversation_id, incoming)
            finally:
                plan_source_recipients.reset(token)

        async def continue_turn(
            conversation_id: UUID,
            incoming: PlanContinuation,
            request: Request,
            chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
            assembler: Annotated[ContextAssembler, Depends(plan_assembler)],
        ):
            stream = await sync_call(
                service.continue_turn, chat, assembler, conversation_id, incoming
            )
            return _sse_response(stream, request_id=_request_id(request))

        host.app.router.routes[0:0] = [
            PlanSelectionRoute(
                "/v1/conversations/{conversation_id}/" + suffix,
                handler,
                methods=["POST"],
                include_in_schema=False,
                dependency_overrides_provider=host.app,
            )
            for suffix, handler in (("context-preview", preview), ("continue", continue_turn))
        ]

    def onboard(self, target, *, memory_content, model=MODEL, gate=True, source_grants=True):
        host = self.host
        actor = f"{target.principal.issuer}|{target.principal.subject}"
        namespace = client_binding_namespace(host.identify(target.token), target.app.app)
        label = f"{target.app.app}-{target.principal.subject}"
        connection_id = uuid4()
        store = ProtectedLocalStore(self.runtime_directory / uuid4().hex)
        now = int(datetime.now(UTC).timestamp())
        credentials = Credentials(
            access_token="fake-plan-access-" + label,
            refresh_token="fake-plan-refresh-" + label,
            id_token="fake-plan-id-" + label,
            scopes=tuple(REQUIRED_USAGE_SCOPES),
            expires_at=now + 3600,
        )
        registration = Registration(
            connection_id=str(connection_id),
            client_id="oaiapp_" + target.app.app,
            issuer=ISSUER,
            subject="plan-subject-" + label,
            credentials=credentials,
            state="connected",
            revision=1,
        )
        with store.transaction() as tx:
            tx.state.registrations[str(connection_id)] = registration
            tx.save()
            installation = LocalChatInstallation(
                scope=LocalChatScope(
                    owner_id=target.principal.owner_id, actor_id=actor, workspace_id=None
                ),
                origin="http://127.0.0.1:49321",
                host_id=tx.state.host_id,
                runtime_id=UUID(tx.state.runtime_id),
                signer_key_id="app-plan",
                connection_id=connection_id,
                connection_revision=1,
                client_id=registration.client_id,
                account_issuer=registration.issuer,
                account_subject=registration.subject,
            )
        scope = ApplicationPlanScope(
            application_id=target.app.app,
            workspace_id=target.workspace,
            owner_id=target.principal.owner_id,
            actor_id=actor,
            client_namespace=namespace,
            runtime_id=installation.runtime_id,
            registration_binding=installation.registration_binding,
            local_recipient=f"local:{installation.runtime_id}",
            model_recipient=f"openai-responses:{installation.registration_binding}",
        )
        installation = replace(installation, scope=scope)
        provider = ProviderFixture()
        compatibility = CompatibilityGate(
            connection_id=installation.connection_id,
            client_id=registration.client_id,
            distribution="local_personal",
            compatibility_reference="fixture-eligibility",
            plan_only_reference="fixture-no-credits",
            execution_profile=CHATGPT_PLAN_PROFILE,
            model_id=model,
            plan_only_verified=gate,
            verified_at=now,
            valid_until=now + 300,
            data_use={
                "status": "approved",
                "max_sensitivity": "sensitive",
                "policy_reference": "fixture-privacy",
            },
        )
        bridge = LocalChatGPTBridge(
            CredentialLifecycle(store, FakeOAuth()),
            provider.provider,
            DispatchGrantVerifier(
                issuer=self.signer.issuer,
                keys={self.signer.key_id: self.private.public_key()},
                audience=installation.runtime_id,
            ),
            installation=installation,
            gates=(compatibility,),
            root_authority=self.service,
        )
        session = bridge.approve_pairing(installation.origin, str(connection_id))
        runtime = PairedApplicationRuntime(bridge, session)
        pairing = PlanTarget(
            scope=scope,
            runtime=runtime,
            caller_id=session.caller_id,
            connection_id=connection_id,
            connection_revision=1,
            profile=CHATGPT_PLAN_PROFILE,
            provider_id=PROVIDER,
            serialize_payload=lambda package: serialize(package.chat_messages(), package.model_id),
            model=model,
            source_provider_id=target.app.source,
        )
        self.targets[scope.owner_id, scope.application_id, scope.workspace_id, namespace] = pairing
        if source_grants:
            revision = host.control(
                target.control,
                target.app,
                target.workspace,
                target.token,
                operation="link",
                expected_revision=0,
            )
            for recipient, fields in (
                (RUNTIME, ("title", *target.app.fields)),
                (scope.local_recipient, target.app.fields),
                (scope.model_recipient, target.app.fields),
            ):
                revision = host.control(
                    target.control,
                    target.app,
                    target.workspace,
                    target.token,
                    operation="grant",
                    expected_revision=revision,
                    recipient=recipient,
                    fields=fields,
                    expires_at=host.now + timedelta(minutes=2),
                )
        memory = self.seed_memory(target, memory_content)
        target.plan, target.store, target.provider = pairing, store, provider
        target.bridge, target.session, target.memory = bridge, session, memory
        self.share_memory(target, memory)
        target.source_grant_revision = revision if source_grants else None
        target.local_payloads, target.proofs = [], []
        original_execute = bridge.execute

        def record_delivery(package, proof, **options):
            target.local_payloads.append(package.canonical())
            target.proofs.append((package, proof))
            return original_execute(package, proof, **options)

        bridge.execute = record_delivery
        return target

    def seed_memory(self, target, content):
        scope = ApplicationScope(application_id=target.app.app, workspace_id=target.workspace)
        with application_scope_context(scope):
            return self._seed_memory(target, content)

    def _seed_memory(self, target, content):
        now = self.host.now
        ids = uuid4(), uuid4(), uuid4()
        scope = {
            "owner_id": target.principal.owner_id,
            "application_id": target.app.app,
            "workspace_id": target.workspace,
        }
        self.host.conversations.create(
            Conversation(
                id=ids[0],
                title="Fixture memory origin",
                created_at=now,
                updated_at=now,
                **scope,
            )
        )
        user = self.host.messages.create(
            Message(
                id=ids[1],
                conversation_id=ids[0],
                role="user",
                content=content,
                status="completed",
                created_at=now,
                **scope,
            )
        )
        self.host.messages.create(
            Message(
                id=ids[2],
                conversation_id=ids[0],
                role="assistant",
                content="Recorded.",
                status="completed",
                created_at=now,
                parent_message_id=user.id,
                **scope,
            )
        )
        candidate = MemoryCandidate(
            memory_type="preference",
            content=content,
            source_message_ids=(user.id,),
            confidence=1,
            effective_at=now,
            rationale_code="user_preference",
        )
        source = fingerprint([user])
        model, dimensions = (
            self.settings.memory_embedding_model,
            self.settings.memory_embedding_dimensions,
        )
        record, _ = self.memories.create(
            Memory(
                id=identity(
                    scope["owner_id"],
                    source,
                    candidate,
                    application_id=scope["application_id"],
                    workspace_id=scope["workspace_id"],
                ),
                normalized_content=normalize(content),
                source_fingerprint=source,
                source_turn_id=ids[2],
                source_conversation_id=ids[0],
                observed_at=now,
                effective_at=now,
                created_at=now,
                embedding=(1.0,) + (0.0,) * (dimensions - 1),
                embedding_model=model,
                embedding_dimensions=dimensions,
                **candidate.model_dump(exclude={"effective_at"}),
                **scope,
            )
        )
        return record


def plan_request(key=None, confirmation=None, *, content=PROMPT):
    choice = {"mode": "user_owned_plan"}
    if confirmation is not None:
        choice["confirmation"] = confirmation
    return {"content": content, "idempotency_key": str(key or uuid4()), "choice": choice}


def plan_http(host, target, cid, action, payload):
    return host.http.post(
        f"/v1/conversations/{cid}/{action}",
        headers={**target.headers, PRIVATE_HEADER.decode(): "1"},
        json=payload,
    )


def opt_in_sdk(client):
    original = client._opener.open

    def open_http(request, **options):
        if (
            request.data
            and json.loads(request.data).get("choice", {}).get("mode") == "user_owned_plan"
        ):
            request.add_header(PRIVATE_HEADER.decode(), "1")
        return original(request, **options)

    client._opener.open = open_http
    return client
