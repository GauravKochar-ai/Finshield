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
    return {"detail-type": "Incident Updated", "detail": {"alert_id": AID, "status": "AWAITING_APPROVAL", "step": "awaitingapproval"}}
def test_ai_message_content_and_idempotency(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    monkeypatch.setattr(fn, "ADVICE_WAIT_S", 0)
    ddb.put_item("AiSuggestions", {"alert_id": AID, "task": "SECOND_OPINION", "status": "OK", "output": {"risk_rating": "CRITICAL", "reasoning": "Bulk export and no approval.", "agrees_with_score": True, "computed_severity": "CRITICAL"}})
    ddb.put_item("AiSuggestions", {"alert_id": AID, "task": "CONTAINMENT_ADVICE", "status": "OK", "output": {"actions": [{"action": "DNS_BLOCK", "reason": "Stops the upload destination."}]}})
    a = ddb.get_item("Alerts", {"alert_id": AID})
    a["ai"] = fixture("alert_sc01")["ai"]
    a["ai_status"] = "OK"
    ddb.put_item("Alerts", a)
    assert fn.handler(ai_event())["kind"] == "SLACK_AI"
    text = json.dumps(fn.sent[0][1])
    assert "According to FinShield AI" in text and "96 / 100" in text and "CRITICAL" in text
    assert "Second opinion" in text and "agrees with the computed severity" in text and "DNS_BLOCK" in text
    assert "DPDP-aligned readiness and controls" in text and "compliant" not in text.lower().replace("non-compliant", "")
    assert fn.handler(ai_event())["reason"] == "already sent" and len(fn.sent) == 1
def test_ai_message_works_without_ai_or_suggestions(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    monkeypatch.setattr(fn, "ADVICE_WAIT_S", 0)
    assert fn.handler(ai_event())["sent"] is True
    assert "not available yet" in json.dumps(fn.sent[0][1])
def test_other_incident_updates_are_ignored(fn, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_SLACK_WEBHOOK_URL", URL)
    ev = ai_event()
    ev["detail"]["status"] = "CONTAINED"
    assert fn.handler(ev)["sent"] is False and fn.sent == []
