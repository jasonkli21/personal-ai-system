"""Postgres adapters for AI-owned context profile records."""

from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic

from personal_ai.auth.scope import STANDALONE_APPLICATION_ID, ApplicationScope
from personal_ai.context.profile import (
    GlobalProfile,
    GlobalProfileFieldRecord,
    GlobalProfileRepository,
    GlobalProfileUpdate,
)
from personal_ai.persistence.postgres import (
    PersistenceConflict,
    PersistenceRecordNotFound,
    PostgresDatabase,
    PostgresPayloadRepository,
    _ensure_namespace,
    _is_unique_violation,
)

_PROFILE_SCOPE = ApplicationScope(application_id=STANDALONE_APPLICATION_ID)
_PROFILE_RECORD_ID = "owner-global-profile-v1"


class PostgresGlobalProfileRepository(GlobalProfileRepository):
    """Owner-wide profile in Postgres with CAS updates and filtered share reads."""

    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database

    @staticmethod
    def _decode(payload, owner_id: str) -> GlobalProfile:
        try:
            profile = GlobalProfile.model_validate(payload)
        except (ValueError, TypeError) as error:
            raise RuntimeError("global_profile_record_invalid") from error
        if profile.owner_id != owner_id:
            raise PersistenceRecordNotFound("profile not found")
        return profile

    def get(self, owner_id: str) -> GlobalProfile:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM global_profiles WHERE scope_id=%s AND record_id=%s "
                "AND owner_id=%s AND application_id=%s AND workspace_id IS NULL",
                (
                    PostgresPayloadRepository.scope_id(owner_id, _PROFILE_SCOPE),
                    _PROFILE_RECORD_ID,
                    owner_id,
                    STANDALONE_APPLICATION_ID,
                ),
            ).fetchone()
        if row is None:
            return GlobalProfile(owner_id=owner_id, revision=0, fields=(), updated_at=None)
        return self._decode(row[0], owner_id)

    def update(self, owner_id: str, update: GlobalProfileUpdate) -> GlobalProfile:
        if any(item.shared_with_applications for item in update.fields):
            raise ValueError("profile_sharing_requires_consent")
        if not owner_id or len(owner_id) > 200:
            raise ValueError("owner_id_invalid")
        now = datetime.now(UTC)
        for attempt in range(3):
            try:
                with self.database.transaction(deadline=monotonic() + 2) as connection:
                    self._lock_owner(connection, owner_id)
                    scope_id = _ensure_namespace(connection, owner_id, _PROFILE_SCOPE)
                    row = connection.execute(
                        "SELECT payload,revision FROM global_profiles WHERE scope_id=%s "
                        "AND record_id=%s AND owner_id=%s AND application_id=%s "
                        "AND workspace_id IS NULL FOR UPDATE",
                        (scope_id, _PROFILE_RECORD_ID, owner_id, STANDALONE_APPLICATION_ID),
                    ).fetchone()
                    current = (
                        self._decode(row[0], owner_id)
                        if row is not None
                        else GlobalProfile(
                            owner_id=owner_id, revision=0, fields=(), updated_at=None
                        )
                    )
                    fields = {item.field: item for item in current.fields}
                    for name in update.remove_fields:
                        fields.pop(name, None)
                    for item in update.fields:
                        fields[item.field] = GlobalProfileFieldRecord(
                            **item.model_dump(), set_by="user", set_at=now
                        )
                    candidate = GlobalProfile(
                        owner_id=owner_id,
                        revision=current.revision + 1,
                        fields=tuple(fields[key] for key in sorted(fields)),
                        updated_at=now,
                    )
                    serialized = PostgresPayloadRepository._json(candidate.model_dump(mode="json"))
                    if row is None:
                        connection.execute(
                            "INSERT INTO global_profiles(record_id,scope_id,owner_id,application_id,"
                            "workspace_id,record_version,revision,created_at,updated_at,payload) "
                            "VALUES (%s,%s,%s,%s,NULL,1,%s,%s,%s,%s::jsonb)",
                            (
                                _PROFILE_RECORD_ID,
                                scope_id,
                                owner_id,
                                STANDALONE_APPLICATION_ID,
                                candidate.revision,
                                now,
                                now,
                                serialized,
                            ),
                        )
                    else:
                        cursor = connection.execute(
                            "UPDATE global_profiles SET payload=%s::jsonb,revision=%s,updated_at=%s "
                            "WHERE scope_id=%s AND record_id=%s AND owner_id=%s "
                            "AND application_id=%s AND workspace_id IS NULL AND revision=%s",
                            (
                                serialized,
                                candidate.revision,
                                now,
                                scope_id,
                                _PROFILE_RECORD_ID,
                                owner_id,
                                STANDALONE_APPLICATION_ID,
                                int(row[1]),
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise PersistenceConflict("profile revision changed")
                return candidate
            except Exception as error:
                if _is_unique_violation(error):
                    if attempt < 2:
                        continue
                    raise PersistenceConflict("profile update contention") from error
                raise
        raise PersistenceConflict("profile update contention")

    @staticmethod
    def _lock_owner(connection, owner_id):
        from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced

        assert_owner_unfenced(connection, owner_id)
        # Owner -> consent -> profile; shared by profile writes and consent transitions.
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"profile-consent:{owner_id}",),
        )

    def shared_fields(self, owner_id, application_id, fields, *, deadline=None):
        return ()  # Legacy allowlists and old dependencies never authorize sharing.

    def _read_profile(self, connection, owner_id):
        row = connection.execute(
            "SELECT payload FROM global_profiles WHERE scope_id=%s AND record_id=%s AND owner_id=%s",
            (PostgresPayloadRepository.scope_id(owner_id, _PROFILE_SCOPE), _PROFILE_RECORD_ID, owner_id),
        ).fetchone()
        return self._decode(row[0], owner_id) if row else GlobalProfile(owner_id=owner_id, revision=0)

    @staticmethod
    def _read_consents(connection, owner_id):
        from personal_ai.context.profile_consent import ProfileConsents

        row = connection.execute(
            "SELECT payload FROM profile_consents WHERE scope_id=%s AND record_id=%s AND owner_id=%s",
            (PostgresPayloadRepository.scope_id(owner_id, _PROFILE_SCOPE),
             "owner-profile-consents-v1", owner_id),
        ).fetchone()
        result = ProfileConsents.model_validate(row[0]) if row else ProfileConsents(owner_id=owner_id)
        if result.owner_id != owner_id:
            raise PersistenceRecordNotFound("profile not found")
        return result

    def get_consents(self, owner_id):
        with self.database.connection(deadline=monotonic() + 2) as connection:
            self._lock_owner(connection, owner_id)
            return self._read_consents(connection, owner_id)

    def mutate_consent(self, owner_id, actor, intent):
        from personal_ai.context.profile_consent import transition_consents

        # One bounded transaction; never automatically retry an uncertain commit.
        with self.database.transaction(deadline=monotonic() + 2) as connection:
            self._lock_owner(connection, owner_id)
            scope_id = _ensure_namespace(connection, owner_id, _PROFILE_SCOPE)
            current = self._read_consents(connection, owner_id)
            candidate, receipt = transition_consents(
                current, self._read_profile(connection, owner_id), actor, intent, datetime.now(UTC)
            )
            if candidate is not current:
                now = datetime.now(UTC)
                connection.execute(
                    "INSERT INTO profile_consents(scope_id,record_id,owner_id,application_id,"
                    "revision,created_at,updated_at,payload) VALUES (%s,%s,%s,'personal_ai',%s,%s,%s,%s::jsonb) "
                    "ON CONFLICT (scope_id,record_id) DO UPDATE SET revision=EXCLUDED.revision,"
                    "updated_at=EXCLUDED.updated_at,payload=EXCLUDED.payload",
                    (scope_id, "owner-profile-consents-v1", owner_id, candidate.revision, now, now,
                     PostgresPayloadRepository._json(candidate.model_dump(mode="json"))),
                )
        return receipt

    def authorized_fields(self, scope, fields, *, deadline=None):
        from personal_ai.context.profile_consent import authorized_fields

        with self.database.connection(deadline=deadline or monotonic() + 2) as connection:
            self._lock_owner(connection, scope.owner_id)
            return authorized_fields(
                self._read_profile(connection, scope.owner_id),
                self._read_consents(connection, scope.owner_id), scope, fields, datetime.now(UTC),
            )

    def purge_owner(self, owner_id):
        """Irreversible operator erasure requires a retained owner deletion fence."""
        from personal_ai.persistence.postgres.owner_lifecycle import lock_owner

        with self.database.transaction(deadline=monotonic() + 2) as connection:
            lock_owner(connection, owner_id)
            if not connection.execute(
                "SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s", (owner_id,)
            ).fetchone():
                raise ValueError("owner_fence_required")
            for table in ("profile_consents", "global_profiles"):
                connection.execute(f"DELETE FROM {table} WHERE owner_id=%s", (owner_id,))
