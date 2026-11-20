"""fs-analyze: builds the case timeline, masks Aadhaar / PAN (local regex +
optional Bedrock Guardrail), asks Bedrock for a verdict and returns
severity, summary, MITRE ATT&CK and regulation mapping.

Safety rules:
  * The AI can RAISE severity, it can never LOWER it below the rule engine.
  * PRIVILEGED + BULK_KYC + UNAUTHORIZED_DESTINATION is always CRITICAL.
  * If Bedrock is not configured or fails, a rule-based verdict is used so
    the workflow never breaks.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

ddb = boto3.resource("dynamodb")
events_table = ddb.Table(os.environ["EVENTS_TABLE"])
cases_table = ddb.Table(os.environ["CASES_TABLE"])
bedrock = boto3.client("bedrock-runtime")

MODEL_ID = os.environ.get("MODEL_ID", "NONE")
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID", "NONE")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "1")
IST = timezone(timedelta(hours=5, minutes=30))

SEVERITIES = ["LOW", "WATCH", "HIGH", "CRITICAL"]
CRITICAL_TRIAD = {"PRIVILEGED_ACTOR", "BULK_KYC_ACCESS", "UNAUTHORIZED_DESTINATION"}
ALLOWED_REGULATIONS = [
    "DPDP Act 2023",
    "RBI Cybersecurity Directions (NBFC) 2026",
    "RBI Digital Lending Directions 2025",
    "RBI IT Outsourcing Directions 2023",
    "CERT-In Directions 2022",
]
SIGNAL_MITRE = {
    "PRIVILEGED_ACTOR": "T1078",           # Valid Accounts
    "ANOMALOUS_LOGIN": "T1078",
    "BULK_KYC_ACCESS": "T1530",            # Data from Cloud Storage
    "UNAUTHORIZED_DESTINATION": "T1537",   # Transfer Data to Cloud Account
}

# ---------------------------------------------------------------- masking
# Order matters: loan numbers first, and Aadhaar only allows spaces/dashes
# inside the number (never line breaks), so nothing is matched across lines.
PII_PATTERNS = [
    ("{LOAN_ACCOUNT}", re.compile(r"\bLN-\d{8}\b")),
    ("{AADHAAR}", re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b")),
    ("{PAN}", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("{EMAIL}", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("{PHONE}", re.compile(r"(?<![\d=])(?:\+91[ -]?)?[6-9]\d{9}\b")),
]


def local_mask(text):
    count = 0
    for label, pattern in PII_PATTERNS:
        text, n = pattern.subn(label, text)
        count += n
    return text, count


def guardrail_mask(text):
    """Second layer of masking with Bedrock Guardrails (if configured)."""
    if GUARDRAIL_ID in ("", "NONE"):
        return text, False
    try:
        r = bedrock.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID,
            guardrailVersion=GUARDRAIL_VERSION,
            source="INPUT",
            content=[{"text": {"text": text}}],
        )
        if r.get("action") == "GUARDRAIL_INTERVENED" and r.get("outputs"):
            return r["outputs"][0]["text"], True
    except Exception as exc:  # never break the workflow on masking layer 2
        print("Guardrail error:", repr(exc))
    return text, False


# ---------------------------------------------------------------- timeline
def load_events(actor_id, event_ids):
    items, kwargs = [], {"KeyConditionExpression": Key("actor_id").eq(actor_id)}
    while True:
        page = events_table.query(**kwargs)
        items.extend(page["Items"])
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    wanted = set(event_ids or [])
    if wanted:
        items = [e for e in items if e.get("event_id") in wanted]
    return sorted(items, key=lambda e: e["ts"])


def describe(e):
    parts = [f"{e['ts']} | {e.get('event_type')}"]
    for field in ("actor_role", "source_ip", "geo", "mfa", "role_assumed", "resource",
                  "doc_count", "bytes", "destination", "ticket_id", "notes"):
        if e.get(field) not in (None, ""):
            parts.append(f"{field}={e[field]}")
    return " | ".join(parts)


# ---------------------------------------------------------------- bedrock
SYSTEM_PROMPT = (
    "You are a senior SOC analyst at an Indian digital lending NBFC. You receive a "
    "correlated security case (risk signals plus a timeline of events for one user). "
    "Reply ONLY with one JSON object, no markdown, with these keys:\n"
    '  "severity": one of LOW, WATCH, HIGH, CRITICAL\n'
    '  "summary": 2-3 plain-English sentences explaining what happened and why it is risky\n'
    '  "mitre": list of MITRE ATT&CK technique IDs (e.g. "T1078")\n'
    '  "regulation": list chosen ONLY from: ' + "; ".join(ALLOWED_REGULATIONS) + "\n"
    '  "recommended_actions": list of 3-5 short action strings\n'
    "Never include personal data such as names, Aadhaar, PAN or phone numbers."
)


def extract_json(text):
    text = text.strip().strip("`")
    if text.lower().startswith("json"):
        text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def ask_bedrock(case_text):
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": case_text}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 800},
    )
    return extract_json(resp["output"]["message"]["content"][0]["text"])


def rule_based_verdict(signals, severity_rule, docs, destinations):
    sig = set(signals)
    bits = []
    if "PRIVILEGED_ACTOR" in sig:
        bits.append("a privileged account")
    if "ANOMALOUS_LOGIN" in sig:
        bits.append("logged in anomalously (unknown network / no MFA / off-hours)")
    if "BULK_KYC_ACCESS" in sig:
        bits.append(f"accessed {docs} KYC documents, far above its normal baseline")
    if "UNAUTHORIZED_DESTINATION" in sig:
        bits.append(f"transferred data to an unapproved destination ({', '.join(destinations) or 'unknown'})")
    summary = ("Rule engine: " + "; ".join(bits) + ".") if bits else "Rule engine: low-risk activity."
    actions = ["Revoke active sessions", "Block the destination", "Disable the account after CISO approval",
               "Preserve the evidence pack", "Prepare RBI / CERT-In / DPDP notifications"]
    return {
        "severity": severity_rule,
        "summary": summary,
        "mitre": sorted({SIGNAL_MITRE[s] for s in sig if s in SIGNAL_MITRE}),
        "regulation": ALLOWED_REGULATIONS[:2] + ["CERT-In Directions 2022"],
        "recommended_actions": actions,
    }


def clean_verdict(v, fallback):
    sev = str(v.get("severity", "")).upper()
    out = {
        "severity": sev if sev in SEVERITIES else fallback["severity"],
        "summary": str(v.get("summary") or fallback["summary"])[:1200],
        "mitre": [str(m) for m in v.get("mitre", [])][:8] or fallback["mitre"],
        "regulation": [r for r in v.get("regulation", []) if r in ALLOWED_REGULATIONS] or fallback["regulation"],
        "recommended_actions": [str(a) for a in v.get("recommended_actions", [])][:6]
                               or fallback["recommended_actions"],
    }
    return out


def final_severity(ai_sev, rule_sev, signals):
    if CRITICAL_TRIAD.issubset(set(signals)):
        return "CRITICAL"
    return SEVERITIES[max(SEVERITIES.index(ai_sev), SEVERITIES.index(rule_sev))]


# ---------------------------------------------------------------- handler
def lambda_handler(event, context):
    case_id = event["case_id"]
    actor_id = event["actor_id"]
    signals = event.get("signals", [])
    severity_rule = event.get("severity_rule", "HIGH")
    if severity_rule not in SEVERITIES:
        severity_rule = "HIGH"
    docs = event.get("docs_involved", 0)
    destinations = event.get("destinations", [])

    events = load_events(actor_id, event.get("event_ids"))
    timeline_raw = "\n".join(describe(e) for e in events)
    timeline, local_hits = local_mask(timeline_raw)
    timeline, guardrail_hit = guardrail_mask(timeline)

    case_text = (
        f"Case: {case_id}\nActor: {actor_id}\nRule score: {event.get('case_score')}\n"
        f"Rule severity: {severity_rule}\nSignals: {', '.join(signals)}\n"
        f"Documents involved: {docs}\nDestinations: {', '.join(destinations) or 'none'}\n"
        f"Timeline:\n{timeline}"
    )

    fallback = rule_based_verdict(signals, severity_rule, docs, destinations)
    ai_used, ai_error = False, None
    if MODEL_ID not in ("", "NONE"):
        try:
            verdict = clean_verdict(ask_bedrock(case_text), fallback)
            ai_used = True
        except Exception as exc:
            ai_error = repr(exc)[:300]
            print("Bedrock error, using rule-based verdict:", ai_error)
            verdict = fallback
    else:
        verdict = fallback

    verdict["severity"] = final_severity(verdict["severity"], severity_rule, signals)
    analyzed_at = datetime.now(IST).isoformat(timespec="seconds")

    alert_message = (
        f"FinShield AI - {verdict['severity']} case {case_id}\n"
        f"Actor: {actor_id}   Score: {event.get('case_score')}\n"
        f"Signals: {', '.join(signals)}\n\n"
        f"{verdict['summary']}\n\n"
        f"MITRE ATT&CK: {', '.join(verdict['mitre'])}\n"
        f"Regulations: {', '.join(verdict['regulation'])}\n"
        f"Recommended: {'; '.join(verdict['recommended_actions'])}\n\n"
        f"Open the FinShield SOC dashboard to review the evidence and approve."
    )

    cases_table.update_item(
        Key={"case_id": case_id},
        UpdateExpression=(
            "SET severity = :sev, summary = :sum, mitre = :m, regulation = :r, "
            "recommended_actions = :ra, masked_timeline = :tl, pii_masked_count = :pc, "
            "guardrail_applied = :g, ai_used = :ai, ai_error = :err, analyzed_at = :at, #st = :st"
        ),
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":sev": verdict["severity"],
            ":sum": verdict["summary"],
            ":m": verdict["mitre"],
            ":r": verdict["regulation"],
            ":ra": verdict["recommended_actions"],
            ":tl": timeline,
            ":pc": local_hits,
            ":g": guardrail_hit,
            ":ai": ai_used,
            ":err": ai_error,
            ":at": analyzed_at,
            ":st": "ANALYZED",
        },
    )

    return {**event, **verdict, "ai_used": ai_used, "alert_message": alert_message,
            "analyzed_at": analyzed_at}
