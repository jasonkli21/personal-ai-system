"""Explicit composition for the isolated, versioned application inference profile."""

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from hashlib import sha256
from typing import Annotated, Protocol
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.routing import APIRoute
from starlette.datastructures import Headers
from starlette.routing import Match

from personal_ai.api import dependencies as deps
from personal_ai.api.routes import _request_id, _sse_response
from personal_ai.api.schemas import ExternalCreateConversationRequest
from personal_ai.auth.application_clients import require_current_client_authority
from personal_ai.auth.scope import current_verified_principal
from personal_ai.context import ContextAssembler
from personal_ai.context.providers import ContextPreparationError
from personal_ai.contracts.private_dispatch import (
    MEDIA_TYPE,
    ORIGINAL_KEY_HEADER,
    canonical_object,
)
from personal_ai.contracts.private_dispatch import (
    RECEIPT_HEADER as DISPATCH_RECEIPT_HEADER,
)
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.conversations import ConversationService
from personal_ai.services.external_turns.application_plan import (
    ApplicationPlanService,
    BoundPreviewMetadata,
    PlanContinuation,
    PlanTarget,
    encode_preview_response,
)
from personal_ai.services.external_turns.private_dispatch import DispatchDenied, PrivateDispatch
from personal_ai.storage.async_io import sync_call
from personal_ai.storage.errors import ResourceNotFoundError

PROFILE_PREFIX = "/private/application-plan/v1/conversations"
MAX_PREVIEW_BYTES = 8192
MAX_RECEIPT_BYTES = 8192
RECEIPT_HEADER = "x-application-plan-receipt"


class _DispatchReadRoute(APIRoute):
    def matches(self, scope):
        if scope.get("type") != "http" or Headers(scope=scope).getlist("accept") != [MEDIA_TYPE]:
            return Match.NONE, {}
        return super().matches(scope)


def _dispatch_response(status, *, body=b"", committed_at=None):
    headers = {"cache-control": "no-store"}
    if committed_at is not None:
        headers["x-pas-committed-at"] = str(committed_at)
    return Response(body, status_code=status, headers=headers, media_type=MEDIA_TYPE if body else None)


def _canonical_path(request, conversation_id, original_key=None):
    if request.path_params.get("conversation_id") != str(conversation_id) or (
        original_key is not None and request.path_params.get("original_key") != str(original_key)
    ):
        raise DispatchDenied


class BoundReceiptAttestor(Protocol):
    def __call__(
        self, conversation: UUID, body: bytes, frozen: BoundPreviewMetadata | None,
    ) -> str: ...

    def require_current(self) -> None: ...


class BoundReceiptAuthority(Protocol):
    """An isolated host's transaction authority and response attestor."""

    def __call__(
        self, request: Request, target: PlanTarget, conversation_id: UUID | None, body: bytes,
    ) -> BoundReceiptAttestor: ...


def _checked_receipt(value: str) -> str:
    if not value or len(value) > MAX_RECEIPT_BYTES or not value.isascii() or not value.isprintable():
        raise ContextPreparationError("context_no_ai_route")
    return value


