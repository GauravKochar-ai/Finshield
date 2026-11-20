"""slack_notify: off without a webhook, formatted message, no PII, idempotent, never raises."""
import json
import urllib.error
import pytest
from conftest import fixture, load_fn, put_alert
from finshield import ddb
AID = "ALR-20261120-0007"
URL = "https://hooks.slack.com/services/T000/B000/XXXX"
@pytest.fixture
def fn(aws, monkeypatch):
    put_alert()
    mod = load_fn("slack_notify")
    mod.sent = []
    monkeypatch.setattr(mod, "post", lambda url, msg: mod.sent.append((url, msg)))
    return mod
def event():
    return {"detail-type": "Alert Raised", "detail": fixture("alert_raised_critical")}
def test_off_when_not_configured(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", "NONE")
    assert fn.handler(event())["reason"] == "not configured" and fn.sent == []
def test_rejects_non_slack_url(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", "https://evil.example/hook")
    assert fn.handler(event())["sent"] is False and fn.sent == []
def test_message_is_formatted_and_has_no_pii(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    monkeypatch.setenv("FINSHIELD_SETTING_PORTAL_URL", "https://portal.example")
    assert fn.handler(event())["sent"] is True
    url, msg = fn.sent[0]
    assert url == URL and msg["attachments"][0]["color"] == "#D92D20"
    blocks = msg["attachments"][0]["blocks"]
    assert blocks[0]["type"] == "header" and "CRITICAL" in blocks[0]["text"]["text"] and AID in blocks[0]["text"]["text"]
    text = json.dumps(msg)
    assert "Volume spike" in text and "RBI" in text and "CERT-In" in text and "DPB" in text
    assert "21 Nov 05:49" in text  # RBI 6h after 23:49 IST
    assert "212" in text and "https://portal.example/alerts/" + AID in text
    assert "arn:aws" not in text and "aadhaar" not in text.lower()
    assert all(b["type"] in {"header", "section", "divider", "actions", "context"} for b in blocks)
def test_idempotent_per_severity_and_escalation_resends(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    fn.handler(event())
    assert fn.handler(event())["reason"] == "already sent" and len(fn.sent) == 1
    a = ddb.get_item("Alerts", {"alert_id": AID})
    a["severity"] = "HIGH"
    ddb.put_item("Alerts", a)
    ev = event()
    ev["detail"].update(severity="HIGH", previous_severity="MEDIUM")
    assert fn.handler(ev)["sent"] is True and len(fn.sent) == 2
    assert "escalated from MEDIUM" in json.dumps(fn.sent[1][1])
def test_slack_failure_is_swallowed_and_retryable(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    def boom(url, msg):
        raise urllib.error.URLError("down")
    monkeypatch.setattr(fn, "post", boom)
    assert fn.handler(event())["reason"] == "post failed"
    monkeypatch.setattr(fn, "post", lambda u, m: fn.sent.append((u, m)))
    assert fn.handler(event())["sent"] is True
def test_missing_alert_skips(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    ev = event()
    ev["detail"]["alert_id"] = "ALR-NOPE"
    assert fn.handler(ev)["reason"] == "alert not found"
def ai_event():
    return {"ai_followup": True, "alert_id": AID, "severity": "CRITICAL", "score": 96}
def put_suggestions(score=96):
    ddb.put_item("AiSuggestions", {"alert_id": AID, "task": "SECOND_OPINION", "status": "OK", "score": score, "output": {"risk_rating": "CRITICAL", "reasoning": "Bulk export and no approval.", "missed_considerations": ["Check other users on the same device"], "agrees_with_score": True, "computed_severity": "CRITICAL"}})
    ddb.put_item("AiSuggestions", {"alert_id": AID, "task": "CONTAINMENT_ADVICE", "status": "OK", "score": score, "output": {"actions": [{"action": "DNS_BLOCK", "reason": "Stops the upload destination."}]}})
    ddb.put_item("AiSuggestions", {"alert_id": AID, "task": "COMPLIANCE_MAP", "status": "OK", "score": score, "output": {"controls": [{"regulation": "RBI IT governance and cyber security directions for NBFCs", "clause": "Privileged access and incident reporting", "gap": "Emergency role used without approval.", "suggested_control": "Require a covering approval before the role can be assumed."}]}})
def with_ai():
    a = ddb.get_item("Alerts", {"alert_id": AID})
    a["ai"] = fixture("alert_sc01")["ai"]
    a["ai_status"] = "OK"
    ddb.put_item("Alerts", a)
    return a
def test_ai_message_has_all_three_suggestions(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    put_suggestions()
    with_ai()
    assert fn.handler(ai_event())["kind"] == "SLACK_AI#CRITICAL"
    text = json.dumps(fn.sent[0][1])
    assert "According to FinShield AI" in text and "96 / 100" in text
    assert "Second opinion" in text and "agrees with the computed severity" in text and "Check other users" in text
    assert "DNS_BLOCK" in text and "need approval" in text
    assert "Compliance mapping" in text and "Require a covering approval" in text and "Gap:" in text
    assert "Waiting for a human decision" in text
    assert "DPDP-aligned readiness and controls" in text and "compliant" not in text.lower()
    assert fn.handler(ai_event())["reason"] == "already sent" and len(fn.sent) == 1
def test_stale_suggestions_for_old_score_are_not_shown(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    put_suggestions(score=70)
    with_ai()
    fn.handler(ai_event())
    text = json.dumps(fn.sent[0][1])
    assert "Second opinion" not in text and "Compliance mapping" not in text
def test_high_alert_gets_review_wording_and_waits_for_ai(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    monkeypatch.setattr(fn, "AI_WAIT_S", 0)
    a = ddb.get_item("Alerts", {"alert_id": AID})
    a.update(severity="HIGH", score=70)
    ddb.put_item("Alerts", a)
    calls = []
    real = fn.ddb.get_item
    def get_item(table, key, consistent=False):
        item = real(table, key, consistent)
        if table == "Alerts":
            calls.append(1)
            if len(calls) == 3:  # ai_explain finishes while slack waits
                item["ai"] = fixture("alert_sc01")["ai"]
        return item
    monkeypatch.setattr(fn.ddb, "get_item", get_item)
    assert fn.handler({"ai_followup": True, "alert_id": AID})["kind"] == "SLACK_AI#HIGH"
    text = json.dumps(fn.sent[0][1])
    assert "Analyst review needed" in text and "Waiting for a human decision" not in text and "212" in text
def test_ai_message_works_without_ai_or_suggestions(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    monkeypatch.setattr(fn, "AI_WAIT_S", 0)
    assert fn.handler(ai_event())["sent"] is True
    assert "not available yet" in json.dumps(fn.sent[0][1])
