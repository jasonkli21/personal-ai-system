"""Run the inspected PI-2 fixture with only numeric loopback sockets permitted.

Python audit fence, not native/OS sandbox evidence. Any observed attempted
non-loopback connect/bind/DNS/send fails even when a test catches the exception.
"""

import os
import socket
import sys
from pathlib import Path

attempts = []


def fence(event, args):
    denied = event in {"socket.sendto", "socket.sendmsg"}
    if event == "socket.getaddrinfo":
        denied = args[0] not in {"127.0.0.1", "::1"}
    elif event in {"socket.connect", "socket.bind"}:
        address = args[1]
        denied = isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1"}
    if denied:
        attempts.append(event)
        raise PermissionError("PI-2 forbidden network attempt")


sys.addaudithook(fence)
try:
    socket.getaddrinfo("egress-self-test.invalid", 443)
except PermissionError:
    pass
assert attempts == ["socket.getaddrinfo"]
attempts.clear()
assert not Path(".env").exists() and not Path("backend/.env").exists()
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"


def main():
    import pytest

    result = pytest.main(["-p", "anyio.pytest_plugin", *sys.argv[1:]])
    print(f"PI2_FORBIDDEN_NETWORK_ATTEMPTS={len(attempts)} events={attempts}")
    return 3 if attempts else result


if __name__ == "__main__":
    raise SystemExit(main())
