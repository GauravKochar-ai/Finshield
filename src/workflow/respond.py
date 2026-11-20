"""fs-respond (MOCK): disables the account after the CISO approves.

In production this would disable the user / revoke all credentials.
"""
import os
from datetime import datetime, timedelta, timezone

import boto3

cases = boto3.resource("dynamodb").Table(os.environ["CASES_TABLE"])
IST = timezone(timedelta(hours=5, minutes=30))


def lambda_handler(event, context):
    now = datetime.now(IST).isoformat(timespec="seconds")
    approval = event.get("approval") or {}
    approver = approval.get("approver", "ciso")
    cases.update_item(
        Key={"case_id": event["case_id"]},
        UpdateExpression="SET #s = :s, disabled_at = :t, approver = :a, approval_comment = :c REMOVE approval_token",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "ACCOUNT_DISABLED",
            ":t": now,
            ":a": approver,
            ":c": approval.get("comment", ""),
        },
    )
    print(f"MOCK account disable for {event.get('actor_id')} approved by {approver}")
    return {**event, "status": "ACCOUNT_DISABLED", "disabled_at": now, "approver": approver}
