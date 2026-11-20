"""The installed consumer SDK uses one isolated, explicitly selected app-plan lane."""

# ruff: noqa: F811 - pytest imports fixtures by their parameter names

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from threading import Event
from uuid import UUID, uuid4

import pytest

from personal_ai.api.private_application_plan import PROFILE_PREFIX
from personal_ai.llm.chatgpt.responses import serialize
from personal_ai.local_bridge.store import LocalStoreError, ProtectedLocalStore
from personal_ai.memory.contracts import normalize
from personal_ai.memory.lifecycle.contracts import MemoryLifecycleState
from personal_ai.services.external_turns import application_plan
from tests.app_context_support.application_plan import (
    ApplicationPlanFixture,
    plan_http,
    plan_request,
)
from tests.app_context_support.shared import FITNESS_APP, READING_APP, TRAVEL_APP
from tests.app_context_support.shared_inference import RoutedGeneration
from tests.test_shared_application_service import (
    SECRET_TITLE,
    SITE,
    A,
    B,
    create,
    headers,
    post,
    provision,
    shared_factory,  # noqa: F401 - pytest fixture
    status,
)
from tests.test_shared_application_service import (
    body as automatic_body,
)

TRAVEL_MEMORY = "I prefer quiet places when traveling."
FITNESS_MEMORY = "I prefer a recovery walk after workouts."
READING_MEMORY = "I prefer short audiobooks."
TRAVEL_PLATFORM = "North platform"
BOOK_LABEL = "Borrowed book"


@pytest.fixture
def plan_factory(shared_factory, tmp_path):
    def create(*, selected=(TRAVEL_APP, FITNESS_APP), attempts=None, **options):
        def configure(host):
            host.plan = ApplicationPlanFixture(host, tmp_path, attempts=attempts)
            return RoutedGeneration(host.counter)

        return shared_factory(
            selected=selected,
            generation=configure,
            application_plan=True,
            **options,
        )

    return create


def travel(host, **options):
    target = provision(
        host,
        TRAVEL_APP,
        A,
        grant=False,
        data={"title": SECRET_TITLE, "platform": TRAVEL_PLATFORM},
    )
    return host.plan.onboard(target, memory_content=TRAVEL_MEMORY, **options)


def preview(host, target, cid, body):
    response = plan_http(host, target, cid, "context-preview", body)
    assert response.status_code == 200, response.text
    return response.json()


def confirmed(host, target, cid, body=None):
    body = body or plan_request()
    proposal = preview(host, target, cid, body)
    return plan_request(body["idempotency_key"], proposal["confirmation"], content=body["content"])


def assert_delivery(target, included, excluded):
    assert len(target.local_payloads) == 1
    assert len(target.provider.sends()) == 1
    package, proof = target.proofs[0]
    send = target.provider.sends()[0]
    assert target.local_payloads[0] == package.canonical()
    assert sha256(target.local_payloads[0]).hexdigest() == proof.claims.package_hash
    assert send.content == serialize(package.chat_messages(), package.model_id)
    assert sha256(send.content).hexdigest() == proof.claims.application_plan.provider_payload_sha256
    assert proof.claims.application_plan.scope == target.plan.scope
    assert send.headers["authorization"] == (
        f"Bearer fake-plan-access-{target.app.app}-{target.principal.subject}"
    )
    assert json.loads(send.content)["store"] is False
    for payload in (target.local_payloads[0], send.content):
        for marker in included:
            assert marker.encode() in payload
        for marker in excluded:
            assert marker.encode() not in payload


