"""Run the independent fixture auditor from a clean wheel-only environment."""

import asyncio
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import venv
from contextlib import aclosing
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import uvicorn

from personal_ai.api.synthetic_reasoning import create_preview
from personal_ai.llm.fake import FakeLLMClient

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("sdk/python", "sdk/contract-probes/synthetic-reasoning")


def main():
    uv = sys.argv[1] if len(sys.argv) == 2 else "uv"
    with tempfile.TemporaryDirectory(prefix="synthetic-reasoning-install-") as directory:
        root = Path(directory)
        env = {
            "PATH": os.environ["PATH"],
            "TMPDIR": directory,
            "UV_CACHE_DIR": str(root / "cache"),
            "UV_OFFLINE": "1",
        }
        wheels = root / "wheels"
        for package in PACKAGES:
            subprocess.run(
                [
                    uv,
                    "build",
                    "--wheel",
                    "--no-build-isolation",
                    "--python",
                    sys.executable,
                    "--out-dir",
                    str(wheels),
                    str(ROOT / package),
                ],
                cwd=root,
                env=env,
                check=True,
            )
        assert len(list(wheels.glob("*.whl"))) == len(PACKAGES)
        consumer = root / "consumer"
        venv.EnvBuilder(with_pip=False).create(consumer)
        python = consumer / "bin/python"
        subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--python",
                str(python),
                *map(str, sorted(wheels.glob("*.whl"))),
            ],
            cwd=root,
            env=env,
            check=True,
        )

        original = FakeLLMClient.stream_events
        sends = 0

        async def pause_third_send(client, *args, **kwargs):
            nonlocal sends
            sends += 1
            if sends == 3:
                await asyncio.sleep(10)  # Canonical step deadline bounds the injected stall.
            async with aclosing(original(client, *args, **kwargs)) as events:
                async for event in events:
                    yield event

        token = secrets.token_urlsafe(32)
        with (
            patch.object(FakeLLMClient, "stream_events", pause_third_send),
            socket.socket() as listener,
        ):
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(
                uvicorn.Config(
                    create_preview(token),
                    access_log=False,
                    proxy_headers=False,
                    log_level="error",
                )
            )
            thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 5
                while not server.started:
                    if not thread.is_alive() or time.monotonic() >= deadline:
                        raise RuntimeError("synthetic_preview_start_failed")
                    time.sleep(0.01)
                subprocess.run(
                    [str(python), "-I", "-m", "fixture_auditor"],
                    cwd=root,
                    check=True,
                    timeout=30,
                    env={
                        **env,
                        "FIXTURE_AUDITOR_URL": f"http://127.0.0.1:{port}",
                        "SYNTHETIC_REASONING_TOKEN": token,
                        "FIXTURE_AUDITOR_STALLED_SEND": "1",
                    },
                )
            finally:
                server.should_exit = True
                thread.join(5)
            if thread.is_alive():
                raise RuntimeError("synthetic_preview_shutdown_failed")
        assert sends == 3


if __name__ == "__main__":
    main()
