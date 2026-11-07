"""Run explicitly inspected pytest files with Python network egress forbidden.

Invoke in a clean environment, without a local .env. This fences Python socket
operations, not arbitrary native code. Never use it as evidence for live services.
"""

import os
import socket
import sys
from pathlib import Path

# urllib3 probes IPv6 support by creating a socket and binding loopback when it
# is first imported. Prime that local capability check before installing the
# test-time fence; the fence remains active for every collected test and run.
import urllib3.util.connection as urllib3_connection

_ = urllib3_connection.HAS_IPV6

attempts = []


def fence(event, args):
    denied = event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}
    if event == "socket.__new__" and len(args) > 1:
        denied = args[1] in (2, 10)
    if denied:
        attempts.append(event)
        raise PermissionError("offline test network fence")


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


def main():
    import pytest

    result = pytest.main(["-p", "anyio.pytest_plugin", *sys.argv[1:]])
    print(f"OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS={len(attempts)} events={attempts}")
    return 3 if attempts else result


if __name__ == "__main__":
    raise SystemExit(main())
