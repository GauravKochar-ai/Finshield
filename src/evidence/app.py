"""fs-evidence: builds a tamper-evident evidence pack for a case.

For every event in the case: hash the raw log in S3 (SHA-256), link it to the
previous record's hash, and store the whole pack in the versioned
fs-evidence bucket. The pack hash is saved on the case so anyone can verify it.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

from chain import GENESIS, pack_hash, record_hash, sha256

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")
events_table = ddb.Table(os.environ["EVENTS_TABLE"])
cases_table = ddb.Table(os.environ["CASES_TABLE"])
RAW_BUCKET = os.environ["RAW_BUCKET"]
EVIDENCE_BUCKET = os.environ["EVIDENCE_BUCKET"]
IST = timezone(timedelta(hours=5, minutes=30))


def load_events(actor_id, event_ids):
    items, kwargs = [], {"KeyConditionExpression": Key("actor_id").eq(actor_id)}
    while True:
        page = events_table.query(**kwargs)
        items.extend(page["Items"])
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    wanted = set(event_ids or [])
    if wanted:
        items = [e for e in items if e.get("event_id") in wanted]
    return sorted(items, key=lambda e: e["ts"])


def describe(e):
    t = e.get("event_type")
    if t == "LOGIN":
        return f"Login from {e.get('source_ip', '?')} ({e.get('geo', '?')}), MFA={e.get('mfa')}"
    if t == "ASSUME_ROLE":
        return f"Assumed role {e.get('role_assumed', '?')}"
    if t == "KYC_DOC_DOWNLOAD":
        return f"Downloaded {e.get('doc_count', '?')} KYC documents from {e.get('resource', '?')}"
    if t == "DATA_TRANSFER":
        return f"Transferred {e.get('doc_count', '?')} documents to {e.get('destination', '?')}"
    return f"{t} event"


def lambda_handler(event, context):
    case_id = event["case_id"]
    actor_id = event["actor_id"]
    events = load_events(actor_id, event.get("event_ids"))

    records, prev = [], GENESIS
    for seq, e in enumerate(events, start=1):
        raw_key = e.get("raw_key")
        try:
            raw_bytes = s3.get_object(Bucket=RAW_BUCKET, Key=raw_key)["Body"].read()
            raw_sha = sha256(raw_bytes)
        except Exception as exc:
            print("Raw log missing:", raw_key, repr(exc))
            raw_sha = "MISSING"
        rec = {
            "seq": seq,
            "ts": e["ts"],
            "event_id": e.get("event_id"),
            "event_type": e.get("event_type"),
            "actor_id": actor_id,
            "description": describe(e),
            "raw_log": f"s3://{RAW_BUCKET}/{raw_key}",
            "raw_sha256": raw_sha,
            "prev_hash": prev,
        }
        rec["record_hash"] = record_hash(rec)
        prev = rec["record_hash"]
        records.append(rec)

    pack = {
        "case_id": case_id,
        "actor_id": actor_id,
        "generated_at": datetime.now(IST).isoformat(timespec="seconds"),
        "generator": "fs-evidence v1",
        "hash_algorithm": "SHA-256 hash chain",
        "severity": event.get("severity"),
        "case_score": event.get("case_score"),
        "signals": event.get("signals", []),
        "mitre": event.get("mitre", []),
        "summary": event.get("summary"),
        "records": records,
        "chain_head": prev,
    }
    pack["pack_sha256"] = pack_hash(pack)

    key = f"evidence/{case_id}.json"
    put = s3.put_object(Bucket=EVIDENCE_BUCKET, Key=key,
                        Body=json.dumps(pack, indent=2, default=str).encode("utf-8"),
                        ContentType="application/json")
    version_id = put.get("VersionId", "unversioned")
    evidence_uri = f"s3://{EVIDENCE_BUCKET}/{key}"

    cases_table.update_item(
        Key={"case_id": case_id},
        UpdateExpression="SET evidence_key = :k, evidence_hash = :h, evidence_version = :v, evidence_records = :n",
        ExpressionAttributeValues={":k": evidence_uri, ":h": pack["pack_sha256"],
                                   ":v": version_id, ":n": len(records)},
    )

    return {**event, "evidence_key": evidence_uri, "evidence_hash": pack["pack_sha256"],
            "evidence_records": len(records)}
