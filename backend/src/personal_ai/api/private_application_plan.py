"""Explicit composition for the isolated, versioned application inference profile."""

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from personal_ai.api import dependencies as deps
from personal_ai.api.routes import _request_id, _sse_response
from personal_ai.context import ContextAssembler
from personal_ai.context.providers import ContextPreparationError
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.external_turns.application_plan import (
    ApplicationPlanService,
    PlanContinuation,
    PlanTarget,
)
from personal_ai.storage.async_io import sync_call

PROFILE_PREFIX = "/private/application-plan/v1/conversations"
MAX_PREVIEW_BYTES = 8192


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate property")
    return result


async def _intent(request: Request, *, confirmed: bool) -> PlanContinuation:
    media = request.headers.getlist("content-type")
    if (
        len(media) != 1
        or media[0].split(";", 1)[0].strip().lower() != "application/json"
        or request.url.query
    ):
        raise HTTPException(422, "validation_error")
    try:
        value = json.loads((await request.body()).decode("utf-8"), object_pairs_hook=_unique_object)
        parsed = PlanContinuation.model_validate(value)
        present = "confirmation" in parsed.choice.model_fields_set
        if present != confirmed or (confirmed and parsed.choice.confirmation is None):
            raise ValueError("invalid confirmation")
        parsed.content.encode("utf-8")
        return parsed
    except (ValueError, RecursionError):
        raise HTTPException(422, "validation_error") from None


def mount_application_plan(
    app: FastAPI,
    *,
    service: ApplicationPlanService,
    assembler_dependency: Callable[..., ContextAssembler],
    preview_recipient_scope: Callable[[PlanTarget], AbstractContextManager[None]],
) -> None:
    """Mount only on an explicitly isolated host before its middleware starts."""
    if (
        not getattr(app.state, "isolate_external_conversations", False)
        or getattr(app.state, "private_application_plan_routes", ())
        or app.middleware_stack is not None
    ):
        raise ValueError("application_plan_requires_isolated_host")

    async def preview(
        conversation_id: UUID,
        request: Request,
        chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        incoming = await _intent(request, confirmed=False)
        target = await sync_call(service.current_target)
        with preview_recipient_scope(target):
            selection = await sync_call(service.preview, chat, assembler, conversation_id, incoming)
        response = JSONResponse(jsonable_encoder(selection))
        if len(response.body) > MAX_PREVIEW_BYTES:
            raise ContextPreparationError("context_no_ai_route")
        return response

    async def continue_turn(
        conversation_id: UUID,
        request: Request,
        chat: Annotated[ChatTurnService, Depends(deps.get_chat_turn_service)],
        assembler: Annotated[ContextAssembler, Depends(assembler_dependency)],
    ):
        incoming = await _intent(request, confirmed=True)
        stream = await sync_call(service.continue_turn, chat, assembler, conversation_id, incoming)
        return _sse_response(stream, request_id=_request_id(request))

    routes = []
    for suffix, handler in (("context-preview", preview), ("continue", continue_turn)):
        app.add_api_route(
            f"{PROFILE_PREFIX}/{{conversation_id}}/{suffix}",
            handler,
            methods=["POST"],
            include_in_schema=False,
        )
        routes.append(app.router.routes[-1])
    app.state.private_application_plan_routes = tuple(routes)
