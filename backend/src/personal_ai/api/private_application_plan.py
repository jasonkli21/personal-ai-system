"""Explicit composition for the isolated, versioned application inference profile."""

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response

from personal_ai.api import dependencies as deps
from personal_ai.api.routes import _request_id, _sse_response
from personal_ai.api.schemas import ExternalCreateConversationRequest
from personal_ai.auth.application_clients import require_current_client_authority
from personal_ai.auth.scope import current_verified_principal
from personal_ai.context import ContextAssembler
from personal_ai.context.providers import ContextPreparationError
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.conversations import ConversationService
from personal_ai.services.external_turns.application_plan import (
    ApplicationPlanService,
    PlanContinuation,
    PlanTarget,
    encode_preview_response,
)
from personal_ai.storage.async_io import sync_call

PROFILE_PREFIX = "/private/application-plan/v1/conversations"
MAX_PREVIEW_BYTES = 8192
RECEIPT_HEADER = "x-application-plan-receipt"


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


async def _json_body(request: Request, *, max_bytes: int) -> bytes:
    media = request.headers.getlist("content-type")
    if (
        len(media) != 1
        or media[0].split(";", 1)[0].strip().lower() != "application/json"
        or request.url.query
    ):
        raise HTTPException(422, "validation_error")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > max_bytes:
            raise HTTPException(422, "validation_error")
        body.extend(chunk)
    return bytes(body)


async def _intent(request: Request, *, confirmed: bool) -> tuple[PlanContinuation, bytes]:
    body = await _json_body(request, max_bytes=128 * 1024)
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
        parsed = PlanContinuation.model_validate(value)
        present = "confirmation" in parsed.choice.model_fields_set
        if present != confirmed or (confirmed and parsed.choice.confirmation is None):
            raise ValueError("invalid confirmation")
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
) -> None:
    """Mount only on an explicitly isolated host before its middleware starts."""
    if (
        not getattr(app.state, "isolate_external_conversations", False)
        or getattr(app.state, "private_application_plan_routes", ())
        or app.middleware_stack is not None
    ):
        raise ValueError("application_plan_requires_isolated_host")

    async def create(
        request: Request,
        conversations: Annotated[ConversationService, Depends(deps.get_conversation_service)],
    ):
        assert travel_receipt_key is not None
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
            or target.scope.application_id != "travel"
            or target.scope.workspace_id is not None
        ):
            raise ContextPreparationError("context_no_ai_route")
        conversation = await sync_call(
            conversations.create_conversation,
            title=incoming.title,
            idempotency_key=incoming.idempotency_key,
        )
        await sync_call(require_current_client_authority)
        if (
            target is not await sync_call(service.current_target)
            or conversation.owner_id != principal.owner_id
            or conversation.application_id != "travel"
            or conversation.workspace_id is not None
            or conversation.external_client_namespace != target.scope.client_namespace
            or conversation.title != incoming.title.strip()
        ):
            raise ContextPreparationError("context_no_ai_route")
        response_body = encode_preview_response({"conversation_id": str(conversation.id)})
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
        incoming, raw = await _intent(request, confirmed=False)
        target = await sync_call(service.current_target)
        with preview_recipient_scope(target):
            selection, source_revision = await sync_call(
                service.preview_with_source_revision,
                chat,
                assembler,
                conversation_id,
                incoming,
                expected_target=target,
            )
        response_body = encode_preview_response(selection)
        if len(response_body) > MAX_PREVIEW_BYTES:
            raise ContextPreparationError("context_no_ai_route")
        headers = {"cache-control": "no-store"}
        if travel_receipt_key is not None and target.preview_source is not None:
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
        return Response(response_body, media_type="application/json", headers=headers)

    async def continue_turn(
        conversation_id: UUID,
        request: Request,
        chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        incoming, _ = await _intent(request, confirmed=True)
        stream = await sync_call(service.continue_turn, chat, assembler, conversation_id, incoming)
        return _sse_response(stream, request_id=_request_id(request))

    routes = []
    if travel_receipt_key is not None:
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
    app.state.private_application_plan_routes = tuple(routes)
