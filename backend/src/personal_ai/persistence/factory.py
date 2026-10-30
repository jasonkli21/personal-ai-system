"""Repository construction seam used by HTTP, worker, and control services.

Repositories use Postgres for query-rich knowledge and DynamoDB for operational
timeline state. Local/test environments require explicit local endpoints;
deployed environments require the configured Neon and federated AWS adapters.
"""

from __future__ import annotations

from hashlib import sha256
from threading import RLock
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from personal_ai.agents.research.iterative.repositories import IterativeResearchRepository
    from personal_ai.agents.research.repositories import ResearchRepository
    from personal_ai.auth.account_data import AccountDataRepository
    from personal_ai.auth.directory import PrincipalDirectory
    from personal_ai.auth.safeguards import SafeguardStore
    from personal_ai.booking_extractions.repositories import BookingExtractionRepository
    from personal_ai.context.contracts import ConversationSummaryRepository
    from personal_ai.context.profile import GlobalProfileRepository
    from personal_ai.context.traces import ContextTraceRepository
    from personal_ai.decisions.repositories import DecisionRepository
    from personal_ai.domains.repositories import DomainRepository
    from personal_ai.itinerary_proposals.repositories import ItineraryProposalRepository
    from personal_ai.memory.contracts import MemoryRepository
    from personal_ai.memory.lifecycle.contracts import MemoryLifecycleRepository
    from personal_ai.storage.repositories import ConversationRepository, MessageRepository


class PersistenceFactory(Protocol):
    def conversation_repository(self) -> ConversationRepository: ...
    def message_repository(self) -> MessageRepository: ...
    def summary_repository(self) -> ConversationSummaryRepository: ...
    def context_trace_repository(self) -> ContextTraceRepository: ...
    def federation_grant_repository(self): ...
    def mutation_repository(self): ...
    def global_profile_repository(self) -> GlobalProfileRepository: ...
    def memory_repository(self) -> MemoryRepository: ...
    def memory_lifecycle_repository(
        self, memories: MemoryRepository, messages: MessageRepository
    ) -> MemoryLifecycleRepository: ...
    def memory_control_repository(self): ...
    def research_repository(self) -> ResearchRepository: ...
    def iterative_research_repository(self) -> IterativeResearchRepository: ...
    def decision_repository(self) -> DecisionRepository: ...
    def domain_repository(self) -> DomainRepository: ...
    def itinerary_proposal_repository(self) -> ItineraryProposalRepository: ...
    def booking_extraction_repository(self) -> BookingExtractionRepository: ...
    def principal_directory(self) -> PrincipalDirectory: ...
    def account_data_repository(self) -> AccountDataRepository: ...
    def safeguard_store(self) -> SafeguardStore: ...
    def provider_rate_limiter(self, provider: str, repository=None): ...
    def provider_usage_accounting(self, settings): ...
    def endpoint_profile_resolver(self, settings): ...
    def routing_decision_repository(self): ...
    def routing_service(
        self, settings, *, authorization, evaluation_quality_authority=None,
        adaptive_strategy_registry=None,
    ): ...
    def provider_matrix_evaluation_repository(self): ...
    def research_experiment_repository(self): ...
    def artifact_service(self, settings): ...
    def artifact_maintenance_service(self, settings): ...


