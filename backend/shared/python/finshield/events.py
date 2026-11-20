"""EventBridge helper. Bus name comes from env EVENT_BUS_NAME (set by the SAM template)."""
from __future__ import annotations

import json
import os
from typing import Any

import boto3

from .config import region

DETAIL_TYPES = ("Raw Activity", "Normalized Event", "Alert Raised", "Incident Updated")
SOURCES = {
    "Raw Activity": "finshield.simulator",
    "Normalized Event": "finshield.normalizer",
    "Alert Raised": "finshield.detection",
    "Incident Updated": "finshield.response",
}

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client("events", region_name=region())
    return _client


def reset_client() -> None:
    global _client
    _client = None


def put_event(detail_type: str, detail: dict[str, Any], source: str | None = None, bus_name: str | None = None) -> str:
    """Put one event on the FinShield bus. Returns the EventBridge event id; raises on failure."""
    if detail_type not in DETAIL_TYPES:
        raise ValueError(f"detail_type must be one of {DETAIL_TYPES}")
    return put_events([(detail_type, detail, source)], bus_name)[0]


def put_events(entries: list[tuple[str, dict[str, Any], str | None]], bus_name: str | None = None) -> list[str]:
    bus = bus_name or os.environ["EVENT_BUS_NAME"]
    ids: list[str] = []
    for i in range(0, len(entries), 10):  # PutEvents limit is 10 per call
        batch = entries[i : i + 10]
        resp = client().put_events(
            Entries=[
                {"EventBusName": bus, "Source": src or SOURCES.get(dt, "finshield.app"), "DetailType": dt, "Detail": json.dumps(detail, default=str)}
                for dt, detail, src in batch
            ]
        )
        if resp.get("FailedEntryCount"):
            failed = [e for e in resp["Entries"] if "ErrorCode" in e]
            raise RuntimeError(f"put_events failed for {len(failed)} entries: {failed[:1]}")
        ids.extend(e["EventId"] for e in resp["Entries"])
    return ids
