"""Detection pipeline on moto: every scenario file goes simulator -> normalizer -> detection, and must give the
expected score and level from the file, with one alert per user and one Alert Raised per severity step.
Also: normalizer mappings, counters, dedup, late events, baseline Lambda, test_runner end to end."""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
moto = pytest.importorskip("moto")
boto3 = pytest.importorskip("boto3")
sys.path.insert(0, str(ROOT / "simulator" / "seed"))

SCENARIOS = sorted(p.stem for p in (ROOT / "simulator" / "scenarios").glob("SC-*.json"))
KYC_BUCKET, RAW_BUCKET = "test-kyc-docs", "test-raw-events"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"fn_{name}", ROOT / "backend" / "functions" / name / "app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _L(yaml.SafeLoader):
    pass


_L.add_multi_constructor("!", lambda loader, suffix, node: None)


def _tables():
    t = yaml.load((ROOT / "infra" / "template.yaml").read_text(), Loader=_L)
    for name, res in t["Resources"].items():
        if res["Type"] == "AWS::DynamoDB::Table":
            p = res["Properties"]
            kw = {"AttributeDefinitions": p["AttributeDefinitions"], "KeySchema": p["KeySchema"], "BillingMode": "PAY_PER_REQUEST"}
            if p.get("GlobalSecondaryIndexes"):
                kw["GlobalSecondaryIndexes"] = [{k: g[k] for k in ("IndexName", "KeySchema", "Projection")}
                                                for g in p["GlobalSecondaryIndexes"]]
            yield name[: -len("Table")], kw


class Bus:
    """Captures put_events and lets a test drive the next hop by hand."""

    def __init__(self):
        self.sent = []

    def put_events(self, entries, bus_name=None):
        self.sent += [(dt, json.loads(json.dumps(d, default=str))) for dt, d, _src in entries]
        return [f"id-{len(self.sent)}-{i}" for i in range(len(entries))]

    def take(self, detail_type):
        out = [d for dt, d in self.sent if dt == detail_type]
        self.sent = [(dt, d) for dt, d in self.sent if dt != detail_type]
        return out


@pytest.fixture(scope="module")
def env():
    mp = pytest.MonkeyPatch()
    with moto.mock_aws():
        ddbc = boto3.client("dynamodb", region_name="ap-south-1")
        for logical, kw in _tables():
            mp.setenv(f"TABLE_{logical.upper()}", f"test-{logical}")
            ddbc.create_table(TableName=f"test-{logical}", **kw)
        s3 = boto3.client("s3", region_name="ap-south-1")
        for b in (KYC_BUCKET, RAW_BUCKET):
            s3.create_bucket(Bucket=b, CreateBucketConfiguration={"LocationConstraint": "ap-south-1"})
        mp.setenv("KYC_BUCKET", KYC_BUCKET)
        mp.setenv("RAW_BUCKET", RAW_BUCKET)
        mp.setenv("EVENT_BUS_NAME", "test-bus")
        mp.setenv("SIMULATOR_FUNCTION_NAME", "test-simulator")
        from finshield import ddb, events
        ddb.reset_resource()
        bus = Bus()
        mp.setattr(events, "put_events", bus.put_events)
        import generate
        now = datetime.now(generate.IST)
        data = generate.build(now)
        recent = [e for e in data["Events"] if e["ts"] >= (now - timedelta(days=3)).isoformat()]
        data["Events"] = recent  # the full 30 days only matter to the baseline test, which loads its own
        data.pop("KycFiles")
        generate.load(data, "test")
        fns = {n: _load(n) for n in ("normalizer", "detection", "simulator", "baseline", "test_runner")}
        yield {"bus": bus, "fn": fns, "data": data, "mp": mp, "now": now}
    mp.undo()


