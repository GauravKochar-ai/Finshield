"""Contract checks: config, schema fixtures, API fixtures vs openapi.yaml, forbidden wording."""
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7, DRAFT202012

from finshield import config, schema

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contract"
FIX = CONTRACT / "fixtures"
SCHEMA_FIXTURES = {"event": "event", "alert": "alert", "alert_sc01": "alert", "ai_explanation": "ai_explanation", "evidence_entry": "evidence_entry", "report": "report"}


@pytest.mark.parametrize("fixture,name", SCHEMA_FIXTURES.items())
def test_schema_fixture_valid(fixture, name):
    schema.validate(name, json.loads((FIX / f"{fixture}.json").read_text()))


def test_invalid_event_rejected():
    assert not schema.is_valid("event", {"event_id": "x", "ts": "2026-11-20T23:48:12Z", "source": "simulator", "user_id": "u", "action": "DOWNLOAD"})


def test_config_covers_all_signs_and_thresholds():
    c = config.load_config()
    assert set(c["signals"]) == {f"S{i}" for i in range(1, 12)}
    assert set(c["exceptions"]) == {"E1", "E2", "E3"}
    assert c["severity_thresholds"] == {"CRITICAL": 80, "HIGH": 60, "MEDIUM": 40}
    assert {d["body"]: d["hours"] for d in c["deadlines"]} == {"RBI": 6, "CERT-In": 6, "DPB": 72}
    assert c["incident_window_minutes"] == 60
    assert [config.severity_for(s) for s in (96, 80, 79, 60, 59, 40, 39)] == ["CRITICAL", "CRITICAL", "HIGH", "HIGH", "MEDIUM", "MEDIUM", None]


def test_sc01_alert_fixture_is_96_critical_and_matches_config():
    a = json.loads((FIX / "alert.json").read_text())
    c = config.load_config()
    assert a["score"] == sum(s["points"] for s in a["signals"]) == 96
    assert a["severity"] == config.severity_for(96) == "CRITICAL"
    s5 = c["signals"]["S5"]
    assert {s["code"]: s["points"] for s in a["signals"]} == {"S1": 40, "S3": c["signals"]["S3"]["points"], "S4": c["signals"]["S4"]["points_high"], "S5": s5["max_points"], "S6": c["signals"]["S6"]["points"]}
    hours = {d["body"]: d["hours"] for d in c["deadlines"]}
    assert hours["RBI"] == 6 and hours["DPB"] == 72
    assert a["ai"]["numbers_used"]["score"] == a["score"] and a["ai"]["numbers_used"]["customers_affected"] == a["customers_affected"]


def _inline_registry():
    reg = Registry()
    for p in (CONTRACT / "schemas").glob("*.json"):
        doc = json.loads(p.read_text())
        reg = reg.with_resource(doc["$id"], Resource.from_contents(doc, default_specification=DRAFT7))
    return reg


def _spec():
    return yaml.safe_load((CONTRACT / "openapi.yaml").read_text())


def _resolve_response(spec, resp):
    while "$ref" in resp:
        resp = spec["components"]["responses"][resp["$ref"].split("/")[-1]]
    return resp["content"]["application/json"]["schema"]


# fixture file -> (path, method)
API_FIXTURES = {
    "api_posture": ("/posture", "get"),
    "api_alerts_list": ("/alerts", "get"),
    "api_alert_detail": ("/alerts/{id}", "get"),
    "api_alert_timeline": ("/alerts/{id}/timeline", "get"),
    "api_alert_evidence": ("/alerts/{id}/evidence", "get"),
    "api_evidence_verify": ("/alerts/{id}/evidence/verify", "post"),
    "api_evidence_tamper_demo": ("/alerts/{id}/evidence/tamper-demo", "post"),
    "api_decision": ("/alerts/{id}/decision", "post"),
    "api_release": ("/alerts/{id}/release", "post"),
    "api_reports": ("/alerts/{id}/reports", "get"),
    "api_ask": ("/alerts/{id}/ask", "post"),
    "api_user": ("/users/{id}", "get"),
    "api_rules": ("/rules", "get"),
    "api_compliance": ("/compliance", "get"),
    "api_privacy": ("/privacy", "get"),
    "api_approvals_list": ("/approvals", "get"),
    "api_approvals_create": ("/approvals", "post"),
    "api_simulate": ("/simulate", "post"),
    "api_accuracy_run": ("/accuracy/run", "post"),
    "api_accuracy": ("/accuracy", "get"),
}


def test_every_openapi_operation_has_a_fixture():
    spec = _spec()
    ops = {(p, m) for p, item in spec["paths"].items() for m in item if m in ("get", "post")}
    assert ops == set(API_FIXTURES.values())
    assert len(ops) == 20


@pytest.mark.parametrize("fixture,op", API_FIXTURES.items())
def test_api_fixture_matches_openapi(fixture, op):
    spec = _spec()
    path, method = op
    resp = spec["paths"][path][method]["responses"]["200"]
    sch = _resolve_response(spec, resp)
    wrapper = {"$id": "https://finshield.local/contract/openapi.yaml", "components": spec["components"], **sch}
    validator = Draft202012Validator(wrapper, registry=_inline_registry().with_resource("https://finshield.local/contract/openapi.yaml", Resource.from_contents(wrapper, default_specification=DRAFT202012)))
    body = json.loads((FIX / f"{fixture}.json").read_text())
    errs = [e.message for e in validator.iter_errors(body)]
    assert not errs, errs
    assert body["error"] is None


FORBIDDEN = [re.compile(p, re.I) for p in (r"DPDP[- ]compliant", r"DPDP compliance", r"Consent Manager")]


def test_no_forbidden_wording_in_contract_docs_and_code():
    bad = []
    for base in ("contract", "docs", "backend", "web", "infra", "scripts", "simulator", ".kiro/specs"):
        for p in (ROOT / base).rglob("*"):
            if p.is_file() and p.suffix in {".json", ".md", ".yaml", ".yml", ".py", ".ts", ".tsx", ".sh", ".mjs"} and "node_modules" not in p.parts and p.name != "test_contract.py":
                text = p.read_text(errors="ignore")
                if p.name == "playbook.md":
                    continue  # the playbook quotes the forbidden terms in its own rules
                for rx in FORBIDDEN:
                    for m in rx.finditer(text):
                        line = text[: m.start()].count("\n")
                        ctx = text.splitlines()[line].lower()
                        if "never" in ctx or "not " in ctx or "forbidden" in ctx:
                            continue
                        bad.append(f"{p.relative_to(ROOT)}:{line + 1}: {m.group(0)}")
    assert not bad, bad
