"""Bounded POSIX child execution for inspected offline release commands.

The runner owns one process group and applies finite per-process limits where
supported. It does not claim aggregate process-tree memory/process containment.
"""

import os
import re
import resource
import signal
import subprocess
import sys
import tempfile
import threading
import time

ADDRESS_SPACE_LIMIT = 4_000_000_000
OUTPUT_LIMIT = 4_000_000
GRACE_SECONDS = 0.2


class _SupervisorSignal(Exception):
    def __init__(self, number):
        self.number = number


def _resource_limits():
    """Apply portable limits; address-space enforcement is host-qualified."""
    if not all(hasattr(resource, name) for name in ("RLIMIT_FSIZE", "RLIMIT_CPU")):
        raise RuntimeError("required_resource_limit_unavailable")
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_000_000, 4_000_000))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    if sys.platform.startswith("linux"):
        if not hasattr(resource, "RLIMIT_AS"):
            raise RuntimeError("address_space_limit_unavailable")
        resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_LIMIT, ADDRESS_SPACE_LIMIT))


def _group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _stop_owned_group(pgid):
    """Gracefully stop, then force-stop only the newly created session group."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return "STOPPED"
    except PermissionError:
        return "BLOCKED_SIGNAL_PERMISSION"
    deadline = time.monotonic() + GRACE_SECONDS
    while time.monotonic() < deadline and _group_exists(pgid):
        time.sleep(0.01)
    if _group_exists(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            return "STOPPED"
        except PermissionError:
            return "BLOCKED_SIGNAL_PERMISSION"
    return "STOPPED"


def bounded_run(argv, *, cwd, env, timeout=120):
    """Run a child in an owned process group with finite wall/output bounds."""
    if threading.active_count() != 1 or threading.current_thread() is not threading.main_thread():
        raise ValueError("bounded_runner_requires_single_thread")

    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    handlers = {}
    process = None
    timed_out = False
    interrupted = None
    group_cleanup = "NOT_STARTED"
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=_resource_limits,  # noqa: PLW1509
        )

        def interrupt(number, _frame):
            raise _SupervisorSignal(number)

        try:
            for number in (signal.SIGTERM, signal.SIGINT):
                handlers[number] = signal.signal(number, interrupt)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            except _SupervisorSignal as exc:
                interrupted = signal.Signals(exc.number).name
        finally:
            try:
                group_cleanup = _stop_owned_group(process.pid)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            finally:
                for number, previous in handlers.items():
                    signal.signal(number, previous)

        wall = time.monotonic() - start
        output.seek(0)
        raw = output.read(OUTPUT_LIMIT + 1)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    from release_profiles import sha

    text = raw.decode("utf-8", errors="replace")
    failed_tests = re.findall(r"^FAILED ([a-zA-Z0-9_./:]+)", text, re.MULTILINE)[:32]
    counts = re.findall(r"([0-9]+) (passed|failed|skipped|deselected)", text)
    attempts = re.findall(r"OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=([0-9]+)", text)
    return {
        "exit": process.returncode,
        "timed_out": timed_out,
        "interrupted_by": interrupted,
        "process_group_cleanup": group_cleanup,
        "output_cap_reached": len(raw) >= OUTPUT_LIMIT,
        "failed_tests_display_untrusted": failed_tests,
        "test_counts_display_untrusted": {key: int(n) for n, key in counts},
        "reported_network_attempts_display_untrusted": int(attempts[-1]) if attempts else None,
        "output_sha256": sha(raw),
        "output_bytes": min(len(raw), OUTPUT_LIMIT),
        "wall_seconds": round(wall, 6),
        "child_cpu_seconds": round(
            after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 6
        ),
        "supervisor_cumulative_terminated_children_rss_high_water_bytes": int(
            after.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        ),
        "per_invocation_peak_rss_bytes": None,
        "resource_envelope": {
            "per_process_address_space_bytes": ADDRESS_SPACE_LIMIT
            if sys.platform.startswith("linux")
            else None,
            "address_space_limit_status": "ENFORCED"
            if sys.platform.startswith("linux")
            else "UNAVAILABLE_ON_HOST",
            "file_size_bytes": 4_000_000,
            "cpu_seconds": 120,
            "process_count": "UNENFORCED",
            "descendant_session_escape": "UNCONTAINED",
            "e2_resource_status": "BLOCKED",
        },
        "argv": argv,
    }
