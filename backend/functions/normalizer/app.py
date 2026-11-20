"""normalizer (M3): every source becomes the unified event (contract/schemas/event.schema.json).

Input on the bus: Raw Activity (simulator, app), CloudTrail API calls and console sign-ins, GuardDuty findings,
AWS Config compliance changes. For each record: map -> validate -> archive the raw JSON to
s3://<RAW_BUCKET>/YYYY/MM/DD/<event_id>.json -> idempotent insert into Events (put_if_absent on sk) ->
emit Normalized Event. A duplicate event_id is dropped. A record that does not map is skipped, not retried.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime

from finshield import ddb, events, schema
from finshield.config import load_config
from finshield.scoring import tz_offset
from finshield.stub import log_json

_users_cache = {"at": 0.0, "by_arn": {}, "ids": set()}
USERS_TTL_S = 300
KEY_RX = re.compile(r"^kyc/(?P<cid>[^/]+)/(?P<name>[^/]+?)(\.[A-Za-z0-9]+)?$")


def _local_tz():
    return tz_offset(load_config())


def to_local(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(_local_tz()).isoformat(timespec="seconds")


# ------------------------------------------------------------------ principal -> user
def _users():
    if time.time() - _users_cache["at"] > USERS_TTL_S:
        by_arn, ids, kw = {}, set(), {"ProjectionExpression": "user_id, iam_principal_arn"}
        tbl = ddb.table("Users")
        while True:
            r = tbl.scan(**kw)
            for u in r.get("Items", []):
                ids.add(u["user_id"])
                if u.get("iam_principal_arn"):
                    by_arn[u["iam_principal_arn"]] = u["user_id"]
            if "LastEvaluatedKey" not in r:
                break
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
        _users_cache.update(at=time.time(), by_arn=by_arn, ids=ids)
    return _users_cache


def _role_arn(arn: str | None) -> str | None:
    """arn:aws:sts::123:assumed-role/Name/session -> arn:aws:iam::123:role/Name"""
    m = re.match(r"^arn:(aws[\w-]*):sts::(\d+):assumed-role/([^/]+)/", arn or "")
    return f"arn:{m.group(1)}:iam::{m.group(2)}:role/{m.group(3)}" if m else None


def map_principal(identity: dict) -> tuple[str, str | None]:
    """Users.iam_principal_arn lookup. Returns (user_id, principal_arn); unknown principals keep their ARN."""
    u = _users()
    arn = identity.get("arn")
    issuer = ((identity.get("sessionContext") or {}).get("sessionIssuer") or {}).get("arn")
    for cand in (arn, issuer, _role_arn(arn)):
        if cand and cand in u["by_arn"]:
            return u["by_arn"][cand], issuer or _role_arn(arn) or arn
    session = (arn or "").rsplit("/", 1)[-1]
    if session in u["ids"]:
        return session, issuer or arn
    return f"unmapped:{arn or identity.get('principalId') or 'unknown'}", arn


def _device(user_agent: str | None) -> str | None:
    return "ua-" + hashlib.sha256(user_agent.encode()).hexdigest()[:8] if user_agent else None


def _blank(**kw):
    e = {k: None for k in ("scenario_id", "principal_arn", "object_id", "customer_id", "data_class", "purpose", "bytes",
                           "amount_inr", "ip", "city", "device_id", "role", "destination", "resource_arn", "raw_ref")}
    e["is_replay"] = False
    e.update(kw)
    return e


# ------------------------------------------------------------------ mappers
def from_raw(detail: dict) -> dict:
    ev = dict(detail)
    if ev.get("ts"):
        ev["ts"] = to_local(ev["ts"])
    return ev


def from_cloudtrail(detail: dict) -> dict | None:
    name = detail.get("eventName")
    req = detail.get("requestParameters") or {}
    uid, principal = map_principal(detail.get("userIdentity") or {})
    base = _blank(event_id=f"ct-{detail.get('eventID')}", ts=to_local(detail["eventTime"]), source="cloudtrail",
                  user_id=uid, principal_arn=principal, ip=detail.get("sourceIPAddress"),
                  device_id=_device(detail.get("userAgent")))
    role = _role_arn((detail.get("userIdentity") or {}).get("arn"))
    if name == "GetObject":
        kyc = os.environ.get("KYC_BUCKET")
        if not kyc or req.get("bucketName") != kyc:
            return None  # only data events on the KYC document bucket are monitored
        m = KEY_RX.match(req.get("key", ""))
        if not m:
            return None
        bytes_out = (detail.get("additionalEventData") or {}).get("bytesTransferredOut")
        return dict(base, action="DOWNLOAD", object_id=m.group("name"), customer_id=m.group("cid"), data_class="KYC",
                    bytes=int(bytes_out) if bytes_out else None, role=role.rsplit("/", 1)[-1] if role else None,
                    resource_arn=f"arn:aws:s3:::{kyc}/{req.get('key')}")
    if name == "AssumeRole":
        target = (req.get("roleArn") or "").rsplit("/", 1)[-1] or None
        return dict(base, action="ASSUME_ROLE", role=target, resource_arn=req.get("roleArn"))
    if name in ("StopLogging", "DeleteTrail"):
        return dict(base, action="LOGGING_CHANGE", resource_arn=req.get("name"))
    if name == "PutBucketLogging":
        status = req.get("BucketLoggingStatus") or {}
        if "LoggingEnabled" in status:
            return None  # logging switched on or changed target: not tampering
        return dict(base, action="LOGGING_CHANGE", resource_arn=f"arn:aws:s3:::{req.get('bucketName')}")
    if name == "ConsoleLogin":
        return from_signin(detail)
    return None


def from_signin(detail: dict) -> dict | None:
    if (detail.get("responseElements") or {}).get("ConsoleLogin") not in (None, "Success"):
        return None
    uid, principal = map_principal(detail.get("userIdentity") or {})
    return _blank(event_id=f"ct-{detail.get('eventID')}", ts=to_local(detail["eventTime"]), source="cloudtrail",
                  user_id=uid, principal_arn=principal, action="LOGIN", ip=detail.get("sourceIPAddress"),
                  device_id=_device(detail.get("userAgent")))


def from_guardduty(event: dict) -> dict:
    """Normalized but not scored (GuardDuty is not in our scoring)."""
    d = event.get("detail") or {}
    key = (d.get("resource") or {}).get("accessKeyDetails") or {}
    user_id, principal = "svc-aws-guardduty", None
    if key.get("userName"):
        u = _users()
        hit = next(((a, i) for a, i in u["by_arn"].items() if a.rsplit("/", 1)[-1] == key["userName"]), None)
        if hit:
            principal, user_id = hit
    return _blank(event_id=f"gd-{d.get('id')}-{d.get('updatedAt', '')}", ts=to_local(d.get("updatedAt") or event["time"]),
                  source="guardduty", user_id=user_id, principal_arn=principal, action="GUARDDUTY_FINDING",
                  resource_arn=d.get("arn"), ip=((d.get("service") or {}).get("action") or {}).get("awsApiCallAction", {})
                  .get("remoteIpDetails", {}).get("ipAddressV4"))


def write_posture(control_id, status, resource_arn, rule, ts, source="config"):
    ddb.put_item("Posture", {"control_id": control_id, "source": source, "status": status, "resource_arn": resource_arn,
                             "rule": rule, "last_evaluated": ts})


def from_config(event: dict) -> dict | None:
    d = event.get("detail") or {}
    res = d.get("newEvaluationResult") or {}
    rule, rid, rtype = d.get("configRuleName"), d.get("resourceId"), d.get("resourceType")
    ts = to_local(res.get("resultRecordedTime") or event["time"])
    arn = f"arn:aws:s3:::{rid}" if rtype == "AWS::S3::Bucket" else (d.get("resourceArn") or rid)
    status = res.get("complianceType")
    write_posture(f"config:{rule}:{rid}", status, arn, rule, ts)
    if status != "NON_COMPLIANT":
        return None
    kyc = os.environ.get("KYC_BUCKET")
    eid = "cfg-" + hashlib.sha256(f"{rule}|{rid}|{ts}".encode()).hexdigest()[:16]
    return _blank(event_id=eid, ts=ts, source="config", user_id="svc-aws-config", action="CONFIG_NONCOMPLIANT",
                  resource_arn=arn, data_class="KYC" if kyc and rid == kyc else "NONE")


MAPPERS = {
    "AWS API Call via CloudTrail": lambda e: from_cloudtrail(e.get("detail") or {}),
    "AWS Console Sign In via CloudTrail": lambda e: from_signin(e.get("detail") or {}),
    "GuardDuty Finding": from_guardduty,
    "Config Rules Compliance Change": from_config,
    "Raw Activity": lambda e: from_raw(e.get("detail") or {}),
}


# ------------------------------------------------------------------ pipeline
def raw_key(ev: dict) -> str:
    d = datetime.fromisoformat(ev["ts"])
    return f"{d:%Y/%m/%d}/{ev['event_id']}.json"


def event_item(ev: dict) -> dict:
    """Events row. Null attributes are left out (GSI key attributes must not be NULL)."""
    item = {k: v for k, v in ev.items() if v is not None}
    item["sk"] = f"{ev['ts']}#{ev['event_id']}"
    return item


def process(ev: dict, raw: dict) -> dict:
    errs = schema.errors("event", ev)
    if errs:
        log_json("WARN", "event rejected", event_id=ev.get("event_id"), errors=errs[:5])
        return {"status": "REJECTED", "errors": errs[:5]}
    if ev.get("action") == "CONFIG_NONCOMPLIANT" and ev.get("source") != "config":  # simulated finding: keep Posture in step
        write_posture(f"config:simulated:{ev.get('resource_arn')}", "NON_COMPLIANT", ev.get("resource_arn"),
                      "simulated", ev["ts"], source="simulator")
    bucket = os.environ.get("RAW_BUCKET")
    if bucket:
        key = raw_key(ev)
        ev["raw_ref"] = f"s3://{bucket}/{key}"
    if not ddb.put_if_absent("Events", event_item(ev), "sk"):
        log_json("INFO", "duplicate dropped", event_id=ev["event_id"])
        return {"status": "DUPLICATE", "event_id": ev["event_id"]}
    try:
        if bucket:
            import boto3
            boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=json.dumps(raw, default=str).encode(),
                                          ContentType="application/json")
        events.put_event("Normalized Event", ev)
    except Exception:
        # undo the insert so the bus retry is not dropped as a duplicate
        ddb.table("Events").delete_item(Key={"user_id": ev["user_id"], "sk": event_item(ev)["sk"]})
        raise
    log_json("INFO", "normalized", event_id=ev["event_id"], action=ev["action"], user_id=ev["user_id"])
    return {"status": "OK", "event_id": ev["event_id"], "action": ev["action"]}


def handler(event, context=None):
    fn = MAPPERS.get(event.get("detail-type"))
    if not fn:
        return {"status": "SKIPPED", "reason": f"detail-type {event.get('detail-type')!r} not handled"}
    ev = fn(event)
    if ev is None:
        return {"status": "SKIPPED"}
    return process(ev, event)