def pipeline(env, sid, shuffle_seed=None):
    """simulator -> normalizer -> detection, entirely in-process. Returns (simulator result, Alert Raised list)."""
    bus, fn = env["bus"], env["fn"]
    res = fn["simulator"].handler({"scenario_id": sid})
    raw = bus.take("Raw Activity")
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(raw)
    for d in raw:
        assert fn["normalizer"].handler({"detail-type": "Raw Activity", "detail": d})["status"] == "OK"
    for d in bus.take("Normalized Event"):
        fn["detection"].handler({"detail-type": "Normalized Event", "detail": d})
    return res, bus.take("Alert Raised")


def alerts_for(uid):
    from finshield import ddb
    from finshield.ddb import Key
    return ddb.query("Alerts", Key("user_id").eq(uid), index="user-detected-index")


def best_score(uid):
    from finshield import ddb
    return ddb.get_item("Counters", {"pk": f"{uid}#score", "bucket_start": "max"}) or {}


def scenario(sid):
    return json.loads((ROOT / "simulator" / "scenarios" / f"{sid}.json").read_text())


import os

# Full replays through moto are slow (hundreds of events each). Default run: two small scenarios end to end.
# RUN_SLOW=1 runs all 11 plus the out-of-order, redelivery and accuracy-runner checks.
SLOW = pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="slow moto replay; set RUN_SLOW=1")
FAST = ("SC-08", "SC-09")
ORDER = [pytest.param(s, marks=() if s in FAST else SLOW) for s in
         ["SC-01", "SC-01b", "SC-02", "SC-03", "SC-05"] + [x for x in SCENARIOS if x not in ("SC-01", "SC-01b", "SC-02", "SC-03", "SC-05")]]


@pytest.mark.parametrize("sid", ORDER)
def test_scenario_gives_expected_score_and_level(env, sid):
    sc = scenario(sid)
    env["fn"]["simulator"].handler({"reset": True, "scenario_id": sid})
    res, raised = pipeline(env, sid)
    assert res["events_sent"] == len(sc["events"])
    alerts = alerts_for(sc["user_id"])
    from finshield.scoring import LEVEL_ORDER
    if sc["expected_level"] == "LOGGED":
        assert alerts == [], "below 40 must not create an alert record"
        assert raised == []
        assert int(best_score(sc["user_id"])["score"]) == sc["expected_score"]
        return
    assert len(alerts) == 1, "exactly one alert per user per window"
    a = alerts[0]
    assert (a["score"], a["severity"]) == (sc["expected_score"], sc["expected_level"]), a["signals"]
    assert sum(s["points"] for s in a["signals"]) >= a["score"]
    steps = [r["severity"] for r in raised]
    assert steps[-1] == sc["expected_level"]
    assert [LEVEL_ORDER[s] for s in steps] == sorted({LEVEL_ORDER[s] for s in steps}), "one Alert Raised per severity step"
    assert raised[0]["previous_severity"] is None
    assert all(r["alert_id"] == a["alert_id"] for r in raised)
    from finshield import schema
    schema.validate("alert", a)


@SLOW
def test_sc01_matches_the_contract_fixture(env):
    env["fn"]["simulator"].handler({"reset": True, "scenario_id": "SC-01"})
    pipeline(env, "SC-01")
    a = alerts_for("u-017")[0]
    sig = {s["code"]: s for s in a["signals"]}
    assert {c: s["points"] for c, s in sig.items()} == {"S1": 40, "S3": 20, "S4": 15, "S5": 11, "S6": 10}
    assert sig["S1"]["facts"] == {"downloads_15m": 212, "baseline_p95": 2, "ratio": 106}
    assert sig["S3"]["facts"] == {"role": "KYC-Emergency", "covering_approval": False}
    assert sig["S5"]["facts"]["cities"] == ["Pune", "Delhi"] and sig["S5"]["facts"]["new_device"] == "d-new-77"
    assert sig["S6"]["facts"]["usual_hours"] == "09:00-18:00"
    assert a["customers_affected"] == 198 and a["data_classes"] == ["KYC"]
    assert a["alert_id"].startswith("ALR-") and a["status"] == "OPEN" and a["ai_status"] == "PENDING"
    assert [d["body"] for d in a["deadlines"]] == ["RBI", "CERT-In", "DPB"]