def test_automatic_history_requires_its_own_recipient(plan_factory):
    host = plan_factory()
    target = travel(host)
    outputs = iter(
        (
            ("EMPTY FOLLOWUP ANSWER", "success"),
            ("ORDINARY HISTORY ANSWER", "success"),
            ("POPULATED FOLLOWUP ANSWER", "success"),
        )
    )
    host.generation.transport = lambda _payload: next(outputs)

    empty_conversation = create(host, target)
    original = confirmed(host, target, empty_conversation)
    assert "event: response.completed" in plan_http(
        host, target, empty_conversation, "continue", original
    ).text
    assert len(target.provider.sends()) == 1

    empty_followup = post(
        host,
        target,
        empty_conversation,
        "continue",
        automatic_body(content="Continue with the next step."),
    )
    assert "event: response.completed" in empty_followup.text
    empty_input = host.generation.sends[-1][3]
    assert b"A streamed answer" not in empty_input
    assert TRAVEL_MEMORY.encode() not in empty_input

    replay = plan_http(host, target, empty_conversation, "continue", original)
    assert "event: response.completed" in replay.text
    assert len(target.provider.sends()) == 1
    assert len(target.local_payloads) == 1

    populated_conversation = create(host, target)
    ordinary = post(
        host,
        target,
        populated_conversation,
        "continue",
        automatic_body(content="Please say hello."),
    )
    assert "event: response.completed" in ordinary.text
    assert "ORDINARY HISTORY ANSWER" in ordinary.text
    proposal = confirmed(host, target, populated_conversation)
    assert "event: response.completed" in plan_http(
        host, target, populated_conversation, "continue", proposal
    ).text
    assert len(target.provider.sends()) == 2

    populated_followup = post(
        host,
        target,
        populated_conversation,
        "continue",
        automatic_body(content="Use the still-authorized conversation."),
    )
    assert "event: response.completed" in populated_followup.text
    populated_input = host.generation.sends[-1][3]
    assert b"ORDINARY HISTORY ANSWER" in populated_input
    assert b"A streamed answer" not in populated_input
    assert TRAVEL_MEMORY.encode() not in populated_input
    assert len(target.provider.sends()) == 2

    memory_revoked_conversation = create(host, target)
    memory_plan = confirmed(host, target, memory_revoked_conversation)
    assert "event: response.completed" in plan_http(
        host, target, memory_revoked_conversation, "continue", memory_plan
    ).text
    assert len(target.provider.sends()) == 3
    host.plan.disclosures.pop(target.plan.scope)
    sends_before_memory_denial = len(host.generation.sends)
    memory_followup = post(
        host,
        target,
        memory_revoked_conversation,
        "continue",
        automatic_body(content="Please say hello again."),
    )
    assert memory_followup.is_error
    assert len(host.generation.sends) == sends_before_memory_denial == 3

    host.plan.share_memory(target, target.memory)
    revoked_conversation = create(host, target)
    revoked_plan = confirmed(host, target, revoked_conversation)
    assert "event: response.completed" in plan_http(
        host, target, revoked_conversation, "continue", revoked_plan
    ).text
    assert len(target.provider.sends()) == 4

    revision = target.source_grant_revision
    for recipient in (target.plan.scope.local_recipient, target.plan.scope.model_recipient):
        revision = host.control(
            target.control,
            target.app,
            target.workspace,
            target.token,
            operation="revoke",
            expected_revision=revision,
            recipient=recipient,
        )
    host.plan.disclosures.pop(target.plan.scope)
    sends_before_denial = len(host.generation.sends)
    revoked_followup = post(
        host,
        target,
        revoked_conversation,
        "continue",
        automatic_body(content="Continue after the old plan authority was revoked."),
    )
    assert revoked_followup.is_error
    assert len(host.generation.sends) == sends_before_denial == 3
    assert len(target.provider.sends()) == 4


def test_plan_preview_accounts_for_selected_history(plan_factory):
    host = plan_factory()
    target = travel(host)
    host.generation.transport = lambda _payload: ("SOURCE FREE ANSWER", "success")

    conversation = create(host, target)
    prior_prompt = "SOURCE FREE PRIOR PROMPT"
    ordinary = post(
        host,
        target,
        conversation,
        "continue",
        automatic_body(content=prior_prompt),
    )
    assert "event: response.completed" in ordinary.text
    assert "SOURCE FREE ANSWER" in ordinary.text

    request = plan_request()
    selection = preview(host, target, conversation, request)
    history_item = next(
        row for row in selection["selected_context"]
        if row["category"] == "conversation_history"
    )
    assert history_item == {"category": "conversation_history", "turns": 1}
    assert prior_prompt not in json.dumps(selection)
    assert "SOURCE FREE ANSWER" not in json.dumps(selection)
    key = host.plan.service._key(
        target.plan, UUID(conversation), UUID(request["idempotency_key"])
    )
    package = host.plan.service._previews[key].package
    assert any(prior_prompt in message.content for message in package.messages)
    assert any("SOURCE FREE ANSWER" in message.content for message in package.messages)
    assert target.local_payloads == target.provider.sends() == []

    confirmed_request = plan_request(
        request["idempotency_key"], selection["confirmation"], content=request["content"]
    )
    assert "event: response.completed" in plan_http(
        host, target, conversation, "continue", confirmed_request
    ).text
    assert len(target.local_payloads) == len(target.provider.sends()) == 1

    empty_conversation = create(host, target)
    empty_request = plan_request()
    empty_selection = preview(host, target, empty_conversation, empty_request)
    assert next(
        row for row in empty_selection["selected_context"]
        if row["category"] == "conversation_history"
    ) == {"category": "conversation_history", "turns": 0}

    sourced_conversation = create(host, target)
    first = confirmed(host, target, sourced_conversation)
    assert "event: response.completed" in plan_http(
        host, target, sourced_conversation, "continue", first
    ).text
    next_request = plan_request(content="Summarize my app records using my saved preference again.")
    excluded_selection = preview(host, target, sourced_conversation, next_request)
    assert next(
        row for row in excluded_selection["selected_context"]
        if row["category"] == "conversation_history"
    ) == {"category": "conversation_history", "turns": 0}


