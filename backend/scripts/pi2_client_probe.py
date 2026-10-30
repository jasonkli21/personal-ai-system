"""Run the independent client CLI under the same numeric-loopback audit fence."""

import sys

import pi2_http_checks as network
from reading_logbook.cli import main

result = main(sys.argv[1:])
print(f"PI2_CLIENT_FORBIDDEN_NETWORK_ATTEMPTS={len(network.attempts)}", file=sys.stderr)
raise SystemExit(3 if network.attempts else result)