@SLOW
def test_out_of_order_delivery_still_gives_one_alert_and_96(env):
    env["fn"]["simulator"].handler({"reset": True, "scenario_id": "SC-01"})
    _res, raised = pipeline(env, "SC-01", shuffle_seed=7)
    alerts = alerts_for("u-017")
    assert len(alerts) == 1 and alerts[0]["score"] == 96
    assert raised[-1]["severity"] == "CRITICAL"


@SLOW
def test_redelivered_events_are_dropped_and_counters_count_once(env):
    from finshield import ddb
    from finshield.ddb import Key
    fn, bus = env["fn"], env["bus"]
    fn["simulator"].handler({"reset": True, "scenario_id": "SC-05"})
    fn["simulator"].handler({"scenario_id": "SC-05"})
    raw = bus.take("Raw Activity")
    for d in raw + raw[:5]:  # five redeliveries
        fn["normalizer"].handler({"detail-type": "Raw Activity", "detail": d})
    norm = bus.take("Normalized Event")
    assert len(norm) == len(raw)
    for d in norm + norm[:3]:  # detection redelivery
        fn["detection"].handler({"detail-type": "Normalized Event", "detail": d})
    rows = ddb.query("Counters", Key("pk").eq("u-011#1d"))
    assert sum(int(r["downloads"]) for r in rows) == 15
    assert len(rows[-1]["customer_ids"]) == 15


def test_reset_keeps_normal_history(env):
    from finshield import ddb
    from finshield.ddb import Key
    before = [e for e in ddb.query("Events", Key("user_id").eq("u-017")) if not e.get("is_replay")]
    env["fn"]["simulator"].handler({"reset": True})
    after = ddb.query("Events", Key("user_id").eq("u-017"))
    assert all(not e.get("is_replay") for e in after) and len(after) == len(before)
    assert alerts_for("u-017") == []


# ------------------------------------------------------------------ normalizer mappings
def _ct(name, **kw):
    d = {"eventName": name, "eventID": f"ev-{name}-{random.random()}", "eventTime": "2026-11-20T18:10:00Z",
         "sourceIPAddress": "49.36.1.2", "userAgent": "aws-cli/2",
         "userIdentity": {"type": "AssumedRole", "arn": "arn:aws:sts::000000000000:assumed-role/finshield-dev-demo-ops-admin/s1",
                          "sessionContext": {"sessionIssuer": {"arn": "arn:aws:iam::000000000000:role/finshield-dev-demo-ops-admin"}}}}
    d.update(kw)
    return {"detail-type": "AWS API Call via CloudTrail", "detail": d}


def _norm(env, ev):
    out = env["fn"]["normalizer"].handler(ev)
    got = env["bus"].take("Normalized Event")
    return out, (got[0] if got else None)


def test_cloudtrail_getobject_on_kyc_bucket_becomes_download(env):
    key = "kyc/C-10442/KYC-PAN-C-10442.png"
    out, ev = _norm(env, _ct("GetObject", requestParameters={"bucketName": KYC_BUCKET, "key": key},
                                additionalEventData={"bytesTransferredOut": 215000}))
    assert out["status"] == "OK"
    assert (ev["action"], ev["object_id"], ev["customer_id"], ev["data_class"]) == ("DOWNLOAD", "KYC-PAN-C-10442", "C-10442", "KYC")
    assert ev["user_id"] == "u-017" and ev["ts"].endswith("+05:30") and ev["ts"].startswith("2026-11-20T23:40")
    assert ev["raw_ref"].startswith(f"s3://{RAW_BUCKET}/2026/11/20/")
    obj = boto3.client("s3").get_object(Bucket=RAW_BUCKET, Key=ev["raw_ref"].split("/", 3)[3])
    assert json.loads(obj["Body"].read())["detail"]["eventName"] == "GetObject"
    out, ev = _norm(env, _ct("GetObject", requestParameters={"bucketName": "other-bucket", "key": key}))
    assert out["status"] == "SKIPPED" and ev is None


