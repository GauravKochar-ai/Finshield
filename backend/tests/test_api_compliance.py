"""GET /v1/compliance: Arvind's 43 verified controls (simulator/seed/compliance_controls.json) with live status."""
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from conftest import load_fn, put_alert

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = json.loads((ROOT / "simulator" / "seed" / "compliance_controls.json").read_text())


def _event(groups="[Auditor]"):
    return {"routeKey": "GET /v1/compliance", "requestContext": {"authorizer": {"jwt": {"claims": {
        "cognito:groups": groups, "email": "auditor@finshield.example"}}}}}


def _call(api, **kw):
    r = api.handler(_event(**kw))
    return r["statusCode"], json.loads(r["body"])


def _validator():
    spec = yaml.safe_load((ROOT / "contract" / "openapi.yaml").read_text())
    resp = spec["paths"]["/compliance"]["get"]["responses"]["200"]
    while "$ref" in resp:
        resp = spec["components"]["responses"][resp["$ref"].split("/")[-1]]
    return Draft202012Validator(resp["content"]["application/json"]["schema"])


def _by_id(body):
    return {r["control_id"]: r for r in body["data"]}


def test_returns_every_control_from_the_file_and_matches_openapi(aws):
    api = load_fn("api")
    status, body = _call(api)
    assert status == 200 and body["error"] is None
    assert [r["control_id"] for r in body["data"]] == [c["control_id"] for c in CONTROLS]
    assert len(body["data"]) == 43
    errs = [e.message for e in _validator().iter_errors(body)]
    assert not errs, errs
    for r, c in zip(body["data"], CONTROLS):   # verified clause details pass through unchanged
        for k in ("regulation", "clause", "obligation", "source_url", "verify_clause", "framework"):
            assert r[k] == c[k]
        assert r["status_detail"]


def test_every_control_has_a_live_check_or_is_not_applicable():
    api = load_fn("api")
    ids = {c["control_id"] for c in CONTROLS}
    na = {c["control_id"] for c in CONTROLS if c["status"] == "NOT_APPLICABLE"}
    assert ids - na <= set(api.CHECKS), sorted(ids - na - set(api.CHECKS))
    assert set(api.CHECKS) <= ids, sorted(set(api.CHECKS) - ids)


def test_empty_account_shows_built_controls_and_waits_for_incidents(aws):
    api = load_fn("api")
    rows = _by_id(_call(api)[1])
    assert rows["IN-13"]["status"] == "IN_PLACE"          # ap-south-1
    assert rows["ISO27001-A.8.24"]["status"] == "IN_PLACE"  # template: KMS
    assert rows["SOC2-CC6.1"]["status"] == "IN_PLACE"      # no AWS Config findings
    assert rows["IN-15"]["status"] == "UNKNOWN"            # no Critical incident yet
    assert rows["IN-01"]["status"] == "UNKNOWN"            # no evidence chain yet
    assert rows["IN-18"]["status"] == "NOT_APPLICABLE"
    assert {r["status"] for r in rows.values()} <= {"IN_PLACE", "UNKNOWN", "NOT_APPLICABLE"}


def test_critical_incident_lights_up_timers_reports_and_containment(aws):
    from finshield import ddb

    api = load_fn("api")
    a = put_alert(status="CONTAINED", deadlines=[
        {"body": "RBI", "due_at": "2026-11-21T05:48:12+05:30"},
        {"body": "CERT-In", "due_at": "2026-11-21T05:48:12+05:30"},
        {"body": "DPB", "due_at": "2026-11-23T23:48:12+05:30"}])
    for t in ("RBI_INCIDENT", "CERTIN_FORM", "DPB_NOTICE"):
        ddb.put_item("Reports", {"alert_id": a["alert_id"], "report_type": t, "status": "DRAFT", "body_md": "x",
                                 "model_id": "NONE", "generated_at": "2026-11-20T23:50:00+05:30"})
    rows = _by_id(_call(api)[1])
    for cid in ("IN-15", "IN-16", "IN-08", "IN-07", "IN-23", "IN-03", "IN-04", "ISO27001-A.8.12", "IN-21"):
        assert rows[cid]["status"] == "IN_PLACE", (cid, rows[cid]["status_detail"])
    assert rows["IN-06"]["status"] == "GAP"               # CUSTOMER_NOTICE not drafted
    assert "CUSTOMER_NOTICE" in rows["IN-06"]["status_detail"]


def test_missing_timer_and_config_finding_show_as_gap(aws):
    from finshield import ddb

    api = load_fn("api")
    put_alert()  # Critical, OPEN, no deadlines
    ddb.put_item("Posture", {"control_id": "s3-bucket-public-read-prohibited", "source": "aws.config", "status": "NON_COMPLIANT",
                             "resource_arn": "arn:aws:s3:::finshield-dev-kyc-docs"})
    rows = _by_id(_call(api)[1])
    assert rows["IN-23"]["status"] == "GAP"
    assert rows["IN-15"]["status"] == "GAP"
    assert rows["SOC2-CC6.1"]["status"] == "GAP"


def test_sign_in_required(aws):
    api = load_fn("api")
    r = api.handler({"routeKey": "GET /v1/compliance", "requestContext": {}})
    assert r["statusCode"] == 401


def test_layer_bundles_the_controls_file():
    assert "cp simulator/seed/compliance_controls.json $(LAYER)/python/finshield/compliance_controls.json" in \
        (ROOT / "Makefile").read_text()