def test_pending_previews_leave_capacity_for_another_client(plan_factory, monkeypatch):
    from personal_ai.context.providers import ContextPreparationError
    from personal_ai.services.external_turns.application_plan import MAX_PREVIEWS_PER_CLIENT

    host = plan_factory()
    first = travel(host)
    second = host.plan.onboard(
        provision(host, FITNESS_APP, B, grant=False),
        memory_content=FITNESS_MEMORY,
    )
    first_conversation = create(host, first)
    second_conversation = create(host, second)

    for index in range(MAX_PREVIEWS_PER_CLIENT):
        response = plan_http(
            host,
            first,
            first_conversation,
            "context-preview",
            plan_request(),
        )
        assert response.status_code == 200, response.text

    first_source = host.sources[first.app.source]
    first_reads = len(first_source.lookup_paths)
    memory_reads = 0
    original_retrieve = host.plan.memory.retrieve

    def count_memory_read(*args, **kwargs):
        nonlocal memory_reads
        memory_reads += 1
        return original_retrieve(*args, **kwargs)

    monkeypatch.setattr(host.plan.memory, "retrieve", count_memory_read)
    first_memory_reads = memory_reads
    denied = plan_http(
        host,
        first,
        first_conversation,
        "context-preview",
        plan_request(),
    )
    assert denied.is_error
    assert len(first_source.lookup_paths) == first_reads
    assert memory_reads == first_memory_reads

    request = plan_request()
    original_check = host.plan.service._require_current
    fail_once = True

    def fail_current_once(preview, permissions):
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise ContextPreparationError("context_no_ai_route")
        return original_check(preview, permissions)

    monkeypatch.setattr(host.plan.service, "_require_current", fail_current_once)
    failed = plan_http(
        host, second, second_conversation, "context-preview", request
    )
    assert failed.is_error
    assert not host.plan.service._reservations
    monkeypatch.setattr(host.plan.service, "_require_current", original_check)

    preview(host, second, second_conversation, request)
    for index in range(MAX_PREVIEWS_PER_CLIENT - 1):
        assert plan_http(
            host,
            second,
            second_conversation,
            "context-preview",
            plan_request(),
        ).status_code == 200
    second_source = host.sources[second.app.source]
    second_reads = len(second_source.lookup_paths)
    second_memory_reads = memory_reads
    blocked = plan_http(
        host,
        second,
        second_conversation,
        "context-preview",
        plan_request(),
    )
    assert blocked.is_error
    assert len(second_source.lookup_paths) == second_reads
    assert memory_reads == second_memory_reads

    from dataclasses import replace
    from datetime import timedelta

    now = host.plan.service.clock()
    with host.plan.service._lock:
        host.plan.service._previews = {
            key: replace(entry, expires_at=now - timedelta(seconds=1))
            for key, entry in host.plan.service._previews.items()
        }
    replacement_request = plan_request()
    replacement = preview(host, second, second_conversation, replacement_request)
    confirmed_request = plan_request(
        replacement_request["idempotency_key"],
        replacement["confirmation"],
        content=replacement_request["content"],
    )
    response = plan_http(
        host, second, second_conversation, "continue", confirmed_request
    )
    assert "event: response.completed" in response.text
    assert len(second.provider.sends()) == 1
    assert first.provider.sends() == []


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("blocked_check", [1, 2])
async def test_slow_plan_admission_preserves_other_client_progress(
    plan_factory, monkeypatch, blocked_check,
):
    import httpx

    host = plan_factory()
    first = travel(host)
    second = host.plan.onboard(
        provision(host, FITNESS_APP, B, grant=False),
        memory_content=FITNESS_MEMORY,
    )
    first_conversation = create(host, first)
    second_conversation = create(host, second)
    first_request = confirmed(host, first, first_conversation)
    second_request = confirmed(host, second, second_conversation)
    entered, release = Event(), Event()
    original_check = first.bridge._require_dispatch
    checks = 0

    def hold_admission(*args, **kwargs):
        nonlocal checks
        checks += 1
        if checks == blocked_check:
            entered.set()
            assert release.wait(8)
        return original_check(*args, **kwargs)

    monkeypatch.setattr(first.bridge, "_require_dispatch", hold_admission)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=host.app), base_url="https://shared.invalid"
    ) as client:
        pending = asyncio.create_task(
            client.post(
                f"{PROFILE_PREFIX}/{first_conversation}/continue",
                headers=first.headers,
                json=first_request,
            )
        )
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            second_result = await client.post(
                f"{PROFILE_PREFIX}/{second_conversation}/continue",
                headers=second.headers,
                json=second_request,
            )
            assert "event: response.completed" in second_result.text
            assert len(second.provider.sends()) == 1

            pending.cancel()
            await asyncio.sleep(0.05)
            assert not pending.done()
            denied = await client.post(
                f"{PROFILE_PREFIX}/{first_conversation}/context-preview",
                headers=first.headers,
                json=plan_request(),
            )
            assert denied.status_code == 429
            assert first.provider.sends() == []
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await pending

        released = await client.post(
            f"{PROFILE_PREFIX}/{first_conversation}/context-preview",
            headers=first.headers,
            json=plan_request(),
        )
        assert released.status_code == 200

    assert first.provider.sends() == []
    assert len(second.provider.sends()) == 1


