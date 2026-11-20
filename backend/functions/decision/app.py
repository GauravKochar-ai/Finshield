"""decision: CISO approval for the incident workflow.

1. Step Functions (waitForTaskToken) calls it with {action: STORE_TOKEN, alert_id, task_token, execution_arn, escalated}.
   The token is kept on the Alerts row (approval_token, never returned by the API) and evidence gets APPROVAL_REQUESTED.
2. POST /v1/alerts/{id}/decision {decision: APPROVE|REJECT, reason} (SecurityHead, ComplianceHead) sends the token back
   with SendTaskSuccess; the workflow then quarantines (APPROVE) or records the rejection (REJECT).
"""
from __future__ import annotations

import json
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from finshield import ddb, evidence
from finshield.config import load_config, region
from finshield.http import HttpError, body, caller, is_http, path_id, require, run
from finshield.log import log
from finshield.scoring import tz_offset

GROUPS = ["SecurityHead", "ComplianceHead"]


def _now():
    return datetime.now(tz_offset(load_config())).isoformat(timespec="seconds")


def store_token(ev):
    aid = ev["alert_id"]
    ddb.update_item("Alerts", {"alert_id": aid}, "SET approval_token = :t, approval_escalated = :e, approval_requested_at = :at",
                    {":t": ev["task_token"], ":e": bool(ev.get("escalated")), ":at": _now()},
                    condition="attribute_exists(alert_id)")
    evidence.append(aid, "APPROVAL_REQUESTED", "decision",
                    {"escalated": bool(ev.get("escalated")), "execution_arn": ev.get("execution_arn"),
                     "to": "ComplianceHead" if ev.get("escalated") else "SecurityHead"},
                    dedup_key=f"{ev.get('execution_arn')}:APPROVAL_REQUESTED:{bool(ev.get('escalated'))}")
    log("approval token stored", alert_id=aid, escalated=bool(ev.get("escalated")))
    return {"stored": True, "alert_id": aid}


def decide(event):
    require(event, GROUPS)
    aid = path_id(event)
    b = body(event)
    if b.get("decision") not in ("APPROVE", "REJECT") or not isinstance(b.get("reason"), str) or set(b) - {"decision", "reason"}:
        raise HttpError(400, "BAD_REQUEST", 'body must be {"decision": "APPROVE"|"REJECT", "reason": "..."}')
    a = ddb.get_item("Alerts", {"alert_id": aid}, consistent=True)
    if not a:
        raise HttpError(404, "NOT_FOUND", f"alert {aid} not found")
    token = a.get("approval_token")
    if not token:
        raise HttpError(409, "NO_PENDING_APPROVAL", "this alert is not waiting for approval")
    who = caller(event)
    out = {"decision": b["decision"], "reason": b["reason"], "by": who, "at": _now()}
    try:
        boto3.client("stepfunctions", region_name=region()).send_task_success(taskToken=token, output=json.dumps(out))
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("TaskTimedOut", "TaskDoesNotExist", "InvalidToken"):
            ddb.table("Alerts").update_item(Key={"alert_id": aid}, UpdateExpression="REMOVE approval_token")
            raise HttpError(409, "APPROVAL_EXPIRED", "the approval request has expired or was already answered")
        raise
    status = "LOCKED" if b["decision"] == "APPROVE" else a.get("status", "CONTAINED")
    ddb.update_item("Alerts", {"alert_id": aid}, "SET #s = :s REMOVE approval_token", {":s": status}, names={"#s": "status"})
    evidence.append(aid, f"DECISION_{b['decision']}", who, out)
    log("decision sent", alert_id=aid, decision=b["decision"], by=who)
    return {"alert_id": aid, "decision": b["decision"], "status": status}


def handler(event, context=None):
    if is_http(event):
        return run(event, lambda: decide(event))
    if event.get("action") == "STORE_TOKEN":
        return store_token(event)
    raise ValueError(f"unknown action {event.get('action')!r}")
