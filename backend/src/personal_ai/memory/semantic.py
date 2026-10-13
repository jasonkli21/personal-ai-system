"""Conservative deterministic equivalence for explicit preference assertions."""

from __future__ import annotations

import re
from hashlib import sha256

from personal_ai.memory.contracts import normalize

_NEGATION_OR_QUALIFICATION = re.compile(
    r"\b(no|not|never|dislike|avoid|unless|except|sometimes|might|may)\b"
)
_FORMS = (
    re.compile(r"i prefer (?P<value>.+?) for (?P<context>.+)"),
    re.compile(r"(?P<value>.+?) (?:is|are) my preference for (?P<context>.+)"),
    re.compile(r"my preference for (?P<context>.+?) is (?P<value>.+)"),
)


def preference_support_key(content: str) -> str | None:
    """Return a key only for narrow, positive preference syntax.

    The value and its complete context clause are retained verbatim after case,
    whitespace, and terminal punctuation normalization. Numbers and qualifiers
    remain part of the key; negated or hedged statements are not consolidated.
    """
    text = normalize(content).rstrip(".!?").strip()
    if _NEGATION_OR_QUALIFICATION.search(text):
        return None
    for pattern in _FORMS:
        match = pattern.fullmatch(text)
        if match is None:
            continue
        value = match.group("value").strip(" .,!?:;")
        context = match.group("context").strip(" .,!?:;")
        if value and context:
            return f"preference\0{value}\0{context}"
    return None


def preference_support_fingerprint(content: str) -> str | None:
    key = preference_support_key(content)
    return sha256(key.encode()).hexdigest() if key is not None else None
