"""api: the read endpoints of contract/openapi.yaml, on live tables, in the {data, error} envelope.

GET  /v1/posture /v1/alerts?status=&severity= /v1/alerts/{id} /v1/alerts/{id}/timeline /v1/alerts/{id}/evidence
POST /v1/alerts/{id}/evidence/verify
GET  /v1/alerts/{id}/reports /v1/users/{id} /v1/rules /v1/compliance /v1/privacy /v1/accuracy
GET  /v1/approvals   POST /v1/approvals (SecurityHead)
Groups follow x-groups in openapi.yaml ("all" = any signed-in user).
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from boto3.dynamodb.conditions import Attr

from finshield import ddb, evidence, schema
from finshield.config import load_config
from finshield.ddb import Key
from finshield.http import ALL, HttpError, body, caller, is_http, path_id, public_alert, require, run
from finshield.scoring import t, tz_offset

OPEN = ("OPEN", "CONTAINED", "AWAITING_APPROVAL", "LOCKED")
SEV_WEIGHT = {"CRITICAL": 15, "HIGH": 8, "MEDIUM": 3}  # posture display only, not scoring
EVENT_KEYS = schema._schemas()["event"]["properties"].keys()
LIMIT = 100


def _scan(logical, **kw):
    out, tbl = [], ddb.table(logical)
    while True:
        r = tbl.scan(**kw)
        out += [ddb.from_ddb(i) for i in r.get("Items", [])]
        if "LastEvaluatedKey" not in r:
            return out
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _now():
    return datetime.now(tz_offset(load_config()))


def _alert(aid):
    a = ddb.get_item("Alerts", {"alert_id": aid}, consistent=True)
    if not a:
        raise HttpError(404, "NOT_FOUND", f"alert {aid} not found")
    return a


# ------------------------------------------------------------------ alerts
def list_alerts(q):
    status, sev = q.get("status"), q.get("severity")
    if status:
        rows = ddb.query("Alerts", Key("status").eq(status), index="status-detected-index", forward=False)
    else:
        rows = _scan("Alerts")
    if sev:
        rows = [a for a in rows if a.get("severity") == sev]
    rows.sort(key=lambda a: a["detected_at"], reverse=True)
    return [public_alert(a) for a in rows[:LIMIT]]


def timeline(aid):
    a = _alert(aid)
    ids = set(a.get("event_ids") or [])
    lo = a.get("window_start") or a["detected_at"]
    evs = ddb.query("Events", Key("user_id").eq(a["user_id"]) & Key("sk").gte(lo))
    out = [{k: e.get(k) for k in EVENT_KEYS} for e in evs if e["event_id"] in ids]
    return sorted(out, key=lambda e: (e["ts"], e["event_id"]))


def reports(aid):
    _alert(aid)
    return ddb.query("Reports", Key("alert_id").eq(aid))


# ------------------------------------------------------------------ overview screens
def posture():
    alerts = [a for a in _scan("Alerts") if a.get("status") in OPEN]
    by_sev = {s: sum(1 for a in alerts if a["severity"] == s) for s in ("CRITICAL", "HIGH", "MEDIUM")}
    config_rows = _scan("Posture")
    bad = sum(1 for p in config_rows if p.get("status") == "NON_COMPLIANT")
    now = _now()
    due = []
    for a in alerts:
        for d in a.get("deadlines") or []:
            left = int((t(d["due_at"]) - now).total_seconds())
            if left > 0:
                due.append({"alert_id": a["alert_id"], "body": d["body"], "due_at": d["due_at"], "seconds_remaining": left})
    due.sort(key=lambda d: d["seconds_remaining"])
    s9 = [a for a in alerts if any(s["code"] == "S9" for s in a.get("signals") or [])]
    score = max(0, 100 - sum(SEV_WEIGHT[a["severity"]] for a in alerts) - 5 * bad)
    return {"posture_score": score, "alerts_by_severity": by_sev,
            "config_results": [{k: p.get(k) for k in ("control_id", "source", "status", "resource_arn", "last_evaluated")}
                               for p in config_rows],
            "consent_risks": {"purpose_mismatches": len(s9),
                              "withdrawn_consents_accessed": sum(int(next((s["facts"].get("customers", 0) for s in a["signals"]
                                                                            if s["code"] == "S9"), 0)) for a in s9)},
            "deadlines_due_soon": due[:10]}


def privacy():
    alerts = _scan("Alerts")
    mism = []
    for a in alerts:
        for s in a.get("signals") or []:
            if s["code"] == "S9":
                mism.append({"alert_id": a["alert_id"], "user_id": a["user_id"], "customers": s["facts"].get("customers"),
                             "purpose": s["facts"].get("purpose")})
    withdrawn = _scan("Consent", FilterExpression=Attr("withdrawn").size().gt(0), ProjectionExpression="customer_id, withdrawn")
    unmasked = _scan("KycFiles", FilterExpression=Attr("unmasked_aadhaar_flag").eq(True),
                     ProjectionExpression="file_id, customer_id, doc_type")
    return {"consent_risks": [{"customer_id": c["customer_id"], "issue": f"withdrew consent for {', '.join(c['withdrawn'])}"}
                              for c in sorted(withdrawn, key=lambda c: c["customer_id"])[:50]],
            "unmasked_aadhaar_files": unmasked[:50], "purpose_mismatches": mism}


# ------------------------------------------------------------------ compliance map
# Rows come from simulator/seed/compliance_controls.json (M8, verified clauses). `make layer` bundles the file next to
# the finshield package; tests and local runs read it from the repo. Status is computed live per request.
CONTROLS_FILE = "compliance_controls.json"
CONTAINED = ("CONTAINED", "AWAITING_APPROVAL", "LOCKED", "RELEASED", "CLOSED")
DRAFTED = ("DRAFT", "FALLBACK")
NOT_YET = "UNKNOWN"

# control_id -> how its status is decided. Rows not listed keep the status written in the file.
#   template      guaranteed by infra/template.yaml (checked in test_template.py)
#   region        the stack runs in ap-south-1
#   chain         evidence chains verify
#   detection     the pipeline has produced at least one alert
#   containment   at least one alert has reached containment
#   signal:A|B    an alert carries one of these signals
#   deadline:X    Critical alerts carry the X readiness timer
#   report:T      a Critical alert has a T report drafted
#   timer_report:X:T   both of the above
#   consent       the consent ledger has records
#   kyc_label     KYC files have been labelled
#   private_kyc   template guarantees, unless AWS Config reports a NON_COMPLIANT resource
CHECKS = {
    "IN-01": "chain", "IN-02": "template", "IN-03": "containment", "IN-04": "detection", "IN-05": "template",
    "IN-06": "report:CUSTOMER_NOTICE", "IN-07": "report:DPB_NOTICE", "IN-08": "timer_report:DPB:DPB_NOTICE",
    "IN-09": "consent", "IN-10": "consent", "IN-11": "consent", "IN-12": "signal:S7", "IN-13": "region",
    "IN-14": "kyc_label", "IN-15": "timer_report:RBI:RBI_INCIDENT", "IN-16": "timer_report:CERT-In:CERTIN_FORM",
    "IN-17": "region", "IN-20": "detection", "IN-21": "signal:S3|S5", "IN-22": "containment", "IN-23": "deadline:RBI",
    "IN-24": "chain", "IN-25": "detection",
    "SOC2-CC6.1": "private_kyc", "SOC2-CC6.2": "containment", "SOC2-CC6.3": "template", "SOC2-CC7.2": "detection",
    "SOC2-CC7.3": "detection", "SOC2-CC7.4": "containment", "SOC2-CC8.1": "template", "SOC2-C1.1": "kyc_label",
    "ISO27001-A.5.15": "template", "ISO27001-A.8.2": "signal:S3", "ISO27001-A.8.12": "signal:S1|S4",
    "ISO27001-A.8.15": "template", "ISO27001-A.8.16": "detection", "ISO27001-A.5.24": "template",
    "ISO27001-A.5.25": "detection", "ISO27001-A.5.26": "containment", "ISO27001-A.5.28": "chain",
    "ISO27001-A.5.34": "kyc_label", "ISO27001-A.8.24": "template",
}


@lru_cache(maxsize=1)
def _controls() -> list[dict]:
    import finshield

    places = [Path(finshield.__file__).resolve().parent / CONTROLS_FILE]               # Lambda layer
    places += [p / "simulator" / "seed" / CONTROLS_FILE for p in Path(__file__).resolve().parents]  # repo checkout
    for p in places:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    raise HttpError(500, "CONFIG_MISSING", f"{CONTROLS_FILE} is not bundled; run `make build`")


def _has_rows(logical) -> bool:
    return ddb.table(logical).scan(Select="COUNT", Limit=1).get("Count", 0) > 0


def _facts() -> dict:
    alerts = _scan("Alerts")
    reports = _scan("Reports", ProjectionExpression="alert_id, report_type, #s", ExpressionAttributeNames={"#s": "status"})
    crit = [a for a in alerts if a.get("severity") == "CRITICAL"]
    return {
        "alerts": alerts,
        "crit": crit,
        "drafted": {(r["alert_id"], r["report_type"]) for r in reports if r.get("status") in DRAFTED},
        "chains": [evidence.verify(a["alert_id"])["valid"] for a in alerts[:20]],
        "noncompliant": sum(1 for p in _scan("Posture") if p.get("status") == "NON_COMPLIANT"),
        "consent": _has_rows("Consent"),
        "kyc": _has_rows("KycFiles"),
        "region": os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "",
    }


def _status(check: str, f: dict) -> tuple[str, str]:
    """(status, short reason) for one check, from live data."""
    kind, _, arg = check.partition(":")
    alerts, crit = f["alerts"], f["crit"]
    no_crit = (NOT_YET, "No Critical incident yet")
    if kind == "template":
        return "IN_PLACE", "Set in infra/template.yaml"
    if kind == "region":
        ok = f["region"] == "ap-south-1"
        return ("IN_PLACE" if ok else "GAP"), f"Running in {f['region'] or 'an unknown region'}"
    if kind == "private_kyc":
        if f["noncompliant"]:
            return "GAP", f"AWS Config reports {f['noncompliant']} non-compliant resource(s)"
        return "IN_PLACE", "Private, KMS-encrypted bucket; no AWS Config findings"
    if kind == "chain":
        if not f["chains"]:
            return NOT_YET, "No evidence chain yet"
        bad = f["chains"].count(False)
        return ("GAP", f"{bad} evidence chain(s) fail verification") if bad else \
               ("IN_PLACE", f"{len(f['chains'])} evidence chain(s) verify")
    if kind == "detection":
        return ("IN_PLACE", f"{len(alerts)} alert(s) raised") if alerts else (NOT_YET, "No alert yet")
    if kind == "containment":
        n = sum(1 for a in alerts if a.get("status") in CONTAINED)
        return ("IN_PLACE", f"{n} alert(s) contained") if n else (NOT_YET, "No alert contained yet")
    if kind == "signal":
        codes = set(arg.split("|"))
        n = sum(1 for a in alerts if codes & {s.get("code") for s in a.get("signals") or []})
        return ("IN_PLACE", f"{n} alert(s) with {'/'.join(sorted(codes))}") if n else \
               (NOT_YET, f"No {'/'.join(sorted(codes))} alert yet")
    if kind == "consent":
        return ("IN_PLACE", "Consent ledger loaded") if f["consent"] else (NOT_YET, "Consent ledger is empty")
    if kind == "kyc_label":
        return ("IN_PLACE", "KYC files labelled") if f["kyc"] else (NOT_YET, "No KYC files labelled yet")
    if kind == "deadline":
        if not crit:
            return no_crit
        ok = any(d.get("body") == arg for a in crit for d in a.get("deadlines") or [])
        return ("IN_PLACE", f"{arg} timer running") if ok else ("GAP", f"Critical alert without a {arg} timer")
    if kind == "report":
        if not crit:
            return no_crit
        ok = any((a["alert_id"], arg) in f["drafted"] for a in crit)
        return ("IN_PLACE", f"{arg} drafted") if ok else ("GAP", f"Critical alert without a {arg} draft")
    if kind == "timer_report":
        body_, report = arg.split(":")
        timer, draft = _status(f"deadline:{body_}", f), _status(f"report:{report}", f)
        for s in ("GAP", NOT_YET):
            for st in (timer, draft):
                if st[0] == s:
                    return st
        return "IN_PLACE", f"{body_} timer running and {report} drafted"
    return NOT_YET, f"unknown check {check}"


def compliance():
    f = _facts()
    out = []
    for row in _controls():
        r = dict(row)
        check = CHECKS.get(r["control_id"])
        if check and r.get("status") != "NOT_APPLICABLE":
            r["status"], r["status_detail"] = _status(check, f)
        else:
            r["status_detail"] = "Not claimed by FinShield" if r.get("status") == "NOT_APPLICABLE" else "Not checked live"
        out.append(r)
    return out


def user(uid):
    u = ddb.get_item("Users", {"user_id": uid})
    if not u:
        raise HttpError(404, "NOT_FOUND", f"user {uid} not found")
    b = ddb.get_item("Baselines", {"subject_id": uid}) or {}
    recent = ddb.query("Alerts", Key("user_id").eq(uid), index="user-detected-index", forward=False, limit=10)
    keys = ("user_id", "name_pseudo", "team", "role", "is_admin", "is_service", "office_start", "office_end", "home_city",
            "devices", "partner_id", "iam_principal_arn")
    return {**{k: u.get(k) for k in keys},
            "baseline": {k: b.get(k) for k in ("p95_15min", "avg_daily", "usual_hours", "cities", "devices", "p95_disburse_inr")},
            "recent_risk": [{k: a[k] for k in ("alert_id", "score", "severity", "detected_at")} for a in recent]}


def accuracy():
    rows = _scan("AccuracyRuns")
    if not rows:
        raise HttpError(404, "NOT_FOUND", "no accuracy run yet; POST /v1/accuracy/run")
    run_id = max(r["run_id"] for r in rows)
    mine = [r for r in rows if r["run_id"] == run_id]
    normal = next((r for r in mine if r["scenario_id"] == "NORMAL-7D"), {})
    sc = sorted((r for r in mine if r["scenario_id"].startswith("SC-")), key=lambda r: r["scenario_id"])
    keys = ("scenario_id", "expected_level", "actual_level", "expected_score", "actual_score", "pass", "time_to_alert_ms")
    return {"run_id": run_id, "ran_at": (sc or [normal])[0].get("ran_at"), "passed": sum(1 for r in sc if r["pass"]),
            "total": len(sc), "false_alerts_normal_days": int(normal.get("false_alerts", 0)),
            "rows": [{k: r.get(k) for k in keys} for r in sc]}


# ------------------------------------------------------------------ approvals
APPROVAL_KEYS = ("type", "subject_id", "max_files", "data_class", "valid_from", "valid_to", "approver_id", "job_id",
                 "window_start", "window_end", "note")


def create_approval(event):
    b = body(event)
    missing = [k for k in ("type", "subject_id", "valid_from", "valid_to") if not b.get(k)]
    if missing:
        raise HttpError(400, "BAD_REQUEST", f"missing {missing}")
    if b["type"] not in ("ticket", "scheduled_job", "emergency_access"):
        raise HttpError(400, "BAD_REQUEST", "type must be ticket, scheduled_job or emergency_access")
    for k in ("valid_from", "valid_to"):
        try:
            t(b[k])
        except ValueError:
            raise HttpError(400, "BAD_REQUEST", f"{k} must be ISO 8601")
    item = {k: b[k] for k in APPROVAL_KEYS if b.get(k) is not None}
    item.setdefault("approver_id", caller(event))
    item["approval_id"] = f"APR-{_now():%Y%m%d%H%M%S}-{secrets.token_hex(2)}"
    ddb.put_item("Approvals", item)
    return item


ROUTES = {
    "GET /v1/posture": ([ALL], lambda e: posture()),
    "GET /v1/alerts": ([ALL], lambda e: list_alerts(e.get("queryStringParameters") or {})),
    "GET /v1/alerts/{id}": ([ALL], lambda e: public_alert(_alert(path_id(e)))),
    "GET /v1/alerts/{id}/timeline": ([ALL], lambda e: timeline(path_id(e))),
    "GET /v1/alerts/{id}/evidence": ([ALL], lambda e: (_alert(path_id(e)), evidence.chain(path_id(e)))[1]),
    "POST /v1/alerts/{id}/evidence/verify": ([ALL], lambda e: evidence.verify(path_id(e))),
    "GET /v1/alerts/{id}/reports": ([ALL], lambda e: reports(path_id(e))),
    "GET /v1/users/{id}": ([ALL], lambda e: user(path_id(e))),
    "GET /v1/rules": ([ALL], lambda e: load_config()),
    "GET /v1/compliance": ([ALL], lambda e: compliance()),
    "GET /v1/privacy": ([ALL], lambda e: privacy()),
    "GET /v1/approvals": (["SecurityHead"], lambda e: sorted(_scan("Approvals"), key=lambda a: a["approval_id"])),
    "POST /v1/approvals": (["SecurityHead"], create_approval),
    "GET /v1/accuracy": (["Admin"], lambda e: accuracy()),
}


def handler(event, context=None):
    if not is_http(event):
        return {"status": "SKIPPED", "reason": "api only serves HTTP routes"}
    route = " ".join(event["routeKey"].split())
    if route not in ROUTES:
        return run(event, lambda: (_ for _ in ()).throw(HttpError(404, "NOT_FOUND", f"no route {route}")))
    groups_allowed, fn = ROUTES[route]

    def go():
        require(event, groups_allowed)
        return fn(event)
    return run(event, go)
