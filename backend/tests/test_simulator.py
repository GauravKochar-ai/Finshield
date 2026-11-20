"""simulator: GuardDuty sample findings and a reset that releases LIVE containment before deleting alerts."""
import io
import json

from conftest import fixture, load_fn, put_alert

ADMIN = {"authorizer": {"jwt": {"claims": {"cognito:groups": "[Admin]"}}}}


def _http(body):
    return {"routeKey": "POST /v1/simulate", "requestContext": ADMIN, "body": json.dumps(body)}


class FakeGuardDuty:
    def __init__(self, detectors):
        self.detectors, self.calls = detectors, []

    def list_detectors(self):
        return {"DetectorIds": self.detectors}

    def create_sample_findings(self, **kw):
        self.calls.append(kw)
        return {}


class FakeLambda:
    def __init__(self):
        self.calls = []

    def invoke(self, **kw):
        self.calls.append(kw)
        return {"StatusCode": 200, "Payload": io.BytesIO(b"{}")}


def test_guardduty_sample_with_a_detector_returns_events_sent_3(aws, monkeypatch):
    sim = load_fn("simulator")
    gd = FakeGuardDuty(["det-1"])
    monkeypatch.setattr(sim, "guardduty_client", lambda: gd)
    r = sim.handler(_http({"guardduty_sample": True}))
    assert r["statusCode"] == 200
    assert json.loads(r["body"]) == {"data": {"accepted": True, "scenario_id": None, "events_sent": 3}, "error": None}
    assert gd.calls == [{"DetectorId": "det-1", "FindingTypes": sim.GUARDDUTY_SAMPLE_TYPES}]


def test_guardduty_sample_without_a_detector_is_501(aws, monkeypatch):
    sim = load_fn("simulator")
    monkeypatch.setattr(sim, "guardduty_client", lambda: FakeGuardDuty([]))
    r = sim.handler(_http({"guardduty_sample": True}))
    body = json.loads(r["body"])
    assert r["statusCode"] == 501 and body["error"]["code"] == "NOT_IMPLEMENTED"
    assert "no GuardDuty detector" in body["error"]["message"]


def test_reset_releases_only_live_contained_alerts_then_deletes_them(aws, monkeypatch):
    from finshield import ddb
    sim = load_fn("simulator")
    fake = FakeLambda()
    monkeypatch.setattr(sim, "lambda_client", lambda: fake)
    monkeypatch.setenv("RELEASE_FUNCTION_NAME", "finshield-dev-release")
    live = fixture("alert_sc01")["containment"]  # LIVE, OK entries
    put_alert(status="LOCKED", containment=live)
    put_alert(alert_id="ALR-20261120-0002", status="RELEASED", containment=live)
    put_alert(alert_id="ALR-20261120-0003", status="CONTAINED",
              containment=[{**c, "mode": "DRY_RUN"} for c in live])
    ddb.put_item("Counters", {"pk": "alert_seq", "bucket_start": "20261120", "n": 7})

    out = sim.handler({"reset": True, "scenario_id": "SC-01"})

    assert [json.loads(c["Payload"]) for c in fake.calls] == [{"alert_id": fixture("alert_sc01")["alert_id"], "actor": "simulator-reset"}]
    assert fake.calls[0]["FunctionName"] == "finshield-dev-release" and fake.calls[0]["InvocationType"] == "RequestResponse"
    assert out["deleted"]["released"] == 1 and out["deleted"]["alerts"] == 3
    assert ddb.get_item("Alerts", {"alert_id": fixture("alert_sc01")["alert_id"]}) is None
    assert ddb.get_item("Counters", {"pk": "alert_seq", "bucket_start": "20261120"})["n"] == 7


def test_reset_keeps_going_when_release_fails(aws, monkeypatch):
    from finshield import ddb
    sim = load_fn("simulator")

    class Broken:
        def invoke(self, **kw):
            raise RuntimeError("boom")

    monkeypatch.setattr(sim, "lambda_client", lambda: Broken())
    monkeypatch.setenv("RELEASE_FUNCTION_NAME", "finshield-dev-release")
    put_alert(status="LOCKED", containment=fixture("alert_sc01")["containment"])
    out = sim.handler({"reset": True, "scenario_id": "SC-01"})
    assert out["deleted"]["alerts"] == 1
    assert ddb.get_item("Alerts", {"alert_id": fixture("alert_sc01")["alert_id"]}) is None
