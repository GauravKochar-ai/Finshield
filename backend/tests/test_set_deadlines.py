from datetime import datetime

from conftest import fixture, load_fn, put_alert
from finshield import config, ddb, evidence

AID = "ALR-20261120-0007"


def test_deadlines_from_config_and_written_to_alert(aws):
    put_alert()
    raised = fixture("alert_raised_critical")
    out = load_fn("set_deadlines").handler({"alert_id": AID, "detected_at": raised["detected_at"], "execution": "e1"}, None)
    hours = {d["body"]: d["hours"] for d in config.load_config()["deadlines"]}
    start = datetime.fromisoformat(raised["detected_at"])
    for d in out["deadlines"]:
        assert (datetime.fromisoformat(d["due_at"]) - start).total_seconds() == hours[d["body"]] * 3600
    assert out["deadlines"] == fixture("alert_sc01")["deadlines"]
    assert ddb.get_item("Alerts", {"alert_id": AID})["deadlines"] == out["deadlines"]


def test_idempotent_per_execution(aws):
    put_alert()
    fn = load_fn("set_deadlines")
    fn.handler({"alert_id": AID, "detected_at": "2026-11-20T23:49:02+05:30", "execution": "e1"}, None)
    fn.handler({"alert_id": AID, "detected_at": "2026-11-20T23:49:02+05:30", "execution": "e1"}, None)
    assert [e["type"] for e in evidence.chain(AID)] == ["DEADLINES_SET"]


def test_detected_at_falls_back_to_alert(aws):
    put_alert()
    out = load_fn("set_deadlines").handler({"alert_id": AID}, None)
    assert out["deadlines"][0]["due_at"] == "2026-11-21T05:49:02+05:30"
