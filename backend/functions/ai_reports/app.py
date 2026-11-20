"""ai_reports: four regulatory drafts per alert (invoked asynchronously by Step Functions with {alert_id, execution}).

RBI_INCIDENT, CERTIN_FORM, DPB_NOTICE, CUSTOMER_NOTICE. Every number comes from the alert (code computes, AI only words).
With a Bedrock model configured (SSM bedrock_model_id + guardrail) the model rewrites each template in plain language
and the result is kept only if it uses no number that is not in the alert; otherwise the template is stored (FALLBACK).
Wording: drafts only, "DPDP-aligned readiness and controls", no legal finding.
"""
from __future__ import annotations

import re
from datetime import datetime

from finshield import bedrock, ddb, evidence, schema
from finshield.config import load_config
from finshield.log import log
from finshield.scoring import tz_offset

TYPES = ("RBI_INCIDENT", "CERTIN_FORM", "DPB_NOTICE", "CUSTOMER_NOTICE")
NUM = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")
SYSTEM = ("You rewrite a regulatory draft for an Indian digital lender in clear, formal English. Keep every heading. "
          "Use only the numbers already in the draft and add no new ones. Never state that a breach, violation or "
          "non-compliance has occurred; say 'potential' or 'may require review'. Return only the Markdown.")


def _now():
    return datetime.now(tz_offset(load_config())).isoformat(timespec="seconds")


def _facts(a):
    sig = "\n".join(f"- {s['code']} (+{s['points']}): " + ", ".join(f"{k} {v}" for k, v in (s.get('facts') or {}).items())
                    for s in a.get("signals") or [])
    due = {d["body"]: d["due_at"] for d in a.get("deadlines") or []}
    cont = "\n".join(f"- {c['action']}: {c['result']} ({c['mode']})" for c in a.get("containment") or []) or "- pending"
    return sig, due, cont


def templates(a):
    sig, due, cont = _facts(a)
    head = (f"**DRAFT, SAMPLE data. A human reviewer checks and submits this.**\n\n"
            f"- Incident: {a['alert_id']}\n- Detected: {a['detected_at']}\n- Severity: {a['severity']} (score {a['score']})\n"
            f"- Customers potentially affected: {a['customers_affected']}\n- Data classes: {', '.join(a.get('data_classes') or [])}\n")
    return {
        "RBI_INCIDENT": f"# RBI cyber incident report (draft)\n\n{head}- Readiness timer due: {due.get('RBI')}\n\n"
                        f"## Warning signs\n{sig}\n\n## Containment\n{cont}\n\n## Assessment\nThe activity may require review as "
                        f"a potential reportable incident. This draft makes no legal finding.\n",
        "CERTIN_FORM": f"# CERT-In incident form (draft)\n\n{head}- Readiness timer due: {due.get('CERT-In')}\n\n"
                       f"## Incident type\nPotential unauthorised access to customer KYC data by a privileged account.\n\n"
                       f"## Indicators\n{sig}\n\n## Actions taken\n{cont}\n\nLogs are kept in the sealed evidence chain.\n",
        "DPB_NOTICE": f"# Data Protection Board detailed report (draft)\n\n{head}- Readiness timer due: {due.get('DPB')}\n\n"
                      f"## What happened\n{sig}\n\n## Measures\n{cont}\n\nPrepared as part of DPDP-aligned readiness and "
                      f"controls. This draft makes no legal finding.\n",
        "CUSTOMER_NOTICE": f"# Notice to customers (draft)\n\n**DRAFT, SAMPLE data.**\n\nWe noticed unusual access to some "
                           f"customer records on {a['detected_at'][:10]} and acted at once to stop it. About "
                           f"{a['customers_affected']} customers may be affected. We are reviewing what happened and will "
                           f"write again with next steps. Our Privacy Officer reviews this notice before it is sent.\n",
    }


def _numbers_ok(text, source):
    allowed = set(NUM.findall(source))
    return all(n in allowed for n in NUM.findall(text))


def generate(alert_id, execution=None, use_ai=True):
    a = ddb.get_item("Alerts", {"alert_id": alert_id}, consistent=True)
    if not a:
        log("alert not found, no reports", level="WARNING", alert_id=alert_id)
        return {"alert_id": alert_id, "written": 0}
    out = []
    for rtype, body in templates(a).items():
        status, model = "FALLBACK", "template"
        if use_ai:
            try:
                r = bedrock.converse(SYSTEM, body, timeout_s=12, max_tokens=1500)
                if not r["guardrail_intervened"] and _numbers_ok(r["text"], body) and r["text"].strip():
                    body, status, model = r["text"].strip(), "DRAFT", r["model_id"]
            except bedrock.BedrockUnavailable as exc:
                log("bedrock unavailable, template report", alert_id=alert_id, report=rtype, reason=str(exc)[:200])
                use_ai = False  # no point retrying for the other three
        item = {"alert_id": alert_id, "report_type": rtype, "status": status, "body_md": body, "model_id": model,
                "generated_at": _now()}
        schema.validate("report", item)
        ddb.put_item("Reports", item)
        out.append({"report_type": rtype, "status": status})
    evidence.append(alert_id, "REPORTS_DRAFTED", "ai_reports", {"reports": out},
                    dedup_key=f"{execution}:REPORTS_DRAFTED" if execution else None)
    return {"alert_id": alert_id, "written": len(out), "reports": out}


def handler(event, context=None):
    return generate(event.get("alert_id") or (event.get("detail") or {}).get("alert_id"), event.get("execution"),
                    use_ai=not event.get("force_fallback"))
