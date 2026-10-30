"""Reference errors retain the common safe envelope."""

from fastapi import Request
from fastapi.responses import JSONResponse
from personal_ai.domains.contracts import DomainContractError

from personal_ai_reference_apps.booking_extractions.repositories import ExtractionError
from personal_ai_reference_apps.domains.providers import DomainProviderError
from personal_ai_reference_apps.itinerary_proposals.contracts import ProposalError


def _error_response(status_code, code, message):
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


async def itinerary_proposal_error(_: Request, error: ProposalError) -> JSONResponse:
    return _error_response(
        error.status,
        error.code,
        "The itinerary proposal could not be completed. Check its status or submit a new request.",
    )


async def booking_extraction_error(_: Request, error: ExtractionError) -> JSONResponse:
    return _error_response(
        error.status,
        error.code,
        "The booking extraction could not be completed. Check its status or submit a new request.",
    )


async def domain_contract_error(_: Request, error: DomainContractError) -> JSONResponse:
    return _error_response(
        error.status,
        error.code,
        "The domain comparison could not be completed. Check its constraints and source evidence.",
    )


async def domain_provider_error(_: Request, error: DomainProviderError) -> JSONResponse:
    return _error_response(
        error.status,
        error.code,
        "The configured source is unavailable or declined the request.",
    )
