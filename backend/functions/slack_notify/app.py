"""slack_notify: formatted Slack messages (Block Kit), two kinds:
  1. "Alert Raised": the detection message (score, signs, readiness timers); sent again if severity escalates.
  2. "Incident Updated" with status AWAITING_APPROVAL: the FinShield AI analysis (explanation, second opinion, containment
     taken, proposed next steps, rules affected). By then ai_explain and containment have finished.
Webhook URL: SSM SecureString /finshield/<stage>/slack_webhook_url (env FINSHIELD_SETTING_SLACK_WEBHOOK_URL wins).
Unset or "NONE" means Slack is off: nothing is sent, nothing fails. A Slack error is logged and never raised, so it
cannot disturb detection or the incident workflow. Idempotent on (alert_id, severity) via the AiSuggestions table.
The message carries only computed facts: no names, Aadhaar or PAN; the person appears by user id only.
Optional SSM /finshield/<stage>/portal_url adds an "Open case" button.
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
import boto3
from finshield import config, ddb
from finshield.log import log
IST = timezone(timedelta(hours=5, minutes=30))
STYLE = {"CRITICAL": ("#D92D20", ":rotating_light:"), "HIGH": ("#F79009", ":warning:"), "MEDIUM": ("#EAAA08", ":large_yellow_circle:")}
HIDE = {"name", "name_pseudo", "email", "phone", "aadhaar", "aadhaar_number", "pan", "pan_number", "address"}
MAX_FACTS = 4
ADVICE_WAIT_S = 3.0  # ai_suggest writes CONTAINMENT_ADVICE from the same event; poll briefly for it
ADVICE_TRIES = 3
def webhook_url() -> str | None:
    url = os.environ.get("FINSHIELD_SETTING_SLACK_WEBHOOK_URL")
    if url is None:
        try:
            ssm = boto3.client("ssm", region_name=config.region())
            url = ssm.get_parameter(Name=f"/finshield/{config.stage()}/slack_webhook_url", WithDecryption=True)["Parameter"]["Value"]
        except Exception as exc:
            if exc.__class__.__name__ != "ParameterNotFound":
                log("slack webhook lookup failed", level="WARNING", error=exc.__class__.__name__)
            return None
    if not url or url.strip().upper() == "NONE":
        return None
    if not url.startswith("https://hooks.slack.com/"):
        log("slack webhook ignored: not a hooks.slack.com URL", level="WARNING")
        return None
    return url.strip()
def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, list):
        return ", ".join(_fmt(x) for x in v)
    return str(v)
def role_name(arn: str | None) -> str:
    return (arn or "unknown").rsplit("/", 1)[-1]
def fmt_time(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(IST).strftime("%d %b %H:%M IST")  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return iso or "unknown"
def deadline_lines(detected_at: str | None) -> list[str]:
    try:
        t0 = datetime.fromisoformat(detected_at)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return []
    return [f"*{d['body']}* {d['hours']}h  ->  {(t0 + timedelta(hours=d['hours'])).astimezone(IST).strftime('%d %b %H:%M')}" for d in config.load_config()["deadlines"]]
def signal_lines(alert: dict[str, Any]) -> list[str]:
    names = {k: v.get("name", k) for k, v in config.load_config()["signals"].items()}
    out = []
    for s in sorted(alert.get("signals", []), key=lambda s: -s["points"]):
        facts = [f"{k.replace('_', ' ')} {_fmt(v)}" for k, v in (s.get("facts") or {}).items() if k.lower() not in HIDE][:MAX_FACTS]
        out.append(f"*{names.get(s['code'], s['code'])}*  +{s['points']}" + (f"\n      _{', '.join(facts)}_" if facts else ""))
    return out
def build_message(alert: dict[str, Any], previous_severity: str | None, portal_url: str | None) -> dict[str, Any]:
    sev = alert["severity"]
    color, emoji = STYLE.get(sev, STYLE["MEDIUM"])
    title = f"{emoji} {sev} alert {alert['alert_id']}"
    if previous_severity and previous_severity != sev:
        title += f" (escalated from {previous_severity})"
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:150], "emoji": True}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Risk score*\n{alert['score']} / {config.load_config()['score_cap']}"},
            {"type": "mrkdwn", "text": f"*Customers affected*\n{alert['customers_affected']:,}"},
            {"type": "mrkdwn", "text": f"*User / principal*\n{alert['user_id']} / `{role_name(alert.get('principal_arn'))}`"},
            {"type": "mrkdwn", "text": f"*Data*\n{', '.join(alert.get('data_classes') or ['unknown'])}"},
            {"type": "mrkdwn", "text": f"*Detected*\n{fmt_time(alert.get('detected_at'))}"},
            {"type": "mrkdwn", "text": f"*Status*\n{alert.get('status', 'OPEN')}"},
        ]},
    ]
    sig = signal_lines(alert)
    if sig:
        blocks += [{"type": "divider"}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Why it fired*\n" + "\n".join(f"{i + 1}. {line}" for i, line in enumerate(sig))[:2900]}}]
    dl = deadline_lines(alert.get("detected_at"))
    if dl:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": ":alarm_clock: *Readiness timers (from detection)*\n" + "\n".join(dl)}})
    if portal_url:
        blocks.append({"type": "actions", "elements": [{"type": "button", "style": "danger" if sev == "CRITICAL" else "primary", "text": {"type": "plain_text", "text": "Open case"}, "url": f"{portal_url.rstrip('/')}/alerts/{alert['alert_id']}"}]})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "FinShield AI  |  DPDP-aligned readiness and controls  |  ap-south-1  |  SAMPLE data"}]})
    return {"text": f"{sev} alert {alert['alert_id']}, score {alert['score']}", "attachments": [{"color": color, "blocks": blocks}]}
def _bullets(items: list[str], limit: int = 5) -> str:
    return "\n".join(f"\u2022 {x}" for x in items[:limit])
def suggestion(alert_id: str, task: str) -> dict[str, Any] | None:
    item = ddb.get_item("AiSuggestions", {"alert_id": alert_id, "task": task})
    return item.get("output") if item else None
def build_ai_message(alert: dict[str, Any], second: dict[str, Any] | None, advice: dict[str, Any] | None, portal_url: str | None) -> dict[str, Any]:
    sev, ai = alert["severity"], alert.get("ai") or {}
    color, _ = STYLE.get(sev, STYLE["MEDIUM"])
    cap = config.load_config()["score_cap"]
    fallback = alert.get("ai_status") == "FALLBACK"
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": f":brain: FinShield AI analysis  {alert['alert_id']}"[:150], "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*According to FinShield AI, this case scores {alert['score']} / {cap} ({sev}).*\n"
                                     "_The score and severity are computed by rules in code. The AI only explains them._"}},
    ]
    if ai:
        head = f"*{ai['headline']}*\n{ai['summary']}"
        if fallback:
            head += "\n_Template text: the AI model was unavailable._"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": head[:2900]}})
        if ai.get("why_unusual"):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Why it is unusual*\n" + _bullets(ai["why_unusual"])[:2900]}})
        if ai.get("root_cause_hypotheses"):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Likely cause* (confidence: {ai.get('confidence', 'n/a')})\n" + _bullets(ai["root_cause_hypotheses"], 3)}})
    else:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "_The AI explanation is not available yet._"}})
    if second:
        verdict = "agrees with the computed severity" if second.get("agrees_with_score") else f"differs from the computed severity ({second.get('computed_severity')})"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f":mag: *Second opinion:* {second['risk_rating']}, {verdict}\n_{second['reasoning']}_"[:2900]}})
    blocks.append({"type": "divider"})
    done = [f"{c['action']} ({c.get('mode')}, {c.get('result')})" for c in alert.get("containment") or []]
    if done:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": ":shield: *Containment taken* (reversible)\n" + _bullets(done)}})
    nxt = [f"{a['action']}: {a['reason']}" for a in (advice or {}).get("actions", [])]
    nxt = nxt or ai.get("recommended_actions", [])
    if nxt:
        label = "AI-proposed next steps (need approval)" if (advice or {}).get("actions") else "Recommended next steps"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: *{label}*\n" + _bullets(nxt)[:2900]}})
    rules = [f"{r['regulation']}, {r['clause']}" for r in ai.get("rules_affected", [])]
    if rules:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": ":scales: *Rules in scope* (DPDP-aligned readiness and controls)\n" + _bullets(rules, 4)}})
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": ":hourglass_flowing_sand: *Waiting for a human decision.* Approve or reject the lock-down in the portal."}})
    if portal_url:
        blocks.append({"type": "actions", "elements": [{"type": "button", "style": "danger" if sev == "CRITICAL" else "primary", "text": {"type": "plain_text", "text": "Review and decide"}, "url": f"{portal_url.rstrip('/')}/alerts/{alert['alert_id']}"}]})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "AI-generated, advisory  |  FinShield AI  |  ap-south-1  |  SAMPLE data"}]})
    return {"text": f"FinShield AI analysis for {alert['alert_id']}: score {alert['score']} ({sev})", "attachments": [{"color": color, "blocks": blocks}]}
def post(url: str, message: dict[str, Any]) -> None:
    req = urllib.request.Request(url, data=json.dumps(message).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 (URL checked to be hooks.slack.com)
        resp.read()
def handler(event, context=None):
    detail = event.get("detail") or event
    alert_id = detail.get("alert_id")
    ai_message = event.get("detail-type") == "Incident Updated"
    if ai_message and detail.get("status") != "AWAITING_APPROVAL":
        return {"sent": False, "reason": "not AWAITING_APPROVAL"}
    url = webhook_url()
    if not url:
        log("slack not configured, skipped", alert_id=alert_id)
        return {"sent": False, "reason": "not configured"}
    alert = ddb.get_item("Alerts", {"alert_id": alert_id}, consistent=True) if alert_id else None
    if not alert:
        log("alert not found, slack skipped", level="WARNING", alert_id=alert_id)
        return {"sent": False, "reason": "alert not found"}
    sev = alert["severity"]
    kind = "SLACK_AI" if ai_message else f"SLACK#{sev}"
    marker = {"alert_id": alert_id, "task": kind, "status": "SENT", "generated_at": datetime.now(IST).isoformat(timespec="seconds")}
    if not ddb.put_if_absent("AiSuggestions", marker, "alert_id"):
        return {"sent": False, "reason": "already sent"}
    try:
        portal = config.get_setting("portal_url", "") or None
        if ai_message:
            advice = suggestion(alert_id, "CONTAINMENT_ADVICE")
            for _ in range(ADVICE_TRIES - 1):
                if advice is not None:
                    break
                time.sleep(ADVICE_WAIT_S)
                advice = suggestion(alert_id, "CONTAINMENT_ADVICE")
            message = build_ai_message(alert, suggestion(alert_id, "SECOND_OPINION"), advice, portal)
        else:
            message = build_message(alert, detail.get("previous_severity"), portal)
        post(url, message)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        log("slack post failed", level="ERROR", alert_id=alert_id, kind=kind, error=exc.__class__.__name__)
        ddb.table("AiSuggestions").delete_item(Key={"alert_id": alert_id, "task": kind})  # allow a later retry
        return {"sent": False, "reason": "post failed"}
    log("slack sent", alert_id=alert_id, kind=kind)
    return {"sent": True, "kind": kind}
