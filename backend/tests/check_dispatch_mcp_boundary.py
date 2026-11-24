"""Explicit pytest target for the optional MCP and private-dispatch composition."""

import asyncio

from context_host import SyntheticHost
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from test_context_server import http, reads, rpc

from tests.test_health_plan_preview import setup  # noqa: F401
from tests.test_private_dispatch import MEDIA_TYPE, LoopbackReceiver, install, pending


def test_crossed_credentials_deny_before_source_access(setup, tmp_path):  # noqa: F811
    mcp = SyntheticHost()
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    receiver = LoopbackReceiver(1, Ed25519PrivateKey.generate().public_key())
    _, creates, _, phases = install(host, receiver, tmp_path)
    with TestClient(host.app) as client:
        _, post, _, confirmation, _ = pending(host, client, creates)
        previous = list(phases)
        calls = list(host.reverse.calls)
        response = client.post(
            post, content=confirmation, headers=host.headers | {
                "authorization": f"Bearer {mcp.token()}", "content-type": MEDIA_TYPE,
            },
        )
        assert response.status_code in {401, 403, 404}
        assert phases == previous and host.reverse.calls == calls

    async def check_mcp():
        before = reads(mcp)
        async with http(mcp, host.headers["authorization"].removeprefix("Bearer ")) as client:
            for name, arguments in (("search", {"query": "Demo"}), ("fetch", {"id": "synthetic"})):
                response = await rpc(client, "tools/call", {"name": name, "arguments": arguments})
                assert response.status_code == 401
        assert reads(mcp) == before

    asyncio.run(check_mcp())
