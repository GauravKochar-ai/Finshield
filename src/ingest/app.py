"""fs-ingest: receives every event, keeps a raw copy, correlates the actor's
last 60 minutes of activity into a case, and starts the response workflow
ONCE per case when the case score reaches 0.7.

All timestamps ("ts") must be ISO-8601 with the same offset, e.g.
"2026-11-20T01:41:00+05:30", so they sort correctly as strings.
"""
import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

s3 = boto3.client("s3")
eventbridge = boto3.client("events")
ddb = boto3.resource("dynamodb")
events_table = ddb.Table(os.environ["EVENTS_TABLE"])
cases_table = ddb.Table(os.environ["CASES_TABLE"])
RAW_BUCKET = os.environ["RAW_BUCKET"]
IST = timezone(timedelta(hours=5, minutes=30))

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "baselines.json")) as f:
    BASELINES = json.load(f)                      # {"ADM-07": 40, ...} docs per day
with open(os.path.join(_HERE, "approved_destinations.json")) as f:
    APPROVED = set(json.load(f))                  # ["s3://fs-audit-vault", ...]

DEFAULT_BASELINE = 20
WINDOW_MINUTES = 60
WORKFLOW_THRESHOLD = 0.7
REQUIRED = ["actor_id", "event_type", "ts"]
WEIGHTS = {
    "PRIVILEGED_ACTOR": 0.1,
    "ANOMALOUS_LOGIN": 0.2,
    "BULK_KYC_ACCESS": 0.3,
    "UNAUTHORIZED_DESTINATION": 0.4,
    "AUTHORIZED_TICKET": -0.3,
}


def _resp(code, obj):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(obj, default=str),
    }


def _parse_body(event):
    """Works for API Gateway (HTTP API) calls and for console test events."""
    if "body" not in event:
        return event
    body = event["body"] or "{}"
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body)


def signals_for(window):
    """Turn the actor's recent events into a set of risk signals."""
    sig = set()
    for e in window:
        etype = e.get("event_type")
        if e.get("privileged"):
            sig.add("PRIVILEGED_ACTOR")
        if etype == "LOGIN":
            hour = datetime.fromisoformat(e["ts"]).hour
            if e.get("mfa") is False or e.get("geo") == "unknown-vpn" or hour < 6 or hour >= 22:
                sig.add("ANOMALOUS_LOGIN")
        if etype == "KYC_DOC_DOWNLOAD":
            baseline = BASELINES.get(e["actor_id"], DEFAULT_BASELINE)
            if int(e.get("doc_count", 0)) >= 10 * baseline:
                sig.add("BULK_KYC_ACCESS")
        if etype == "DATA_TRANSFER":
            if e.get("destination") not in APPROVED:
                sig.add("UNAUTHORIZED_DESTINATION")
            elif e.get("ticket_id"):
                sig.add("AUTHORIZED_TICKET")
    return sig


def score_for(signals):
    return round(max(0.0, min(1.0, sum(WEIGHTS[s] for s in signals))), 2)


def severity_for(score):
    if score >= 0.9:
        return "CRITICAL"
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "WATCH"
    return "LOW"


def lambda_handler(event, context):
    try:
        body = _parse_body(event)
    except (ValueError, TypeError):
        return _resp(400, {"error": "body must be valid JSON"})

    missing = [f for f in REQUIRED if f not in body]
    if missing:
        return _resp(400, {"error": f"missing fields: {missing}"})
    try:
        now = datetime.fromisoformat(body["ts"])
    except ValueError:
        return _resp(400, {"error": "ts must be ISO-8601, e.g. 2026-11-20T01:41:00+05:30"})

    body.setdefault("event_id", "ev-" + uuid.uuid4().hex[:10])

    # 1. Raw copy in S3 - this is the evidence source
    raw_key = f"raw/{body['actor_id']}/{body['event_id']}.json"
    s3.put_object(Bucket=RAW_BUCKET, Key=raw_key,
                  Body=json.dumps(body, sort_keys=True).encode("utf-8"),
                  ContentType="application/json")
    body["raw_key"] = raw_key

    # 2. Store the event (DynamoDB needs Decimal instead of float)
    events_table.put_item(Item=json.loads(json.dumps(body), parse_float=Decimal))

    # 3. Correlate: same actor, last 60 minutes
    start = (now - timedelta(minutes=WINDOW_MINUTES)).isoformat()
    window = events_table.query(
        KeyConditionExpression=Key("actor_id").eq(body["actor_id"]) & Key("ts").between(start, body["ts"])
    )["Items"]

    signals = sorted(signals_for(window))
    score = score_for(signals)
    severity = severity_for(score)
    case_id = f"case-{body['actor_id']}-{now.strftime('%Y%m%d')}"
    event_ids = [e["event_id"] for e in sorted(window, key=lambda x: x["ts"])]
    docs_involved = max([int(e.get("doc_count", 0) or 0) for e in window] + [0])
    destinations = sorted({e["destination"] for e in window if e.get("destination")})

    cases_table.update_item(
        Key={"case_id": case_id},
        UpdateExpression=(
            "SET actor_id = :a, case_score = :s, severity_rule = :v, signals = :g, "
            "event_ids = :e, docs_involved = :d, destinations = :dst, updated_at = :u, "
            "#st = if_not_exists(#st, :open)"
        ),
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":a": body["actor_id"],
            ":s": Decimal(str(score)),
            ":v": severity,
            ":g": signals,
            ":e": event_ids,
            ":d": docs_involved,
            ":dst": destinations,
            ":u": body["ts"],
            ":open": "OPEN",
        },
    )

    # 4. Start the workflow only ONCE per case
    workflow_started = False
    if score >= WORKFLOW_THRESHOLD:
        detected_at = datetime.now(IST).isoformat(timespec="seconds")
        try:
            cases_table.update_item(
                Key={"case_id": case_id},
                UpdateExpression="SET workflow_started = :t, detected_at = :t",
                ConditionExpression="attribute_not_exists(workflow_started)",
                ExpressionAttributeValues={":t": detected_at},
            )
            detail = {
                "case_id": case_id,
                "actor_id": body["actor_id"],
                "case_score": score,
                "severity_rule": severity,
                "signals": signals,
                "event_ids": event_ids,
                "docs_involved": docs_involved,
                "destinations": destinations,
                "detected_at": detected_at,
            }
            result = eventbridge.put_events(Entries=[{
                "Source": "finshield.monitor",
                "DetailType": "CaseRiskUpdated",
                "Detail": json.dumps(detail),
            }])
            print("EventBridge FailedEntryCount:", result.get("FailedEntryCount"))
            workflow_started = True
        except cases_table.meta.client.exceptions.ConditionalCheckFailedException:
            print("Workflow already started for", case_id)

    print(json.dumps({"case_id": case_id, "score": score, "signals": signals}))
    return _resp(200, {
        "event_id": body["event_id"],
        "case_id": case_id,
        "case_score": score,
        "severity": severity,
        "signals": signals,
        "workflow_started": workflow_started,
    })
