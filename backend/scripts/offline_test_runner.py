"""Run explicitly inspected pytest files with Python network egress forbidden.

Invoke in a clean environment, without a local .env. This fences Python socket
operations, not arbitrary native code. Never use it as evidence for live services.
"""

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# urllib3 probes IPv6 support by creating a socket and binding loopback when it
# is first imported. Prime that local capability check before installing the
# test-time fence; the fence remains active for every collected test and run.
import urllib3.util.connection as urllib3_connection

_ = urllib3_connection.HAS_IPV6

attempts = []
NETWORK_FAMILIES = {socket.AF_INET, socket.AF_INET6}


def fence(event, args):
    denied = event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}
    if event == "socket.__new__" and len(args) > 1:
        denied = args[1] in NETWORK_FAMILIES
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

    plugins = []
    if any("test_reasoning_grounded" in arg for arg in sys.argv):
        if str(ROOT / "backend/src") not in sys.path:
            sys.path.insert(0, str(ROOT / "backend/src"))
        from personal_ai.evaluation.replay_clock import frozen_monotonic

        class FrozenSealedReplayClock:
            @pytest.hookimpl(hookwrapper=True)
            def pytest_runtest_call(self, item):
                if (
                    item.path.name == "test_reasoning_grounded.py"
                    and item.name == "test_sealed_evaluation"
                ):
                    with frozen_monotonic():
                        yield
                else:
                    yield

        plugins.append(FrozenSealedReplayClock())

    result = pytest.main(
        ["-p", "anyio.pytest_plugin", *sys.argv[1:]],
        plugins=plugins,
    )
    print(f"OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS={len(attempts)} events={attempts}")
    return 3 if attempts else result


if __name__ == "__main__":
    raise SystemExit(main())
