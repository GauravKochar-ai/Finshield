"""fs-store-token: saves the Step Functions task token on the case.

The workflow pauses until someone calls SendTaskSuccess with this token
(the dashboard Approve / Reject buttons, or tools/approve.py).
"""
import os
from datetime import datetime, timedelta, timezone

import boto3

cases = boto3.resource("dynamodb").Table(os.environ["CASES_TABLE"])
IST = timezone(timedelta(hours=5, minutes=30))


def lambda_handler(event, context):
    cases.update_item(
        Key={"case_id": event["case_id"]},
        UpdateExpression="SET approval_token = :t, approval_requested_at = :at, #s = :s",
        ExpressionAttributeNames={"#s": "status"},   # "status" is a DynamoDB reserved word
        ExpressionAttributeValues={
            ":t": event["token"],
            ":at": datetime.now(IST).isoformat(timespec="seconds"),
            ":s": "PENDING_APPROVAL",
        },
    )
    return {"saved": True}