def test_cloudtrail_role_logging_and_signin(env):
    _o, ev = _norm(env, _ct("AssumeRole", requestParameters={"roleArn": "arn:aws:iam::000000000000:role/KYC-Emergency"}))
    assert (ev["action"], ev["role"]) == ("ASSUME_ROLE", "KYC-Emergency")
    for name in ("StopLogging", "DeleteTrail"):
        assert _norm(env, _ct(name, requestParameters={"name": "trail"}))[1]["action"] == "LOGGING_CHANGE"
    assert _norm(env, _ct("PutBucketLogging", requestParameters={"bucketName": "b", "BucketLoggingStatus": {}}))[1]["action"] == "LOGGING_CHANGE"
    assert _norm(env, _ct("PutBucketLogging", requestParameters={"bucketName": "b", "BucketLoggingStatus": {"LoggingEnabled": {}}}))[1] is None
    signin = _ct("ConsoleLogin", responseElements={"ConsoleLogin": "Success"})
    signin["detail-type"] = "AWS Console Sign In via CloudTrail"
    assert _norm(env, signin)[1]["action"] == "LOGIN"
    stranger = _ct("AssumeRole", requestParameters={"roleArn": "x/KYC-Emergency"},
                   userIdentity={"type": "IAMUser", "arn": "arn:aws:iam::000000000000:user/nobody"})
    assert _norm(env, stranger)[1]["user_id"] == "unmapped:arn:aws:iam::000000000000:user/nobody"


def test_cloudtrail_duplicate_is_dropped(env):
    ev = _ct("AssumeRole", eventID="fixed-1", requestParameters={"roleArn": "r/KYC-Emergency"})
    assert _norm(env, ev)[0]["status"] == "OK"
    assert _norm(env, ev)[0]["status"] == "DUPLICATE"


def test_config_and_guardduty(env):
    from finshield import ddb
    cfg = {"detail-type": "Config Rules Compliance Change", "time": "2026-11-20T10:00:00Z",
           "detail": {"configRuleName": "s3-bucket-public-read-prohibited", "resourceId": KYC_BUCKET,
                      "resourceType": "AWS::S3::Bucket",
                      "newEvaluationResult": {"complianceType": "NON_COMPLIANT", "resultRecordedTime": "2026-11-20T10:00:00Z"}}}
    _o, ev = _norm(env, cfg)
    assert (ev["action"], ev["data_class"], ev["resource_arn"]) == ("CONFIG_NONCOMPLIANT", "KYC", f"arn:aws:s3:::{KYC_BUCKET}")
    row = ddb.get_item("Posture", {"control_id": f"config:s3-bucket-public-read-prohibited:{KYC_BUCKET}"})
    assert row["status"] == "NON_COMPLIANT" and row["source"] == "config"
    cfg["detail"]["newEvaluationResult"]["complianceType"] = "COMPLIANT"
    assert _norm(env, cfg)[1] is None
    assert ddb.get_item("Posture", {"control_id": f"config:s3-bucket-public-read-prohibited:{KYC_BUCKET}"})["status"] == "COMPLIANT"
    gd = {"detail-type": "GuardDuty Finding", "time": "2026-11-20T10:00:00Z",
          "detail": {"id": "f1", "type": "UnauthorizedAccess:IAMUser/ConsoleLogin", "severity": 8,
                     "updatedAt": "2026-11-20T10:00:00Z", "resource": {"accessKeyDetails": {"userName": "sample-u-046"}}}}
    _o, ev = _norm(env, gd)
    assert (ev["action"], ev["user_id"]) == ("GUARDDUTY_FINDING", "u-046")
    r = env["fn"]["detection"].handler({"detail-type": "Normalized Event", "detail": ev})
    assert r["score"] == 0  # normalized but not scored


