"""PI-3 inspected suite under an OS network fence, plus Python/native probes.

macOS sandbox denies native TCP/UDP/Unix egress, inherited by child processes.
Other systems must supply an equivalent sandbox before this target is supported.
No broad pytest discovery or manual/native/cloud persistence suites are run.
"""

import ctypes
import errno
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

FILES = [
    "test_inference_execution.py", "test_chat_stream_lifecycle.py", "test_context_provider.py",
    "test_context_authorization.py", "test_context_builder.py", "test_context_sources.py",
    "test_context_runtime_composition.py", "test_context.py", "test_memory_provider.py",
    "test_memory_disclosure_authorization.py", "test_memory.py", "test_memory_phase34.py",
    "test_memory_control.py", "test_memory_control_context.py", "test_memory_control_api.py",
    "test_memory_knowledge.py", "test_memory_knowledge_consumer.py", "test_memory_worker.py",
    "test_llm.py", "test_litellm_gateway.py", "test_provider_usage.py", "test_provider_usage_api.py",
    "test_routing_phase21.py", "test_routing_phase23.py", "test_provider_matrix.py",
    "test_booking_extractions.py", "test_itinerary_proposals.py", "test_planning_experiment.py", "test_external_turn_composition.py", "test_retrieval_phase33.py", "test_phase36_integrated.py",
]


def main():
    if "--fenced" not in sys.argv:
        if sys.platform != "darwin":
            raise SystemExit("PI3: equivalent native network sandbox required on this OS")
        with tempfile.TemporaryDirectory(prefix="pi3-", dir="/tmp") as directory:
            address = directory + "/probe.sock"
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(address)
                listener.listen(1)
                return subprocess.call([
                    "/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)",
                    sys.executable, __file__, "--fenced", *sys.argv[1:],
                ], env={**os.environ, "PI3_PROBE_SOCKET": address})
    assert not Path(".env").exists() and not Path("backend/.env").exists()
    # ctypes bypasses Python socket audit hooks: prove native IPv4/IPv6/Unix
    # connections are denied by the OS, including local PostgreSQL transports.
    libc = ctypes.CDLL(None, use_errno=True)
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        fd = libc.socket(family, socket.SOCK_STREAM, 0)
        if fd < 0:
            assert ctypes.get_errno() in {errno.EPERM, errno.EACCES}
            continue
        try:
            if family == socket.AF_UNIX:
                path = os.environ["PI3_PROBE_SOCKET"].encode() + b"\0"
                address = bytes([len(path) + 2, socket.AF_UNIX]) + path
            elif family == socket.AF_INET:
                address = b"\x10\x02\x00\x09\x7f\x00\x00\x01" + bytes(8)
            else:
                address = b"\x1c\x1e\x00\x09" + bytes(4) + bytes(15) + b"\x01" + bytes(4)
            assert libc.connect(fd, address, len(address)) == -1
            assert ctypes.get_errno() in {errno.EPERM, errno.EACCES}, (family, ctypes.get_errno())
        finally:
            libc.close(fd)
    print("PI3_NATIVE_IPV4_IPV6_UNIX_DENIAL=passed", flush=True)
    attempts = []
    def fence(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"} or (
            event == "socket.__new__" and len(args) > 1 and args[1] in (2, 10)
        ):
            attempts.append((event, os.environ.get("PYTEST_CURRENT_TEST")))
            raise PermissionError("PI3 Python network fence")
    sys.addaudithook(fence)
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError:
        pass
    assert attempts == [("socket.__new__", None)]
    attempts.clear()
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    import pytest

    chosen = FILES
    if "--only" in sys.argv:
        chosen = sys.argv[sys.argv.index("--only") + 1:]
        assert chosen and set(chosen) <= set(FILES)
    result = pytest.main([
        "-p", "anyio.pytest_plugin", "-q", "--tb=short",
        *["backend/tests/" + name for name in chosen],
    ])
    print(f"PI3_FORBIDDEN_PYTHON_NETWORK_ATTEMPTS={len(attempts)} cases={attempts}", flush=True)
    return 3 if attempts else result


if __name__ == "__main__":
    raise SystemExit(main())