class PostgresDynamoPersistenceFactory:
    """Compose existing repository contracts over the two canonical stores."""

    def __init__(self, database, runtime_table) -> None:
        self.database = database
        self.runtime_table = runtime_table
        self._artifact_services = {}
        self._endpoint_profile_resolver = None

    def conversation_repository(self):
        from personal_ai.persistence.dynamodb.conversations import DynamoDBConversationRepository

        return DynamoDBConversationRepository(self.runtime_table)

    def message_repository(self):
        from personal_ai.persistence.dynamodb.messages import DynamoDBMessageRepository

        return DynamoDBMessageRepository(self.runtime_table, self.conversation_repository())

    def summary_repository(self):
        from personal_ai.persistence.dynamodb.summaries import DynamoDBSummaryRepository

        return DynamoDBSummaryRepository(self.runtime_table, self.conversation_repository())

    def context_trace_repository(self):
        from personal_ai.persistence.dynamodb.context_traces import DynamoDBContextTraceRepository

        return DynamoDBContextTraceRepository(self.runtime_table)

    def artifact_service(self, settings):
        if not settings.artifacts_enabled:
            return None
        return self._artifact_service(settings, writes_enabled=True)

    def artifact_maintenance_service(self, settings):
        """Keep expiry, revocation and deletion cleanup running with writes disabled."""
        return self._artifact_service(settings, writes_enabled=False)

    def _artifact_service(self, settings, *, writes_enabled):
        from personal_ai.artifacts.local import InMemoryArtifactStore
        from personal_ai.artifacts.service import ArtifactService
        from personal_ai.persistence.postgres.artifacts import PostgresArtifactMetadataRepository

        key = (
            settings.artifact_store,
            settings.artifact_gcs_bucket,
            settings.artifact_gcs_region,
            settings.artifact_gcs_preflight_reference,
            settings.artifact_max_operations_per_day,
            settings.artifact_max_write_bytes_per_day,
            settings.artifact_max_live_bytes,
            settings.artifact_max_objects,
            writes_enabled,
        )
        store_id = (
            f"gcs:{settings.artifact_gcs_bucket}"
            if settings.artifact_store == "gcs"
            else "memory:local"
        )
        with _FACTORY_LOCK:
            metadata = PostgresArtifactMetadataRepository(
                self.database,
                max_operations=settings.artifact_max_operations_per_day,
                max_daily_bytes=settings.artifact_max_write_bytes_per_day,
                max_live_bytes=settings.artifact_max_live_bytes,
                max_objects=settings.artifact_max_objects,
            )
            metadata.assert_store_compatible(store_id)
            if key in self._artifact_services:
                return self._artifact_services[key]
            if settings.artifact_store == "gcs":
                from personal_ai.artifacts.gcs import PrivateGCSArtifactStore

                metadata.reserve(operations=1, byte_count=0)
                store = PrivateGCSArtifactStore(
                    settings.artifact_gcs_bucket,
                    region=settings.artifact_gcs_region,
                    preflight_verified=settings.artifact_gcs_preflight_verified,
                )
                try:
                    store.verify_private_bucket()
                except Exception:
                    store.close()
                    raise
            else:
                store = InMemoryArtifactStore()
            from personal_ai.context.deployment import configured_context_runtime
            from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry
            from personal_ai.search.authority import ResearchSourceRightsRevalidator
            runtime = configured_context_runtime(settings)
            service = ArtifactService(
                metadata, store, writes_enabled=writes_enabled,
                permission_revalidator=ContextPermissionRevalidatorRegistry((
                    ResearchSourceRightsRevalidator(settings), *runtime.permission_revalidators,
                )),
            )
            self._artifact_services[key] = service
            return service

    def federation_grant_repository(self):
        from personal_ai.persistence.postgres.federation import PostgresFederationGrantRepository

        return PostgresFederationGrantRepository(self.database)

    def mutation_repository(self):
        from personal_ai.persistence.postgres.mutations import PostgresMutationRepository

        return PostgresMutationRepository(self.database)

    def global_profile_repository(self):
        from personal_ai.persistence.postgres.context import PostgresGlobalProfileRepository

        return PostgresGlobalProfileRepository(self.database)

    def memory_repository(self):
        from personal_ai.persistence.dynamodb.memory_effects import DynamoDBMemoryEffectGuard
        from personal_ai.persistence.postgres.memory import PostgresMemoryRepository

        return PostgresMemoryRepository(
            self.database,
            DynamoDBMemoryEffectGuard(self.runtime_table, self.message_repository()),
        )

    def memory_lifecycle_repository(self, memories, messages):
        from personal_ai.persistence.dynamodb.memory_jobs import DynamoDBMemoryJobRepository
        from personal_ai.persistence.postgres.lifecycle import PostgresMemoryLifecycleRepository

        return PostgresMemoryLifecycleRepository(
            memories, messages, DynamoDBMemoryJobRepository(self.runtime_table)
        )

    def memory_control_repository(self):
        from personal_ai.persistence.postgres.control import PostgresControlRepository

        memories = self.memory_repository()
        lifecycle = self.memory_lifecycle_repository(memories, self.message_repository())
        return PostgresControlRepository(memories, lifecycle)

    def research_repository(self):
        from personal_ai.persistence.postgres.research import PostgresResearchRepository

        return PostgresResearchRepository(self.database)

    def iterative_research_repository(self):
        from personal_ai.persistence.postgres.research import (
            PostgresIterativeResearchRepository,
            PostgresResearchRepository,
        )

        return PostgresIterativeResearchRepository(
            self.database, PostgresResearchRepository(self.database)
        )

    def decision_repository(self):
        from personal_ai.persistence.postgres.decisions import PostgresDecisionRepository

        return PostgresDecisionRepository(self.database)

    def domain_repository(self):
        from personal_ai.persistence.postgres.domains import PostgresDomainRepository

        return PostgresDomainRepository(self.database)

    def itinerary_proposal_repository(self):
        from personal_ai.persistence.postgres.capabilities import (
            PostgresItineraryProposalRepository,
        )

        return PostgresItineraryProposalRepository(self.database)

    def booking_extraction_repository(self):
        from personal_ai.persistence.postgres.capabilities import (
            PostgresBookingExtractionRepository,
        )

        return PostgresBookingExtractionRepository(self.database)

    def principal_directory(self):
        from personal_ai.persistence.postgres.auth import PostgresPrincipalDirectory

        return PostgresPrincipalDirectory(self.database)

    def account_data_repository(self):
        from personal_ai.persistence.postgres.auth import PostgresAccountLifecycleRepository

        return PostgresAccountLifecycleRepository(self.database, self.runtime_table)

    def safeguard_store(self):
        from personal_ai.persistence.controls import (
            DynamoDBSafeguardStore,
            PostgresDailyBudgetRepository,
        )

        return DynamoDBSafeguardStore(
            self.runtime_table, PostgresDailyBudgetRepository(self.database)
        )

    def provider_rate_limiter(self, provider: str, repository=None):
        del repository
        from personal_ai.persistence.controls import PostgresDomainProviderRateLimiter

        return PostgresDomainProviderRateLimiter(self.database, provider)

    def routing_decision_repository(self):
        from personal_ai.persistence.postgres.routing_observations import (
            PostgresRoutingDecisionRepository,
        )

        return PostgresRoutingDecisionRepository(self.database)

    def provider_matrix_evaluation_repository(self):
        from personal_ai.persistence.postgres.provider_matrix import (
            PostgresProviderMatrixRepository,
        )

        return PostgresProviderMatrixRepository(self.database)

    def routing_service(
        self, settings, *, authorization, evaluation_quality_authority=None,
        adaptive_strategy_registry=None,
    ):
        """Canonical internal P21 runtime; no permissive default authorization."""
        from personal_ai.routing.adaptive import configured_routing_strategy
        from personal_ai.routing.service import RoutingDecisionService

        return RoutingDecisionService(
            self.endpoint_profile_resolver(settings).endpoint_registry,
            self.routing_decision_repository(),
            strategy=configured_routing_strategy(
                settings, registry=adaptive_strategy_registry
            ),
            usage=self.provider_usage_accounting(settings),
            authorization=authorization,
            evaluation_quality_authority=evaluation_quality_authority,
        )

    def research_experiment_repository(self):
        from personal_ai.persistence.postgres.research_experiments import (
            PostgresResearchExperimentRepository,
        )

        return PostgresResearchExperimentRepository(self.database)

    def provider_usage_accounting(self, settings):
        from personal_ai.persistence.dynamodb.usage import DynamoDBProviderUsageEventRepository
        from personal_ai.persistence.postgres.usage.accounting import (
            PostgresProviderUsageAccounting,
        )

        events = DynamoDBProviderUsageEventRepository(
            self.runtime_table, retention_days=settings.provider_usage_retention_days
        )
        return PostgresProviderUsageAccounting(
            self.database,
            retention_days=settings.provider_usage_retention_days,
            request_attempt_limit=settings.provider_usage_max_attempts_per_request,
            request_token_limit=settings.provider_usage_max_tokens_per_request,
            default_cooldown_seconds=settings.provider_usage_default_cooldown_seconds,
            header_freshness_seconds=settings.provider_usage_header_freshness_seconds,
            stale_attempt_seconds=settings.provider_usage_stale_attempt_seconds,
            endpoint_profile_resolver=self.endpoint_profile_resolver(settings),
            operational_event_writer=events.publish,
            operational_event_purger=lambda now, limit: events.purge_expired(now=now, limit=limit),
        )

    def endpoint_profile_resolver(self, settings):
        """Routing/profile registry dependency shared with accounting at composition."""
        if self._endpoint_profile_resolver is None:
            from personal_ai.persistence.postgres.routing import PostgresEndpointRegistryRepository
            from personal_ai.usage.profiles import EndpointProfileResolver

            self._endpoint_profile_resolver = EndpointProfileResolver.from_settings(
                settings, PostgresEndpointRegistryRepository(self.database)
            )
        return self._endpoint_profile_resolver

    def close(self) -> None:
        for service in self._artifact_services.values():
            close = getattr(service.store, "close", None)
            if close is not None:
                close()
        self._artifact_services.clear()
        self.database.close()
        close = getattr(self.runtime_table, "close", None)
        if close is not None:
            close()


