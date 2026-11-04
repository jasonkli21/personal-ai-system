"""Private owner profile correction and portable copies."""

from asyncio import timeout
from datetime import UTC, datetime
from threading import BoundedSemaphore
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from personal_ai.api.dependencies import (
    get_global_profile_repository,
    require_standalone_application_scope,
)
from personal_ai.auth.scope import RequestScope
from personal_ai.context.profile import (
    GlobalProfile,
    GlobalProfileRepository,
    GlobalProfileUpdate,
    ProfileRevisionConflict,
)
from personal_ai.memory.portability import (
    DOWNLOAD_WARNING,
    MAX_PORTABLE_BYTES,
    ImportPreview,
    export_profile,
    parse_portable_profile,
    preview_profile,
)
from personal_ai.settings import Settings, get_settings

_slots = BoundedSemaphore(8)
_NO_STORE = {"Cache-Control": "private, no-store"}


def require_portability(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    if not (settings.memory_user_management_enabled and settings.memory_portability_enabled):
        raise HTTPException(status_code=404, detail="not_found")


async def portability_slot():
    if not _slots.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="memory_portability_busy")
    try:
        yield
    finally:
        _slots.release()


router = APIRouter(
    prefix="/portability",
    dependencies=[
        Depends(require_standalone_application_scope),
        Depends(require_portability),
        Depends(portability_slot),
    ],
)

OwnerScope = Annotated[RequestScope, Depends(require_standalone_application_scope)]
ProfileRepository = Annotated[GlobalProfileRepository, Depends(get_global_profile_repository)]


class ProfileCorrection(GlobalProfileUpdate):
    expected_revision: int = Field(strict=True, ge=0, le=2**63 - 1)


async def read_json(request: Request) -> bytes:
    if request.headers.get("content-type", "").partition(";")[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="portable_json_required")
    content = bytearray()
    try:
        async with timeout(2):
            async for chunk in request.stream():
                if len(chunk) > MAX_PORTABLE_BYTES - len(content):
                    raise HTTPException(status_code=413, detail="portable_body_too_large")
                content.extend(chunk)
    except (TimeoutError, ClientDisconnect):
        raise HTTPException(status_code=408, detail="portable_body_interrupted") from None
    return bytes(content)


def _unavailable():
    return HTTPException(status_code=503, detail="memory_portability_unavailable")


@router.get("/capabilities")
def capabilities(response: Response):
    response.headers.update(_NO_STORE)
    return {
        "profile_correction": True,
        "profile_export": True,
        "import_preview": True,
        "import_commit": False,
        "verified_knowledge_revision": False,
        "verified_knowledge_export": False,
        "download_warning": DOWNLOAD_WARNING,
    }


@router.get("/profile", response_model=GlobalProfile)
def read_profile(scope: OwnerScope, repository: ProfileRepository, response: Response):
    try:
        with repository.profile_snapshot(scope.owner_id) as profile:
            response.headers.update(_NO_STORE)
            return profile
    except Exception:  # noqa: BLE001 - bounded content-free storage failure
        raise _unavailable() from None


@router.post("/profile", response_model=GlobalProfile)
async def correct_profile(
    request: Request, scope: OwnerScope, repository: ProfileRepository, response: Response
):
    raw = await read_json(request)
    try:
        correction = ProfileCorrection.model_validate_json(raw)
        update = GlobalProfileUpdate.model_validate(
            correction.model_dump(exclude={"expected_revision"})
        )
        if any(item.shared_with_applications for item in update.fields):
            raise ValueError("profile_sharing_requires_consent")
    except ValueError:
        raise HTTPException(status_code=422, detail="profile_correction_invalid") from None
    try:
        result = await run_in_threadpool(
            repository.update, scope.owner_id, update, expected_revision=correction.expected_revision
        )
    except ProfileRevisionConflict:
        raise HTTPException(status_code=409, detail="profile_update_conflict") from None
    except Exception:  # noqa: BLE001 - caller must reload after an uncertain result
        raise _unavailable() from None
    response.headers.update(_NO_STORE)
    return result


@router.get("/export")
def download(scope: OwnerScope, repository: ProfileRepository):
    try:
        with repository.profile_snapshot(scope.owner_id) as prepared:
            content = export_profile(prepared, datetime.now(UTC))
        with repository.profile_snapshot(scope.owner_id) as current:
            if current != prepared:
                raise ProfileRevisionConflict
            return Response(
                content,
                media_type="application/json",
                headers={
                    **_NO_STORE,
                    "Content-Disposition": 'attachment; filename="personal-ai-profile.json"',
                },
            )
    except Exception:  # noqa: BLE001 - a failed fence or serialization never releases bytes
        raise _unavailable() from None


@router.post("/import-preview", response_model=ImportPreview)
async def preview(
    request: Request, scope: OwnerScope, repository: ProfileRepository, response: Response
):
    raw = await read_json(request)
    try:
        manifest = parse_portable_profile(raw)
    except (ValueError, RecursionError):
        raise HTTPException(status_code=422, detail="portable_manifest_invalid") from None

    def assess():
        with repository.profile_snapshot(scope.owner_id) as profile:
            return preview_profile(manifest, profile)

    try:
        result = await run_in_threadpool(assess)
    except Exception:  # noqa: BLE001 - content-free failure
        raise _unavailable() from None
    response.headers.update(_NO_STORE)
    return result
