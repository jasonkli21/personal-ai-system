"""Synthetic PAS retrieval host used only by the independent process canary."""

import json
import sys
from pathlib import Path

import anyio
from mcp.server.stdio import stdio_server
from personal_ai.applications.contracts import (
    ApplicationDefinition,
    CapabilityRegistration,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.application_clients import bind_client_authority
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    RequestScope,
    bind_request_scope,
    bind_verified_principal,
)
from personal_ai.retrieval.service import RetrievalService
from personal_ai.retrieval.tools import MAX_TOOL_BYTES, TOOL_ID
from personal_ai.settings import Settings
from personal_ai_mcp_adapter.server import retrieval_server


def main():
    def fence(event, args):
        if event.startswith("socket.") and (
            event != "socket.__new__" or args[1] in (2, 10)
        ):
            raise PermissionError("fixture_network_denied")

    sys.addaudithook(fence)
    config = json.loads(Path(sys.argv[1]).read_text())
    scope = RequestScope(**config["scope"])
    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="fixture",
        app_environment="test",
        retrieval_enabled=True,
        retrieval_installation_file=config["installation_path"],
    )
    principal = AuthenticatedPrincipal(
        "synthetic-test-host",
        scope.acting_user_id,
        scope.owner_id,
        None,
        1,
        True,
        audience="fixture-client",
    )
    registry = ApplicationRegistry(
        (
            ApplicationDefinition(
                application_id=scope.application_id,
                display_name="Fixture",
                memory_namespace=scope.application_id,
                tool_ids=(TOOL_ID,),
            ),
        ),
        (
            CapabilityRegistration(
                capability_id=TOOL_ID,
                kind="tool",
                available=True,
                read_only_context=True,
                result_fields=("retrieval",),
                max_result_bytes=MAX_TOOL_BYTES,
            ),
        ),
    )
    service = RetrievalService(
        settings, scope, lambda: None, request_authority=lambda: None
    )

    def current_client():
        if not config.get("client_authorized", True):
            raise ValueError("synthetic_client_denied")

    authority = bind_client_authority(current_client)
    scope_token = bind_request_scope(scope)
    principal_token = bind_verified_principal(principal)

    server = retrieval_server(service, lambda: registry, enabled=True)

    async def serve():
        async with stdio_server() as (reader, writer):
            await server.run(reader, writer, server.create_initialization_options())

    try:
        anyio.run(serve)
    finally:
        from personal_ai.auth.application_clients import reset_client_authority
        from personal_ai.auth.scope import reset_request_scope, reset_verified_principal

        reset_verified_principal(principal_token)
        reset_request_scope(scope_token)
        reset_client_authority(authority)


if __name__ == "__main__":
    main()
