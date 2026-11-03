"""Explicit local excerpts through shared context packing and retained authority.

This is a conservative single-host authority, not a distributed source lease.
External source attachment remains unavailable. No source bodies are cached here.
"""

from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from personal_ai.auth.application_clients import require_current_client_authority
from personal_ai.auth.scope import ApplicationScope
from personal_ai.context.authorization import authorize_context_selection
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextItem,
    ContextOperationSpec,
    ContextPermissionDependency,
    ContextProviderError,
    ContextProviderSpec,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.retrieval.contracts import RetrievalItem, RetrievalQuery
from personal_ai.retrieval.installation import (
    LexicalIndex,
    legacy_issuer_id,
    load_snapshot,
    local_rights_authority_id,
)
from personal_ai.usage.trace import Event, Reason, State, emit

PROVIDER_ID = "retrieval_context"
NAMESPACE = "retrieval_context:"
PURPOSE = "assist_response_with_local_excerpt"


def context_selection():
    return ContextSelection(
        provider_id=PROVIDER_ID,
        operation="search",
        fields=("excerpt",),
        max_results=8,
        max_bytes=32768,
        max_tokens=8192,
        timeout_seconds=2,
        required=True,
    )


class ExcerptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    excerpt: RetrievalItem


class RetrievalContextAuthority:
    def __init__(
        self, settings, *, scope=None, authority=None, context=None, current_settings=None
    ):
        self.settings = settings
        self.scope, self.authority, self.context = scope, authority, context
        self.current_settings = current_settings or (lambda: settings)

    @staticmethod
    def supports(dependency):
        return dependency.permission_id.startswith(NAMESPACE)

    def snapshot(self, scope):
        try:
            require_current_client_authority()
            if self.authority is None:
                raise ValueError("retrieval_authority_unavailable")
            self.authority()
            current = self.current_settings()
            if (
                not current.retrieval_enabled
                or not current.retrieval_context_enabled
                or current.retrieval_installation_file != self.settings.retrieval_installation_file
                or current.app_environment not in {"local", "test"}
            ):
                raise ValueError("retrieval_context_unavailable")
            if self.scope is None or any(
                getattr(scope, name) != getattr(self.scope, name)
                for name in ("owner_id", "acting_user_id", "application_id", "workspace_id")
            ):
                raise ValueError("retrieval_context_scope_denied")
            context = self.context() if callable(self.context) else self.context
            if context is None:
                raise ValueError("retrieval_context_policy_unavailable")
            if context.scope != scope:
                raise ValueError("retrieval_context_scope_denied")
            authorize_context_selection(context, context_selection())
            capability = next(
                (c for c in context.context_provider_capabilities if c.capability_id == PROVIDER_ID),
                None,
            )
            if capability is None or not capability.is_enabled():
                raise ValueError("retrieval_context_capability_denied")
            snapshot = load_snapshot(current.retrieval_installation_file)
            if not snapshot.installation.allows(scope) or not any(
                grant.allows(scope) for grant in snapshot.installation.model_context_access
            ):
                raise ValueError("retrieval_context_scope_denied")
            return snapshot
        except Exception:
            emit(Event.SOURCE, State.DENIED, reason=Reason.SOURCE_AUTHORITY)
            raise

    def is_current(self, dependency):
        if not self.supports(dependency):
            return False
        try:
            scope = self.scope
            if scope is None or (
                dependency.owner_id != scope.owner_id
                or dependency.acting_user_id != scope.acting_user_id
                or dependency.source_scope
                != ApplicationScope(
                    application_id=scope.application_id, workspace_id=scope.workspace_id
                )
                or dependency.purpose != PURPOSE
                or dependency.entity_ref is None
                or dependency.entity_ref.entity_type != "retrieval_source"
            ):
                return False
            snapshot = self.snapshot(scope)
            if snapshot.digest != dependency.version:
                return False
            issuer = snapshot.installation.issuer_id or legacy_issuer_id(
                self.settings.retrieval_installation_file
            )
            return any(
                doc.model_context_allowed
                and doc.allows(scope, datetime.now(UTC))
                and doc.revision == dependency.source_revision
                and local_rights_authority_id(issuer, scope, doc.source_id)
                == dependency.entity_ref.entity_id
                and dependency.permission_id == NAMESPACE + dependency.entity_ref.entity_id[6:]
                for doc in snapshot.installation.documents
            )
        except Exception:  # noqa: BLE001 - unavailable authority always denies
            emit(Event.SOURCE, State.DENIED, reason=Reason.SOURCE_AUTHORITY)
            return False


