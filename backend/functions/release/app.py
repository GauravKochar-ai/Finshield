"""release: POST /v1/alerts/{id}/release (SecurityHead). Undoes every containment step on the alert (reversibility demo).

Per recorded containment action: REVOKE_SESSIONS / QUARANTINE delete their inline policy, DEACTIVATE_KEYS reactivates
exactly the keys it switched off, BUCKET_DENY removes its Sid from the KYC bucket policy, DNS_BLOCK removes the domains.
An action that ran in DRY_RUN is released in DRY_RUN (the exact undo calls go to evidence as would_call).
"""
from __future__ import annotations

import json
import os

from finshield import containment, ddb, evidence
from finshield.http import HttpError, caller, is_http, path_id, require, run
from finshield.log import log

POLICIES = {"REVOKE_SESSIONS": "FinShieldRevokeSessions", "QUARANTINE": "FinShieldQuarantine"}


def _undo_calls(item, principal):
    action, detail = item["action"], item.get("detail") or {}
    if action in POLICIES:
        name = POLICIES[action]
        if principal.kind == "role":
            return [containment.call("iam", "delete_role_policy", RoleName=principal.name, PolicyName=name)]
        if principal.kind == "user":
            return [containment.call("iam", "delete_user_policy", UserName=principal.name, PolicyName=name)]
    if action == "DEACTIVATE_KEYS" and principal.kind == "user":
        return [containment.call("iam", "update_access_key", UserName=principal.name, AccessKeyId=k, Status="Active")
                for k in detail.get("deactivated_keys") or []]
    if action == "BUCKET_DENY" and detail.get("bucket") and detail.get("sid"):
        return [{"service": "s3", "operation": "s3:RemoveStatement", "method": "_remove_sid",
                 "params": {"Bucket": detail["bucket"], "Sid": detail["sid"]}}]
    if action == "DNS_BLOCK" and detail.get("domains"):
        list_id = os.environ.get("DNS_DOMAIN_LIST_ID") or "<dns-firewall-domain-list-id>"
        return [containment.call("route53resolver", "update_firewall_domains", FirewallDomainListId=list_id,
                                 Operation="REMOVE", Domains=detail["domains"])]
    return []


def _remove_sid(Bucket, Sid):
    pol = json.loads(containment.execute(containment.call("s3", "get_bucket_policy", Bucket=Bucket))["Policy"])
    rest = [s for s in pol.get("Statement", []) if s.get("Sid") != Sid]
    if rest:
        containment.execute(containment.call("s3", "put_bucket_policy", Bucket=Bucket,
                                             Policy=json.dumps({**pol, "Statement": rest})))
    else:
        containment.execute(containment.call("s3", "delete_bucket_policy", Bucket=Bucket))


def release(aid, who):
    a = ddb.get_item("Alerts", {"alert_id": aid}, consistent=True)
    if not a:
        raise HttpError(404, "NOT_FOUND", f"alert {aid} not found")
    if a.get("status") == "RELEASED":
        raise HttpError(409, "ALREADY_RELEASED", "containment was already released")
    principal = containment.parse_principal(a.get("principal_arn") or containment.lookup_principal_arn(a, a.get("user_id")))
    live_ok, _src = containment.resolve_mode(None)
    out = []
    for item in a.get("containment") or []:
        if item.get("result") != "OK":
            continue
        calls = _undo_calls(item, principal)
        mode = "LIVE" if item.get("mode") == "LIVE" and live_ok == "LIVE" and containment.is_demo_principal(principal) else "DRY_RUN"
        result, detail = "RELEASED", {"calls": [{"operation": c["operation"], "params": c["params"]} for c in calls]}
        if mode == "LIVE":
            for c in calls:
                try:
                    _remove_sid(**c["params"]) if c["method"] == "_remove_sid" else containment.execute(c)
                except Exception as exc:
                    if "NoSuchEntity" not in str(exc):
                        result, detail["error"] = "FAILED", f"{c['operation']}: {exc}"[:300]
                        break
        out.append({"action": item["action"], "mode": mode, "result": result})
        evidence.append(aid, f"RELEASE_{item['action']}", who, {"mode": mode, "result": result, "detail": detail})
    status = "RELEASED" if all(r["result"] == "RELEASED" for r in out) else a.get("status")
    ddb.update_item("Alerts", {"alert_id": aid}, "SET #s = :s", {":s": status}, names={"#s": "status"})
    log("released", alert_id=aid, actions=len(out), status=status)
    return {"alert_id": aid, "status": status, "released": out}


def handler(event, context=None):
    if is_http(event):
        def go():
            require(event, ["SecurityHead"])
            return release(path_id(event), caller(event))
        return run(event, go)
    return release(event["alert_id"], event.get("actor", "release"))
