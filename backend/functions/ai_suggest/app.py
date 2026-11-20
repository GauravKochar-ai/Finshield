"""ai_suggest: advisory Bedrock tasks. Nothing here changes a score, a severity or a containment state.
Tasks (event {"task": ..., "alert_id": ...}). EventBridge "Alert Raised" runs SECOND_OPINION and COMPLIANCE_MAP;
"Incident Updated" with status AWAITING_APPROVAL runs CONTAINMENT_ADVICE (after containment, so only open actions are proposed):
  SECOND_OPINION      independent risk rating + reasoning next to the alert
  CONTAINMENT_ADVICE  which not-yet-done containment actions to consider (a person approves; code executes elsewhere)
  COMPLIANCE_MAP      DPDP-aligned readiness gaps and suggested controls, limited to regulations.json
  DIGEST              shift handover over the open alerts (event {"task": "DIGEST"})
Results go to the AiSuggestions table, key (alert_id, task); the digest uses alert_id "DIGEST".
Bedrock only writes words. Code checks enums, numbers and citations; on any failure a template from the same facts is stored (status FALLBACK).
Pass {"force": true} to regenerate. Without it an existing result for the same score is kept (idempotent on alert_id + task
+ score; an escalated alert gets fresh results).
After its tasks are stored it asynchronously invokes slack_notify ({"ai_followup": true, ...}) so the Slack AI message
always carries the finished suggestions. CRITICAL: after CONTAINMENT_ADVICE (AWAITING_APPROVAL). HIGH/MEDIUM: after
SECOND_OPINION and COMPLIANCE_MAP. A Slack trigger failure is logged and never fails the tasks.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import boto3
from boto3.dynamodb.conditions import Key
from finshield import bedrock, config, ddb
from finshield.log import log
HERE = Path(__file__).resolve().parent
REGS = json.loads((HERE / "regulations.json").read_text(encoding="utf-8"))
IST = timezone(timedelta(hours=5, minutes=30))
ALERT_TASKS = ("SECOND_OPINION", "CONTAINMENT_ADVICE", "COMPLIANCE_MAP")
TASKS = ALERT_TASKS + ("DIGEST",)
ACTIONS = ("REVOKE_SESSIONS", "DEACTIVATE_KEYS", "BUCKET_DENY", "DNS_BLOCK")
SEVERITIES = ("MEDIUM", "HIGH", "CRITICAL")
OPEN_STATUSES = ("OPEN", "CONTAINED", "AWAITING_APPROVAL", "LOCKED")
BUDGET_S = 40.0
MIN_ATTEMPT_S = 2.0
SMALL_NUMBER = 100
NUMBER_RE = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")
DROP_KEYS = {"name", "name_pseudo", "email", "phone", "aadhaar", "aadhaar_number", "pan", "pan_number", "address"}
COMMON = (
    "You support a security analyst at an Indian digital lender (an NBFC). Use ONLY the facts in the JSON. Never invent numbers, "
    "people, events or regulations. Every number you write must appear in the facts. Refer to the person only by the pseudonym in "
    '"subject". Never write names, Aadhaar or PAN. Say "DPDP-aligned readiness and controls", never "compliant" or "certified". '
    "The score and severity are computed by code; do not change them. Do no arithmetic: never add, convert or round numbers, copy them exactly as given. Return ONLY one JSON object, no other text.\n"
)
PROMPTS = {
    "SECOND_OPINION": COMMON + 'Give an independent risk rating. Keys: {"risk_rating": "MEDIUM|HIGH|CRITICAL", "reasoning": "max 60 words", "missed_considerations": ["0 to 3 short strings"]}',
    "CONTAINMENT_ADVICE": COMMON + 'Choose from "allowed_actions" only. Keys: {"actions": [{"action": "<one of allowed_actions>", "reason": "one sentence"}]}. Order by priority; 0 to 4 items.',
    "COMPLIANCE_MAP": COMMON + 'Cite regulations only from "regulations", copying "regulation" and "clause" exactly. Keys: {"controls": [{"regulation": "...", "clause": "...", "gap": "one sentence", "suggested_control": "one sentence"}]}. 1 to 4 items.',
    "DIGEST": COMMON + 'Write a shift handover. Keys: {"headline": "max 15 words", "summary": "max 100 words", "priorities": [{"alert_id": "<from facts>", "why": "one sentence"}]}. 0 to 5 priorities, most urgent first.',
}
def now() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")
def pseudonym(user_id: str) -> str:
    return "User-" + hashlib.sha1(user_id.encode("utf-8")).hexdigest()[:4].upper()
def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k.lower() not in DROP_KEYS}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj
def regulations_for(alert: dict[str, Any]) -> list[dict[str, Any]]:
    ids: list[str] = []
    for s in alert.get("signals", []):
        for rid in REGS["by_signal"].get(s["code"], []):
            if rid not in ids:
                ids.append(rid)
    if alert.get("severity") == "CRITICAL" and "DPDP-BREACH" not in ids:
        ids.append("DPDP-BREACH")
    return [{"id": rid, **REGS["refs"][rid]} for rid in ids if rid in REGS["refs"]]
def done_actions(alert: dict[str, Any]) -> set[str]:
    return {c["action"] for c in alert.get("containment") or [] if c.get("result") == "OK"}
def build_facts(alert: dict[str, Any]) -> dict[str, Any]:
    names = {k: v.get("name", k) for k, v in config.load_config()["signals"].items()}
    return {
        "alert_id": alert["alert_id"], "subject": pseudonym(alert["user_id"]), "score": alert["score"], "severity": alert["severity"],
        "customers_affected": alert["customers_affected"], "data_classes": alert.get("data_classes", []),
        "signals": [{"code": s["code"], "name": names.get(s["code"], s["code"]), "points": s["points"], "facts": _scrub(s.get("facts") or {})} for s in alert.get("signals", [])],
        "containment_done": [{"action": c["action"], "mode": c.get("mode"), "result": c.get("result")} for c in alert.get("containment") or []],
        "allowed_actions": [a for a in ACTIONS if a not in done_actions(alert)],
        "regulations": [{"regulation": r["regulation"], "clause": r["clause"], "summary": r["summary"]} for r in regulations_for(alert)],
    }
# ------------------------------------------------------------------ checks (return None when fine, else the reason)
def _allowed_numbers(facts: Any) -> set[str]:
    allowed: set[str] = set()
    def walk(o: Any) -> None:
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            allowed.update({str(o), str(int(o)), f"{int(o):,}"})
            if isinstance(o, float):
                allowed.add(f"{o:g}")
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            allowed.update(NUMBER_RE.findall(o))
    walk(facts)
    return allowed
def numbers_ok(texts: list[str], facts: Any) -> str | None:
    allowed = _allowed_numbers(facts)
    for n in NUMBER_RE.findall(" ".join(texts)):
        if n in allowed:
            continue
        try:
            if float(n.replace(",", "")) <= SMALL_NUMBER:
                continue
        except ValueError:
            pass
        return f"number {n} is not in the facts"
    return None
def _str_list(v: Any, max_len: int) -> bool:
    return isinstance(v, list) and len(v) <= max_len and all(isinstance(x, str) and x.strip() for x in v)
def check_second_opinion(out: dict[str, Any], facts: dict[str, Any]) -> str | None:
    if set(out) != {"risk_rating", "reasoning", "missed_considerations"}:
        return "keys must be risk_rating, reasoning, missed_considerations"
    if out["risk_rating"] not in SEVERITIES:
        return "risk_rating must be MEDIUM, HIGH or CRITICAL"
    if not isinstance(out["reasoning"], str) or not out["reasoning"].strip() or len(out["reasoning"].split()) > 60:
        return "reasoning must be 1 to 60 words"
    if not _str_list(out["missed_considerations"], 3):
        return "missed_considerations must be up to 3 strings"
    return numbers_ok([out["reasoning"], *out["missed_considerations"]], facts)
def check_containment(out: dict[str, Any], facts: dict[str, Any]) -> str | None:
    acts = out.get("actions")
    if set(out) != {"actions"} or not isinstance(acts, list) or len(acts) > 4:
        return 'must be {"actions": [up to 4 items]}'
    seen: set[str] = set()
    for a in acts:
        if not isinstance(a, dict) or set(a) != {"action", "reason"} or not isinstance(a["reason"], str) or not a["reason"].strip():
            return "each action needs action and reason"
        if a["action"] not in facts["allowed_actions"]:
            return f"action {a['action']!r} is not in allowed_actions"
        if a["action"] in seen:
            return f"duplicate action {a['action']}"
        seen.add(a["action"])
    return numbers_ok([a["reason"] for a in acts], facts)
def check_compliance(out: dict[str, Any], facts: dict[str, Any]) -> str | None:
    ctl = out.get("controls")
    if set(out) != {"controls"} or not isinstance(ctl, list) or not 1 <= len(ctl) <= 4:
        return 'must be {"controls": [1 to 4 items]}'
    cited = {(r["regulation"], r["clause"]) for r in facts["regulations"]}
    for c in ctl:
        if not isinstance(c, dict) or set(c) != {"regulation", "clause", "gap", "suggested_control"} or not all(isinstance(v, str) and v.strip() for v in c.values()):
            return "each control needs regulation, clause, gap, suggested_control"
        if (c["regulation"], c["clause"]) not in cited:
            return f"cited {c['regulation']} {c['clause']} which is not in the provided regulations"
    return numbers_ok([f"{c['gap']} {c['suggested_control']}" for c in ctl], facts)
def check_digest(out: dict[str, Any], facts: dict[str, Any]) -> str | None:
    if set(out) != {"headline", "summary", "priorities"}:
        return "keys must be headline, summary, priorities"
    if not all(isinstance(out[k], str) and out[k].strip() for k in ("headline", "summary")) or len(out["summary"].split()) > 100:
        return "headline and summary (max 100 words) are required"
    ids = {a["alert_id"] for a in facts["alerts"]}
    pr = out["priorities"]
    if not isinstance(pr, list) or len(pr) > 5:
        return "priorities must be up to 5 items"
    for p in pr:
        if not isinstance(p, dict) or set(p) != {"alert_id", "why"} or p["alert_id"] not in ids or not isinstance(p["why"], str):
            return "each priority needs a known alert_id and why"
    return numbers_ok([out["headline"], out["summary"], *[p["why"] for p in pr]], facts)
CHECKS = {"SECOND_OPINION": check_second_opinion, "CONTAINMENT_ADVICE": check_containment, "COMPLIANCE_MAP": check_compliance, "DIGEST": check_digest}
# ------------------------------------------------------------------ template fallbacks (same facts, no model)
SIGNAL_ACTIONS = {"S1": ["BUCKET_DENY"], "S2": ["BUCKET_DENY"], "S3": ["REVOKE_SESSIONS"], "S4": ["DNS_BLOCK", "BUCKET_DENY"], "S5": ["REVOKE_SESSIONS", "DEACTIVATE_KEYS"], "S8": ["REVOKE_SESSIONS"], "S11": ["BUCKET_DENY"]}
ACTION_REASON = {
    "REVOKE_SESSIONS": "Ends the active sessions of the principal; reversible by signing in again after approval.",
    "DEACTIVATE_KEYS": "Stops access keys from being used; reversible by re-activating them.",
    "BUCKET_DENY": "Blocks reads of the KYC store while the case is open; reversible by removing the deny statement.",
    "DNS_BLOCK": "Blocks the outside destination seen in the alert; reversible by removing the block rule.",
}
def fallback(task: str, facts: dict[str, Any]) -> dict[str, Any]:
    if task == "SECOND_OPINION":
        n = len(facts["signals"])
        return {"risk_rating": facts["severity"] if facts["severity"] in SEVERITIES else "MEDIUM", "missed_considerations": [],
                "reasoning": f"Template: {n} independent warning signs agree with the computed score {facts['score']} ({facts['severity']}). The AI second opinion was unavailable."}
    if task == "CONTAINMENT_ADVICE":
        picks: list[str] = []
        for s in sorted(facts["signals"], key=lambda s: -s["points"]):
            for a in SIGNAL_ACTIONS.get(s["code"], []):
                if a in facts["allowed_actions"] and a not in picks:
                    picks.append(a)
        return {"actions": [{"action": a, "reason": ACTION_REASON[a]} for a in picks]}
    if task == "COMPLIANCE_MAP":
        ctl = []
        for r in facts["regulations"][:4]:
            full = next(x for x in REGS["refs"].values() if x["clause"] == r["clause"] and x["regulation"] == r["regulation"])
            pending = "" if full.get("verified") else " (clause pending verification)"
            ctl.append({"regulation": r["regulation"], "clause": r["clause"], "gap": r["summary"] + pending,
                        "suggested_control": "Review the evidence trail against this requirement and record the decision in the case."})
        return {"controls": ctl}
    crit = [a for a in facts["alerts"] if a["severity"] == "CRITICAL"]
    return {"headline": f"{len(facts['alerts'])} open alerts, {len(crit)} critical",
            "summary": "Template: " + (", ".join(f"{a['alert_id']} {a['severity']} {a['score']} ({a['status']})" for a in facts["alerts"][:5]) or "no open alerts") + ".",
            "priorities": [{"alert_id": a["alert_id"], "why": f"{a['severity']} score {a['score']}, status {a['status']}."} for a in sorted(facts["alerts"], key=lambda a: -a["score"])[:5]]}
# ------------------------------------------------------------------ model call
def ask_model(task: str, facts: dict[str, Any], deadline: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    meta: dict[str, Any] = {"attempts": 0}
    prompt = "Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False, default=str)
    feedback = ""
    for _ in range(2):
        remaining = deadline - time.monotonic()
        if remaining < MIN_ATTEMPT_S:
            meta["reason"] = meta.get("reason") or "time budget exhausted"
            break
        meta["attempts"] += 1
        try:
            resp = bedrock.converse(PROMPTS[task], prompt + feedback, timeout_s=min(remaining, 20), max_tokens=700)
        except bedrock.BedrockUnavailable as exc:
            meta["reason"] = f"bedrock unavailable: {exc}"[:300]
            break
        meta.update(model_id=resp["model_id"], latency_ms=resp["latency_ms"])
        if resp["guardrail_intervened"]:
            meta["reason"] = "guardrail intervened"
            break
        try:
            out = bedrock.extract_json(resp["text"])
        except (ValueError, json.JSONDecodeError) as exc:
            reason: str | None = f"not JSON: {exc}"
        else:
            reason = CHECKS[task](out, facts)
            if reason is None:
                return out, meta
        meta["reason"] = reason
        feedback = f"\n\nYour previous answer was rejected: {reason}. Return the corrected JSON object only."
    return None, meta
def after_checks(task: str, out: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    """Numbers and flags that code owns."""
    if task == "SECOND_OPINION":
        out["agrees_with_score"] = out["risk_rating"] == facts["severity"]
        out["computed_severity"] = facts["severity"]
    return out
def run_task(task: str, key: str, facts: dict[str, Any], force: bool) -> dict[str, Any]:
    existing = None if force else ddb.get_item("AiSuggestions", {"alert_id": key, "task": task}, consistent=True)
    if existing and existing.get("score") == facts.get("score"):
        log("suggestion exists, kept", alert_id=key, task=task)
        return {"alert_id": key, "task": task, "written": False, "reason": "exists"}
    out, meta = ask_model(task, facts, time.monotonic() + BUDGET_S)
    status = "OK" if out else "FALLBACK"
    if out is None:
        out = fallback(task, facts)
    out = after_checks(task, out, facts)
    if task == "CONTAINMENT_ADVICE" and not out["actions"]:
        out["note"] = "No further containment action suggested."
    item = {"alert_id": key, "task": task, "status": status, "output": out, "model_id": meta.get("model_id"), "generated_at": now(),
            "review_status": "PROPOSED" if task in ("CONTAINMENT_ADVICE", "COMPLIANCE_MAP") else "INFO", "reason": meta.get("reason"),
            "score": facts.get("score"), "severity": facts.get("severity")}
    ddb.put_item("AiSuggestions", {k: v for k, v in item.items() if v is not None})
    log("ai suggestion", alert_id=key, task=task, status=status, attempts=meta.get("attempts"), reason=meta.get("reason"))
    return {"alert_id": key, "task": task, "written": True, "status": status}
def digest_facts() -> dict[str, Any]:
    alerts: list[dict[str, Any]] = []
    for st in OPEN_STATUSES:
        alerts += ddb.query("Alerts", Key("status").eq(st), index="status-detected-index", forward=False, limit=20)
    alerts.sort(key=lambda a: a["detected_at"], reverse=True)
    alerts = alerts[:20]
    by_sev: dict[str, int] = {}
    for a in alerts:
        by_sev[a["severity"]] = by_sev.get(a["severity"], 0) + 1
    return {"as_of": now(), "open_alerts": len(alerts), "by_severity": by_sev, "alerts": [
        {"alert_id": a["alert_id"], "subject": pseudonym(a["user_id"]), "severity": a["severity"], "score": a["score"], "status": a["status"],
         "customers_affected": a["customers_affected"], "signal_codes": [s["code"] for s in a.get("signals", [])]} for a in alerts]}
def trigger_slack(alert: dict[str, Any]) -> None:
    fn = os.environ.get("SLACK_NOTIFY_FN")
    if not fn:
        return
    payload = {"ai_followup": True, "alert_id": alert["alert_id"], "severity": alert["severity"], "score": alert["score"]}
    try:
        boto3.client("lambda", region_name=config.region()).invoke(FunctionName=fn, InvocationType="Event", Payload=json.dumps(payload).encode("utf-8"))
        log("slack ai follow-up triggered", alert_id=alert["alert_id"], severity=alert["severity"])
    except Exception as exc:  # Slack must never break the AI tasks
        log("slack ai follow-up trigger failed", level="WARNING", alert_id=alert["alert_id"], error=exc.__class__.__name__)
def handler(event, context=None):
    detail_type = event.get("detail-type")
    detail = event.get("detail") or {}
    task = event.get("task")
    tasks: tuple[str, ...] = ALERT_TASKS
    if detail_type == "Alert Raised":
        tasks = ("SECOND_OPINION", "COMPLIANCE_MAP")
    elif detail_type == "Incident Updated":
        if detail.get("status") != "AWAITING_APPROVAL":
            return [{"written": False, "reason": "not AWAITING_APPROVAL"}]
        tasks = ("CONTAINMENT_ADVICE",)
    alert_id = (detail if detail_type else event).get("alert_id")
    force = bool(event.get("force"))
    if task == "DIGEST":
        return [run_task("DIGEST", "DIGEST", digest_facts(), True)]
    if task and task not in ALERT_TASKS:
        raise ValueError(f"unknown task {task!r}; use one of {TASKS}")
    alert = ddb.get_item("Alerts", {"alert_id": alert_id}, consistent=True) if alert_id else None
    if not alert:
        log("alert not found", level="WARNING", alert_id=alert_id)
        return [{"alert_id": alert_id, "written": False, "reason": "alert not found"}]
    facts = build_facts(alert)
    results = []
    for t in ([task] if task else tasks):
        try:
            results.append(run_task(t, alert_id, facts, force))
        except Exception as exc:  # one failing task must not stop the others
            log("ai suggestion failed", level="ERROR", alert_id=alert_id, task=t, error=str(exc))
            results.append({"alert_id": alert_id, "task": t, "written": False, "reason": "error"})
    if detail_type == "Incident Updated" or (detail_type == "Alert Raised" and alert["severity"] != "CRITICAL"):
        trigger_slack(alert)
    return results
