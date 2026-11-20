"""ai_suggest: checks, fallbacks, idempotency, masking, and that nothing touches the alert."""
import json
import pytest
from conftest import fixture, load_fn, put_alert
from finshield import bedrock, ddb
AID = "ALR-20261120-0007"
@pytest.fixture
def fn(aws, monkeypatch):
    monkeypatch.setenv("FINSHIELD_SETTING_BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setenv("FINSHIELD_SETTING_GUARDRAIL_ID", "gr-test")
    put_alert()
    return load_fn("ai_suggest")
class Fake:
    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []
    def __call__(self, system, user_text, timeout_s=8.0, **kw):
        self.prompts.append(user_text)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return {"text": json.dumps(a), "stop_reason": "end_turn", "guardrail_intervened": False, "latency_ms": 5, "usage": {}, "model_id": "test-model"}
def stored(task, key=AID):
    return ddb.get_item("AiSuggestions", {"alert_id": key, "task": task})
def test_second_opinion_ok_and_code_sets_agreement(fn, monkeypatch):
    monkeypatch.setattr(bedrock, "converse", Fake([{"risk_rating": "HIGH", "reasoning": "Bulk export plus unapproved emergency role.", "missed_considerations": []}]))
    out = fn.handler({"task": "SECOND_OPINION", "alert_id": AID})
    assert out[0]["status"] == "OK"
    item = stored("SECOND_OPINION")
    assert item["output"]["agrees_with_score"] is False and item["output"]["computed_severity"] == "CRITICAL"
    assert ddb.get_item("Alerts", {"alert_id": AID})["score"] == 96  # alert untouched
def test_invented_number_falls_back_after_retry(fn, monkeypatch):
    bad = {"risk_rating": "CRITICAL", "reasoning": "Exported 9999 files.", "missed_considerations": []}
    fake = Fake([bad, bad])
    monkeypatch.setattr(bedrock, "converse", fake)
    fn.handler({"task": "SECOND_OPINION", "alert_id": AID})
    item = stored("SECOND_OPINION")
    assert item["status"] == "FALLBACK" and item["output"]["risk_rating"] == "CRITICAL" and len(fake.prompts) == 2
def test_bedrock_down_gives_fallback_for_every_task(fn, monkeypatch):
    def boom(*a, **k):
        raise bedrock.BedrockUnavailable("down")
    monkeypatch.setattr(bedrock, "converse", boom)
    out = fn.handler({"alert_id": AID})
    assert {r["task"] for r in out} == set(fn.ALERT_TASKS) and all(r["status"] == "FALLBACK" for r in out)
    assert stored("COMPLIANCE_MAP")["output"]["controls"]
    assert stored("CONTAINMENT_ADVICE")["output"]["actions"]
def test_containment_rejects_unknown_and_done_actions(fn, monkeypatch):
    alert = ddb.get_item("Alerts", {"alert_id": AID})
    alert["containment"] = [{"action": "REVOKE_SESSIONS", "mode": "LIVE", "result": "OK", "at": "x"}]
    ddb.put_item("Alerts", alert)
    bad = {"actions": [{"action": "REVOKE_SESSIONS", "reason": "again"}]}
    good = {"actions": [{"action": "DNS_BLOCK", "reason": "Stops the upload destination."}]}
    fake = Fake([bad, good])
    monkeypatch.setattr(bedrock, "converse", fake)
    fn.handler({"task": "CONTAINMENT_ADVICE", "alert_id": AID})
    item = stored("CONTAINMENT_ADVICE")
    assert item["status"] == "OK" and item["review_status"] == "PROPOSED"
    assert [a["action"] for a in item["output"]["actions"]] == ["DNS_BLOCK"]
    assert "REVOKE_SESSIONS" not in json.loads(fake.prompts[0].split("Facts (JSON):\n")[1])["allowed_actions"]
def test_compliance_rejects_uncited_clause(fn, monkeypatch):
    bad = {"controls": [{"regulation": "Made Up Act", "clause": "1", "gap": "x", "suggested_control": "y"}]}
    fake = Fake([bad, bad])
    monkeypatch.setattr(bedrock, "converse", fake)
    fn.handler({"task": "COMPLIANCE_MAP", "alert_id": AID})
    item = stored("COMPLIANCE_MAP")
    assert item["status"] == "FALLBACK" and all("Made Up" not in c["regulation"] for c in item["output"]["controls"])
def test_input_is_masked_and_idempotent(fn, monkeypatch):
    fake = Fake([{"risk_rating": "CRITICAL", "reasoning": "Consistent.", "missed_considerations": []}])
    monkeypatch.setattr(bedrock, "converse", fake)
    fn.handler({"task": "SECOND_OPINION", "alert_id": AID})
    sent = fake.prompts[0]
    assert "u-017" not in sent and "User-" in sent and "finshield-dev-demo-ops-admin" not in sent
    again = fn.handler({"task": "SECOND_OPINION", "alert_id": AID})  # no second model call: Fake would raise IndexError
    assert again[0]["written"] is False
def test_event_routing(fn, monkeypatch):
    def boom(*a, **k):
        raise bedrock.BedrockUnavailable("down")
    monkeypatch.setattr(bedrock, "converse", boom)
    raised = fn.handler({"detail-type": "Alert Raised", "detail": fixture("alert_raised_critical")})
    assert {r["task"] for r in raised} == {"SECOND_OPINION", "COMPLIANCE_MAP"}
    skipped = fn.handler({"detail-type": "Incident Updated", "detail": {"alert_id": AID, "status": "CONTAINED"}})
    assert skipped[0]["written"] is False
    awaiting = fn.handler({"detail-type": "Incident Updated", "detail": {"alert_id": AID, "status": "AWAITING_APPROVAL"}})
    assert awaiting[0]["task"] == "CONTAINMENT_ADVICE"
def test_digest_checks_alert_ids(fn, monkeypatch):
    good = {"headline": "One critical alert open", "summary": "ALR-20261120-0007 needs a decision.", "priorities": [{"alert_id": AID, "why": "Score 96, awaiting approval."}]}
    monkeypatch.setattr(bedrock, "converse", Fake([good]))
    fn.handler({"task": "DIGEST"})
    item = stored("DIGEST", "DIGEST")
    assert item["status"] == "OK" and item["output"]["priorities"][0]["alert_id"] == AID
    monkeypatch.setattr(bedrock, "converse", Fake([{**good, "priorities": [{"alert_id": "ALR-FAKE", "why": "x"}]}] * 2))
    fn.handler({"task": "DIGEST"})
    assert stored("DIGEST", "DIGEST")["status"] == "FALLBACK"
def test_unknown_task_and_missing_alert(fn):
    with pytest.raises(ValueError):
        fn.handler({"task": "NOPE", "alert_id": AID})
    assert fn.handler({"task": "SECOND_OPINION", "alert_id": "ALR-X"})[0]["reason"] == "alert not found"

def test_slack_followup_triggered_after_tasks(fn, monkeypatch):
    calls = []
    monkeypatch.setenv("SLACK_NOTIFY_FN", "finshield-dev-slack-notify")
    monkeypatch.setattr(fn, "trigger_slack", lambda alert: calls.append(alert["alert_id"]))
    def boom(*a, **k):
        raise bedrock.BedrockUnavailable("down")
    monkeypatch.setattr(bedrock, "converse", boom)
    fn.handler({"detail-type": "Alert Raised", "detail": fixture("alert_raised_critical")})
    assert calls == []  # CRITICAL waits for containment advice
    fn.handler({"detail-type": "Incident Updated", "detail": {"alert_id": AID, "status": "AWAITING_APPROVAL"}})
    assert calls == [AID] and stored("CONTAINMENT_ADVICE")  # stored before Slack is asked
    a = ddb.get_item("Alerts", {"alert_id": AID})
    a.update(severity="HIGH", score=70)
    ddb.put_item("Alerts", a)
    fn.handler({"detail-type": "Alert Raised", "detail": {"alert_id": AID, "severity": "HIGH"}})
    assert calls == [AID, AID]
def test_escalated_score_regenerates(fn, monkeypatch):
    fake = Fake([{"risk_rating": "HIGH", "reasoning": "First.", "missed_considerations": []}, {"risk_rating": "CRITICAL", "reasoning": "Second.", "missed_considerations": []}])
    monkeypatch.setattr(bedrock, "converse", fake)
    fn.handler({"task": "SECOND_OPINION", "alert_id": AID})
    a = ddb.get_item("Alerts", {"alert_id": AID})
    a["score"] = 100
    ddb.put_item("Alerts", a)
    fn.handler({"task": "SECOND_OPINION", "alert_id": AID})
    assert stored("SECOND_OPINION")["output"]["reasoning"] == "Second." and stored("SECOND_OPINION")["score"] == 100
def test_trigger_slack_failure_is_swallowed(fn, monkeypatch):
    monkeypatch.setenv("SLACK_NOTIFY_FN", "nope")
    class Boom:
        def invoke(self, **kw):
            raise RuntimeError("no")
    monkeypatch.setattr(fn.boto3, "client", lambda *a, **k: Boom())
    fn.trigger_slack({"alert_id": AID, "severity": "HIGH", "score": 70})  # no exception
