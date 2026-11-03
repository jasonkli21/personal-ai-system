#!/usr/bin/env bash
set +x
set -euo pipefail

case "${1:-}" in
  ""|plan)
    if [[ $# -gt 0 ]]; then shift; fi
    script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
    exec python3 -I "$script_directory/cloud_plan.py" "$@"
    ;;
  apply)
    printf '%s\n' '{"status":"refused","reason":"apply_blocked_unverified"}' >&2
    exit 2
    ;;
  *)
    printf '%s\n' '{"status":"refused","reason":"explicit_plan_required"}' >&2
    exit 2
    ;;
esac