def test_invalid_raw_activity_is_rejected(env):
    out = env["fn"]["normalizer"].handler({"detail-type": "Raw Activity", "detail": {"event_id": "x", "action": "DANCE"}})
    assert out["status"] == "REJECTED"


# ------------------------------------------------------------------ simulator details
def test_simulator_keeps_clock_time_and_tags_ids(env):
    sim = env["fn"]["simulator"]
    sc = scenario("SC-01")
    now = datetime(2026, 11, 21, 10, 0, tzinfo=env["now"].tzinfo)
    evs = sim.build_events(sc, now, "T1")
    assert evs[3]["ts"] == "2026-11-20T23:40:30+05:30"  # yesterday, same clock time
    assert all(e["event_id"].endswith("-T1") and e["is_replay"] and e["scenario_id"] == "SC-01" for e in evs)
    late = datetime(2026, 11, 21, 23, 59, tzinfo=env["now"].tzinfo)
    assert sim.build_events(sc, late, "T2")[0]["ts"].startswith("2026-11-21T23:00")


def test_simulator_http_needs_admin_and_uses_envelope(env):
    sim = env["fn"]["simulator"]
    ev = {"routeKey": "POST /v1/simulate", "requestContext": {"authorizer": {"jwt": {"claims": {"cognito:groups": "[Analyst]"}}}},
          "body": json.dumps({"scenario_id": "SC-09"})}
    assert sim.handler(ev)["statusCode"] == 403
    ev["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = "[Admin]"
    r = sim.handler(ev)
    body = json.loads(r["body"])
    assert r["statusCode"] == 200 and body == {"data": {"accepted": True, "scenario_id": "SC-09", "events_sent": 1}, "error": None}
    env["bus"].take("Raw Activity")
    ev["body"] = json.dumps({"scenario_id": "SC-99"})
    assert sim.handler(ev)["statusCode"] == 404


# ------------------------------------------------------------------ baseline Lambda
@SLOW
def test_baseline_lambda_recomputes_from_events(env):
    import generate
    from finshield import ddb
    data = generate.build(env["now"])
    generate.load({"Events": [e for e in data["Events"] if e["user_id"] in ("u-017", "u-018", "u-001", "u-002")]}, "test")
    out = env["fn"]["baseline"].handler({})
    assert out["status"] == "OK"
    assert ddb.get_item("Baselines", {"subject_id": "u-017"})["p95_15min"] == 2
    row = ddb.get_item("Baselines", {"subject_id": "u-031"})  # no history loaded for u-031 in this test
    assert row["source"] == "team"
    assert "u-031" in out["team_fallback"]
    generate.load({"Baselines": data["Baselines"]}, "test")  # restore the seeded baselines for later tests


# ------------------------------------------------------------------ test_runner end to end
@SLOW
def test_accuracy_runner_all_pass_zero_false_alerts(env):
    tr, mp = env["fn"]["test_runner"], env["mp"]

    def invoke(payload):
        if payload.get("reset"):
            return env["fn"]["simulator"].handler(payload)
        res, _ = pipeline(env, payload["scenario_id"])
        return res

    mp.setattr(tr, "INVOKE", invoke)
    mp.setenv("FINSHIELD_SETTING_ACCURACY_POLL_SECONDS", "1")
    out = tr.handler({})
    bad = [r for r in out["rows"] if not r["pass"]]
    assert (out["passed"], out["total"], out["false_alerts_normal_days"]) == (11, 11, 0), bad
    from finshield import ddb
    from finshield.ddb import Key
    rows = ddb.query("AccuracyRuns", Key("run_id").eq(out["run_id"]))
    assert len(rows) == 12 and {r["scenario_id"] for r in rows} >= {"SC-01", "NORMAL-7D"}
    sc01 = next(r for r in out["rows"] if r["scenario_id"] == "SC-01")
    assert sc01["time_to_alert_ms"] is not None