def test_two_owners_and_three_independent_app_registrations(plan_factory, caplog):
    caplog.set_level(logging.INFO)
    host = plan_factory(selected=(TRAVEL_APP, FITNESS_APP, READING_APP))
    trip = travel(host)
    workout = host.plan.onboard(
        provision(host, FITNESS_APP, B, grant=False),
        memory_content=FITNESS_MEMORY,
    )
    book = host.plan.onboard(
        provision(
            host, READING_APP, A, grant=False, data={"title": SECRET_TITLE, "label": BOOK_LABEL}
        ),
        memory_content=READING_MEMORY,
    )
    for target, source, memory in (
        (trip, TRAVEL_PLATFORM, TRAVEL_MEMORY),
        (workout, "duration_minutes", FITNESS_MEMORY),
        (book, BOOK_LABEL, READING_MEMORY),
    ):
        cid = create(host, target, title="Application plan test")
        request = plan_request()
        selection = preview(host, target, cid, request)
        assert selection["purpose"] == "foreground_application_plan"
        assert selection["destination"]["application"] == target.app.app
        assert {row["category"] for row in selection["selected_context"]} == {
            "domain_current",
            "ai_memory",
            "conversation_history",
        }
        assert all(value not in json.dumps(selection) for value in (SECRET_TITLE, memory))
        assert target.local_payloads == target.provider.sends() == []
        body = plan_request(request["idempotency_key"], selection["confirmation"])
        response = plan_http(host, target, cid, "continue", body)
        assert "event: response.completed" in response.text and "A streamed answer" in response.text
        assert status(host, target, cid, body).json()["state"] == "completed"
        replay = plan_http(host, target, cid, "continue", body)
        assert "event: response.completed" in replay.text and "A streamed answer" in replay.text
        assert_delivery(
            target,
            (source, memory),
            (
                SECRET_TITLE,
                *(
                    marker
                    for marker in (TRAVEL_MEMORY, FITNESS_MEMORY, READING_MEMORY)
                    if marker != memory
                ),
                "fake-plan-access",
                "fake-plan-refresh",
                "fake-plan-id",
            ),
        )
        assert not host.generation.sends
        package, _ = target.proofs[0]
        context_items = [
            json.loads(line)
            for message in package.messages
            for line in message.content.splitlines()
            if line.startswith("{")
        ]
        model_data = {item["source_class"]: item["data"] for item in context_items}
        assert model_data["domain_current"] == {
            field: target.data[field] for field in target.app.fields
        }
        assert model_data["ai_memory"] == {"content": memory}
    assert len(host.plan.memories.records) == 3
    for target in (trip, workout, book):
        for foreign in (trip, workout, book):
            if target is not foreign:
                assert foreign.provider.sends()[0].headers["authorization"][7:].encode() not in (
                    (target.store.directory / "state.json").read_bytes()
                )
    assert "fake-plan-access-" not in caplog.text
    assert "fake-plan-refresh-" not in caplog.text
    assert "fake-plan-id-" not in caplog.text


