"""Run explicitly inspected pytest files with Python network egress forbidden.

Invoke in a clean environment, without a local .env. This fences Python socket
operations, not arbitrary native code. Never use it as evidence for live services.
"""

import os
import socket
import sys
from pathlib import Path

attempts = []


def fence(event, args):
    denied = event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}
    if event == "socket.__new__" and len(args) > 1:
        denied = args[1] in (2, 10)
    if denied:
        attempts.append(event)
        raise PermissionError("PI-1 offline network fence")


sys.addaudithook(fence)
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except PermissionError:
    pass
else:
    raise RuntimeError("network fence inactive")
assert attempts == ["socket.__new__"]
attempts.clear()
assert not Path(".env").exists() and not Path("backend/.env").exists(), (
    "Refuse local environment files"
)
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
import pytest

result = pytest.main(["-p", "anyio.pytest_plugin", *sys.argv[1:]])
print(f"PI1_BLOCKED_NETWORK_ATTEMPTS={len(attempts)} events={attempts}")
sys.exit(3 if attempts else result)
