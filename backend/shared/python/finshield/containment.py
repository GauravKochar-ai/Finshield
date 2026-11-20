"""Shared containment flow used by the contain_* Lambdas (and release later).

Every containment Lambda takes ``{alert_id, principal_arn, mode, user_id?, execution?}`` and returns
``{action, mode, result, detail}``. Each one supplies a *planner* that turns the principal into a list of
exact AWS calls. In LIVE mode the calls run; in DRY_RUN they are written to evidence as ``would_call``.

Safety rules:
- LIVE only when SSM ``containment_mode`` is LIVE (the stack parameter is only a fallback).
- LIVE only against principals named ``finshield-<stage>-demo-*``; anything else is forced to DRY_RUN.
- A failing call never raises: the result is FAILED and the workflow continues.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import boto3

from . import ddb, evidence
from .config import get_setting, region, stage
from .log import log

IST = timezone(timedelta(hours=5, minutes=30))
MODES = ("LIVE", "DRY_RUN")


@dataclass
class Principal:
    arn: str
    kind: str  # role | user | unknown
    name: str
    iam_arn: str  # role/user ARN usable in policies (assumed-role sessions map to their role)


@dataclass
class Plan:
    calls: list[dict[str, Any]] = field(default_factory=list)  # {service, operation, method, params}
    detail: dict[str, Any] = field(default_factory=dict)
    not_applicable: str | None = None


def call(service: str, method: str, **params: Any) -> dict[str, Any]:
    op = "".join(p.capitalize() for p in method.split("_"))
    return {"service": service, "operation": f"{service}:{op}", "method": method, "params": params}


def parse_principal(arn: str | None) -> Principal:
    arn = arn or ""
    m = re.match(r"^arn:(?P<part>[^:]+):iam::(?P<acct>\d*):(?P<kind>role|user)/(?:.*/)?(?P<name>[^/]+)$", arn)
    if m:
        return Principal(arn, m["kind"], m["name"], arn)
    m = re.match(r"^arn:(?P<part>[^:]+):sts::(?P<acct>\d*):assumed-role/(?P<name>[^/]+)/.+$", arn)
    if m:
        return Principal(arn, "role", m["name"], f"arn:{m['part']}:iam::{m['acct']}:role/{m['name']}")
    return Principal(arn, "unknown", arn.rsplit("/", 1)[-1], arn)


def is_demo_principal(p: Principal) -> bool:
    return p.kind in ("role", "user") and p.name.startswith(f"finshield-{stage()}-demo-")


def resolve_mode(requested: str | None) -> tuple[str, str]:
    """SSM containment_mode wins (read fresh every call); the stack parameter is a fallback."""
    try:
        live_setting = get_setting("containment_mode", default=None, max_age_s=0)
    except Exception as exc:  # no SSM access: never go LIVE on a guess
        log("containment_mode unreadable, using DRY_RUN", level="WARNING", error=str(exc))
        return "DRY_RUN", "containment_mode unreadable"
    mode = (live_setting or requested or "DRY_RUN").upper()
    if mode not in MODES:
        return "DRY_RUN", f"unknown containment_mode {mode!r}"
    return mode, "ssm" if live_setting else "input"


def now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def lookup_alert(alert_id: str) -> dict[str, Any] | None:
    try:
        return ddb.get_item("Alerts", {"alert_id": alert_id})
    except Exception as exc:
        log("alert lookup failed", level="WARNING", alert_id=alert_id, error=str(exc))
        return None


def lookup_principal_arn(alert: dict[str, Any] | None, user_id: str | None) -> str | None:
    if alert and alert.get("principal_arn"):
        return alert["principal_arn"]
    uid = user_id or (alert or {}).get("user_id")
    if not uid:
        return None
    try:
        user = ddb.get_item("Users", {"user_id": uid}) or {}
    except Exception:
        return None
    return user.get("iam_principal_arn")


def execute(c: dict[str, Any]) -> Any:
    client = boto3.client(c["service"], region_name=region())
    return getattr(client, c["method"])(**c["params"])


def record_on_alert(alert_id: str, item: dict[str, Any]) -> None:
    """Append to Alerts.containment. Missing alert is logged, not fatal."""
    try:
        ddb.update_item(
            "Alerts",
            {"alert_id": alert_id},
            "SET containment = list_append(if_not_exists(containment, :empty), :item)",
            {":item": [item], ":empty": []},
            condition="attribute_exists(alert_id)",
        )
    except ddb.ConditionFailed:
        log("alert not found; containment recorded in evidence only", level="WARNING", alert_id=alert_id)


def contain(action: str, event: dict[str, Any], planner: Callable[[Principal, dict[str, Any], dict[str, Any]], Plan], actor: str) -> dict[str, Any]:
    alert_id = event["alert_id"]
    alert = lookup_alert(alert_id)
    principal = parse_principal(event.get("principal_arn") or lookup_principal_arn(alert, event.get("user_id")))
    mode, mode_source = resolve_mode(event.get("mode"))
    reasons = [f"mode from {mode_source}"]
    if mode == "LIVE" and event.get("force_dry_run"):
        mode = "DRY_RUN"
        reasons.append("forced DRY_RUN: the target service is not enabled in this stack")
    if mode == "LIVE" and not is_demo_principal(principal):
        mode = "DRY_RUN"
        reasons.append(f"forced DRY_RUN: {principal.arn or 'no principal'} is not a finshield-{stage()}-demo-* principal")

    ctx = {"alert": alert or {}, "user_id": event.get("user_id") or (alert or {}).get("user_id"), "mode": mode}
    plan = planner(principal, ctx, event)
    detail: dict[str, Any] = {"principal": principal.arn, **plan.detail}

    if plan.not_applicable:
        result = "NOT_APPLICABLE"
        detail["reason"] = plan.not_applicable
    elif mode == "DRY_RUN":
        result = "OK"
        detail["would_call"] = [{"operation": c["operation"], "params": c["params"]} for c in plan.calls]
    else:
        result, done = "OK", []
        for c in plan.calls:
            try:
                execute(c)
                done.append({"operation": c["operation"], "params": c["params"]})
            except Exception as exc:  # keep going; record what happened
                result = "FAILED"
                detail["error"] = f"{c['operation']}: {exc.__class__.__name__}: {exc}"[:400]
                log("containment call failed", level="ERROR", alert_id=alert_id, action=action, operation=c["operation"], error=str(exc))
                break
        detail["called"] = done
    detail["notes"] = reasons

    at = now_iso()
    execution = event.get("execution")
    evidence.append(
        alert_id,
        f"CONTAIN_{action}",
        actor,
        {"action": action, "mode": mode, "result": result, "at": at, "detail": detail},
        dedup_key=f"{execution}:CONTAIN_{action}" if execution else None,
    )
    summary = {"action": action, "mode": mode, "result": result, "at": at, "detail": detail}
    record_on_alert(alert_id, summary)
    log("containment done", alert_id=alert_id, action=action, mode=mode, result=result)
    return {"action": action, "mode": mode, "result": result, "detail": detail}
