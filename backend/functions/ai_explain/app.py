"""ai_explain: Bedrock writes the words for an alert; code supplies every number.

Flow: load alert -> masked facts -> Bedrock Converse (temperature 0, Guardrail, hard budget) ->
schema check + numbers check + clause check -> one retry -> else template from the same facts.
Writes alert.ai and alert.ai_status (OK | FALLBACK) and one AI_EXPLAINED evidence entry.

Input: the incident state (needs alert_id). {"force_fallback": true} skips Bedrock (used when the
state machine's 8 s budget runs out).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from finshield import bedrock, config, ddb, evidence, schema
from finshield.log import log

HERE = Path(__file__).resolve().parent
BUDGET_S = float(os.environ.get("AI_BUDGET_S", "6.0"))  # inside the 8 s Step Functions budget
MIN_ATTEMPT_S = 1.5
SUMMARY_MAX_WORDS = 80
SMALL_NUMBER = 100  # numbers up to this may appear freely in text (hours, points, percentages)
NUMBER_RE = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")  # 212, 18,400, 1.5 (never a trailing comma)
DROP_KEYS = {"name", "name_pseudo", "email", "phone", "aadhaar", "aadhaar_number", "pan", "pan_number", "address"}
SYSTEM = (HERE / "prompts" / "system.md").read_text(encoding="utf-8")
REGS = json.loads((HERE / "regulations.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ facts (masked)

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


def affected_assets(alert: dict[str, Any]) -> list[str]:
    assets: list[str] = []
    if "KYC" in alert.get("data_classes", []) and os.environ.get("KYC_BUCKET"):
        assets.append(os.environ["KYC_BUCKET"])
    for s in alert.get("signals", []):
        f = s.get("facts") or {}
        for k in ("resource_arn", "resource", "destination"):
            if f.get(k) and f[k] not in assets:
                assets.append(str(f[k]))
    return assets or ["KYC document store"]


def computed_numbers(alert: dict[str, Any]) -> dict[str, float]:
    """The numbers the AI may use, keyed by fact name. Conflicting keys are also kept as <code>.<key>."""
    out: dict[str, float] = {"score": alert["score"], "customers_affected": alert["customers_affected"]}
    for s in alert.get("signals", []):
        out[f"{s['code']}_points"] = s["points"]
        for k, v in (s.get("facts") or {}).items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if k in out and out[k] != v:
                out[f"{s['code']}.{k}"] = v
            else:
                out.setdefault(k, v)
    return out


def build_facts(alert: dict[str, Any]) -> dict[str, Any]:
    """Only these fields go to Bedrock. Signal facts are scrubbed of anything name- or ID-like."""
    signal_names = {k: v.get("name", k) for k, v in config.load_config()["signals"].items()}
    return {
        "alert_id": alert["alert_id"],
        "subject": pseudonym(alert["user_id"]),
        "score": alert["score"],
        "severity": alert["severity"],
        "customers_affected": alert["customers_affected"],
        "data_classes": alert.get("data_classes", []),
        "window": {"start": alert.get("window_start"), "detected_at": alert.get("detected_at")},
        "signals": [{"code": s["code"], "name": signal_names.get(s["code"], s["code"]), "points": s["points"], "facts": _scrub(s.get("facts") or {})} for s in alert.get("signals", [])],
        "exceptions_applied": alert.get("exceptions_applied", []),
        "affected_assets": affected_assets(alert),
        "regulations": [{"regulation": r["regulation"], "clause": r["clause"], "summary": r["summary"]} for r in regulations_for(alert)],
    }


# ------------------------------------------------------------------ checks

def _allowed_numbers(facts: dict[str, Any]) -> set[str]:
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
            allowed.update(re.findall(NUMBER_RE, o))

    walk(facts)
    return allowed


def check(ai: dict[str, Any], facts: dict[str, Any], computed: dict[str, float]) -> str | None:
    """Return None when the explanation is acceptable, else the reason it was rejected."""
    errs = schema.errors("ai_explanation", ai)
    if errs:
        return "schema: " + "; ".join(errs[:3])
    if len(ai["summary"].split()) > SUMMARY_MAX_WORDS:
        return f"summary longer than {SUMMARY_MAX_WORDS} words"
    used = ai["numbers_used"]
    if "score" not in used:
        return "numbers_used has no score"
    for k, v in used.items():
        if k not in computed:
            return f"numbers_used.{k} is not a computed fact"
        if abs(float(computed[k]) - float(v)) > 1e-9:
            return f"numbers_used.{k}={v} but computed {computed[k]}"
    allowed = _allowed_numbers(facts)
    text = " ".join([ai["headline"], ai["summary"], *ai["why_unusual"]])
    for n in re.findall(NUMBER_RE, text):
        if n in allowed:
            continue
        try:
            if float(n.replace(",", "")) <= SMALL_NUMBER:
                continue
        except ValueError:
            pass
        return f"number {n} in text is not in the facts"
    cited = {(r["regulation"], r["clause"]) for r in facts["regulations"]}
    for r in ai["rules_affected"]:
        if (r["regulation"], r["clause"]) not in cited:
            return f"cited {r['regulation']} {r['clause']} which is not in the provided regulations"
    return None


# ------------------------------------------------------------------ template fallback

ROOT_CAUSES = [
    ("S8", "An attacker or insider disabled audit logging to hide activity"),
    ("S5", "Privileged credentials are likely compromised"),
    ("S3", "Emergency access was used without a covering approval"),
    ("S4", "Data was exfiltrated to a destination outside the allowlist"),
    ("S1", "Insider misuse or a compromised account bulk-exported records"),
    ("S2", "Slow, sustained export of records over the day"),
    ("S7", "Access to customers outside the user's assigned portfolio"),
    ("S9", "The consent ledger purpose check was not enforced for this use"),
    ("S10", "Possible account takeover or payment fraud on a recently changed bank account"),
    ("S11", "A sensitive resource was misconfigured by a manual change"),
]


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


def template(alert: dict[str, Any], facts: dict[str, Any], computed: dict[str, float]) -> dict[str, Any]:
    names = {s["code"]: s["name"] for s in facts["signals"]}
    signals = sorted(alert.get("signals", []), key=lambda s: -s["points"])
    top = names.get(signals[0]["code"], "Suspicious activity") if signals else "Suspicious activity"
    classes = "/".join(alert.get("data_classes") or ["customer"])
    sig_text = ", ".join(f"{names.get(s['code'], s['code']).lower()} (+{s['points']})" for s in signals)
    summary = (
        f"{facts['subject']} triggered {len(signals)} warning signs: {sig_text}. "
        f"{alert['customers_affected']:,} customers affected. Score {alert['score']} ({alert['severity']}), computed by FinShield rules. "
        "This text is a template because the AI explanation was unavailable."
    )
    words = summary.split()
    if len(words) > SUMMARY_MAX_WORDS:
        summary = " ".join(words[: SUMMARY_MAX_WORDS - 1]) + " ..."
    why = []
    for s in signals:
        details = ", ".join(f"{k.replace('_', ' ')} {_fmt(v)}" for k, v in (s.get("facts") or {}).items())
        why.append(f"{names.get(s['code'], s['code'])}: {details}" if details else names.get(s["code"], s["code"]))
    codes = {s["code"] for s in signals}
    rules = [{"regulation": r["regulation"], "clause": r["clause"], "why": r["summary"] + ("" if r.get("verified") else " (clause pending verification)")} for r in regulations_for(alert)]
    actions = ["Keep containment in place until the investigation closes"]
    if alert["severity"] == "CRITICAL":
        actions += ["Review and approve the lock-down of the account", "Prepare the RBI and CERT-In reports within the 6-hour readiness timers", "Start the breach assessment for the Data Protection Board report"]
    else:
        actions += ["Review the activity with the user's manager", "Confirm whether the access had a business need"]
    if "S4" in codes:
        actions.append("Confirm whether data left the network and block the destination")
    numeric_keys = {k: v for k, v in computed.items() if not k.endswith("_points") and "." not in k}
    return {
        "headline": f"{top} on {classes} data, score {alert['score']} ({alert['severity']})",
        "summary": summary,
        "why_unusual": why,
        "rules_affected": rules,
        "root_cause_hypotheses": [text for code, text in ROOT_CAUSES if code in codes][:3] or ["Unusual access outside the user's normal pattern"],
        "affected_assets": facts["affected_assets"],
        "recommended_actions": actions[:5],
        "confidence": "high" if alert["score"] >= 80 and len(signals) >= 3 else "medium" if alert["score"] >= 60 or len(signals) >= 2 else "low",
        "confidence_reason": f"{len(signals)} independent warning signs computed by deterministic rules.",
        "numbers_used": numeric_keys,
    }


# ------------------------------------------------------------------ Bedrock

def ask_bedrock(facts: dict[str, Any], computed: dict[str, float], deadline: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    meta: dict[str, Any] = {"attempts": 0, "guardrail_intervened": False}
    prompt = "Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False, default=str)
    feedback = ""
    for _ in range(2):  # first try + one retry
        remaining = deadline - time.monotonic()
        if remaining < MIN_ATTEMPT_S:
            meta["reason"] = meta.get("reason") or "time budget exhausted"
            break
        meta["attempts"] += 1
        try:
            resp = bedrock.converse(SYSTEM, prompt + feedback, timeout_s=remaining)
        except bedrock.BedrockUnavailable as exc:
            meta["reason"] = f"bedrock unavailable: {exc}"[:300]
            break
        meta.update(model_id=resp["model_id"], latency_ms=resp["latency_ms"])
        if resp["guardrail_intervened"]:
            meta.update(guardrail_intervened=True, reason="guardrail intervened")
            break
        try:
            ai = bedrock.extract_json(resp["text"])
        except (ValueError, json.JSONDecodeError) as exc:
            reason = f"not JSON: {exc}"
        else:
            reason = check(ai, facts, computed)
            if reason is None:
                return ai, meta
        meta["reason"] = reason
        feedback = f"\n\nYour previous answer was rejected: {reason}. Return the corrected JSON object only."
    return None, meta


def handler(event, context):
    started = time.monotonic()
    alert_id = event.get("alert_id") or (event.get("detail") or {}).get("alert_id")
    alert = ddb.get_item("Alerts", {"alert_id": alert_id}, consistent=True) if alert_id else None
    if not alert:
        log("alert not found, nothing to explain", level="WARNING", alert_id=alert_id)
        return {"alert_id": alert_id, "ai_status": "FALLBACK", "written": False, "reason": "alert not found"}

    facts = build_facts(alert)
    computed = computed_numbers(alert)
    ai, meta = None, {"attempts": 0, "reason": "forced fallback (time budget exceeded)"}
    if not event.get("force_fallback"):
        ai, meta = ask_bedrock(facts, computed, started + BUDGET_S)
    status = "OK" if ai else "FALLBACK"
    if not ai:
        ai = template(alert, facts, computed)
        schema.validate("ai_explanation", ai)

    values = {":ai": ai, ":s": status}
    condition = "attribute_exists(alert_id)"
    names = None
    if status == "FALLBACK":  # never replace a good explanation for the same score with a template
        condition += " AND NOT (ai_status = :ok AND ai.numbers_used.#sc = :score)"
        values.update({":ok": "OK", ":score": alert["score"]})
        names = {"#sc": "score"}
    written = True
    try:
        ddb.update_item("Alerts", {"alert_id": alert_id}, "SET ai = :ai, ai_status = :s", values, names=names, condition=condition)
    except ddb.ConditionFailed:
        written = False
        log("kept existing OK explanation", alert_id=alert_id)

    execution = event.get("execution")
    latency_ms = int((time.monotonic() - started) * 1000)
    evidence.append(
        alert_id, "AI_EXPLAINED", "ai_explain",
        {"ai_status": status, "written": written, "score": alert["score"], "headline": ai["headline"], "model_id": meta.get("model_id"),
         "attempts": meta.get("attempts", 0), "reason": meta.get("reason"), "guardrail_intervened": meta.get("guardrail_intervened", False), "latency_ms": latency_ms},
        dedup_key=f"{execution}:AI_EXPLAINED:{status}" if execution else None,
    )
    log("ai explanation", alert_id=alert_id, ai_status=status, latency_ms=latency_ms, reason=meta.get("reason"))
    return {"alert_id": alert_id, "ai_status": status, "written": written, "latency_ms": latency_ms, "reason": meta.get("reason")}
