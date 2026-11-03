"""Prepare retrieval documents from an operator-selected local text file."""

import os
import stat
from pathlib import Path

from personal_ai.retrieval.installation import LocalDocument

MAX_TEXT_BYTES = 16_000


def document_from_bytes(raw: bytes, metadata: dict) -> LocalDocument:
    if not 0 < len(raw) <= MAX_TEXT_BYTES or "text" in metadata:
        raise ValueError("source_invalid")
    return LocalDocument.model_validate({**metadata, "text": raw.decode("utf-8")})


def load_document(
    path: Path, metadata: dict, *, enabled: bool = False
) -> LocalDocument:
    """Require an absolute path under trusted directories, without following links."""
    if not enabled:
        raise ValueError("source_unavailable")
    if path.anchor != "/" or ".." in path.parts or path.suffix not in {".txt", ".md"}:
        raise ValueError("source_invalid")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open("/", directory_flags)
    try:
        for part in path.parts[1:-1]:
            info = os.fstat(directory)
            _require_trusted(info)
            child = os.open(part, directory_flags, dir_fd=directory)
            os.close(directory)
            directory = child
        _require_trusted(os.fstat(directory))
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            _require_trusted(before)
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_TEXT_BYTES:
                raise ValueError("source_invalid")
            raw = stream.read(MAX_TEXT_BYTES + 1)
            after = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            if _identity(before) != _identity(after) or len(raw) != before.st_size:
                raise ValueError("source_changed")
        return document_from_bytes(raw, metadata)
    except (OSError, ValueError):
        raise ValueError("source_invalid") from None
    finally:
        os.close(directory)


def _require_trusted(info):
    # Sticky writable ancestors (e.g. /private/tmp) protect entries owned by trusted users.
    writable = info.st_mode & 0o022
    sticky_directory = stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX
    if info.st_uid not in {0, os.geteuid()} or writable and not sticky_directory:
        raise ValueError("source_invalid")


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
