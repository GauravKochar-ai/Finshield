"""ask: POST /v1/alerts/{id}/ask {"question": "..."} -> {answer, sources} ("Ask FinShield").

The answer is built from the alert's computed facts and its evidence chain. With a Bedrock model configured the model
answers in plain words from those facts only (masked, Guardrail on) and is rejected if it uses a number that is not in
the facts. Without Bedrock, or on rejection, a rule-based answer from the same facts is returned.
"""
from __future__ import annotations

import json
import re

from finshield import bedrock, ddb, evidence
from finshield.http import HttpError, body, is_http, path_id, require, run

GROUPS = ["Analyst", "SecurityHead", "ComplianceHead", "Admin"]
NUM = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")
SYSTEM = ("You are FinShield, a security assistant for an Indian digital lender. Answer the analyst's question in at most "
          "80 words using ONLY the JSON facts. Use no number that is not in the facts. Never state a legal finding. "
          'Return JSON {"answer": "...", "sources": ["alert:<id>", "signal:S1", ...]}.')


def facts(a):
    chain = evidence.chain(a["alert_id"])
    return {"alert_id": a["alert_id"], "score": a["score"], "severity": a["severity"], "status": a.get("status"),
            "customers_affected": a.get("customers_affected"), "data_classes": a.get("data_classes"),
            "detected_at": a["detected_at"], "window_start": a.get("window_start"),
            "signals": [{"code": s["code"], "points": s["points"], "facts": s.get("facts")} for s in a.get("signals") or []],
            "exceptions_applied": a.get("exceptions_applied"), "deadlines": a.get("deadlines"),
            "containment": [{k: c.get(k) for k in ("action", "mode", "result", "at")} for c in a.get("containment") or []],
            "evidence_steps": [e["type"] for e in chain]}


def rule_answer(q, f):
    ql = q.lower()
    sig = {s["code"]: s for s in f["signals"]}
    src = [f"alert:{f['alert_id']}"]
    parts = []
    if any(w in ql for w in ("why", "score", "signal", "reason", "unusual")):
        parts.append(f"Score {f['score']} ({f['severity']}) from " +
                     ", ".join(f"{c} +{s['points']}" for c, s in sig.items()) + ".")
        src += [f"signal:{c}" for c in sig]
    if "S1" in sig and any(w in ql for w in ("file", "download", "volume", "how many", "much")):
        fa = sig["S1"]["facts"]
        parts.append(f"{fa.get('downloads_15m')} downloads in 15 minutes against a usual {fa.get('baseline_p95')} "
                     f"({fa.get('ratio')}x).")
    if any(w in ql for w in ("customer", "affected", "who")):
        parts.append(f"{f['customers_affected']} customers potentially affected; data classes {', '.join(f['data_classes'] or [])}.")
    if any(w in ql for w in ("contain", "block", "action", "done", "revoke")):
        parts.append("Containment: " + (", ".join(f"{c['action']} {c['result']} ({c['mode']})" for c in f["containment"])
                                        or "not started yet") + ".")
    if any(w in ql for w in ("deadline", "report", "rbi", "cert", "dpb", "when")):
        parts.append("Readiness timers: " + ", ".join(f"{d['body']} by {d['due_at']}" for d in f["deadlines"] or []) + ".")
    if not parts:
        parts.append(f"Alert {f['alert_id']}: score {f['score']} ({f['severity']}), status {f['status']}, "
                     f"{f['customers_affected']} customers, signs " + ", ".join(sig) + ".")
    return {"answer": " ".join(parts), "sources": src}


def answer(aid, q):
    a = ddb.get_item("Alerts", {"alert_id": aid}, consistent=True)
    if not a:
        raise HttpError(404, "NOT_FOUND", f"alert {aid} not found")
    f = facts(a)
    try:
        r = bedrock.converse(SYSTEM, json.dumps({"question": q, "facts": f}, default=str), timeout_s=8, max_tokens=400)
        out = bedrock.extract_json(r["text"])
        allowed = set(NUM.findall(json.dumps(f, default=str)))
        if isinstance(out.get("answer"), str) and all(n in allowed for n in NUM.findall(out["answer"])):
            return {"answer": out["answer"], "sources": [s for s in out.get("sources") or [] if isinstance(s, str)][:10]}
    except (bedrock.BedrockUnavailable, ValueError):
        pass
    return rule_answer(q, f)


def handler(event, context=None):
    if is_http(event):
        def go():
            require(event, GROUPS)
            b = body(event)
            q = b.get("question")
            if not isinstance(q, str) or not q.strip() or set(b) - {"question"}:
                raise HttpError(400, "BAD_REQUEST", 'body must be {"question": "..."}')
            return answer(path_id(event), q.strip()[:500])
        return run(event, go)
    return answer(event["alert_id"], event["question"])
