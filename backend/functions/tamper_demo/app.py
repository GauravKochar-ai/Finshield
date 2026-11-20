"""tamper_demo: POST /v1/alerts/{id}/evidence/tamper-demo (Admin). Edits one entry of an in-memory COPY of the evidence
chain and verifies the copy, so the demo can show where the chain breaks. Nothing is written (read-only role)."""
import copy

from finshield import evidence
from finshield.http import HttpError, body, is_http, path_id, require, run


def tamper(aid, seq=None):
    entries = evidence.chain(aid)
    if not entries:
        raise HttpError(404, "NOT_FOUND", f"no evidence for alert {aid}")
    work = copy.deepcopy(sorted(entries, key=lambda e: e["seq"]))
    pick = next((e for e in work if e["seq"] == seq), None) if seq else work[len(work) // 2]
    if pick is None:
        raise HttpError(400, "BAD_REQUEST", f"seq {seq} not in chain")
    pick.setdefault("payload", {})["tampered"] = "edited by tamper demo"
    out = evidence.verify_entries(aid, work)
    return {"valid": out["valid"], "broken_at_seq": out["broken_at_seq"]}


def handler(event, context=None):
    if is_http(event):
        def go():
            require(event, ["Admin"])
            return tamper(path_id(event), body(event).get("seq"))
        return run(event, go)
    return tamper(event["alert_id"], event.get("seq"))
