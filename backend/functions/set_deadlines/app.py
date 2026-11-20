"""set_deadlines: regulator readiness timers from detected_at, durations from contract/config.json.

Input  {alert_id, detected_at?, execution?}  (detected_at falls back to the alert record)
Output {alert_id, deadlines: [{body, due_at}]}
"""
from datetime import datetime, timedelta

from finshield import config, ddb, evidence
from finshield.log import log


def compute(detected_at: str) -> list[dict]:
    start = datetime.fromisoformat(detected_at)
    return [
        {"body": d["body"], "due_at": (start + timedelta(hours=d["hours"])).isoformat(timespec="seconds")}
        for d in config.load_config()["deadlines"]
    ]


def handler(event, context):
    alert_id = event["alert_id"]
    detected_at = event.get("detected_at")
    if not detected_at:
        alert = ddb.get_item("Alerts", {"alert_id": alert_id}) or {}
        detected_at = alert.get("detected_at")
    if not detected_at:
        raise ValueError(f"no detected_at for {alert_id}")
    deadlines = compute(detected_at)
    try:
        ddb.update_item("Alerts", {"alert_id": alert_id}, "SET deadlines = :d", {":d": deadlines}, condition="attribute_exists(alert_id)")
    except ddb.ConditionFailed:
        log("alert not found; deadlines recorded in evidence only", level="WARNING", alert_id=alert_id)
    execution = event.get("execution")
    evidence.append(
        alert_id, "DEADLINES_SET", "set_deadlines",
        {"detected_at": detected_at, "deadlines": deadlines, "note": "configured readiness timers"},
        dedup_key=f"{execution}:DEADLINES_SET" if execution else None,
    )
    log("deadlines set", alert_id=alert_id, deadlines=deadlines)
    return {"alert_id": alert_id, "deadlines": deadlines}
