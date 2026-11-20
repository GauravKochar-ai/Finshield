"""ai_explain: masked input, schema + numbers + clause checks, retry, template fallback."""
import json

import pytest

from conftest import fixture, load_fn, put_alert
from finshield import bedrock, ddb, evidence, schema

AID = "ALR-20261120-0007"


@pytest.fixture
def fn(aws, monkeypatch):
    monkeypatch.setenv("KYC_BUCKET", "finshield-dev-kyc-docs")
    monkeypatch.setenv("FINSHIELD_SETTING_BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setenv("FINSHIELD_SETTING_GUARDRAIL_ID", "gr-test")
    monkeypatch.setenv("FINSHIELD_SETTING_GUARDRAIL_VERSION", "1")
    put_alert()
    return load_fn("ai_explain")


def good_answer(mod):
    alert = ddb.get_item("Alerts", {"alert_id": AID})
    facts = mod.build_facts(alert)
    reg = facts["regulations"][0]
    return {
        "headline": "Privileged account bulk-exported 212 KYC files off-hours and sent them outside",
        "summary": f"{facts['subject']} downloaded 212 KYC files in 15 minutes, 106 times the usual rate, then uploaded data to a non-allowlisted share. 198 customers are affected.",
        "why_unusual": ["212 downloads vs usual 2 per 15 min (106x)", "Emergency role with no covering approval"],
        "rules_affected": [{"regulation": reg["regulation"], "clause": reg["clause"], "why": "Bulk export of KYC data."}],
        "root_cause_hypotheses": ["Compromised privileged credentials"],
        "affected_assets": ["finshield-dev-kyc-docs"],
        "recommended_actions": ["Keep containment in place", "Approve the lock-down"],
        "confidence": "high",
        "confidence_reason": "Five independent signs agree.",
        "numbers_used": {"score": 96, "downloads_15m": 212, "customers_affected": 198, "ratio": 106},
    }


class FakeBedrock:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, system, user_text, timeout_s=8.0, **kw):
        self.prompts.append(user_text)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return {"text": a if isinstance(a, str) else json.dumps(a), "stop_reason": "end_turn", "guardrail_intervened": False, "latency_ms": 5, "usage": {}, "model_id": "test-model"}


def test_valid_answer_is_stored_as_ok(fn, monkeypatch):
    fake = FakeBedrock([good_answer(fn)])
    monkeypatch.setattr(bedrock, "converse", fake)
    out = fn.handler({"alert_id": AID, "execution": "x"}, None)
    assert out["ai_status"] == "OK"
    alert = ddb.get_item("Alerts", {"alert_id": AID})
    assert alert["ai_status"] == "OK" and alert["ai"]["numbers_used"]["score"] == 96
    schema.validate("alert", alert)
    entry = evidence.chain(AID)[-1]
    assert entry["type"] == "AI_EXPLAINED" and entry["payload"]["model_id"] == "test-model"


def test_input_is_masked(fn, monkeypatch):
    fake = FakeBedrock([good_answer(fn)])
    monkeypatch.setattr(bedrock, "converse", fake)
    fn.handler({"alert_id": AID}, None)
    sent = fake.prompts[0]
    assert "u-017" not in sent and "User-" in sent
    assert "principal_arn" not in sent and "finshield-dev-demo-ops-admin" not in sent


def test_wrong_number_is_retried_then_accepted(fn, monkeypatch):
    bad = good_answer(fn)
    bad["numbers_used"]["downloads_15m"] = 2000
    fake = FakeBedrock([bad, good_answer(fn)])
    monkeypatch.setattr(bedrock, "converse", fake)
    out = fn.handler({"alert_id": AID}, None)
    assert out["ai_status"] == "OK" and len(fake.prompts) == 2
    assert "rejected" in fake.prompts[1]


def test_invented_number_in_text_falls_back(fn, monkeypatch):
    bad = good_answer(fn)
    bad["summary"] = "The user downloaded 18,400 files."
    monkeypatch.setattr(bedrock, "converse", FakeBedrock([bad, bad]))
    out = fn.handler({"alert_id": AID}, None)
    assert out["ai_status"] == "FALLBACK" and "18,400" in out["reason"]


def test_invented_clause_falls_back(fn, monkeypatch):
    bad = good_answer(fn)
    bad["rules_affected"] = [{"regulation": "Made-up Act", "clause": "Sec 99", "why": "x"}]
    monkeypatch.setattr(bedrock, "converse", FakeBedrock([bad, bad]))
    assert fn.handler({"alert_id": AID}, None)["ai_status"] == "FALLBACK"


def test_bedrock_off_gives_valid_template(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_BEDROCK_MODEL_ID", "NONE")
    out = fn.handler({"alert_id": AID}, None)
    assert out["ai_status"] == "FALLBACK"
    alert = ddb.get_item("Alerts", {"alert_id": AID})
    ai = alert["ai"]
    schema.validate("ai_explanation", ai)
    assert ai["numbers_used"]["score"] == 96 and ai["numbers_used"]["customers_affected"] == 198
    assert len(ai["summary"].split()) <= 80
    assert all("pending verification" in r["why"] for r in ai["rules_affected"])


def test_force_fallback_keeps_existing_ok_for_same_score(fn, monkeypatch):
    monkeypatch.setattr(bedrock, "converse", FakeBedrock([good_answer(fn)]))
    fn.handler({"alert_id": AID}, None)
    out = fn.handler({"alert_id": AID, "force_fallback": True}, None)
    assert out["written"] is False
    assert ddb.get_item("Alerts", {"alert_id": AID})["ai_status"] == "OK"


def test_missing_alert_returns_fallback_without_writing(fn):
    out = fn.handler({"alert_id": "ALR-20261120-0999"}, None)
    assert out == {"alert_id": "ALR-20261120-0999", "ai_status": "FALLBACK", "written": False, "reason": "alert not found"}


def test_template_is_valid_for_every_signal(fn):
    alert = fixture("alert_sc01")
    alert["signals"] = [{"code": f"S{i}", "points": 10, "facts": {"count": i * 50, "flag": True, "where": "Pune"}} for i in range(1, 12)]
    facts = fn.build_facts(alert)
    ai = fn.template(alert, facts, fn.computed_numbers(alert))
    schema.validate("ai_explanation", ai)
    assert fn.check(ai, facts, fn.computed_numbers(alert)) is None  # the template passes the same checks as Bedrock output
