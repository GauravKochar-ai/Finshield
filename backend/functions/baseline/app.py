"""baseline (M3): per-user and per-team baselines, hourly and on demand after seeding.

Reads every user's normal (non-replay) events from the last baselines.lookback_days, computes
finshield.baselines.compute() and writes one Baselines row per user and per team ("team:<team>").
Users with less than baselines.min_history_days days of history get their team's numbers.
Direct invoke payload (optional): {"user_ids": ["u-017"]} recomputes those users (teams always recomputed).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from finshield import baselines, ddb
from finshield.config import load_config
from finshield.ddb import Key
from finshield.scoring import tz_offset
from finshield.stub import log_json

FIELDS = "user_id, event_id, ts, #a, city, device_id, amount_inr, is_replay, scenario_id"


def _scan_users():
    out, kw, tbl = [], {}, ddb.table("Users")
    while True:
        r = tbl.scan(**kw)
        out += [ddb.from_ddb(i) for i in r.get("Items", [])]
        if "LastEvaluatedKey" not in r:
            return out
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def run(user_ids=None):
    cfg = load_config()
    now = datetime.now(tz_offset(cfg))
    since = (now - timedelta(days=cfg["baselines"]["lookback_days"])).isoformat(timespec="seconds")
    users = _scan_users()
    evs = []
    for u in users:
        evs += ddb.query("Events", Key("user_id").eq(u["user_id"]) & Key("sk").gte(since),
                         ProjectionExpression=FIELDS, ExpressionAttributeNames={"#a": "action"})
    rows = baselines.compute(cfg, users, evs, now.isoformat(timespec="seconds"))
    keep = set(user_ids or []) | {k for k in rows if k.startswith("team:")} if user_ids else set(rows)
    with ddb.table("Baselines").batch_writer() as bw:
        for k in sorted(keep):
            bw.put_item(Item=ddb.to_ddb(rows[k]))
    team_fallback = sorted(k for k in keep if rows[k].get("kind") == "user" and rows[k]["source"] == "team")
    log_json("INFO", "baselines written", rows=len(keep), events=len(evs), team_fallback=team_fallback)
    return {"status": "OK", "rows": len(keep), "events": len(evs), "team_fallback": team_fallback}


def handler(event, context=None):
    return run((event or {}).get("user_ids"))
