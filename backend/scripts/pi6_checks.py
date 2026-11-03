"""Native loopback-only PI-6 runner and adversarial checks; no remote transport."""
import errno
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = '''(version 1)(allow default)(deny network*)
(allow network-inbound (local ip "localhost:*"))
(allow network-outbound (remote ip "localhost:*"))'''


def main():
    if '--fenced' not in sys.argv:
        if sys.platform != 'darwin':
            raise SystemExit('PI6 requires reviewed equivalent native fence on this OS')
        env = {'PATH': os.environ['PATH'], 'TMPDIR': '/tmp',
               'PYTHONPATH': os.pathsep.join(str(ROOT / p) for p in [
                   'backend/src', 'examples/reading-logbook/client/src', 'examples/reading-logbook/host/src']),
               'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'AI_PROVIDER': 'fake',
               'APP_ENVIRONMENT': 'test', 'UV_OFFLINE': '1'}
        return subprocess.call(['/usr/bin/sandbox-exec', '-p', PROFILE, sys.executable,
                                __file__, '--fenced', *sys.argv[1:]], cwd=ROOT, env=env)
    # Kernel rejects the connect before egress, independently of the Python hook.
    for family, address in [(socket.AF_INET, ('192.0.2.1', 9)),
                            (socket.AF_INET6, ('2001:db8::1', 9))]:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            try:
                probe.connect(address)
            except OSError as error:
                if error.errno not in {errno.EPERM, errno.EACCES}:
                    raise RuntimeError('pi6_native_fence_not_proven') from None
            else:
                raise RuntimeError('pi6_native_fence_absent')
    attempts = []
    def fence(event, args):
        denied = event in {'socket.sendto', 'socket.sendmsg'}
        if event == 'socket.getaddrinfo':
            denied = args[0] not in {'127.0.0.1', '::1'}
        elif event in {'socket.connect', 'socket.bind'}:
            address = args[1]
            denied = not isinstance(address, tuple) or address[0] not in {'127.0.0.1', '::1'}
        if denied:
            attempts.append(event)
            raise PermissionError('pi6_network_denied')
    sys.addaudithook(fence)
    try:
        socket.getaddrinfo('pi6-egress.invalid', 443)
    except PermissionError:
        pass
    assert attempts == ['socket.getaddrinfo']
    attempts.clear()
    assert not (ROOT / '.env').exists() and not (ROOT / 'backend/.env').exists()
    sys._pi6_native_fenced = True
    import pytest
    result = pytest.main(['-p', 'anyio.pytest_plugin', '-q', '--tb=short',
                          'backend/tests/test_pi6.py'])
    if not result:
        from personal_ai.evaluation.pi6 import main as benchmark
        output = ROOT / 'artifacts/pi6/benchmark.json'
        sys.argv = [sys.argv[0], '--output', str(output)]
        result = benchmark()
    print(f'PI6_NATIVE_REMOTE_DENIAL=passed PI6_FORBIDDEN_PYTHON_ATTEMPTS={len(attempts)}')
    return 3 if attempts else result


if __name__ == '__main__':
    raise SystemExit(main())