def test_one_canonical_memory_can_be_shared_to_another_app_only_by_exact_consent(plan_factory):
    host = plan_factory()
    trip = travel(host)
    runner = host.plan.onboard(
        provision(host, FITNESS_APP, A, grant=False, workspace="fitness-space"),
        memory_content=FITNESS_MEMORY,
    )
    host.plan.disclosures.pop(runner.plan.scope)
    cid = create(host, runner)
    assert plan_http(host, runner, cid, "context-preview", plan_request()).is_error
    host.plan.share_memory(runner, trip.memory)
    payload = confirmed(host, runner, cid)
    assert "event: response.completed" in plan_http(host, runner, cid, "continue", payload).text
    assert_delivery(runner, (TRAVEL_MEMORY, "duration_minutes"), (TRAVEL_PLATFORM, FITNESS_MEMORY))
    assert len(host.plan.memories.records) == 2
    host.controls.memberships.pop(
        (trip.principal.issuer, trip.principal.subject, trip.app.app, SITE)
    )
    assert status(host, runner, cid, payload).status_code == 409
    assert plan_http(host, runner, cid, "continue", payload).json()["error"]["code"] == (
        "context_source_authority_changed"
    )


@pytest.mark.parametrize("change", ["body", "confirmation", "client", "actor", "workspace"])
def test_foreground_confirmation_and_pas_scope_are_exact(plan_factory, change):
    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    changed = target
    if change == "body":
        payload["content"] += " Changed."
    elif change == "confirmation":
        payload["choice"]["confirmation"] = "0" * 64
    else:
        if change == "client":
            host.add_binding(target.app.app, audience="alternate-app-client")
            token = host.token(target.app, audience="alternate-app-client")
        else:
            token = host.token(target.app, human=B if change == "actor" else A)
        changed = replace_target(
            target,
            headers=headers(
                token, target.app, "other-workspace" if change == "workspace" else SITE
            ),
        )
    response = plan_http(host, changed, cid, "continue", payload)
    assert response.status_code in {403, 404, 409, 422}
    assert target.local_payloads == target.provider.sends() == host.generation.sends == []
    assert host.plan.roots.rows == {}


def replace_target(target, **updates):
    from types import SimpleNamespace

    return SimpleNamespace(**(vars(target) | updates))


@pytest.mark.parametrize("change", ["expiry", "branch"])
def test_unconsumed_preview_cannot_dispatch_after_expiry_or_branch_advance(plan_factory, change):
    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    if change == "expiry":
        now = host.plan.service.clock() + timedelta(seconds=46)
        host.plan.service.clock = lambda: now
    else:
        advanced = post(host, target, cid, "continue", automatic_body(content="Say hello."))
        assert "event: response.completed" in advanced.text
    result = plan_http(host, target, cid, "continue", payload)
    assert result.status_code in {409, 422}
    assert not host.plan.roots.rows
    assert target.local_payloads == target.provider.sends() == []


@pytest.mark.parametrize(
    "change",
    [
        "caller",
        "origin",
        "host",
        "registration",
        "account",
        "recipient",
        "digest",
        "signature",
        "expired",
    ],
)
def test_runtime_binding_and_signed_payload_fail_closed(plan_factory, monkeypatch, change):
    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    if change in {"caller", "origin"}:
        session = target.session
        value = (
            {"authorization": "x" * 40}
            if change == "caller"
            else {"origin": "http://127.0.0.1:19321"}
        )
        monkeypatch.setattr(target.plan.runtime, "_session", replace(session, **value))
    elif change in {"host", "registration", "account"}:
        with target.store.transaction() as tx:
            if change == "host":
                tx.state.host_id = str(uuid4())
            else:
                registration = tx.state.registrations[str(target.plan.connection_id)]
                if change == "registration":
                    registration.client_id = "oaiapp_changed"
                else:
                    registration.subject = "different-selected-account"
            tx.save()
    elif change == "expired":
        clock = target.bridge.clock
        monkeypatch.setattr(target.bridge, "clock", lambda: clock() + 60)
    elif change == "digest":
        execute = target.bridge.execute

        def substitute(package, proof, **options):
            altered = package.model_copy(
                update={
                    "messages": package.messages[:-1]
                    + (
                        package.messages[-1].model_copy(
                            update={"content": "substituted plaintext"}
                        ),
                    )
                }
            )
            return execute(altered, proof, **options)

        monkeypatch.setattr(target.bridge, "execute", substitute)
    else:
        sign = host.plan.signer.sign

        def changed_sign(package, **options):
            dispatch = options["application_plan"]
            if change == "recipient":
                scope = dispatch.scope.model_copy(update={"model_recipient": "other-provider"})
                options["application_plan"] = dispatch.model_copy(update={"scope": scope})
                return sign(package, **options)
            proof = sign(package, **options)
            return proof.model_copy(update={"signature": "A" * 86})

        monkeypatch.setattr(host.plan.signer, "sign", changed_sign)
    stream = plan_http(host, target, cid, "continue", payload)
    assert "event: response.completed" not in stream.text
    assert target.provider.sends() == host.generation.sends == []
    if change != "digest":
        assert target.local_payloads == []
    assert status(host, target, cid, payload).json()["state"] == "unknown"


