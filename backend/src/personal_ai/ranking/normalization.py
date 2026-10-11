"""normalization ranking policy."""

from __future__ import annotations

import unicodedata


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(char if char.isalnum() else " " for char in normalized).split())


def _identifier(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
