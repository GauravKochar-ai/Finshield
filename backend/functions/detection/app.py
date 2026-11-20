"""detection (M3): Normalized Event -> counters, signs S1-S11, exceptions E1-E3, one open alert per user.

For each event:
  1. Counters: atomic ADD per 15-minute and daily bucket (once per event_id), plus per-device daily counters.
  2. Read the user's events from Events (24 h back for the slow-leak sign, 60 min forward so a late event
     re-scores its window), the user, both baselines, approvals, and only the Consent/Customers rows needed.
  3. finshield.scoring.score() at the event time and at the latest event after it; keep the higher result.
  4. Below MEDIUM: no alert record (the score is kept in Counters <user>#score for the accuracy runner).
  5. Upsert the open alert (status not CLOSED, detected within incident_window_minutes): a pointer item
     Counters <user>#alert / open is claimed with a conditional put so parallel invocations never create two
     alerts; the alert itself is created with attribute_not_exists and raised only with "score < :new".
  6. Emit Alert Raised only when severity goes up. Publish FinShield/TimeToDetectMs (EMF log line).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

from botocore.exceptions import ClientError

from finshield import ddb, events, schema, scoring
from finshield.config import load_config
from finshield.ddb import ConditionFailed, Key
from finshield.stub import log_json

CACHE_TTL_S = 60
_cache: dict = {}
ALERT_ROW_WAIT_S = 3.0
MAX_EVENT_IDS = 500  # DynamoDB item size guard; the full list is in Events (scenario-ts-index)


def _cached(key, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


def _now_local(cfg) -> datetime:
    return datetime.now(scoring.tz_offset(cfg))


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


# ------------------------------------------------------------------ counters
def mark_counted(ev) -> bool:
    """True the first time this event is seen by detection (EventBridge delivers at least once)."""
    try:
        ddb.update_item("Events", {"user_id": ev["user_id"], "sk": f"{ev['ts']}#{ev['event_id']}"},
                        "SET counted_at = :t", {":t": int(time.time() * 1000)},
                        condition="attribute_exists(user_id) AND attribute_not_exists(counted_at)")
        return True
    except ConditionFailed:
        return False


def add_counters(cfg, ev):
    local = scoring.t(ev["ts"]).astimezone(scoring.tz_offset(cfg))
    minutes = cfg["signals"]["S1"]["window_minutes"]
    b15 = _iso(local.replace(minute=(local.minute // minutes) * minutes, second=0, microsecond=0))
    bday = local.date().isoformat()
    a = ev["action"]
    vals = {":d": int(a == "DOWNLOAD"), ":b": int(ev.get("bytes") or 0), ":m": int(a == "MFA_PUSH"),
            ":p": int(a == "PRESIGN"), ":one": 1}
    expr = "ADD downloads :d, bytes_total :b, mfa_pushes :m, presigns :p, events_total :one"
    if ev.get("customer_id"):
        vals[":c"] = {ev["customer_id"]}
        expr += ", customer_ids :c"
    for pk, bucket in ((f"{ev['user_id']}#15m", b15), (f"{ev['user_id']}#1d", bday)):
        ddb.update_item("Counters", {"pk": pk, "bucket_start": bucket}, expr, vals)
    if ev.get("device_id"):  # per-device counters across accounts (P2)
        ddb.update_item("Counters", {"pk": f"device#{ev['device_id']}#1d", "bucket_start": bday},
                        "ADD events_total :one, user_ids :u", {":one": 1, ":u": {ev["user_id"]}})


def record_score(uid, result, ev):
    """Highest score seen for the user (also below MEDIUM, so logged-only scenarios can be measured)."""
    try:
        ddb.update_item("Counters", {"pk": f"{uid}#score", "bucket_start": "max"},
                        "SET score = :s, severity_level = :l, signals = :g, exceptions_applied = :x, scenario_id = :sc, "
                        "updated_at = :u",
                        {":s": result["score"], ":l": result["severity"] or "LOGGED", ":g": result["signals"],
                         ":x": result["exceptions_applied"], ":sc": result.get("scenario_id"), ":u": ev["ts"]},
                        condition="attribute_not_exists(score) OR score < :s")
    except ConditionFailed:
        pass


# ------------------------------------------------------------------ reads
def load_context(cfg, uid, ev):
    user = _cached(("user", uid), lambda: ddb.get_item("Users", {"user_id": uid})) or {"user_id": uid}
    base = _cached(("base", uid), lambda: ddb.get_item("Baselines", {"subject_id": uid})) or {}
    team = _cached(("base", f"team:{user.get('team')}"),
                   lambda: ddb.get_item("Baselines", {"subject_id": f"team:{user.get('team')}"})) or {}
    approvals = _cached(("appr", uid), lambda: ddb.query("Approvals", Key("subject_id").eq(uid), index="subject-index"))
    t = scoring.t(ev["ts"])
    back = _iso(t - timedelta(hours=cfg["signals"]["S2"]["window_hours"]))
    ahead = _iso(t + timedelta(minutes=cfg["incident_window_minutes"]))
    evs = ddb.query("Events", Key("user_id").eq(uid) & Key("sk").between(back, ahead + "#~"), consistent=True)
    if not any(e["event_id"] == ev["event_id"] for e in evs):
        evs.append(ev)  # direct invocation without a stored row
    return user, base, team, approvals, evs


def _batch_get(logical, key_name, ids):
    out, todo = {}, []
    for i in ids:
        hit = _cache.get((logical, i))
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            if hit[1]:
                out[i] = hit[1]
        else:
            todo.append(i)
    name = ddb.table_name(logical)
    for n in range(0, len(todo), 100):
        keys = [{key_name: i} for i in todo[n:n + 100]]
        req = {name: {"Keys": keys}}
        found = {}
        while req:
            r = ddb.resource().batch_get_item(RequestItems=req)
            for item in r.get("Responses", {}).get(name, []):
                found[item[key_name]] = ddb.from_ddb(item)
            req = r.get("UnprocessedKeys") or None
        for k in keys:
            _cache[(logical, k[key_name])] = (time.time(), found.get(k[key_name]))
        out.update(found)
    return out


def evaluate(cfg, user, base, team, approvals, evs, ev):
    """Score at the event time, and again at the latest event in the following window (late events)."""
    times = [ev["ts"]]
    later = [e["ts"] for e in evs if e["ts"] > ev["ts"]]
    if later:
        times.append(max(later))
    best = None
    for ts in times:
        need = scoring.needs(cfg, user, evs, ts)
        ctx = {"approvals": approvals, "consent": _batch_get("Consent", "customer_id", sorted(need["consent"])),
               "customers": _batch_get("Customers", "customer_id", sorted(need["customers"]))}
        r = scoring.score(cfg, user, base, team, evs, ts, ctx)
        if best is None or r["score"] > best["score"]:
            best = r
    return best


# ------------------------------------------------------------------ alerts
def next_alert_id(cfg) -> str:
    day = _now_local(cfg).strftime("%Y%m%d")
    n = ddb.update_item("Counters", {"pk": "alert_seq", "bucket_start": day}, "ADD n :one", {":one": 1})["n"]
    return f"ALR-{day}-{int(n):04d}"


def deadlines(cfg, detected: datetime):
    return [{"body": d["body"], "due_at": _iso(detected + timedelta(hours=d["hours"]))} for d in cfg["deadlines"]]


def _alert_fields(res):
    return {"score": res["score"], "severity": res["severity"], "signals": res["signals"],
            "exceptions_applied": res["exceptions_applied"], "customers_affected": res["customers_affected"],
            "data_classes": res["data_classes"], "event_ids": res["event_ids"][-MAX_EVENT_IDS:]}


def claim_open_alert(cfg, uid, now):
    """Return (alert_id, created). The pointer item makes 'one open alert per user per window' atomic."""
    cutoff = _iso(now - timedelta(minutes=cfg["incident_window_minutes"]))
    key = {"pk": f"{uid}#alert", "bucket_start": "open"}
    ptr = ddb.get_item("Counters", key, consistent=True)
    if ptr and ptr["detected_at"] >= cutoff:
        row = ddb.get_item("Alerts", {"alert_id": ptr["alert_id"]}, consistent=True)
        if row is None or row.get("status") != "CLOSED":
            return ptr["alert_id"], False
    new_id = next_alert_id(cfg)
    cond = "attribute_not_exists(pk) OR detected_at < :cut"
    vals = {":cut": cutoff}
    if ptr:
        cond += " OR alert_id = :old"
        vals[":old"] = ptr["alert_id"]
    try:
        ddb.table("Counters").put_item(Item=ddb.to_ddb({**key, "alert_id": new_id, "detected_at": _iso(now)}),
                                       ConditionExpression=cond, ExpressionAttributeValues=vals)
        return new_id, True
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
    ptr = ddb.get_item("Counters", key, consistent=True)  # another invocation won the race
    return ptr["alert_id"], False


def create_alert(cfg, alert_id, uid, res, now):
    item = {"alert_id": alert_id, "user_id": uid, "principal_arn": res["principal_arn"], **_alert_fields(res),
            "status": "OPEN", "detected_at": _iso(now), "window_start": res["window_start"],
            "scenario_id": res["scenario_id"], "deadlines": deadlines(cfg, now), "containment": [], "ai": None,
            "ai_status": "PENDING", "execution_arn": None}
    schema.validate("alert", item)
    ddb.put_item("Alerts", item, ConditionExpression="attribute_not_exists(alert_id)")
    return item


def raise_alert(alert_id, res):
    """Conditional raise. Returns (old_row, new_row) or (None, None) when the stored score is not lower."""
    deadline = time.time() + ALERT_ROW_WAIT_S
    while True:
        cur = ddb.get_item("Alerts", {"alert_id": alert_id}, consistent=True)
        if cur is not None:
            break
        if time.time() > deadline:
            raise RuntimeError(f"alert {alert_id} row not written by the creating invocation")
        time.sleep(0.1)
    if cur["score"] >= res["score"]:
        return None, None
    new = {**cur, **_alert_fields(res)}
    schema.validate("alert", new)
    f = _alert_fields(res)
    names = {f"#{k}": k for k in f}
    values = {f":{k}": v for k, v in f.items()}
    try:
        old = ddb.table("Alerts").update_item(
            Key={"alert_id": alert_id}, UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in f),
            ConditionExpression="attribute_exists(alert_id) AND #score < :score",
            ExpressionAttributeNames=names, ExpressionAttributeValues=ddb.to_ddb(values), ReturnValues="ALL_OLD")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None, None
        raise
    return ddb.from_ddb(old.get("Attributes", {})), new


def alert_raised(alert, previous):
    detail = {k: alert.get(k) for k in ("alert_id", "severity", "score", "user_id", "principal_arn", "detected_at")}
    detail["previous_severity"] = previous
    events.put_event("Alert Raised", detail)
    return detail


def time_to_detect(ev, alert_id):
    ms = int(time.time() * 1000 - scoring.t(ev["ts"]).timestamp() * 1000)
    print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [
        {"Namespace": "FinShield", "Dimensions": [["Function"]], "Metrics": [{"Name": "TimeToDetectMs", "Unit": "Milliseconds"}]}]},
        "Function": "detection", "TimeToDetectMs": ms, "alert_id": alert_id, "event_id": ev["event_id"]}))
    return ms


# ------------------------------------------------------------------ handler
def process(ev):
    cfg = load_config()
    uid = ev["user_id"]
    if mark_counted(ev):
        add_counters(cfg, ev)
    user, base, team, approvals, evs = load_context(cfg, uid, ev)
    res = evaluate(cfg, user, base, team, approvals, evs, ev)
    record_score(uid, res, ev)
    out = {"user_id": uid, "event_id": ev["event_id"], "score": res["score"], "severity": res["severity"]}
    if not res["severity"]:
        return out
    now = _now_local(cfg)
    alert_id, created = claim_open_alert(cfg, uid, now)
    out["alert_id"] = alert_id
    if created:
        alert = create_alert(cfg, alert_id, uid, res, now)
        out["raised"] = alert_raised(alert, None)
        out["time_to_detect_ms"] = time_to_detect(ev, alert_id)
    else:
        old, new = raise_alert(alert_id, res)
        if new and scoring.LEVEL_ORDER[new["severity"]] > scoring.LEVEL_ORDER[old.get("severity")]:
            out["raised"] = alert_raised(new, old.get("severity"))
            out["time_to_detect_ms"] = time_to_detect(ev, alert_id)
    log_json("INFO", "scored", **{k: v for k, v in out.items() if k != "raised"})
    return out


def handler(event, context=None):
    if event.get("detail-type") not in (None, "Normalized Event"):
        return {"status": "SKIPPED"}
    return process(event.get("detail") or event)