class RetrievalContextProvider:
    spec = ContextProviderSpec(
        provider_id=PROVIDER_ID,
        source_class="external_research",
        source_version="local-retrieval-context-v1",
        operations=(
            ContextOperationSpec(
                operation="search",
                allowed_fields=("excerpt",),
                maximum_results=8,
                maximum_bytes=32768,
                maximum_timeout_seconds=2,
            ),
        ),
        maximum_items_per_call=8,
    )

    def __init__(self, inputs, authority):
        self.inputs, self.authority = inputs, authority

    def validate_selection(self, selection, inputs):
        if inputs.scope != self.inputs.scope or inputs.pending_message is None:
            raise ContextProviderError("retrieval_context_unavailable")

    def fetch(self, selection, scope, *, deadline):
        if monotonic() >= deadline:
            raise ContextProviderError("retrieval_context_unavailable")
        snapshot = self.authority.snapshot(scope)
        issuer = snapshot.installation.issuer_id or legacy_issuer_id(
            self.authority.settings.retrieval_installation_file
        )
        docs = tuple(
            doc
            for doc in snapshot.installation.documents
            if doc.model_context_allowed and doc.allows(scope, datetime.now(UTC))
        )
        question = self.inputs.pending_message.content
        query = RetrievalQuery(
            query=" ".join(question.split())[:400],
            idempotency_key=uuid4(),
            sources=("local",),
            max_items=min(8, selection.max_results),
        )
        items, _ = LexicalIndex(docs, issuer_id=str(issuer)).search(query, scope)
        output = []
        for item in items:
            dependency = ContextPermissionDependency(
                permission_id=NAMESPACE + item.rights_authority_id[6:],
                version=snapshot.digest,
                purpose=PURPOSE,
                owner_id=scope.owner_id,
                acting_user_id=scope.acting_user_id,
                source_scope=ApplicationScope(
                    application_id=scope.application_id, workspace_id=scope.workspace_id
                ),
                entity_ref=ContextEntityReference(
                    entity_type="retrieval_source",
                    entity_id=item.rights_authority_id,
                    application_id=scope.application_id,
                    workspace_id=scope.workspace_id,
                ),
                source_revision=item.source_revision,
            )
            if not self.authority.is_current(dependency) or monotonic() >= deadline:
                raise ContextProviderError("retrieval_context_unavailable")
            output.append(
                ContextItem(
                    provider_id=PROVIDER_ID,
                    source_class="external_research",
                    source_id=item.rights_authority_id,
                    source_version=item.source_revision,
                    item_id=item.citation_id,
                    owner_id=scope.owner_id,
                    application_id=scope.application_id,
                    workspace_id=scope.workspace_id,
                    authority="external",
                    sensitivity=item.sensitivity,
                    observed_at=item.observed_at,
                    expires_at=item.expires_at,
                    source_refs=(
                        ContextSourceReference(
                            kind="source",
                            reference_id=item.citation_id,
                            fingerprint=item.content_fingerprint,
                        ),
                    ),
                    permission_dependencies=(dependency,),
                    payload=ExcerptPayload(excerpt=item),
                )
            )
        emit(
            Event.SOURCE, State.OK, source_count=len(output),
            source_refs=tuple(item.item_id for item in output[:32]),
        )
        return output


class RetrievalContextProviderFactory:
    spec = RetrievalContextProvider.spec

    def __init__(self, authority):
        self.authority = authority

    def create(self, inputs):
        return RetrievalContextProvider(inputs, self.authority)
