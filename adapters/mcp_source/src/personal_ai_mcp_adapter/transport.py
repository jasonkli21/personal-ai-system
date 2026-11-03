"""Bounded SDK transport seams for controlled local fixtures."""

import os
import signal
import subprocess
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import anyio
import httpx2
from anyio.streams.buffered import BufferedByteReceiveStream
from mcp import types
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.message import SessionMessage

MAX_FRAME = 65_536
FIXTURE_ENDPOINT = "http://127.0.0.1:8765/mcp"


@dataclass(frozen=True)
class StdioFixture:
    program: Path
    args: tuple[str, ...]
    cwd: Path
    _program_identity: tuple[int, int, int, int, int] = field(init=False, repr=False)
    _program_realpath: Path = field(init=False, repr=False)
    _cwd_identity: tuple[int, int, int] = field(init=False, repr=False)

    def __post_init__(self):
        """Pin the host-selected executable and working directory at registration."""
        executable = _trusted_executable(self.program)
        directory = _trusted_directory(self.cwd)
        object.__setattr__(self, "_program_realpath", executable)
        object.__setattr__(self, "_program_identity", _file_identity(executable.stat()))
        object.__setattr__(self, "_cwd_identity", _directory_identity(directory.stat()))

    def connect(self):
        return _stdio_fixture(self)


@dataclass(frozen=True)
class HttpFixture:
    app: Callable

    def connect(self):
        return _http_fixture(self.app)


@asynccontextmanager
async def _stdio_fixture(registration: StdioFixture):
    """Run one trusted executable, with no shell and no inherited environment."""
    program, args, cwd = registration.program, registration.args, registration.cwd
    if (
        type(args) is not tuple
        or not program.is_absolute()
        or not cwd.is_absolute()
        or len(args) > 12
        or any(len(arg) > 1024 for arg in args)
    ):
        raise ValueError("fixture_unavailable")
    try:
        executable = _trusted_executable(program)
        directory = _trusted_directory(cwd)
        if (
            executable != registration._program_realpath
            or _file_identity(executable.stat()) != registration._program_identity
            or _directory_identity(directory.stat()) != registration._cwd_identity
        ):
            raise ValueError("fixture_unavailable")
    except (OSError, ValueError):
        raise ValueError("fixture_unavailable") from None
    child_env = {}
    if program != executable:
        # macOS Python uses this launcher marker to recover a venv prefix when
        # invoked through its real binary. Execute the pinned target itself so
        # replacing the selected symlink after validation cannot redirect it.
        child_env["__PYVENV_LAUNCHER__"] = str(program)
    process = await anyio.open_process(
        [str(executable), *args],
        cwd=directory,
        env=child_env,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    incoming, read = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    write, outgoing = anyio.create_memory_object_stream[SessionMessage](0)

    async def receive():
        async with incoming:
            buffer = BufferedByteReceiveStream(process.stdout)
            try:
                for _ in range(8):
                    raw = await buffer.receive_until(b"\n", MAX_FRAME)
                    message = types.jsonrpc_message_adapter.validate_json(raw)
                    if not isinstance(
                        message, (types.JSONRPCResponse, types.JSONRPCError)
                    ):
                        return
                    await incoming.send(SessionMessage(message))
            except (
                anyio.EndOfStream,
                anyio.IncompleteRead,
                anyio.DelimiterNotFound,
                ValueError,
            ):
                return

    async def send():
        async with outgoing:
            async for row in outgoing:
                raw = row.message.model_dump_json(
                    by_alias=True, exclude_none=True
                ).encode()
                if len(raw) >= MAX_FRAME:
                    raise ValueError("fixture_unavailable")
                await process.stdin.send(raw + b"\n")

    try:
        async with anyio.create_task_group() as group:
            group.start_soon(receive)
            group.start_soon(send)
            try:
                yield read, write
            finally:
                group.cancel_scope.cancel()
    finally:
        with anyio.CancelScope(shield=True):
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            with anyio.fail_after(2):
                await process.aclose()


def _trusted_executable(program: Path) -> Path:
    if not isinstance(program, Path) or not program.is_absolute():
        raise ValueError("fixture_unavailable")
    resolved = program.resolve(strict=True)
    info = resolved.stat()
    if (
        not resolved.is_file()
        or not info.st_mode & 0o111
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o022
    ):
        raise ValueError("fixture_unavailable")
    return resolved


def _trusted_directory(cwd: Path) -> Path:
    if not isinstance(cwd, Path) or not cwd.is_absolute():
        raise ValueError("fixture_unavailable")
    resolved = cwd.resolve(strict=True)
    info = resolved.stat()
    if (
        not resolved.is_dir()
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o022
    ):
        raise ValueError("fixture_unavailable")
    return resolved


def _file_identity(info):
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid


def _directory_identity(info):
    return info.st_dev, info.st_ino, info.st_mode


@asynccontextmanager
async def _http_fixture(app):
    """Streamable HTTP JSON via an in-process ASGI peer, with no socket path."""

    async def bounded_app(scope, receive, send):
        total = 0

        async def bounded_send(message):
            nonlocal total
            total += len(message.get("body", b""))
            if total > MAX_FRAME:
                raise ValueError("fixture_unavailable")
            await send(message)

        await app(scope, receive, bounded_send)

    async def enforce_endpoint(request):
        if str(request.url) != FIXTURE_ENDPOINT or request.method not in {
            "GET",
            "POST",
        }:
            raise ValueError("fixture_unavailable")

    async def enforce_response(response):
        # The SDK otherwise follows same-origin redirects irrespective of client settings.
        if response.is_redirect or (
            response.status_code == 200
            and response.headers.get("content-type", "").split(";")[0]
            != "application/json"
        ):
            raise ValueError("fixture_unavailable")

    async with (
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=bounded_app),
            trust_env=False,
            follow_redirects=False,
            event_hooks={"request": [enforce_endpoint], "response": [enforce_response]},
        ) as client,
        streamable_http_client(
            FIXTURE_ENDPOINT, http_client=client, terminate_on_close=False
        ) as streams,
    ):
        yield streams
