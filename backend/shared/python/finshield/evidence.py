"""Tamper-evident evidence chain (the only writer of the Evidence table).

hash_n = SHA-256(hash_(n-1) + canonical_json(entry_n without hash))
entry 1 chains from ``GENESIS:<alert_id>``.
canonical_json = sorted keys, separators (',', ':'), UTF-8.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from . import ddb

IST = timezone(timedelta(hours=5, minutes=30))
MAX_APPEND_RETRIES = 5


def genesis(alert_id: str) -> str:
    return f"GENESIS:{alert_id}"


def _plain(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    """entry may include 'hash'; it is excluded from the digest."""
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256((prev_hash + canonical_json(body)).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def _last_entry(alert_id: str) -> dict[str, Any] | None:
    rows = ddb.query("Evidence", ddb.Key("alert_id").eq(alert_id), limit=1, forward=False, consistent=True)
    return rows[0] if rows else None


def append(alert_id: str, entry_type: str, actor: str, payload: dict[str, Any] | None = None, ts: str | None = None) -> dict[str, Any]:
    """Append one entry. Conditional put on seq; retries when another writer took the seq."""
    for _ in range(MAX_APPEND_RETRIES):
        last = _last_entry(alert_id)
        seq = (last["seq"] + 1) if last else 1
        prev_hash = last["hash"] if last else genesis(alert_id)
        entry = {
            "alert_id": alert_id,
            "seq": seq,
            "ts": ts or _now(),
            "type": entry_type,
            "actor": actor,
            "payload": _plain(payload or {}),
            "prev_hash": prev_hash,
        }
        entry["hash"] = compute_hash(prev_hash, entry)
        try:
            ddb.table("Evidence").put_item(Item=ddb.to_ddb(entry), ConditionExpression="attribute_not_exists(seq)")
            return entry
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
    raise RuntimeError(f"could not append evidence for {alert_id}: too much contention")


def chain(alert_id: str) -> list[dict[str, Any]]:
    return ddb.query("Evidence", ddb.Key("alert_id").eq(alert_id), forward=True, consistent=True)


def verify_entries(alert_id: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure verification. Returns {valid, broken_at_seq} (broken_at_seq is the first bad seq or None)."""
    expected_prev = genesis(alert_id)
    for idx, raw in enumerate(sorted(entries, key=lambda e: e.get("seq", 0)), start=1):
        e = _plain(raw)
        if e.get("seq") != idx or e.get("prev_hash") != expected_prev or e.get("hash") != compute_hash(expected_prev, e):
            return {"valid": False, "broken_at_seq": idx}
        expected_prev = e["hash"]
    return {"valid": True, "broken_at_seq": None}


def verify(alert_id: str) -> dict[str, Any]:
    return verify_entries(alert_id, chain(alert_id))
