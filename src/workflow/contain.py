"""fs-contain (MOCK): immediate, reversible containment for CRITICAL cases.

In production this would revoke the actor's active sessions / access keys
and add the destination to a deny list. For the PoC we record the actions.
"""
import os
from datetime import datetime, timedelta, timezone

import boto3

cases = boto3.resource("dynamodb").Table(os.environ["CASES_TABLE"])
IST = timezone(timedelta(hours=5, minutes=30))


def lambda_handler(event, context):
    now = datetime.now(IST).isoformat(timespec="seconds")
    actions = ["SESSION_REVOKED", "DESTINATION_BLOCKED"]
    blocked = event.get("destinations", [])
    cases.update_item(
        Key={"case_id": event["case_id"]},
        UpdateExpression="SET containment = :c, blocked_destinations = :b, contained_at = :t, #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":c": actions, ":b": blocked, ":t": now, ":s": "CONTAINED"},
    )
    print(f"MOCK containment for {event['case_id']}: {actions}, blocked={blocked}")
    return {"containment": actions, "blocked_destinations": blocked, "contained_at": now}