_FACTORY_LOCK = RLock()
_FACTORIES: dict[tuple[str, ...], PostgresDynamoPersistenceFactory] = {}


def _factory_key(settings) -> tuple[str, ...]:
    cloud = settings.app_environment in {"staging", "production"}
    postgres_dsn = (
        settings.p10_neon_runtime_dsn.get_secret_value()
        if cloud
        else settings.persistence_local_postgres_dsn.get_secret_value()
    )
    postgres_key = sha256(postgres_dsn.encode()).hexdigest()
    endpoint = "cloud" if cloud else settings.persistence_local_dynamodb_endpoint
    return (
        settings.app_environment,
        str(cloud),
        postgres_key,
        endpoint,
        settings.p10_dynamodb_region,
        settings.p10_dynamodb_table_name,
        settings.p10_dynamodb_role_arn,
        settings.p10_dynamodb_identity_token_audience,
        str(settings.p10_neon_pool_max_size),
    )


def persistence_factory(settings) -> PersistenceFactory:
    """Return the configured runtime factory without cloud/local fallback."""
    cloud = settings.app_environment in {"staging", "production"}
    if cloud and not settings.p10_cloud_adapters_configured:
        raise RuntimeError("deployed_polyglot_persistence_required")
    if not cloud and settings.p10_cloud_adapters_configured:
        raise RuntimeError("cloud_persistence_requires_deployed_environment")

    key = _factory_key(settings)
    with _FACTORY_LOCK:
        factory = _FACTORIES.get(key)
        if factory is not None:
            return factory
        if cloud:
            from personal_ai.persistence.dynamodb.cloud import (
                FederatedDynamoDBConfig,
                FederatedDynamoDBRuntimeTable,
            )
            from personal_ai.persistence.postgres.neon import NeonRuntimeDatabase

            database = NeonRuntimeDatabase(
                settings.p10_neon_runtime_dsn.get_secret_value(),
                environment=settings.app_environment,
                max_size=settings.p10_neon_pool_max_size,
            )
            table = FederatedDynamoDBRuntimeTable(
                FederatedDynamoDBConfig(
                    region=settings.p10_dynamodb_region,
                    table_name=settings.p10_dynamodb_table_name,
                    role_arn=settings.p10_dynamodb_role_arn,
                    identity_token_audience=settings.p10_dynamodb_identity_token_audience,
                )
            )
        else:
            from personal_ai.persistence.dynamodb.client import DynamoDBRuntimeTable
            from personal_ai.persistence.postgres.database import PostgresDatabase

            database = PostgresDatabase(
                settings.persistence_local_postgres_dsn.get_secret_value(),
                environment=settings.app_environment,
            )
            table = DynamoDBRuntimeTable(
                settings.persistence_local_dynamodb_endpoint,
                table_name=settings.p10_dynamodb_table_name,
                region=settings.p10_dynamodb_region,
            )
        factory = PostgresDynamoPersistenceFactory(database, table)
        _FACTORIES[key] = factory
        return factory


def close_persistence_clients() -> None:
    """Close shared database clients during process shutdown."""
    with _FACTORY_LOCK:
        factories = tuple(_FACTORIES.values())
        _FACTORIES.clear()
    for factory in factories:
        factory.close()
