"""Stub handler used by every Lambda until its owner replaces it.

Logs the event as one JSON line and returns OK. For HTTP API calls it returns the matching
contract fixture inside the {data, error} envelope, so the web app can run against the live
API from the first deploy. Owners replace `handle(...)` in their app.py with real code.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from .config import contract_dir

log = logging.getLogger("finshield")
log.setLevel(logging.INFO)

ROUTE_FIXTURES = {
    "GET /v1/posture": "api_posture",
    "GET /v1/alerts": "api_alerts_list",
    "GET /v1/alerts/{id}": "api_alert_detail",
    "GET /v1/alerts/{id}/timeline": "api_alert_timeline",
    "GET /v1/alerts/{id}/evidence": "api_alert_evidence",
    "POST /v1/alerts/{id}/evidence/verify": "api_evidence_verify",
    "POST /v1/alerts/{id}/evidence/tamper-demo": "api_evidence_tamper_demo",
    "POST /v1/alerts/{id}/decision": "api_decision",
    "POST /v1/alerts/{id}/release": "api_release",
    "GET /v1/alerts/{id}/reports": "api_reports",
    "POST /v1/alerts/{id}/ask": "api_ask",
    "GET /v1/users/{id}": "api_user",
    "GET /v1/rules": "api_rules",
    "GET /v1/compliance": "api_compliance",
    "GET /v1/privacy": "api_privacy",
    "GET /v1/approvals": "api_approvals_list",
    "POST /v1/approvals": "api_approvals_create",
    "POST /v1/simulate": "api_simulate",
    "POST /v1/accuracy/run": "api_accuracy_run",
    "GET /v1/accuracy": "api_accuracy",
}


def log_json(level: str, message: str, **fields: Any) -> None:
    log.info(json.dumps({"level": level, "message": message, **fields}, default=str))


def _ids(event: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(event, dict):
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else event
        for key in ("alert_id", "event_id"):
            if detail.get(key):
                out[key] = detail[key]
    return out


def _is_http(event: Any) -> bool:
    return isinstance(event, dict) and "routeKey" in event and "requestContext" in event


def _http_response(route_key: str) -> dict[str, Any]:
    route_key = re.sub(r"\s+", " ", route_key)
    name = ROUTE_FIXTURES.get(route_key)
    if name:
        body = (contract_dir() / "fixtures" / f"{name}.json").read_text(encoding="utf-8")
        status = 200
    else:
        body = json.dumps({"data": None, "error": {"code": "NOT_FOUND", "message": f"no stub for {route_key}"}})
        status = 404
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": body}


def handle(function_name: str, event: Any, context: Any = None) -> dict[str, Any]:
    log_json("INFO", "stub invoked", function=function_name, request_id=getattr(context, "aws_request_id", None), event=event, **_ids(event))
    if _is_http(event):
        return _http_response(event["routeKey"])
    return {"status": "OK", "function": function_name, "stub": True}
