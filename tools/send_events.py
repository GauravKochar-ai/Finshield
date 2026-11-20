#!/usr/bin/env python3
"""Send test scenarios to the FinShield API and watch the risk score climb.

Examples:
  python3 tools/send_events.py --scenario hero
  python3 tools/send_events.py --scenario hero --actor ADM-09   # re-run with a fresh case
  python3 tools/send_events.py --scenario decoy
  python3 tools/send_events.py --scenario all --delay 2
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from common import api_url

IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).strftime("%Y-%m-%d")


def ts(hhmm):
    return f"{TODAY}T{hhmm}:00+05:30"


def hero(actor="ADM-07"):
    return [
        {"actor_id": actor, "actor_role": "db_admin", "privileged": True, "event_type": "LOGIN",
         "ts": ts("01:12"), "source_ip": "185.220.101.7", "geo": "unknown-vpn", "mfa": False},
        {"actor_id": actor, "actor_role": "db_admin", "privileged": True, "event_type": "ASSUME_ROLE",
         "ts": ts("01:14"), "role_assumed": "KYC-DocAdmin"},
        {"actor_id": actor, "actor_role": "db_admin", "privileged": True, "event_type": "KYC_DOC_DOWNLOAD",
         "ts": ts("01:38"), "resource": "s3://fs-kyc-docs/customers/", "doc_count": 4800,
         "notes": "sample file: Aadhaar 2345 6789 0123, PAN ABCPE1234F, loan LN-20481234"},
        {"actor_id": actor, "actor_role": "db_admin", "privileged": True, "event_type": "DATA_TRANSFER",
         "ts": ts("01:41"), "destination": "s3://ext-backup-7781", "doc_count": 4800, "bytes": 2400000000},
    ]


def decoy(actor="CMP-02"):
    return [
        {"actor_id": actor, "actor_role": "compliance_officer", "privileged": True,
         "event_type": "KYC_DOC_DOWNLOAD", "ts": ts("15:00"), "resource": "s3://fs-kyc-docs/customers/",
         "doc_count": 1200, "ticket_id": "CHG-2291"},
        {"actor_id": actor, "actor_role": "compliance_officer", "privileged": True,
         "event_type": "DATA_TRANSFER", "ts": ts("15:05"), "destination": "s3://fs-audit-vault",
         "doc_count": 1200, "ticket_id": "CHG-2291"},
    ]


def login_only(actor="OPS-11"):
    return [{"actor_id": actor, "actor_role": "ops_admin", "privileged": True, "event_type": "LOGIN",
             "ts": ts("02:05"), "source_ip": "103.21.44.9", "geo": "unknown-vpn", "mfa": False}]


def night_bulk(actor="ADM-08"):
    return [
        {"actor_id": actor, "actor_role": "db_admin", "privileged": True, "event_type": "LOGIN",
         "ts": ts("00:50"), "source_ip": "10.20.1.15", "geo": "office-mumbai", "mfa": True},
        {"actor_id": actor, "actor_role": "db_admin", "privileged": True, "event_type": "KYC_DOC_DOWNLOAD",
         "ts": ts("01:05"), "resource": "s3://fs-kyc-docs/customers/", "doc_count": 900},
    ]


def personal_cloud(actor="ANL-21"):
    return [
        {"actor_id": actor, "actor_role": "credit_analyst", "privileged": False, "event_type": "LOGIN",
         "ts": ts("14:00"), "source_ip": "10.20.3.40", "geo": "office-mumbai", "mfa": True},
        {"actor_id": actor, "actor_role": "credit_analyst", "privileged": False, "event_type": "DATA_TRANSFER",
         "ts": ts("14:20"), "destination": "https://drive.personal-cloud.example", "doc_count": 20},
    ]


SCENARIOS = {"hero": hero, "decoy": decoy, "login_only": login_only,
             "night_bulk": night_bulk, "personal_cloud": personal_cloud}
EXPECTED = {"hero": "CRITICAL (1.0) + workflow", "decoy": "LOW (0.1)", "login_only": "LOW (0.3)",
            "night_bulk": "WATCH (0.6)", "personal_cloud": "WATCH (0.4)"}


def post(url, event):
    req = urllib.request.Request(url, data=json.dumps(event).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8")}


def run(name, actor, delay, url):
    events = SCENARIOS[name](actor) if actor else SCENARIOS[name]()
    print(f"\n=== {name.upper()}  (expected: {EXPECTED[name]}) ===")
    for i, ev in enumerate(events, 1):
        res = post(url, ev)
        if "error" in res:
            print(f"  [{i}] ERROR {res}")
            continue
        flag = "  -> WORKFLOW STARTED" if res.get("workflow_started") else ""
        print(f"  [{i}] {ev['event_type']:<17} score={res['case_score']:<4} {res['severity']:<8} "
              f"{','.join(res['signals'])}{flag}")
        if i < len(events):
            time.sleep(delay)
    return events[0]["actor_id"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", choices=list(SCENARIOS) + ["all"], default="hero")
    p.add_argument("--actor", help="override actor_id (use a new one to re-run a scenario)")
    p.add_argument("--delay", type=float, default=6, help="seconds between events (demo: 6)")
    args = p.parse_args()

    url = api_url()
    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for n in names:
        actor = run(n, args.actor, args.delay, url)
        print(f"  case id: case-{actor}-{TODAY.replace('-', '')}")


if __name__ == "__main__":
    main()
