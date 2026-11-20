"""DynamoDB helpers addressed by logical table name (Users, Alerts, Evidence, ...).

Physical names come from env vars set by the SAM template: TABLE_<LOGICAL_UPPER>.
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key  # re-exported for callers
from botocore.exceptions import ClientError

from .config import region

__all__ = ["Key", "table", "table_name", "get_item", "put_item", "put_if_absent", "query", "update_item", "to_ddb", "from_ddb", "ConditionFailed"]

_resource = None


class ConditionFailed(Exception):
    """A conditional write was rejected (item exists / version mismatch)."""


def resource():
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", region_name=region())
    return _resource


def reset_resource() -> None:
    global _resource
    _resource = None


def table_name(logical: str) -> str:
    env_key = f"TABLE_{logical.upper()}"
    try:
        return os.environ[env_key]
    except KeyError:
        raise KeyError(f"env var {env_key} not set for table {logical!r}") from None


def table(logical: str):
    return resource().Table(table_name(logical))


def to_ddb(obj: Any) -> Any:
    """Floats to Decimal, drop empty strings are NOT altered; None stays None."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_ddb(v) for v in obj]
    return obj


def from_ddb(obj: Any) -> Any:
    """Decimal to int when integral, else float."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: from_ddb(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [from_ddb(v) for v in obj]
    return obj


def get_item(logical: str, key: dict[str, Any], consistent: bool = False) -> dict[str, Any] | None:
    resp = table(logical).get_item(Key=key, ConsistentRead=consistent)
    item = resp.get("Item")
    return from_ddb(item) if item else None


def put_item(logical: str, item: dict[str, Any], **kwargs) -> None:
    table(logical).put_item(Item=to_ddb(item), **kwargs)


def put_if_absent(logical: str, item: dict[str, Any], key_attr: str) -> bool:
    """Idempotent insert. Returns True if written, False if the key already existed."""
    try:
        table(logical).put_item(Item=to_ddb(item), ConditionExpression=f"attribute_not_exists({key_attr})")
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def query(logical: str, key_condition, index: str | None = None, limit: int | None = None, forward: bool = True, consistent: bool = False, **kwargs) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"KeyConditionExpression": key_condition, "ScanIndexForward": forward, **kwargs}
    if index:
        params["IndexName"] = index
    elif consistent:
        params["ConsistentRead"] = True
    if limit:
        params["Limit"] = limit
    items: list[dict[str, Any]] = []
    t = table(logical)
    while True:
        resp = t.query(**params)
        items.extend(resp.get("Items", []))
        if limit and len(items) >= limit:
            return from_ddb(items[:limit])
        if "LastEvaluatedKey" not in resp:
            return from_ddb(items)
        params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def update_item(logical: str, key: dict[str, Any], update_expression: str, values: dict[str, Any], names: dict[str, str] | None = None, condition: str | None = None):
    """Thin wrapper; raises ConditionFailed when the condition is not met. Not for the Evidence table."""
    if logical.lower() == "evidence":
        raise PermissionError("Evidence table is append-only; use finshield.evidence.append")
    params: dict[str, Any] = {"Key": key, "UpdateExpression": update_expression, "ExpressionAttributeValues": to_ddb(values), "ReturnValues": "ALL_NEW"}
    if names:
        params["ExpressionAttributeNames"] = names
    if condition:
        params["ConditionExpression"] = condition
    try:
        return from_ddb(table(logical).update_item(**params).get("Attributes", {}))
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConditionFailed(str(exc)) from exc
        raise
