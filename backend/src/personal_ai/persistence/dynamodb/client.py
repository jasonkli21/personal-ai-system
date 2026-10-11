"""Local DynamoDB client and runtime table boundary."""

from __future__ import annotations

from time import monotonic
from typing import Any

from personal_ai.storage.errors import StorageUnavailableError

from ._helpers import (
    MAX_DYNAMO_TRANSACTION_BYTES,
    MAX_DYNAMO_TRANSACTION_ITEMS,
    RUNTIME_TABLE_NAME,
    _marshal,
    _operation_size,
    _unmarshal,
)


class DynamoDBLocalClient:
    """Explicit-endpoint Dynamo client that cannot fall back to AWS credentials."""

    def __init__(self, endpoint_url: str, *, region: str = "us-east-1", client=None) -> None:
        from urllib.parse import urlsplit

        parsed = urlsplit(endpoint_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname
            not in {"localhost", "127.0.0.1", "::1", "dynamodb-local", "dynamodb-local-test"}
            or not parsed.port
        ):
            raise ValueError("dynamodb_local_endpoint_invalid")
        if client is not None:
            self.client = client
            self.endpoint_url = endpoint_url
            return
        try:
            import boto3
            from botocore.config import Config
        except ImportError as error:  # pragma: no cover - packaging failure
            raise RuntimeError("boto3_required") from error
        self.endpoint_url = endpoint_url
        self.client = boto3.client(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id="fakeMyKeyId",
            aws_secret_access_key="fakeSecretAccessKey",
            config=Config(
                connect_timeout=2,
                read_timeout=5,
                retries={"mode": "standard", "max_attempts": 2},
                tcp_keepalive=True,
            ),
        )

    def ensure_runtime_table(self, table_name: str = RUNTIME_TABLE_NAME) -> None:
        from botocore.exceptions import ClientError

        try:
            self.client.describe_table(TableName=table_name)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
                raise StorageUnavailableError("dynamodb_local_unavailable") from error
            self.client.create_table(
                TableName=table_name,
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                    {"AttributeName": "PUBPK", "AttributeType": "S"},
                    {"AttributeName": "PUBSK", "AttributeType": "S"},
                ],
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "job-publication-v1",
                        "KeySchema": [
                            {"AttributeName": "PUBPK", "KeyType": "HASH"},
                            {"AttributeName": "PUBSK", "KeyType": "RANGE"},
                        ],
                        "Projection": {
                            "ProjectionType": "INCLUDE",
                            "NonKeyAttributes": [
                                "record_pk",
                                "record_sk",
                                "revision",
                                "created_at",
                                "publish_after",
                                "job_id",
                            ],
                        },
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )
        waiter = self.client.get_waiter("table_exists")
        waiter.wait(TableName=table_name, WaiterConfig={"Delay": 1, "MaxAttempts": 30})


class DynamoDBRuntimeTable:
    """Small SDK boundary shared by the runtime repositories."""

    def __init__(
        self,
        endpoint_url: str,
        *,
        table_name: str = RUNTIME_TABLE_NAME,
        region: str = "us-east-1",
        client=None,
    ) -> None:
        self.local = DynamoDBLocalClient(endpoint_url, region=region, client=client)
        self.client = self.local.client
        self.table_name = table_name

    def bootstrap(self) -> None:
        self.local.ensure_runtime_table(self.table_name)

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            close()

    def get(self, key: dict[str, str], *, consistent: bool = True) -> dict[str, Any] | None:
        response = self.client.get_item(
            TableName=self.table_name,
            Key=_marshal(key),
            ConsistentRead=consistent,
        )
        item = response.get("Item")
        return None if item is None else _unmarshal(item)

    def query(
        self,
        *,
        partition: str,
        sort_prefix: str,
        consistent: bool = True,
        descending: bool = False,
        deadline: float,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        cursor = None
        while True:
            if monotonic() >= deadline:
                raise TimeoutError("dynamodb query deadline")
            request: dict[str, Any] = {
                "TableName": self.table_name,
                "KeyConditionExpression": "#pk = :pk AND begins_with(#sk, :prefix)",
                "ExpressionAttributeNames": {"#pk": "PK", "#sk": "SK"},
                "ExpressionAttributeValues": _marshal({":pk": partition, ":prefix": sort_prefix}),
                "ConsistentRead": consistent,
                "ScanIndexForward": not descending,
                "Limit": min(100, limit - len(result)) if limit is not None else 100,
            }
            if cursor is not None:
                request["ExclusiveStartKey"] = _marshal(cursor)
            page = self.client.query(**request)
            result.extend(_unmarshal(item) for item in page.get("Items", ()))
            if limit is not None and len(result) >= limit:
                break
            cursor = _unmarshal(page["LastEvaluatedKey"]) if page.get("LastEvaluatedKey") else None
            if not cursor:
                break
        return result

    def transact(self, operations: list[dict[str, Any]]) -> None:
        if not operations or len(operations) > MAX_DYNAMO_TRANSACTION_ITEMS:
            raise StorageUnavailableError("dynamodb transaction item bound exceeded")
        total = sum(_operation_size(operation) for operation in operations)
        if total > MAX_DYNAMO_TRANSACTION_BYTES:
            raise StorageUnavailableError("dynamodb transaction byte bound exceeded")
        for operation in operations:
            action = next(iter(operation.values()))
            action["TableName"] = self.table_name
        self.client.transact_write_items(TransactItems=operations)