def _signed_receipt(
    key: Ed25519PrivateKey,
    *,
    target,
    operation: str,
    conversation_id,
    request_body: bytes,
    response_body: bytes,
    source_revision: str | None = None,
) -> str:
    binding = target.preview_binding(current_verified_principal(), conversation_id)
    if (
        binding is None
        or binding.scope.application_id != "travel"
        or binding.scope.workspace_id is not None
        or (operation == "preview") != (source_revision is not None)
    ):
        raise ContextPreparationError("context_no_ai_route")
    statement = {
        "schema_version": "travel-application-plan-receipt-v1",
        "operation": operation,
        "target_id": binding.target_id,
        "client_namespace": binding.client_namespace,
        "application_id": binding.scope.application_id,
        "workspace_id": binding.scope.workspace_id,
        "owner_id": binding.owner_id,
        "issuer": binding.human_issuer,
        "subject": binding.human_subject,
        "conversation_id": str(conversation_id),
        "request_digest": sha256(request_body).hexdigest(),
        "response_digest": sha256(response_body).hexdigest(),
        "source_revision": source_revision,
    }
    encoded = json.dumps(
        statement, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return key.sign(encoded).hex()


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate property")
    return result


async def _json_body(request: Request, *, max_bytes: int, dispatch=False) -> bytes:
    media = request.headers.getlist("content-type")
    if (
        len(media) != 1
        or (
            media[0].split(";", 1)[0].strip().lower() != "application/json"
            if not dispatch else media[0] != MEDIA_TYPE
        )
        or request.url.query
    ):
        raise HTTPException(422, "validation_error")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > max_bytes:
            raise HTTPException(422, "validation_error")
        body.extend(chunk)
    return bytes(body)


async def _intent(
    request: Request, *, confirmed: bool, dispatch=False,
) -> tuple[PlanContinuation, bytes]:
    body = await _json_body(request, max_bytes=128 * 1024, dispatch=dispatch)
    try:
        value = (
            canonical_object(body) if dispatch else
            json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
        )
        parsed = PlanContinuation.model_validate(value)
        present = "confirmation" in parsed.choice.model_fields_set
        if present != confirmed or (confirmed and parsed.choice.confirmation is None):
            raise ValueError("invalid confirmation")
        if dispatch and value["idempotency_key"] != str(parsed.idempotency_key):
            raise ValueError("noncanonical UUID")
        parsed.content.encode("utf-8")
        return parsed, body
    except (ValueError, RecursionError):
        raise HTTPException(422, "validation_error") from None


def mount_application_plan(
    app: FastAPI,
    *,
    service: ApplicationPlanService,
    assembler_dependency: Callable[..., ContextAssembler],
    preview_recipient_scope: Callable[[PlanTarget], AbstractContextManager[None]],
    travel_receipt_key: Ed25519PrivateKey | None = None,
    bound_receipts: BoundReceiptAuthority | None = None,
    dispatch: PrivateDispatch | None = None,
) -> None:
    """Mount only on an explicitly isolated host before its middleware starts."""
    if (
        not getattr(app.state, "isolate_external_conversations", False)
        or getattr(app.state, "private_application_plan_routes", ())
        or app.middleware_stack is not None
        or (travel_receipt_key is not None and bound_receipts is not None)
        or (dispatch is not None and (
            dispatch.plans is not service or (
                bound_receipts is None
                and any(registration.receipt_authority is None for registration in dispatch.registrations)
            )
        ))
    ):
        raise ValueError("application_plan_requires_isolated_host")

    async def create(
        request: Request,
        conversations: Annotated[ConversationService, Depends(deps.get_conversation_service)],
    ):
        raw = await _json_body(request, max_bytes=4096)
        try:
            incoming = ExternalCreateConversationRequest.model_validate(
                json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
            )
            if incoming.title is None or not incoming.title.strip():
                raise ValueError("invalid title")
            incoming.title.encode("utf-8")
        except (ValueError, RecursionError):
            raise HTTPException(422, "validation_error") from None
        target = await sync_call(service.current_target)
        principal = current_verified_principal()
        if (
            principal is None
            or not principal.authenticated
            or target.preview_source is None
            or (travel_receipt_key is not None and target.scope.application_id != "travel")
            or (bound_receipts is not None and incoming.idempotency_key is None)
            or target.scope.workspace_id is not None
        ):
            raise ContextPreparationError("context_no_ai_route")
        attestor = (
            await sync_call(bound_receipts, request, target, None, raw)
            if bound_receipts is not None
            else None
        )
        conversation = await sync_call(
            conversations.create_conversation,
            title=incoming.title,
            idempotency_key=incoming.idempotency_key,
        )
        await sync_call(require_current_client_authority)
        if (
            target is not await sync_call(service.current_target)
            or conversation.owner_id != principal.owner_id
            or conversation.application_id != target.scope.application_id
            or conversation.workspace_id is not None
            or conversation.external_client_namespace != target.scope.client_namespace
            or conversation.title != incoming.title.strip()
        ):
            raise ContextPreparationError("context_no_ai_route")
        response_body = encode_preview_response({"conversation_id": str(conversation.id)})
        if attestor is not None:
            signature = _checked_receipt(
                await sync_call(attestor, conversation.id, response_body, None)
            )
            await sync_call(attestor.require_current)
        else:
            assert travel_receipt_key is not None
            signature = _signed_receipt(
                travel_receipt_key,
                target=target,
                operation="create",
                conversation_id=conversation.id,
                request_body=raw,
                response_body=response_body,
            )
        return Response(
            response_body,
            status_code=201,
            media_type="application/json",
            headers={"cache-control": "no-store", RECEIPT_HEADER: signature},
        )

    async def preview(
        conversation_id: UUID,
        request: Request,
        chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        negotiated = request.headers.getlist("content-type") == [MEDIA_TYPE]
        if negotiated and dispatch is None:
            return _dispatch_response(404)
        incoming, raw = await _intent(request, confirmed=False, dispatch=negotiated)
        headers = {"cache-control": "no-store"}
        attest = None
        require_current_operation = None
        prepare_dispatch = None
        registration = None
        attested_body = None

        try:
            target = await sync_call(service.current_target)
            if negotiated:
                _canonical_path(request, conversation_id)
                registration = await sync_call(dispatch.registration)
                if registration.target is not target:
                    raise DispatchDenied
                create_binding = await sync_call(
                    dispatch.begin_preview, registration, conversation_id, incoming.idempotency_key,
                )
            receipt_authority = (
                registration.receipt_authority
                if registration is not None and registration.receipt_authority is not None
                else bound_receipts
            )
            if receipt_authority is not None:
                if target.preview_source is None:
                    raise ContextPreparationError("context_no_ai_route")
                attestor = await sync_call(receipt_authority, request, target, conversation_id, raw)
                require_current_operation = attestor.require_current

                def attest(body: bytes, frozen: BoundPreviewMetadata) -> None:
                    nonlocal attested_body
                    headers[RECEIPT_HEADER] = _checked_receipt(
                        attestor(conversation_id, body, frozen)
                    )
                    attested_body = body

                if negotiated:
                    def prepare_dispatch(frozen, context):
                        envelope = dispatch.prepare(
                            registration, create_binding, headers[RECEIPT_HEADER], frozen,
                            context, chat, assembler,
                        )
                        headers[DISPATCH_RECEIPT_HEADER] = envelope.decode("ascii")

            with preview_recipient_scope(target):
                selection, source_revision = await sync_call(
                    service.preview_with_source_revision,
                    chat,
                    assembler,
                    conversation_id,
                    incoming,
                    expected_target=target,
                    attest=attest,
                    require_current_operation=require_current_operation,
                    prepare_dispatch=prepare_dispatch,
                    dispatch_destination=registration.runtime.destination if registration else None,
                )
            response_body = (
                attested_body if attested_body is not None else encode_preview_response(selection)
            )
            if len(response_body) > MAX_PREVIEW_BYTES:
                raise ContextPreparationError("context_no_ai_route")
            if not negotiated and travel_receipt_key is not None and target.preview_source is not None:
                if target is not await sync_call(service.current_target):
                    raise ContextPreparationError("context_no_ai_route")
                headers[RECEIPT_HEADER] = _signed_receipt(
                    travel_receipt_key,
                    target=target,
                    operation="preview",
                    conversation_id=conversation_id,
                    request_body=raw,
                    response_body=response_body,
                    source_revision=source_revision,
                )
            return Response(
                response_body, media_type=MEDIA_TYPE if negotiated else "application/json",
                headers=headers,
            )
        except (DispatchDenied, ContextPreparationError, ResourceNotFoundError) as error:
            if not negotiated:
                raise
            if registration is not None:
                await sync_call(dispatch.retire, registration, conversation_id, incoming.idempotency_key)
            return _dispatch_response(error.status if isinstance(error, DispatchDenied) else 404)


    async def observe(
        conversation_id: UUID,
        original_key: UUID,
        request: Request,
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        if bound_receipts is None or request.url.query:
            raise HTTPException(422, "validation_error")
        async for chunk in request.stream():
            if chunk:
                raise HTTPException(422, "validation_error")
        target = await sync_call(service.current_target)
        attestor = await sync_call(bound_receipts, request, target, conversation_id, b"")
        with preview_recipient_scope(target):
            result = await sync_call(
                service.observe_bound_preview,
                assembler,
                conversation_id,
                original_key,
                expected_target=target,
                attest=attestor,
                require_current_operation=attestor.require_current,
            )
        if result is None:
            return Response(status_code=404, headers={"cache-control": "no-store"})
        body, receipt = result
        return Response(
            body,
            media_type="application/json",
            headers={"cache-control": "no-store", RECEIPT_HEADER: _checked_receipt(receipt)},
        )

    async def continue_turn(
        conversation_id: UUID,
        request: Request,
        chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        if request.headers.getlist("content-type") == [MEDIA_TYPE]:
            if dispatch is None:
                return _dispatch_response(404)
            try:
                _canonical_path(request, conversation_id)
                registration = await sync_call(dispatch.registration)
                body = await _json_body(request, max_bytes=512, dispatch=True)
                with preview_recipient_scope(registration.target):
                    await sync_call(dispatch.confirm, registration, conversation_id, body, chat, assembler)
                return _dispatch_response(202)
            except DispatchDenied as error:
                return _dispatch_response(error.status)
            except ValueError:
                return _dispatch_response(422)
        incoming, _ = await _intent(request, confirmed=True)
        stream = await sync_call(service.continue_turn, chat, assembler, conversation_id, incoming)
        return _sse_response(stream, request_id=_request_id(request))

    async def dispatch_read(conversation_id, original_key, request, chat, assembler, *, detail):
        try:
            if request.url.query:
                raise DispatchDenied
            _canonical_path(request, conversation_id, None if detail else original_key)
            async for chunk in request.stream():
                if chunk:
                    raise DispatchDenied
            registration = await sync_call(dispatch.registration)
            with preview_recipient_scope(registration.target):
                body, committed_at = await sync_call(
                    dispatch.inspect, registration, conversation_id, original_key, chat, assembler,
                    detail=detail,
                )
            return _dispatch_response(200, body=body, committed_at=committed_at)
        except DispatchDenied as error:
            return _dispatch_response(error.status)
        except (ValueError, ContextPreparationError, ResourceNotFoundError):
            return _dispatch_response(404)

    async def status(
        conversation_id: str, original_key: str, request: Request,
        chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        try:
            conversation, original = UUID(conversation_id), UUID(original_key)
        except ValueError:
            return _dispatch_response(404)
        return await dispatch_read(conversation, original, request, chat, assembler, detail=False)

    async def detail(
        conversation_id: str, request: Request,
        chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        values = request.headers.getlist(ORIGINAL_KEY_HEADER)
        try:
            conversation = UUID(conversation_id)
            original_key = UUID(values[0])
            if values != [str(original_key)]:
                raise ValueError
        except (IndexError, ValueError):
            return _dispatch_response(404)
        return await dispatch_read(conversation, original_key, request, chat, assembler, detail=True)

    routes = []
    if travel_receipt_key is not None or bound_receipts is not None:
        app.add_api_route(PROFILE_PREFIX, create, methods=["POST"], include_in_schema=False)
        routes.append(app.router.routes[-1])
    for suffix, handler in (("context-preview", preview), ("continue", continue_turn)):
        app.add_api_route(
            f"{PROFILE_PREFIX}/{{conversation_id}}/{suffix}",
            handler,
            methods=["POST"],
            include_in_schema=False,
        )
        routes.append(app.router.routes[-1])
    if bound_receipts is not None:
        app.add_api_route(
            f"{PROFILE_PREFIX}/{{conversation_id}}/context-preview/{{original_key}}",
            observe,
            methods=["GET"],
            include_in_schema=False,
        )
        routes.append(app.router.routes[-1])
        app.state.lookup_only_application_plan_principal = True
    if dispatch is not None:
        app.state.private_dispatch_post_routes = tuple(
            route for route in routes if route.endpoint in (preview, continue_turn)
        )
        for suffix, handler in (("/continuations/{original_key}", status), ("", detail)):
            app.router.add_api_route(
                "/v1/conversations/{conversation_id}" + suffix, handler, methods=["GET"],
                include_in_schema=False, route_class_override=_DispatchReadRoute,
            )
            route = app.router.routes.pop()
            app.router.routes.insert(0, route)
            routes.append(route)
        app.state.private_dispatch_read_routes = tuple(routes[-2:])
    app.state.private_application_plan_routes = tuple(routes)