def invalidate(host, target, change):
    if change in {"local-grant", "onward-grant"}:
        pair = target.plan.scope
        host.control(
            target.control,
            target.app,
            target.workspace,
            target.token,
            operation="revoke",
            expected_revision=target.source_grant_revision,
            recipient=pair.local_recipient if change == "local-grant" else pair.model_recipient,
        )
    elif change == "source-revision":
        host.seed(target.principal, target.app, target.workspace, target.data, revision="changed")
    elif change == "source-membership":
        host.sources[target.app.source].memberships.clear()
    elif change == "memory-consent":
        host.plan.disclosures[target.plan.scope] = host.plan.disclosures[target.plan.scope][:1]
    elif change == "memory-edit":
        memory = target.memory
        edited = TRAVEL_MEMORY.rstrip(".")
        host.plan.memories.records[memory.id] = memory.model_copy(
            update={"content": edited, "normalized_content": normalize(edited)}
        )
    elif change == "memory-forget":
        memory = target.memory
        host.plan.lifecycle.states[(memory.owner_id, memory.id)] = MemoryLifecycleState(
            owner_id=memory.owner_id,
            memory_id=memory.id,
            application_id=memory.application_id,
            workspace_id=memory.workspace_id,
            retrieval_status="forgotten",
            validity_epoch=1,
        )
    elif change == "owner-deletion":
        host.directory.deactivate(target.principal.owner_id)
    elif change == "workspace-removal":
        host.controls.memberships.pop(
            (
                target.principal.issuer,
                target.principal.subject,
                target.app.app,
                target.workspace,
            )
        )
    elif change == "offline-witness":
        host.plan.recovery_available = False
    else:
        raise AssertionError(change)


@pytest.mark.parametrize("edge", ["handoff", "send-start"])
@pytest.mark.parametrize(
    "change",
    [
        "local-grant",
        "onward-grant",
        "source-revision",
        "source-membership",
        "memory-consent",
        "memory-edit",
        "memory-forget",
        "owner-deletion",
        "workspace-removal",
        "offline-witness",
    ],
)
def test_current_rights_at_each_disclosure_boundary(plan_factory, monkeypatch, edge, change):
    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    reached = []
    if edge == "handoff":
        original = target.bridge.authorize_handoff

        def revoke(*args, **kwargs):
            reached.append(True)
            if len(reached) == 2:
                invalidate(host, target, change)
            return original(*args, **kwargs)

        monkeypatch.setattr(target.bridge, "authorize_handoff", revoke)
    else:
        original = target.store.mark_send_started

        def revoke(*args, **kwargs):
            reached.append(True)
            invalidate(host, target, change)
            return original(*args, **kwargs)

        monkeypatch.setattr(target.store, "mark_send_started", revoke)
    response = plan_http(host, target, cid, "continue", payload)
    assert "event: response.completed" not in response.text
    assert len(reached) == (2 if edge == "handoff" else 1)
    assert len(target.local_payloads) == (0 if edge == "handoff" else 1)
    assert target.provider.sends() == host.generation.sends == []
    assert {row[4] for row in host.plan.roots.rows.values()} == {"fenced"}
    with target.store.transaction() as tx:
        assert tx.state.receipts == {}


@pytest.mark.parametrize(
    "reason",
    [
        "missing-registration",
        "model",
        "credits",
        "disconnected",
        "local-only-grant",
        "missing-memory",
        "legacy-reader",
    ],
)
def test_ineligible_plan_has_safe_no_ai_and_no_fallback(plan_factory, shared_factory, reason):
    host = shared_factory() if reason == "legacy-reader" else plan_factory()
    if reason in {"missing-registration", "legacy-reader"}:
        target = provision(host, grant=reason == "legacy-reader")
    else:
        target = travel(host, gate=reason != "credits")
    cid = create(host, target)
    payload = plan_request()
    if reason in {"model", "credits", "disconnected"}:
        payload = confirmed(host, target, cid, payload)
        if reason == "model":
            target.provider.catalog = []
        if reason == "disconnected":
            target.bridge.lifecycle.disconnect(str(target.plan.connection_id))
        response = plan_http(host, target, cid, "continue", payload)
        assert "event: response.completed" not in response.text
    else:
        if reason == "local-only-grant":
            invalidate(host, target, "onward-grant")
        if reason == "missing-memory":
            invalidate(host, target, "memory-consent")
        response = plan_http(host, target, cid, "context-preview", payload)
        assert response.is_error
    if hasattr(target, "provider"):
        assert target.local_payloads == target.provider.sends() == []
    assert host.generation.sends == []
    assert host.http.get(f"/v1/conversations/{cid}", headers=target.headers).status_code in {
        200,
        409,
    }
    if reason == "legacy-reader":
        free = post(host, target, cid, "continue", automatic_body())
        assert "event: response.completed" in free.text
        assert len(host.generation.sends) == 1


