"""evidence: append, verify and export the hash chain (called by the incident state machine).

Actions
- append {alert_id, type, actor?, payload?, execution?} -> {seq, hash}   (idempotent per execution + type)
- verify {alert_id}                                      -> {valid, broken_at_seq}
- export {alert_id, execution?}                          -> {s3_key, entries, verify}
Export writes a JSON bundle to the Object Lock bucket, then appends EVIDENCE_EXPORTED with the bundle hash.
"""
import hashlib
import json
import os
from datetime import datetime

import boto3

from finshield import evidence
from finshield.config import region
from finshield.log import log


def _append(event):
    execution = event.get("execution")
    etype = event["type"]
    entry = evidence.append(
        event["alert_id"], etype, event.get("actor", "incident"), event.get("payload") or {},
        dedup_key=f"{execution}:{etype}" if execution else event.get("dedup_key"),
    )
    return {"seq": entry["seq"], "hash": entry["hash"]}


def _export(event):
    alert_id = event["alert_id"]
    entries = evidence.chain(alert_id)
    result = evidence.verify_entries(alert_id, entries)
    exported_at = datetime.now(evidence.IST).isoformat(timespec="seconds")
    bundle = {"alert_id": alert_id, "exported_at": exported_at, "verify": result, "entries": entries, "note": "SAMPLE synthetic data"}
    body = evidence.canonical_json(bundle).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    tag = event.get("execution") or exported_at.replace(":", "")
    key = f"evidence/{alert_id}/{tag}.json"
    boto3.client("s3", region_name=region()).put_object(
        Bucket=os.environ["EVIDENCE_BUCKET"], Key=key, Body=body, ContentType="application/json", ChecksumAlgorithm="SHA256",
    )
    s3_uri = f"s3://{os.environ['EVIDENCE_BUCKET']}/{key}"
    evidence.append(
        alert_id, "EVIDENCE_EXPORTED", "evidence",
        {"s3_uri": s3_uri, "bundle_sha256": digest, "entries": len(entries), "chain_valid": result["valid"]},
        dedup_key=f"{event['execution']}:EVIDENCE_EXPORTED" if event.get("execution") else None,
    )
    log("evidence exported", alert_id=alert_id, s3_uri=s3_uri, entries=len(entries))
    return {"s3_key": key, "entries": len(entries), "verify": result}


ACTIONS = {"append": _append, "verify": lambda e: evidence.verify(e["alert_id"]), "export": _export}


def handler(event, context):
    action = event.get("action", "append")
    if action not in ACTIONS:
        raise ValueError(f"unknown evidence action {action!r}")
    out = ACTIONS[action](event)
    log("evidence action", alert_id=event.get("alert_id"), action=action)
    return out
