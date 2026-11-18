"""Trusted host seams for verified identity and authorized source projections."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from personal_ai.auth.scope import ApplicationScope

Operation = Literal["search", "fetch"]
RECIPIENT = "chatgpt-mcp"
PURPOSE = "answer-context"
READ_SCOPE = "context:read"


@dataclass(frozen=True, slots=True)
class Identity:
    issuer: str
    subject: str
    client_id: str


@dataclass(frozen=True, slots=True)
class VerifiedAccess:
    """Claims from signature verification or introspection and current revocation state."""

    identity: Identity
    resource: str
    token_kind: str
    scopes: frozenset[str]
    expires_at: datetime
    not_before: datetime | None
    active: bool
    human: bool


VerifyAccess = Callable[[str], Awaitable[VerifiedAccess | None]]


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """One current connection, installation and recipient grant selected by the host."""

    tenant: str
    scope: ApplicationScope
    owner_id: str
    acting_user_id: str | None
    connection_id: str
    connection_generation: int
    source_id: str
    installation_revision: str
    installation_epoch: int
    grant_id: str
    grant_version: int
    grant_epoch: int
    policy_version: str
    recipient: str
    purpose: str
    fields: tuple[str, ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class Selection:
    record_ref: str
    revision: str
    watermark: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SearchHit:
    record_ref: str
    revision: str
    title: str
    fresh_until: datetime


@dataclass(frozen=True, slots=True)
class SearchPage:
    watermark: str
    hits: tuple[SearchHit, ...]


@dataclass(frozen=True, slots=True)
class FetchedRecord:
    """Disclosure projection after source and PAS field/permission validation."""

    record_ref: str
    revision: str
    watermark: str
    source: str
    title: str
    text: str
    observed_at: datetime
    fresh_until: datetime


@dataclass(frozen=True, slots=True)
class AuthorizedRead:
    value: SearchPage | FetchedRecord
    # Recheck owning-source rights, projection, revision and freshness without a second read.
    revalidate: Callable[[], None]


class ReadBudget(Protocol):
    def check(self) -> None: ...
    def charge_bytes(self, raw: bytes) -> None: ...
    def charge_tokens(self, raw: bytes) -> None: ...


class AuthorizedSourceReader(Protocol):
    """The composition owns PAS account mapping, application scope and source authority.

    Resolve raises or returns None for absent, revoked or ambiguous bindings and
    never searches records. Read issues at most one delegated source request,
    charges it and its results to budget, and never retries. Revalidation uses
    the same deadline and examines current dependencies without awaiting.
    Async calls must stop producing results on cancellation. If an implementation
    detaches synchronous work that cannot be physically cancelled, it must bound
    outstanding work and prevent late publication. Credentials stay in the verifier.
    """

    async def resolve(self, identity: Identity, operation: Operation) -> SourceBinding | None: ...
    def budget(self, deadline: float) -> ReadBudget: ...
    async def read(
        self,
        identity: Identity,
        binding: SourceBinding,
        selection: str | Selection,
        budget: ReadBudget,
    ) -> AuthorizedRead: ...
