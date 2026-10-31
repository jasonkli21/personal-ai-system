"""Bounded operator snapshot authority and real deterministic lexical index."""

import os
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from personal_ai.evidence.contracts import ResearchRecord
from personal_ai.retrieval.contracts import item_from_quote

MAX_INSTALLATION_BYTES = 2_097_152


class Access(ResearchRecord):
    owner_id: str = Field(min_length=1, max_length=200)
    acting_user_id: str = Field(min_length=1, max_length=512)
    application_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")
    workspace_id: str | None = Field(default=None, max_length=100)
    purpose: Literal["interactive_retrieval"] = "interactive_retrieval"

    def allows(self, scope):
        return all(
            getattr(self, name) == getattr(scope, name)
            for name in ("owner_id", "acting_user_id", "application_id", "workspace_id")
        )


class LocalDocument(ResearchRecord):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,79}$")
    revision: str = Field(min_length=1, max_length=100)
    rights_epoch: str = Field(min_length=1, max_length=100)
    rights_reference: str = Field(min_length=1, max_length=200)
    license: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=16000)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    observed_at: datetime
    published_at: datetime | None = None
    expires_at: datetime
    enabled: bool = Field(default=True, strict=True)
    quote_allowed: bool = Field(default=False, strict=True)
    access: tuple[Access, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def valid_content(self):
        if (
            sha256(self.text.encode()).hexdigest() != self.content_sha256
            or self.observed_at >= self.expires_at
            or (self.published_at is not None and self.published_at > self.observed_at)
            or any(ord(c) < 32 and c not in "\n\t\r" for c in self.text)
        ):
            raise ValueError("invalid_local_document")
        return self

    def allows(self, scope, now):
        return (
            self.enabled
            and self.quote_allowed
            and self.observed_at <= now < self.expires_at
            and any(grant.allows(scope) for grant in self.access)
        )


class Installation(ResearchRecord):
    schema_version: Literal["retrieval-installation-v1"]
    enabled: bool = Field(default=False, strict=True)
    tool_enabled: bool = Field(default=False, strict=True)
    access: tuple[Access, ...] = Field(default=(), max_length=32)
    # This is explicit permission to disclose the submitted query to the selected search source.
    external_query_access: tuple[Access, ...] = Field(default=(), max_length=32)
    documents: tuple[LocalDocument, ...] = Field(default=(), max_length=128)

    @model_validator(mode="after")
    def unique(self):
        ids = [d.source_id for d in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_source")
        return self

    def allows(self, scope):
        return self.enabled and any(grant.allows(scope) for grant in self.access)


def read_regular_file(filename: str, limit: int) -> bytes:
    path = Path(filename)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("unsafe_operator_path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("invalid_operator_file")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("oversized_operator_file")
    return raw


@dataclass(frozen=True)
class Snapshot:
    installation: Installation
    digest: str


def load_snapshot(filename):
    raw = read_regular_file(filename, MAX_INSTALLATION_BYTES)
    return Snapshot(Installation.model_validate_json(raw), sha256(raw).hexdigest())


def terms(text):
    return set(re.findall(r"\w{2,80}", text.casefold()))


class LexicalIndex:
    """Inverted index built only from authorized records; no hidden-corpus statistics."""

    def __init__(self, documents):
        self.documents = {doc.source_id: doc for doc in documents}
        self.postings = {}
        for doc in documents:
            for term in terms(doc.title + " " + doc.text):
                self.postings.setdefault(term, set()).add(doc.source_id)

    def search(self, query, scope, now=None):
        now = now or datetime.now(UTC)
        scores = {}
        query_terms = terms(query.query)
        for term in sorted(query_terms):
            for source_id in sorted(self.postings.get(term, ())):
                scores[source_id] = scores.get(source_id, 0) + 1
        items, reasons = [], []
        # A public-domain bound does not authorize local documents without such an origin.
        if query.allowed_domains or query.excluded_domains or "site:" in query.query:
            return (), ()
        for source_id in sorted(scores, key=lambda key: (-scores[key], key)):
            doc = self.documents[source_id]
            if not doc.allows(scope, now):
                continue
            if doc.observed_at < now - timedelta(seconds=query.max_age_seconds):
                reasons.append("freshness_unverified")
                continue
            if query.published_after and (
                doc.published_at is None or doc.published_at < query.published_after
            ):
                reasons.append("freshness_unverified")
                continue
            # Literal substring, no whitespace normalization or markup interpretation.
            match = next(
                (m for m in re.finditer(r"\w+", doc.text) if m[0].casefold() in query_terms), None
            )
            start = max(0, match.start() - 100) if match else 0
            quote = doc.text[start : start + 1000]
            while len(quote.encode()) > 1000:
                quote = quote[:-1]
            items.append(
                item_from_quote(
                    source_id=source_id,
                    revision=doc.revision,
                    quote=quote,
                    start=start,
                    origin="local",
                    title=doc.title,
                    rights_epoch=doc.rights_epoch,
                    provider="local_lexical_v1",
                    quote_basis="literal_document",
                    revision_basis="operator_revision",
                    rights_authority_id="local:" + doc.source_id,
                    rights_reference=doc.rights_reference,
                    license=doc.license,
                    sensitivity=doc.sensitivity,
                    observed_at=doc.observed_at,
                    published_at=doc.published_at,
                    expires_at=min(
                        doc.expires_at, doc.observed_at + timedelta(seconds=query.max_age_seconds)
                    ),
                    freshness_basis="publication" if doc.published_at else "observation_only",
                )
            )
            if len(items) >= query.max_items:
                break
        return tuple(items), tuple(dict.fromkeys(reasons))
