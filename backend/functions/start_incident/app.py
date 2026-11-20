"""start_incident: Alert Raised -> start finshield-<stage>-incident with name <alert_id>-<severity>.

A second start for the same alert and severity fails with ExecutionAlreadyExists and is ignored,
so duplicate Alert Raised events are harmless.
"""
import json
import os
import re

import boto3
from botocore.exceptions import ClientError

from finshield import ddb
from finshield.config import region
from finshield.log import log

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM")
REQUIRED = ("alert_id", "severity", "score", "user_id", "detected_at")


def execution_name(alert_id: str, severity: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{alert_id}-{severity}")[:80]


def handler(event, context):
    detail = event.get("detail", event)
    missing = [k for k in REQUIRED if detail.get(k) in (None, "")]
    if missing:
        raise ValueError(f"Alert Raised detail missing {missing}")
    severity = str(detail["severity"]).upper()
    if severity not in SEVERITIES:
        log("severity below MEDIUM, no incident", alert_id=detail["alert_id"], severity=severity)
        return {"status": "SKIPPED", "alert_id": detail["alert_id"]}
    detail = {**detail, "severity": severity, "principal_arn": detail.get("principal_arn"), "previous_severity": detail.get("previous_severity")}
    name = execution_name(detail["alert_id"], severity)
    sfn = boto3.client("stepfunctions", region_name=region())
    try:
        resp = sfn.start_execution(stateMachineArn=os.environ["STATE_MACHINE_ARN"], name=name, input=json.dumps(detail, default=str))
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ExecutionAlreadyExists":
            log("execution already exists, ignoring duplicate", alert_id=detail["alert_id"], execution=name)
            return {"status": "DUPLICATE", "alert_id": detail["alert_id"], "execution_name": name}
        raise
    arn = resp["executionArn"]
    try:
        ddb.update_item("Alerts", {"alert_id": detail["alert_id"]}, "SET execution_arn = :a", {":a": arn}, condition="attribute_exists(alert_id)")
    except ddb.ConditionFailed:
        log("alert not found; execution started anyway", level="WARNING", alert_id=detail["alert_id"])
    log("incident started", alert_id=detail["alert_id"], execution=name)
    return {"status": "STARTED", "alert_id": detail["alert_id"], "execution_arn": arn}
