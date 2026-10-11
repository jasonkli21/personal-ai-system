from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    application_scope_context,
    current_application_scope,
)
from personal_ai.context.adapters import ResearchEvidenceContextProviderFactory
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextProviderInputs,
    ContextSelection,
)
from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry
from personal_ai.evidence.contracts import Evidence, SourceObservation


def test_selected_research_uses_shared_repository_and_fails_closed_for_history():
    now = datetime.now(UTC)
    owner_id = "research-owner"
    session_id, evidence_id, observation_id = uuid4(), uuid4(), uuid4()
    passage = "A bounded synthetic research passage."
    content_fingerprint = sha256(" ".join(passage.split()).encode()).hexdigest()
    observation = SourceObservation(
        id=observation_id,
        session_id=session_id,
        query_id=uuid4(),
        owner_id=owner_id,
        canonical_url="https://example.org/synthetic-research",
        title="Synthetic source",
        provider="fake",
        observed_at=now - timedelta(minutes=1),
        content_fingerprint=content_fingerprint,
        status="accepted",
        attempt_id=uuid4(),
    )
    evidence = Evidence(
        id=evidence_id,
        session_id=session_id,
        owner_id=owner_id,
        source_observation_ids=(observation_id,),
        passage=passage,
        content_fingerprint=content_fingerprint,
        observed_at=observation.observed_at,
        expires_at=now + timedelta(hours=1),
        expiry_policy="general",
    )
    research_session = SimpleNamespace(
        id=session_id,
        state="completed",
        expires_at=now + timedelta(minutes=15),
        evidence=(evidence,),
        observations=(observation,),
    )

    class CanonicalResearchRepository:
        calls = 0

        def get(self, requested_owner, requested_id):
            self.calls += 1
            assert requested_owner == owner_id
            assert requested_id == session_id
            assert current_application_scope() == ApplicationScope()
            return research_session

    repository = CanonicalResearchRepository()
    scope = RequestScope(
        owner_id=owner_id,
        request_id="selected-research-conformance",
        application_id="travel",
    )
    reference = ContextEntityReference(
        entity_type="research_session",
        entity_id=str(session_id),
        application_id="travel",
    )
    selection = ContextSelection(
        provider_id="external_research",
        operation="search",
        fields=("passage", "observed_at", "expires_at"),
        entity_refs=(reference,),
        max_results=1,
        max_bytes=8_192,
        max_tokens=128,
        timeout_seconds=1,
    )
    provider = ResearchEvidenceContextProviderFactory(repository).create(
        ContextProviderInputs(scope=scope)
    )

    with application_scope_context(ApplicationScope(application_id="travel")):
        (item,) = provider.fetch(selection, scope, deadline=10**12)

    assert repository.calls == 1
    assert item.application_id == "travel"
    assert item.payload.passage == passage
    assert item.expires_at == research_session.expires_at
    dependency = item.permission_dependencies[0]
    assert dependency.permission_id == "research_source_policy"
    assert dependency.source_application_id == "personal_ai"
    assert dependency.destination_application_id == "travel"
    assert item.source_refs[0].uri == observation.canonical_url
    assert not ContextPermissionRevalidatorRegistry().is_current(dependency)
    assert not hasattr(provider, "client")
