"""test_runner (M7/M3): POST /v1/accuracy/run, or direct invoke.

1. Reset the scenario users (simulator {"reset": true}).
2. Fire every scenario at once through the simulator Lambda (scenarios use separate users).
3. Poll Alerts (and Counters <user>#score for logged-only scenarios) for up to accuracy_poll_seconds.
4. Score 7 normal days in-process with the same scoring code and count false alerts.
5. Write one AccuracyRuns row per scenario plus NORMAL-7D, return {run_id, ran_at, passed, total, ...}.
Fits the 300 s Lambda timeout: poll budget 90 s, normal days about 2 s.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from finshield import ddb, scoring
from finshield.config import get_setting, load_config
from finshield.ddb import Key
from finshield.stub import log_json

POLL_INTERVAL_S = 3


def _invoke_simulator(payload):
    import boto3
    r = boto3.client("lambda").invoke(FunctionName=os.environ["SIMULATOR_FUNCTION_NAME"],
                                      Payload=json.dumps(payload).encode())
    body = json.loads(r["Payload"].read() or b"{}")
    if r.get("FunctionError"):
        raise RuntimeError(f"simulator failed: {body}")
    return body


INVOKE = _invoke_simulator  # tests replace this with an in-process pipeline


def _scenarios():
    try:
        import finshield
        d = Path(finshield.__file__).resolve().parent / "scenarios"
        if not d.is_dir():
            raise FileNotFoundError
    except FileNotFoundError:
        d = Path(os.environ.get("SCENARIO_DIR") or Path(__file__).resolve().parents[3] / "simulator" / "scenarios")
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("SC-*.json"))]


def _seedgen():
    try:
        from finshield import seedgen  # copied into the layer by `make layer`
        return seedgen
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "simulator" / "seed"))
        import generate
        return generate


def observe(cfg, sc, sent_ms):
    uid = sc["user_id"]
    alerts = ddb.query("Alerts", Key("user_id").eq(uid), index="user-detected-index")
    best = ddb.get_item("Counters", {"pk": f"{uid}#score", "bucket_start": "max"}, consistent=True) or {}
    top = max(alerts, key=lambda a: a["score"], default=None)
    score = max([int(a["score"]) for a in alerts] + [int(best.get("score", 0))])
    level = top["severity"] if top else scoring.level_name(cfg, score)
    tta = None
    if top:
        tta = max(0, int(scoring.t(top["detected_at"]).timestamp() * 1000) - sent_ms)
    return {"scenario_id": sc["scenario_id"], "expected_level": sc["expected_level"], "actual_level": level,
            "expected_score": sc["expected_score"], "actual_score": int(score),
            "pass": level == sc["expected_level"] and int(score) == sc["expected_score"] and len(alerts) <= 1,
            "time_to_alert_ms": tta, "alerts_for_user": len(alerts)}


def normal_days_false_alerts(cfg) -> dict:
    g = _seedgen()
    from finshield import baselines
    now = datetime.now(scoring.tz_offset(cfg))
    users = g.make_users()
    by_id = {u["user_id"]: u for u in users}
    base = baselines.compute(cfg, users, g.history(users, now), now.isoformat(timespec="seconds"))
    ctx = {"approvals": g.make_approvals(now), "consent": {c["customer_id"]: c for c in g.make_consent(now)},
           "customers": {c["customer_id"]: c for c in g.make_customers(now)}}
    seen, alerting, n = {}, set(), 0
    for day in g.accuracy_normal_days(users, now):
        for e in day:
            n += 1
            evs = seen.setdefault(e["user_id"], [])
            evs.append(e)
            u = by_id[e["user_id"]]
            r = scoring.score(cfg, u, base.get(u["user_id"]), base.get(f"team:{u['team']}"), evs, e["ts"], ctx)
            if r["severity"]:
                alerting.add((e["user_id"], e["ts"][:13]))  # one alert per user per hour at most
    return {"events": n, "false_alerts": len(alerting)}


def run():
    cfg = load_config()
    now = datetime.now(scoring.tz_offset(cfg))
    run_id = now.strftime("RUN-%Y%m%d-%H%M%S")
    ran_at = now.isoformat(timespec="seconds")
    budget = int(get_setting("accuracy_poll_seconds", "90"))
    scs = _scenarios()
    INVOKE({"reset": True})
    sent_ms = int(time.time() * 1000)
    with ThreadPoolExecutor(max_workers=len(scs)) as pool:
        list(pool.map(lambda s: INVOKE({"scenario_id": s["scenario_id"]}), scs))
    deadline = time.time() + budget
    rows = {}
    while True:
        rows = {s["scenario_id"]: observe(cfg, s, sent_ms) for s in scs}
        if all(r["pass"] for r in rows.values()) or time.time() >= deadline:
            break
        time.sleep(POLL_INTERVAL_S)
    normal = normal_days_false_alerts(cfg)
    out_rows = [rows[s["scenario_id"]] for s in scs]
    with ddb.table("AccuracyRuns").batch_writer() as bw:
        for r in out_rows:
            bw.put_item(Item=ddb.to_ddb({"run_id": run_id, "ran_at": ran_at, **r}))
        bw.put_item(Item=ddb.to_ddb({"run_id": run_id, "scenario_id": "NORMAL-7D", "ran_at": ran_at,
                                     "expected_level": "LOGGED", "false_alerts": normal["false_alerts"],
                                     "events": normal["events"], "pass": normal["false_alerts"] == 0}))
    result = {"run_id": run_id, "ran_at": ran_at, "passed": sum(r["pass"] for r in out_rows), "total": len(out_rows),
              "false_alerts_normal_days": normal["false_alerts"],
              "rows": [{k: r[k] for k in ("scenario_id", "expected_level", "actual_level", "expected_score", "actual_score",
                                          "pass", "time_to_alert_ms")} for r in out_rows]}
    log_json("INFO", "accuracy run", run_id=run_id, passed=result["passed"], total=result["total"],
             false_alerts=normal["false_alerts"])
    return result


def handler(event, context=None):
    if not (isinstance(event, dict) and "routeKey" in event):
        return run()
    claims = ((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt", {}).get("claims", {})
    groups = claims.get("cognito:groups") or []
    if isinstance(groups, str):
        groups = groups.strip("[]").replace(",", " ").split()
    if "Admin" not in groups:
        body = {"data": None, "error": {"code": "FORBIDDEN", "message": "Admin group required"}}
        return {"statusCode": 403, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}
    body = {"data": run(), "error": None}
    return {"statusCode": 200, "headers": {"content-type": "application/json"}, "body": json.dumps(body, default=str)}
