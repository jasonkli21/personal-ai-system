"""Internal PostgreSQL settings store. Owner access is verified by the caller."""

from psycopg.types.json import Jsonb

from personal_ai.routing.owner_policy import PolicyDenied

from .owner_lifecycle import assert_owner_unfenced


class PostgresInferencePolicy:
    def __init__(self, database):
        self.database = database

    def read_in_transaction(self, connection, owner_id):
        row = connection.execute(
            "SELECT revision,payload::text FROM inference_owner_policies WHERE owner_id=%s",
            (owner_id,),
        ).fetchone()
        return (row[0], row[1].encode()) if row else (0, None)

    def read(self, owner_id):
        with self.database.transaction() as connection:
            assert_owner_unfenced(connection, owner_id)
            return self.read_in_transaction(connection, owner_id)

    def replace(self, owner_id, expected_revision, policy):
        payload = Jsonb(policy.model_dump(mode="json"))
        with self.database.transaction() as connection:
            assert_owner_unfenced(connection, owner_id)
            if expected_revision == 0:
                row = connection.execute(
                    "INSERT INTO inference_owner_policies VALUES (%s,1,%s) "
                    "ON CONFLICT (owner_id) DO NOTHING RETURNING revision",
                    (owner_id, payload),
                ).fetchone()
            else:
                row = connection.execute(
                    "UPDATE inference_owner_policies SET revision=revision+1,payload=%s "
                    "WHERE owner_id=%s AND revision=%s RETURNING revision",
                    (payload, owner_id, expected_revision),
                ).fetchone()
            if row is None:
                raise PolicyDenied("inference_policy_revision_changed")
            return row[0]

    def remaining(self, owner_id, cap):
        if cap is None:
            return None
        with self.database.transaction() as connection:
            assert_owner_unfenced(connection, owner_id)
            used, blocked = connection.execute(
                "SELECT COALESCE(SUM(CASE WHEN state IN ('reserved','claimed') "
                "THEN maximum_micros WHEN state='settled' AND owner_month="
                "date_trunc('month',clock_timestamp() AT TIME ZONE 'UTC')::date "
                "THEN actual_micros ELSE 0 END),0), COALESCE(bool_or(state='claimed'),false) "
                "FROM provider_monetary_holds WHERE owner_id=%s",
                (owner_id,),
            ).fetchone()
            return 0 if blocked else max(0, cap - int(used))

    def open_root(self, connection, *, root_id, owner_id, payload, plan, deadline):
        connection.execute(
            "INSERT INTO inference_route_roots(root_id,owner_id,payload_sha256,plan_sha256,deadline) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (root_id) DO NOTHING",
            (root_id, owner_id, payload, plan, deadline),
        )
        row = self.root(connection, root_id, owner_id)
        if row is None or row[:2] != (payload, plan):
            raise PolicyDenied("inference_request_conflict")
        return row

    def root(self, connection, root_id, owner_id):
        return connection.execute(
            "SELECT payload_sha256,plan_sha256,deadline,candidate,state,attempt_id "
            "FROM inference_route_roots WHERE root_id=%s AND owner_id=%s FOR UPDATE",
            (root_id, owner_id),
        ).fetchone()

    def change_root(self, connection, *, root_id, owner_id, candidate, state, attempt_id):
        connection.execute(
            "UPDATE inference_route_roots SET candidate=%s,state=%s,attempt_id=%s "
            "WHERE root_id=%s AND owner_id=%s",
            (candidate, state, attempt_id, root_id, owner_id),
        )
