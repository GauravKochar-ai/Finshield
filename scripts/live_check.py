#!/usr/bin/env python3
"""End-to-end check of the deployed stack through the real API (Cognito sign-in, every route, the full SC-01 story).

  AWS_PROFILE=<profile> python3 scripts/live_check.py            # needs boto3; stack finshield-dev in ap-south-1
  DEMO_PASSWORD=... STACK=finshield-dev REGION=ap-south-1         # optional overrides

Prints one PASS/FAIL line per check and exits 1 if anything failed. Uses SAMPLE data only.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import boto3

STACK = os.environ.get("STACK", "finshield-dev")
REGION = os.environ.get("REGION", "ap-south-1")
PASSWORD = os.environ.get("DEMO_PASSWORD", "FinShield#Demo2026")
cf = boto3.client("cloudformation", region_name=REGION)
OUT = {o["OutputKey"]: o["OutputValue"] for o in cf.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]}
API, POOL, CLIENT = OUT["ApiUrl"].rstrip("/"), OUT["UserPoolId"], OUT["UserPoolClientId"]
idp = boto3.client("cognito-idp", region_name=REGION)
results = []


def token(user):
    r = idp.initiate_auth(ClientId=CLIENT, AuthFlow="USER_PASSWORD_AUTH",
                          AuthParameters={"USERNAME": f"{user}@finshield.example", "PASSWORD": PASSWORD})
    return r["AuthenticationResult"]["IdToken"]


def call(method, path, tok, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": tok, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(name, ok, info=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({info})" if info else ""))


def wait(fn, secs=60, every=3):
    end = time.time() + secs
    while True:
        v = fn()
        if v or time.time() > end:
            return v
        time.sleep(every)


admin, lead, analyst = token("admin"), token("securityhead"), token("analyst")
check("cognito sign-in (admin, securityhead, analyst)", True)

st, b = call("POST", "/simulate", analyst, {"scenario_id": "SC-01"})
check("POST /simulate refuses a non-Admin", st == 403, st)
st, b = call("POST", "/simulate", admin, {"reset": True})
check("POST /simulate reset", st == 200, b.get("data"))
t0 = time.time()
st, b = call("POST", "/simulate", admin, {"scenario_id": "SC-01"})
check("POST /simulate SC-01", st == 200 and b["data"]["events_sent"] == 217, b.get("data"))


def sc01():
    _s, r = call("GET", "/alerts?severity=CRITICAL", analyst)
    hits = [a for a in r.get("data") or [] if a["user_id"] == "u-017" and a["score"] == 96]
    return hits[0] if hits else None


a = wait(sc01, 60)
check("GET /alerts: one CRITICAL 96 alert for u-017", bool(a), f"{time.time() - t0:.1f}s" if a else "not found")
if not a:
    sys.exit(1)
aid = a["alert_id"]
print(f"      alert {aid}")
st, b = call("GET", f"/alerts/{aid}", analyst)
s1 = next(s for s in b["data"]["signals"] if s["code"] == "S1")
check("GET /alerts/{id} has S1 facts 212 / 2 / 106", s1["facts"] == {"downloads_15m": 212, "baseline_p95": 2, "ratio": 106},
      s1["facts"])
check("alert has no internal fields", "approval_token" not in b["data"])
st, b = call("GET", f"/alerts/{aid}/timeline", analyst)
check("GET /alerts/{id}/timeline", st == 200 and len(b["data"]) >= 200, len(b.get("data") or []))
st, b = call("GET", f"/users/u-017", analyst)
check("GET /users/{id} with baseline", st == 200 and b["data"]["baseline"]["p95_15min"] == 2, b["data"].get("name_pseudo"))
for path, user in (("/posture", analyst), ("/rules", analyst), ("/compliance", analyst), ("/privacy", analyst),
                   ("/approvals", lead)):
    st, b = call("GET", path, user)
    check(f"GET {path}", st == 200 and b.get("error") is None, st)
st, b = call("POST", "/approvals", lead, {"type": "ticket", "subject_id": "u-019", "max_files": 10, "data_class": "KYC",
                                          "valid_from": "2026-11-01T00:00:00+05:30", "valid_to": "2026-11-02T00:00:00+05:30"})
check("POST /approvals", st == 200 and b["data"]["approval_id"].startswith("APR-"), b.get("data", {}).get("approval_id"))
st, b = call("POST", f"/alerts/{aid}/ask", analyst, {"question": "Why is this alert critical?"})
check("POST /alerts/{id}/ask", st == 200 and "96" in b["data"]["answer"], b.get("data", {}).get("answer", "")[:90])


def awaiting():
    _s, r = call("GET", f"/alerts/{aid}", analyst)
    return r["data"] if r["data"]["status"] == "AWAITING_APPROVAL" else None


al = wait(awaiting, 90)
check("workflow: containment ran, status AWAITING_APPROVAL", bool(al), (al or {}).get("status"))
if al:
    check("containment recorded (4 actions)", len(al["containment"]) >= 4,
          ", ".join(f"{c['action']} {c['result']} {c['mode']}" for c in al["containment"]))
    check("ai card filled", al["ai_status"] in ("OK", "FALLBACK") and al["ai"] is not None, al["ai_status"])
reps = wait(lambda: (lambda r: r if len(r) == 4 else None)(call("GET", f"/alerts/{aid}/reports", analyst)[1].get("data") or []), 60)
check("GET /alerts/{id}/reports: 4 drafts", bool(reps), ", ".join(f"{r['report_type']} {r['status']}" for r in reps or []))
st, b = call("POST", f"/alerts/{aid}/decision", analyst, {"decision": "APPROVE", "reason": "test"})
check("POST /decision refuses an Analyst", st == 403, st)
st, b = call("POST", f"/alerts/{aid}/decision", lead, {"decision": "APPROVE", "reason": "live check: confirmed bulk export"})
check("POST /alerts/{id}/decision APPROVE", st == 200 and b["data"]["status"] == "LOCKED", b.get("data") or b.get("error"))
sfn = boto3.client("stepfunctions", region_name=REGION)
arn = f"arn:aws:states:{REGION}:{OUT['StateMachineArn'].split(':')[4]}:execution:{STACK.replace('-dev', '')}-dev-incident:{aid}-CRITICAL"
done = wait(lambda: (lambda s: s if s != "RUNNING" else None)(sfn.describe_execution(executionArn=arn)["status"]), 90)
check("Step Functions CRITICAL execution finished", done == "SUCCEEDED", done)
st, b = call("GET", f"/alerts/{aid}", analyst)
check("quarantine recorded", any(c["action"] == "QUARANTINE" for c in b["data"]["containment"]), b["data"]["status"])
st, b = call("GET", f"/alerts/{aid}/evidence", analyst)
check("GET /alerts/{id}/evidence", st == 200 and len(b["data"]) >= 8, ", ".join(e["type"] for e in b["data"])[:150])
st, b = call("POST", f"/alerts/{aid}/evidence/verify", analyst)
check("POST /evidence/verify: chain valid", st == 200 and b["data"]["valid"] is True, b.get("data"))
st, b = call("POST", f"/alerts/{aid}/evidence/tamper-demo", admin, {})
check("POST /evidence/tamper-demo: copy breaks", st == 200 and b["data"]["valid"] is False, b.get("data"))
st, b = call("POST", f"/alerts/{aid}/evidence/verify", analyst)
check("real chain still valid after tamper demo", b["data"]["valid"] is True)
st, b = call("POST", f"/alerts/{aid}/release", lead)
check("POST /alerts/{id}/release", st == 200 and b["data"]["status"] == "RELEASED",
      ", ".join(f"{r['action']} {r['result']}" for r in (b.get("data") or {}).get("released", [])))
st, b = call("GET", "/accuracy", admin)
check("GET /accuracy (latest run)", st == 200 and b["data"]["total"] == 11, f"{b['data']['passed']}/{b['data']['total']}" if st == 200 else st)

s3 = boto3.client("s3", region_name=REGION)
key = "kyc/C-10001/KYC-PAN-C-10001.png"
s3.put_object(Bucket=OUT["KycBucket"], Key=key, Body=b"\x89PNG SAMPLE", ContentType="image/png")
ddbt = boto3.resource("dynamodb", region_name=REGION).Table(f"{STACK}-KycFiles")
row = wait(lambda: (lambda i: i if i and i.get("label_source") else None)(ddbt.get_item(Key={"file_id": "KYC-PAN-C-10001"}).get("Item")), 45)
check("kyc_label: S3 upload labelled in KycFiles", bool(row), (row or {}).get("ai_label"))

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
