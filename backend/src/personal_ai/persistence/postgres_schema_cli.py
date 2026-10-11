"""Compatibility entry point for the Postgres schema command."""

import sys

from personal_ai.persistence.postgres import schema_cli as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