def test_same_key_race_and_replay_keep_one_transport_and_opaque_foreign_status(plan_factory):
    host = plan_factory()
    target = travel(host)
    foreign = provision(host, FITNESS_APP, B)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [
            pool.submit(plan_http, host, target, cid, "continue", payload) for _ in range(2)
        ]
        results = [future.result(timeout=8) for future in requests]
    assert any("event: response.completed" in response.text for response in results)
    assert len(target.provider.sends()) == len(target.local_payloads) == 1
    assert status(host, target, cid, payload).json()["state"] == "completed"
    first = status(host, foreign, cid, payload)
    absent = status(host, foreign, uuid4(), payload)
    assert first.status_code == absent.status_code == 404 and first.json() == absent.json()
    assert "event: response.completed" in plan_http(host, target, cid, "continue", payload).text
    invalidate(host, target, "memory-forget")
    assert status(host, target, cid, payload).status_code == 409
    assert plan_http(host, target, cid, "continue", payload).json()["error"]["code"] == (
        "context_source_authority_changed"
    )
    assert len(target.provider.sends()) == 1 and host.generation.sends == []


def test_interrupted_stream_restart_and_older_local_state_retain_physical_fence(plan_factory):
    from tests.test_chatgpt_bridge_transport import created, delta

    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    state = target.store.directory / "state.json"
    older_state = state.read_bytes()
    target.provider.events = [created(), delta("Provisional answer.")]

    async def request():
        disconnected = asyncio.Event()
        frames = []

        async def tap(scope, receive, send):
            scope["asgi"]["spec_version"] = "2.3"

            async def guarded_receive():
                if disconnected.is_set():
                    return {"type": "http.disconnect"}
                result = await receive()
                return result if not disconnected.is_set() else {"type": "http.disconnect"}

            async def stop_after_delta(message):
                frame = message.get("body", b"")
                frames.append(frame)
                if b"event: response.delta" in frame:
                    disconnected.set()
                    await asyncio.sleep(0)
                if not disconnected.is_set():
                    await send(message)

            await host.app(scope, guarded_receive, stop_after_delta)

        # Drive an ASGI disconnect at the first delta, without a loopback listener.
        sent_request = False

        async def receive():
            nonlocal sent_request
            if not sent_request:
                sent_request = True
                return {"type": "http.request", "body": json.dumps(payload).encode()}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(_message):
            pass

        path = f"{PROFILE_PREFIX}/{cid}/continue"
        await tap(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "method": "POST",
                "scheme": "https",
                "path": path,
                "raw_path": path.encode(),
                "root_path": "",
                "query_string": b"",
                "server": ("shared.invalid", 443),
                "client": ("127.0.0.1", 1001),
                "headers": [(k.lower().encode(), v.encode()) for k, v in target.headers.items()]
                + [
                    (b"content-type", b"application/json"),
                ],
            },
            receive,
            send,
        )
        return frames

    frames = asyncio.run(request())
    assert any(b"response.delta" in frame for frame in frames)
    assert not any(b"response.completed" in frame for frame in frames)
    assert len(target.provider.sends()) == 1
    assert status(host, target, cid, payload).json()["state"] == "unknown"
    package, proof = target.proofs[0]
    state.write_bytes(older_state)
    restarted = ProtectedLocalStore(target.store.directory)
    assert (
        restarted.reconcile(
            package.dispatch_identity,
            package.fingerprint,
            str(target.plan.connection_id),
            target.plan.connection_revision,
            target.session.origin,
        )
        == "unknown"
    )
    with pytest.raises(LocalStoreError, match="dispatch_already_claimed"):
        restarted.claim(
            package.dispatch_identity,
            package.fingerprint,
            str(target.plan.connection_id),
            target.plan.connection_revision,
            proof.claims.expires_at,
            origin=target.session.origin,
        )
    assert plan_http(host, target, cid, "continue", payload).status_code == 409
    assert len(target.provider.sends()) == 1 and host.generation.sends == []


