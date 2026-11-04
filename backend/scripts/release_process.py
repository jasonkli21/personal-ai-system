"""Bounded POSIX child execution for inspected offline release commands."""

import os
import re
import resource
import signal
import subprocess
import sys
import tempfile
import threading
import time


def bounded_run(argv, *, cwd, env, timeout=120):
    """Finite child group lifetime and output; callers own the command allowlist."""
    if threading.active_count() != 1:
        raise ValueError("bounded_runner_requires_single_thread")

    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (4_000_000, 4_000_000))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))

    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    with tempfile.TemporaryFile() as output:
        # This standalone CLI refuses multithreaded callers above.
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=limits,  # noqa: PLW1509
        )
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            timed_out = True
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        wall = time.monotonic() - start
        output.seek(0)
        raw = output.read(4_000_001)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    from release_profiles import sha

    text = raw.decode("utf-8", errors="replace")
    failed_tests = re.findall(r"^FAILED ([a-zA-Z0-9_./:]+)", text, re.MULTILINE)[:32]
    counts = re.findall(r"([0-9]+) (passed|failed|skipped|deselected)", text)
    attempts = re.findall(r"OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=([0-9]+)", text)
    return {
        "exit": process.returncode,
        "timed_out": timed_out,
        "output_cap_reached": len(raw) >= 4_000_000,
        "failed_tests": failed_tests,
        "test_counts": {key: int(n) for n, key in counts},
        "python_network_attempts": int(attempts[-1]) if attempts else None,
        "output_sha256": sha(raw),
        "output_bytes": len(raw),
        "wall_seconds": round(wall, 6),
        "child_cpu_seconds": round(
            after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 6
        ),
        "child_peak_rss_bytes": int(after.ru_maxrss * (1 if sys.platform == "darwin" else 1024)),
        "rss_scope": "process child high-water mark; not idle or whole process-tree RAM",
        "argv": argv,
    }
