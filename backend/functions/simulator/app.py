"""simulator (M7/M3): replay a scenario file as Raw Activity, or reset the scenario users.

POST /v1/simulate {"scenario_id":"SC-01"} or direct invoke with the same payload.
  Each event gets the scenario's clock time on today or yesterday (local time, whichever keeps the whole
  scenario in the past), so off-hours signs still fire: 23:40 stays 23:40. Event ids get a run tag.
  Events go to the bus as Raw Activity in batches of 10.
{"reset": true} deletes Alerts, Counters and replayed Events for every scenario user
  (or only the given scenario's user when scenario_id is also set). Normal history is kept.
HTTP calls need the Admin group and answer in the {data, error} envelope.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from boto3.dynamodb.conditions import Attr

from finshield import ddb, events, schema
from finshield.config import load_config
from finshield.ddb import Key
from finshield.scoring import tz_offset
from finshield.stub import log_json


def scenario_dir() -> Path:
    if os.environ.get("SCENARIO_DIR"):
        return Path(os.environ["SCENARIO_DIR"])
    import finshield
    bundled = Path(finshield.__file__).resolve().parent / "scenarios"  # copied in by `make layer`
    if bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parents[3] / "simulator" / "scenarios"


def list_scenarios() -> list[str]:
    return sorted(p.stem for p in scenario_dir().glob("SC-*.json"))


def load_scenario(sid: str) -> dict:
    p = scenario_dir() / f"{sid}.json"
    if not p.is_file():
        raise KeyError(sid)
    return json.loads(p.read_text(encoding="utf-8"))


def anchor(sc: dict, now: datetime) -> datetime:
    """Start time on today, or yesterday when today's run would end in the future."""
    hh, mm, ss = (int(x) for x in sc["start_time_ist"].split(":"))
    start = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
    span = max(e["offset_seconds"] for e in sc["events"])
    if start + timedelta(seconds=span) > now:
        start -= timedelta(days=1)
    return start


def build_events(sc: dict, now: datetime, run_tag: str, principal_arn: str | None = None) -> list[dict]:
    start = anchor(sc, now)
    out = []
    for raw in sc["events"]:
        e = {k: v for k, v in raw.items() if k != "offset_seconds"}
        e["event_id"] = f"{raw['event_id']}-{run_tag}"
        e["ts"] = (start + timedelta(seconds=raw["offset_seconds"])).isoformat(timespec="seconds")
        e["user_id"] = raw.get("user_id", sc["user_id"])
        e["scenario_id"] = sc["scenario_id"]
        e["is_replay"] = True
        e.setdefault("source", "simulator")
        if principal_arn and e.get("principal_arn"):
            e["principal_arn"] = principal_arn
        schema.validate("event", e)
        out.append(e)
    return out


def run(sid: str) -> dict:
    sc = load_scenario(sid)
    cfg = load_config()
    now = datetime.now(tz_offset(cfg))
    tag = now.strftime("%H%M%S") + secrets.token_hex(2)
    user = ddb.get_item("Users", {"user_id": sc["user_id"]}) or {}
    evs = build_events(sc, now, tag, user.get("iam_principal_arn"))
    events.put_events([("Raw Activity", e, "finshield.simulator") for e in evs])  # batches of 10 inside
    log_json("INFO", "scenario sent", scenario_id=sid, events=len(evs), run_tag=tag)
    return {"accepted": True, "scenario_id": sid, "events_sent": len(evs), "run_tag": tag,
            "user_id": sc["user_id"], "first_ts": evs[0]["ts"], "last_ts": evs[-1]["ts"]}


def _delete_all(logical, keys):
    tbl = ddb.table(logical)
    with tbl.batch_writer() as bw:
        for k in keys:
            bw.delete_item(Key=k)
    return len(keys)


def reset(sid: str | None = None) -> dict:
    users = sorted({load_scenario(s)["user_id"] for s in ([sid] if sid else list_scenarios())})
    counts = {"alerts": 0, "counters": 0, "events": 0}
    for uid in users:
        alerts = ddb.query("Alerts", Key("user_id").eq(uid), index="user-detected-index")
        counts["alerts"] += _delete_all("Alerts", [{"alert_id": a["alert_id"]} for a in alerts])
        for pk in (f"{uid}#15m", f"{uid}#1d", f"{uid}#alert", f"{uid}#score"):
            rows = ddb.query("Counters", Key("pk").eq(pk), ProjectionExpression="pk, bucket_start")
            counts["counters"] += _delete_all("Counters", [{"pk": r["pk"], "bucket_start": r["bucket_start"]} for r in rows])
        rows = ddb.query("Events", Key("user_id").eq(uid), FilterExpression=Attr("is_replay").eq(True),
                         ProjectionExpression="user_id, sk")
        counts["events"] += _delete_all("Events", [{"user_id": r["user_id"], "sk": r["sk"]} for r in rows])
    log_json("INFO", "reset", users=users, **counts)
    return {"reset": True, "users": users, "deleted": counts}


# ------------------------------------------------------------------ handler
def _groups(event) -> set[str]:
    claims = ((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt", {}).get("claims", {})
    g = claims.get("cognito:groups") or []
    if isinstance(g, str):
        g = [x for x in g.strip("[]").replace(",", " ").split() if x]
    return set(g)


def _http(status, data=None, code=None, message=None):
    body = {"data": data, "error": None if code is None else {"code": code, "message": message}}
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body, default=str)}


def handle(body: dict) -> dict:
    if body.get("reset"):
        return reset(body.get("scenario_id"))
    if body.get("guardduty_sample"):
        raise NotImplementedError("guardduty_sample is P2 and not built yet")
    sid = body.get("scenario_id")
    if not sid:
        raise ValueError("scenario_id or reset is required")
    return run(sid)


def handler(event, context=None):
    if not (isinstance(event, dict) and "routeKey" in event):
        return handle(event or {})
    if "Admin" not in _groups(event):
        return _http(403, code="FORBIDDEN", message="Admin group required")
    try:
        body = json.loads(event.get("body") or "{}")
    except ValueError:
        return _http(400, code="BAD_REQUEST", message="body is not valid JSON")
    if set(body) - {"scenario_id", "guardduty_sample", "reset"}:
        return _http(400, code="BAD_REQUEST", message="unknown field")
    try:
        out = handle(body)
    except KeyError as exc:
        return _http(404, code="NOT_FOUND", message=f"unknown scenario {exc.args[0]}")
    except NotImplementedError as exc:
        return _http(501, code="NOT_IMPLEMENTED", message=str(exc))
    except (ValueError, schema.SchemaError) as exc:
        return _http(400, code="BAD_REQUEST", message=str(exc)[:300])
    if out.get("reset"):
        return _http(200, {"accepted": True, "scenario_id": body.get("scenario_id"), "events_sent": 0})
    return _http(200, {k: out[k] for k in ("accepted", "scenario_id", "events_sent")})