def test_aggregate_context_budget_and_single_external_projection(plan_factory, monkeypatch):
    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    start = len(host.sources[target.app.source].lookup_paths)
    original_limit = application_plan.MAX_CONTEXT_BYTES
    monkeypatch.setattr(application_plan, "MAX_CONTEXT_BYTES", original_limit - 1)
    assert plan_http(host, target, cid, "context-preview", plan_request()).is_error
    assert len(host.sources[target.app.source].lookup_paths) == start
    monkeypatch.setattr(application_plan, "MAX_CONTEXT_BYTES", original_limit)
    base = application_plan.MAX_CONTEXT_TOKENS
    monkeypatch.setattr(application_plan, "MAX_CONTEXT_TOKENS", base - 1)
    assert plan_http(host, target, cid, "context-preview", plan_request()).is_error
    assert len(host.sources[target.app.source].lookup_paths) == start
    monkeypatch.setattr(application_plan, "MAX_CONTEXT_TOKENS", base)
    payload = confirmed(host, target, cid)
    assert "event: response.completed" in plan_http(host, target, cid, "continue", payload).text
    source = host.sources[target.app.source]
    assert len(source.lookup_paths) - start == 2
    assert len(target.local_payloads[0]) <= application_plan.MAX_PAYLOAD_BYTES
    assert len(target.provider.sends()[0].content) <= application_plan.MAX_PAYLOAD_BYTES


def test_private_preview_shares_worker_slots_and_deadline(plan_factory, monkeypatch):
    host = plan_factory()
    trip = travel(host)
    runner = host.plan.onboard(
        provision(host, FITNESS_APP, B, grant=False),
        memory_content=FITNESS_MEMORY,
    )
    trip_id, run_id = create(host, trip), create(host, runner)
    ready, release = Event(), Event()
    read = host.sources[trip.app.source].exchange

    def block(*args, **kwargs):
        if not ready.is_set():
            ready.set()
            assert release.wait(4)
        return read(*args, **kwargs)

    monkeypatch.setattr(host.sources[trip.app.source], "exchange", block)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(plan_http, host, trip, trip_id, "context-preview", plan_request())
        try:
            assert ready.wait(4)
            assert (
                plan_http(host, trip, trip_id, "context-preview", plan_request()).status_code == 429
            )
            assert preview(host, runner, run_id, plan_request())["confirmation"]
        finally:
            release.set()
        assert pending.result(timeout=6).is_success
    clock = application_plan.monotonic
    times = iter([clock(), clock() + host.settings.request_timeout_seconds + 1])
    monkeypatch.setattr(application_plan, "monotonic", lambda: next(times))
    assert plan_http(host, trip, trip_id, "context-preview", plan_request()).is_error
    assert trip.local_payloads == runner.local_payloads == []
    assert trip.provider.sends() == runner.provider.sends() == host.generation.sends == []


def test_regrant_cannot_revive_a_preview_and_public_loopback_refuses_the_app_runtime(plan_factory):
    from personal_ai.local_bridge.http import create_loopback_app
    from personal_ai.local_bridge.runtime import BridgeDenied

    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    old = confirmed(host, target, cid)
    host.plan.share_memory(target, target.memory)
    refused = plan_http(host, target, cid, "continue", old)
    assert refused.json()["error"]["code"] == "context_source_authority_changed"
    assert target.local_payloads == target.provider.sends() == []
    with pytest.raises(BridgeDenied, match="bridge_admission_denied"):
        create_loopback_app(target.bridge, port=8765)
    current = confirmed(host, target, cid)
    assert "event: response.completed" in plan_http(host, target, cid, "continue", current).text
    assert target.proofs[0][1].claims.schema_version == 2
    assert len(target.provider.sends()) == 1


def test_revocation_after_a_delta_blocks_subsequent_output_and_replay(plan_factory):
    import httpx

    from tests.test_chatgpt_bridge_transport import completed, created, delta

    host = plan_factory()
    target = travel(host)
    cid = create(host, target)
    payload = confirmed(host, target, cid)
    target.provider.events = [created(), delta("A streamed "), delta("answer"), completed()]
    seen = []

    async def tap(scope, receive, send):
        async def record(frame):
            await send(frame)
            if b"response.delta" in frame.get("body", b""):
                seen.append(frame["body"])
                if len(seen) == 1:
                    await asyncio.to_thread(invalidate, host, target, "memory-forget")

        await host.app(scope, receive, record)

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=tap),
            base_url="https://shared.invalid",
        ) as client:
            return await client.post(
                f"{PROFILE_PREFIX}/{cid}/continue",
                json=payload,
                headers=target.headers,
            )

    response = asyncio.run(request())
    assert len(seen) == 1 and "A streamed " in response.text and "answer" not in response.text
    assert "event: response.completed" not in response.text
    assert status(host, target, cid, payload).status_code == 409
    detail = host.http.get(f"/v1/conversations/{cid}", headers=target.headers)
    assert detail.status_code == 409 and "A streamed" not in detail.text
    assert len(target.provider.sends()) == 1 and host.generation.sends == []
