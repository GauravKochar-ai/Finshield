#!/usr/bin/env python3
"""FinShield seed data and scenario files (M3 / M7). Ported from the boilerplate generator.py.

All data is synthetic and marked SAMPLE: pseudonymous names ("SAMPLE-Ops-017"), Aadhaar last 4 digits only,
fake PAN values, hashed bank accounts. Output is deterministic for a given --now.

  python3 simulator/seed/generate.py --out build/seed            # JSON files, for tests
  python3 simulator/seed/generate.py --load                      # batch-write every table (TABLE_* env or finshield-<stage>-<Table>)
  python3 simulator/seed/generate.py --scenarios simulator/scenarios   # rewrite SC-01..SC-10 + SC-01b

Scoring numbers are never used here. Each scenario user gets its own normal pattern so the baseline gives the
p95 the scenario needs (contract/CHANGES.md OPEN-1); the scenario files carry the expected score and level.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "backend" / "shared" / "python", Path(__file__).resolve().parent):
    if str(p) not in sys.path and p.is_dir():
        sys.path.insert(0, str(p))

IST = timezone(timedelta(hours=5, minutes=30))
SEED = 2026
ACCOUNT_PLACEHOLDER = "000000000000"
DOC_TYPES = ["PAN", "AADHAAR", "SELFIE", "ADDRESS"]
CUSTOMER_FIRST, CUSTOMER_LAST = 10001, 12000
CITIES = ["Mumbai", "Pune", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad", "Jaipur"]
BASE_PURPOSES = ["loan_processing", "collections", "audit", "registry_upload"]
PARTNERS = {"P-QUICKCOLLECT": ["p-001", "p-002", "p-003"], "P-RECOVERWELL": ["p-004", "p-005", "p-006"]}
INTERNAL_AGENTS = ["u-031", "u-032", "u-033", "u-034", "u-035", "u-036"]
NORMAL_HISTORY_DAYS = 30   # days of normal activity written to Events (ends 2 days before --now)
NORMAL_GAP_DAYS = 2        # keeps normal history out of every scenario user's last 24 hours
ACCURACY_NORMAL_DAYS = 7

# team: (label, role, access_scope, purpose, data_class, action)
TEAMS = {
    "ops": ("Ops", "Ops Executive", "ALL", "loan_processing", "KYC", "DOWNLOAD"),
    "kyc": ("KYC", "KYC Analyst", "ALL", "loan_processing", "KYC", "DOWNLOAD"),
    "credit": ("Credit", "Credit Analyst", "ALL", "loan_processing", "KYC", "DOWNLOAD"),
    "collections": ("Coll", "Collections Agent", "ASSIGNED", "collections", "PII", "DOWNLOAD"),
    "partner_lsp": ("LSP", "Partner LSP Agent", "ASSIGNED", "collections", "PII", "DOWNLOAD"),
    "marketing": ("Mkt", "Marketing Executive", "ASSIGNED", "marketing", "PII", "VIEW"),
    "audit": ("Audit", "Internal Auditor", "ALL", "audit", "KYC", "DOWNLOAD"),
    "security": ("Sec", "Security", "ALL", "audit", "PII", "VIEW"),
    "cloud": ("Cloud", "Cloud Admin", "ALL", None, None, None),
    "service": ("Svc", "Service account", "ALL", None, None, None),
}

# user_id: (team, downloads per active 15-min window = the p95 the baseline will show, home city, extras)
USERS = {
    **{f"u-{n:03d}": ("ops", 1 if n % 2 else 2, "Mumbai", {}) for n in range(1, 9)},
    "u-017": ("ops", 2, "Pune", {"is_admin": True, "role": "Ops Admin", "iam": "role/finshield-{stage}-demo-ops-admin",
                                 "staff_email": "ops.admin@finlend.example"}),
    "u-018": ("ops", 2, "Pune", {"is_admin": True, "role": "Ops Admin"}),
    **{f"u-{n:03d}": ("kyc", 2 + n % 2, "Mumbai", {}) for n in (9, 10, 12, 13, 14, 15, 16)},
    "u-011": ("kyc", 4, "Mumbai", {}),
    **{f"u-{n:03d}": ("credit", 1 + n % 3, "Bengaluru", {}) for n in range(19, 25)},
    "u-031": ("collections", 4, "Mumbai", {"staff_email": "collections.agent@finlend.example"}),
    "u-032": ("collections", 3, "Mumbai", {}),
    **{f"u-{n:03d}": ("collections", 3, "Pune", {}) for n in range(33, 37)},
    **{p: ("partner_lsp", 2, "Delhi", {"partner_id": pid}) for pid, ps in PARTNERS.items() for p in ps},
    "u-037": ("marketing", 0, "Mumbai", {"staff_email": "marketing.user@finlend.example"}),
    **{f"u-{n:03d}": ("marketing", 0, "Mumbai", {}) for n in (38, 39, 40)},
    "u-041": ("audit", 4, "Mumbai", {}),
    "u-042": ("audit", 4, "Mumbai", {}),
    "u-043": ("audit", 3, "Mumbai", {}),
    "u-044": ("security", 0, "Mumbai", {"is_admin": True, "role": "Security Head"}),
    "u-045": ("security", 0, "Mumbai", {"role": "Compliance Head"}),
    "u-046": ("cloud", 0, "Kolkata", {"is_admin": True}),
    "u-047": ("cloud", 0, "Mumbai", {"is_admin": True}),
    "u-048": ("cloud", 0, "Mumbai", {"is_admin": True}),
    "svc-ckyc": ("service", 20, "Mumbai", {"role": "CKYC registry upload job"}),
    "svc-aws-config": ("service", 0, "Mumbai", {"role": "AWS Config findings"}),
    "svc-aws-guardduty": ("service", 0, "Mumbai", {"role": "Amazon GuardDuty findings"}),
    "svc-bureau": ("service", 0, "Mumbai", {"role": "Credit bureau pull job"}),
}


def iso(dt: datetime) -> str:
    return dt.astimezone(IST).isoformat(timespec="seconds")


def h(s: str, n: int = 16) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:n]


# ------------------------------------------------------------------ reference data
def make_users(account=ACCOUNT_PLACEHOLDER, stage="dev"):
    out = []
    for uid, (team, _p95, city, extra) in USERS.items():
        label, role, scope, purpose, *_ = TEAMS[team]
        svc = team == "service"
        num = uid.split("-")[-1]
        iam = extra.get("iam", f"user/sample-{uid}").format(stage=stage)
        out.append({
            "user_id": uid, "name_pseudo": f"SAMPLE-{label}-{num}", "team": team, "role": extra.get("role", role),
            "is_admin": bool(extra.get("is_admin")), "is_service": svc,
            "office_start": "00:00" if svc else "09:00", "office_end": "23:59" if svc else "18:00",
            "home_city": city, "devices": [f"srv-{uid}" if svc else f"d-{uid}"],
            "partner_id": extra.get("partner_id"), "access_scope": scope,
            "iam_principal_arn": f"arn:aws:iam::{account}:{iam}", "sample": True,
            "staff_email": extra.get("staff_email"), "default_purpose": purpose,  # FinLend Ops persona (CHANGE-10)
        })
    return out


def agent_for(n: int):
    """Customer number -> (assigned_agent, partner_id)."""
    i = n - CUSTOMER_FIRST
    if i < 1200:
        return INTERNAL_AGENTS[i // 200], None
    j = (i - 1200) // 134
    flat = [(p, pid) for pid, ps in PARTNERS.items() for p in ps]
    return flat[min(j, len(flat) - 1)]


def consent_purposes(n: int):
    """Even customers also consented to marketing; every tenth one later withdrew marketing."""
    purposes = list(BASE_PURPOSES)
    withdrawn = []
    if n % 2 == 0:
        if n % 10 == 0:
            withdrawn = ["marketing"]
        else:
            purposes.append("marketing")
    return purposes, withdrawn


def kyc_manifest() -> dict[str, dict]:
    """customer_id -> Roopak's manifest row (simulator/seed/kyc-docs/manifest.csv), empty when the file is absent."""
    manifest = Path(__file__).resolve().parent / "kyc-docs" / "manifest.csv"
    if not manifest.is_file():
        return {}
    with open(manifest, newline="", encoding="utf-8") as f:
        return {r["customer_id"]: r for r in csv.DictReader(f) if r.get("customer_id")}


def make_customers(now):
    rnd = random.Random(SEED + 1)
    docs = kyc_manifest()
    out = []
    for n in range(CUSTOMER_FIRST, CUSTOMER_LAST + 1):
        agent, partner = agent_for(n)
        city, last4 = rnd.choice(CITIES), f"{rnd.randint(0, 9999):04d}"
        doc = docs.get(f"C-{n}") or {}
        if doc.get("doc_type") == "AADHAAR" and doc.get("aadhaar_last4"):
            last4 = doc["aadhaar_last4"]  # the record agrees with the card image
        out.append({
            "customer_id": f"C-{n}", "city": city, "aadhaar_last4": last4,
            "pan_fake": doc.get("pan_fake") or f"SAMPL{n % 10000:04d}A", "loan_id": f"LN-SAMPLE-{n}", "assigned_agent": agent,
            "partner_id": partner, "bank_account_hash": h(f"bank-{n}-{SEED}"),
            "bank_account_changed_at": iso(now - timedelta(days=60 + (n * 37) % 600)), "sample": True,
        })
    return out


def make_kyc_files(customers):
    manifest = Path(__file__).resolve().parent / "kyc-docs" / "manifest.csv"
    if manifest.is_file():  # Roopak's manifest of the real sample files, when present
        rows = []
        with open(manifest, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = r.get("s3_key") or r.get("key")
                name = key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                parts = name.split("-")
                rows.append({"file_id": r.get("file_id") or name, "customer_id": r.get("customer_id") or "-".join(parts[-2:]),
                             "doc_type": r.get("doc_type") or parts[1], "s3_key": key, "size_kb": int(r.get("size_kb") or 0),
                             "ai_label": None, "unmasked_aadhaar_flag": False, "sample": True})
        return rows
    rnd = random.Random(SEED + 2)
    return [{"file_id": f"KYC-{d}-{c['customer_id']}", "customer_id": c["customer_id"], "doc_type": d,
             "s3_key": f"kyc/{c['customer_id']}/KYC-{d}-{c['customer_id']}.png", "size_kb": rnd.randint(80, 900),
             "ai_label": None, "unmasked_aadhaar_flag": False, "sample": True}
            for c in customers for d in DOC_TYPES]


def make_consent(now):
    out = []
    for n in range(CUSTOMER_FIRST, CUSTOMER_LAST + 1):
        purposes, withdrawn = consent_purposes(n)
        out.append({"customer_id": f"C-{n}", "purposes": purposes, "withdrawn": withdrawn,
                    "given_at": iso(now - timedelta(days=200 + n % 300)), "notice_version": "v2.1-SAMPLE", "sample": True})
    return out


def make_approvals(now):
    far_past, far_future = iso(now - timedelta(days=365)), iso(now + timedelta(days=365))
    ticket_from, ticket_to = iso(now - timedelta(days=2)), iso(now + timedelta(days=30))
    return [
        {"approval_id": "JOB-CKYC-NIGHTLY", "type": "scheduled_job", "subject_id": "svc-ckyc", "job_id": "ckyc-nightly-upload",
         "max_files": 1000, "data_class": "KYC", "window_start": "01:30", "window_end": "03:30",
         "valid_from": far_past, "valid_to": far_future, "approver_id": "u-044", "sample": True},
        {"approval_id": "T-SC03-AUDIT", "type": "ticket", "subject_id": "u-041", "max_files": 100, "data_class": "KYC",
         "valid_from": ticket_from, "valid_to": ticket_to, "approver_id": "u-044", "note": "Quarterly KYC sample audit", "sample": True},
        {"approval_id": "T-SC10-AUDIT", "type": "ticket", "subject_id": "u-042", "max_files": 100, "data_class": "KYC",
         "valid_from": ticket_from, "valid_to": ticket_to, "approver_id": "u-044", "note": "Branch KYC audit", "sample": True},
        {"approval_id": "T-SELF-019", "type": "ticket", "subject_id": "u-019", "max_files": 50, "data_class": "KYC",
         "valid_from": ticket_from, "valid_to": ticket_to, "approver_id": "u-019",
         "note": "Self-approved ticket: ignored by E3", "sample": True},
    ]


# ------------------------------------------------------------------ normal activity
def _ev(eid, ts, user, action, **kw):
    e = {"event_id": eid, "ts": iso(ts), "source": "app", "user_id": user["user_id"], "action": action,
         "principal_arn": user["iam_principal_arn"], "city": user["home_city"], "device_id": user["devices"][0],
         "ip": f"10.20.{sum(map(ord, user['user_id'])) % 250}.{len(user['user_id'])}"}
    e.update({k: v for k, v in kw.items() if v is not None})
    return e


def _assigned_customers(uid):
    return [f"C-{n}" for n in range(CUSTOMER_FIRST, CUSTOMER_LAST + 1) if agent_for(n)[0] == uid]


def _marketing_customers():
    return [f"C-{n}" for n in range(CUSTOMER_FIRST, CUSTOMER_LAST + 1) if "marketing" in consent_purposes(n)[0]]


def normal_day(users, day, seed):
    """One working day of normal activity for every user (day = local midnight)."""
    rnd = random.Random(seed)
    mkt = _marketing_customers()
    allc = [f"C-{n}" for n in range(CUSTOMER_FIRST, CUSTOMER_LAST + 1)]
    out = []
    tag = day.strftime("%Y%m%d")
    for u in users:
        uid = u["user_id"]
        team, p95, _city, _x = USERS[uid]
        _label, _role, scope, purpose, dclass, action = TEAMS[team]
        n = 0

        def nid():
            nonlocal n
            n += 1
            return f"n-{tag}-{uid}-{n:04d}"

        if team == "service":
            if p95:  # nightly job inside its window: p95 downloads in one 15-min bucket, then the registry upload
                t0 = day + timedelta(hours=2)
                k = p95 if rnd.random() < 0.5 else p95 - 1
                for i in range(k):
                    c = rnd.choice(allc)
                    out.append(_ev(nid(), t0 + timedelta(seconds=20 * i), u, "DOWNLOAD", customer_id=c,
                                   object_id=f"KYC-{rnd.choice(DOC_TYPES)}-{c}", data_class="KYC", purpose="registry_upload",
                                   bytes=rnd.randint(200_000, 900_000)))
                out.append(_ev(nid(), t0 + timedelta(minutes=10), u, "UPLOAD_EXTERNAL", destination="registry.finshield.example",
                               bytes=k * 500_000, data_class="KYC", purpose="registry_upload"))
            continue
        start = day + timedelta(hours=9, minutes=rnd.randint(5, 50))
        out.append(_ev(nid(), start - timedelta(seconds=15), u, "MFA_PUSH"))
        out.append(_ev(nid(), start, u, "LOGIN"))
        pool = _assigned_customers(uid) if scope == "ASSIGNED" and team != "marketing" else (mkt if team == "marketing" else allc)
        if action == "DOWNLOAD" and p95:
            hours = rnd.sample(range(10, 17), 3)  # three active 15-min buckets, at least an hour apart
            for hr in sorted(hours):
                bucket = day + timedelta(hours=hr, minutes=15 * rnd.randint(0, 3))
                k = p95 if rnd.random() < 0.4 else rnd.randint(max(1, p95 - 1), p95)
                for i in range(k):
                    c = rnd.choice(pool)
                    out.append(_ev(nid(), bucket + timedelta(minutes=rnd.randint(0, 12), seconds=rnd.randint(0, 59)), u,
                                   "DOWNLOAD", customer_id=c, object_id=f"KYC-{rnd.choice(DOC_TYPES)}-{c}",
                                   data_class=dclass, purpose=purpose, bytes=rnd.randint(200_000, 900_000)))
        elif action == "VIEW":
            for i in range(rnd.randint(4, 8)):
                c = rnd.choice(pool)
                out.append(_ev(nid(), day + timedelta(hours=10 + i, minutes=rnd.randint(0, 50)), u, "VIEW",
                               customer_id=c, data_class=dclass, purpose=purpose))
        if team == "collections":
            for _ in range(rnd.randint(0, 2)):
                c = rnd.choice(pool)
                out.append(_ev(nid(), day + timedelta(hours=rnd.randint(11, 16), minutes=rnd.randint(0, 59)), u, "DISBURSE",
                               customer_id=c, amount_inr=rnd.randrange(40_000, 120_001, 1000), data_class="FINANCIAL",
                               purpose="loan_processing"))
    out.sort(key=lambda e: (e["ts"], e["event_id"]))
    return out


def normal_days(users, end_day, days, seed_base):
    """`days` consecutive days ending the day before end_day."""
    return [normal_day(users, end_day - timedelta(days=i), seed_base + i) for i in range(days, 0, -1)]


def history(users, now):
    end = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=NORMAL_GAP_DAYS - 1)
    return [e for d in normal_days(users, end, NORMAL_HISTORY_DAYS, SEED) for e in d]


def accuracy_normal_days(users, now):
    """7 more normal days (different random seed) for the false-alert check; ends 2 days before now."""
    end = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=NORMAL_GAP_DAYS - 1)
    return normal_days(users, end, ACCURACY_NORMAL_DAYS, SEED + 500)


# ------------------------------------------------------------------ scenarios
def _sev(e):
    return {k: v for k, v in e.items() if v is not None}


def scenarios(account=ACCOUNT_PLACEHOLDER, stage="dev"):
    """The 11 scenarios from the playbook table. Times are local (IST) clock times; the simulator keeps them."""
    users = {u["user_id"]: u for u in make_users(account, stage)}
    rnd = random.Random(SEED + 99)
    out = []

    def sc(sid, title, uid, start, score, level, signs, events):
        u = users[uid]
        evs = []
        for i, (off, action, kw) in enumerate(events, 1):
            e = {"offset_seconds": off, "event_id": f"{sid.lower()}-{i:04d}", "source": "simulator", "action": action,
                 "principal_arn": u["iam_principal_arn"], "city": u["home_city"], "device_id": u["devices"][0]}
            e.update(kw)
            evs.append(_sev(e))
        out.append({"scenario_id": sid, "title": title, "user_id": uid, "start_time_ist": start,
                    "expected_score": score, "expected_level": level, "signs": signs, "sample": True, "events": evs})

    def kyc_dl(c, **kw):
        return dict(customer_id=c, object_id=f"KYC-{rnd.choice(DOC_TYPES)}-{c}", data_class="KYC", **kw)

    # SC-01 / SC-01b: emergency role at 23:40 from a new device in a second city, 212 KYC files, external upload
    pool = [f"C-{n}" for n in range(10600, 10798)]                      # 198 distinct customers
    custs = pool + rnd.sample(pool, 14)                                  # 212 downloads
    rnd.shuffle(custs)
    for sid, uid, upload in (("SC-01", "u-017", True), ("SC-01b", "u-018", False)):
        new = dict(city="Delhi", device_id="d-new-77", ip="103.21.58.10")
        ev = [(0, "LOGIN", {}),
              (2400, "MFA_PUSH", new), (2410, "LOGIN", new), (2430, "ASSUME_ROLE", dict(new, role="KYC-Emergency"))]
        ev += [(2460 + 2 * i, "DOWNLOAD", dict(new, role="KYC-Emergency", purpose="loan_processing", bytes=1_014_000,
                                                **kyc_dl(c))) for i, c in enumerate(custs)]
        if upload:
            ev.append((2900, "UPLOAD_EXTERNAL", dict(new, destination="files.example-share.com", bytes=215_000_000)))
        sc(sid, ("Ops admin assumes emergency role at 23:40 from a new device and second city, downloads 212 KYC files, "
                 "uploads to an external share (mandatory demo)") if upload else
           "Same as SC-01, no external upload", uid, "23:00:00", 96 if upload else 81, "CRITICAL",
           ["S1 40", "S3 20", "S4 15", "S5 11", "S6 10"] if upload else ["S1 40", "S3 20", "S5 11", "S6 10"], ev)

    # SC-02: nightly registry job inside its window; S1 capped by E1
    reg = [(i, "DOWNLOAD", kyc_dl(f"C-{10001 + (i * 7) % 2000}", purpose="registry_upload", bytes=480_000)) for i in range(450)]
    reg.append((480, "UPLOAD_EXTERNAL", dict(destination="registry.finshield.example", bytes=216_000_000, data_class="KYC",
                                             purpose="registry_upload")))
    sc("SC-02", "Nightly KYC registry upload by the service account inside its job window", "svc-ckyc", "02:00:00",
       30, "LOGGED", ["S1 30, capped by E1 at 30"], reg)

    # SC-03: auditor pulls 90 files under an approved 100-file ticket; S1 capped by E2
    sc("SC-03", "Auditor pulls 90 files under an approved 100-file ticket", "u-041", "15:00:00", 30, "LOGGED",
       ["S1 30, capped by E2 at 30"],
       [(5 * i, "DOWNLOAD", kyc_dl(f"C-{11000 + i}", purpose="audit", bytes=650_000)) for i in range(90)])

    # SC-04: collections agent opens 120 customers that are not assigned to them
    sc("SC-04", "Collections agent opens 120 unassigned customers in 15 min", "u-031", "11:00:00", 70, "HIGH",
       ["S7 40", "S1 30"],
       [(6 * i, "DOWNLOAD", dict(customer_id=f"C-{10401 + i}", object_id=f"KYC-ADDRESS-C-{10401 + i}", data_class="PII",
                                 purpose="collections", bytes=300_000)) for i in range(120)])

    # SC-05: one late download of 15 files
    sc("SC-05", "One late download of 15 files", "u-011", "23:30:00", 20, "LOGGED", ["S1 10", "S6 10"],
       [(20 * i, "DOWNLOAD", kyc_dl(f"C-{10900 + i}", purpose="loan_processing", bytes=700_000)) for i in range(15)])

    # SC-06: compromised cloud admin: MFA fatigue, login 1,300 km from home, emergency role, StopLogging
    far = dict(city="Delhi", device_id="d-new-66", ip="185.220.101.4")
    sc("SC-06", "Compromised cloud admin: 6 MFA pushes, login from a distant city, emergency role, StopLogging", "u-046",
       "02:05:00", 100, "CRITICAL", ["S5 11", "S3 20", "S8 100"],
       [(0, "LOGIN", {})] + [(900 + 20 * i, "MFA_PUSH", far) for i in range(6)] +
       [(1030, "LOGIN", far), (1150, "ASSUME_ROLE", dict(far, role="KYC-Emergency")),
        (1270, "LOGGING_CHANGE", dict(far, resource_arn=f"arn:aws:cloudtrail:ap-south-1:{account}:trail/finshield-{stage}-trail"))])

    # SC-07: marketing reads KYC of 40 customers who consented only to loan processing (odd numbers: no marketing consent)
    sc("SC-07", "Marketing user reads KYC of 40 customers who consented only to loan processing", "u-037", "14:00:00",
       70, "HIGH", ["S9 30", "S7 40"],
       [(15 * i, "VIEW", dict(customer_id=f"C-{10101 + 2 * i}", data_class="KYC", purpose="marketing")) for i in range(40)])

    # SC-08: agent changes a borrower's bank account from a new device, Rs 4.8 lakh disbursed to it at 01:40
    nd = dict(device_id="d-new-88", ip="49.36.200.7")
    sc("SC-08", "Agent changes a borrower's bank account from a new device; Rs 4.8 lakh disbursed to it at 01:40", "u-032",
       "01:20:00", 65, "HIGH", ["S10 50", "S6 10", "S5 5"],
       [(0, "LOGIN", nd),
        (300, "BANK_ACCOUNT_CHANGE", dict(nd, customer_id="C-10250", data_class="FINANCIAL")),
        (1200, "DISBURSE", dict(nd, customer_id="C-10250", amount_inr=480_000, data_class="FINANCIAL", purpose="loan_processing"))])

    # SC-09: KYC bucket made public; AWS Config marks it non-compliant
    sc("SC-09", "KYC bucket made public; Config marks it non-compliant", "svc-aws-config", "16:10:00", 45, "MEDIUM",
       ["S11 45"],
       [(0, "CONFIG_NONCOMPLIANT", dict(source="config", resource_arn=f"arn:aws:s3:::finshield-{stage}-kyc-docs",
                                        data_class="KYC", city=None, device_id=None))])

    # SC-10: auditor with a 100-file ticket downloads 150 (exceeded by more than 20 %)
    sc("SC-10", "Auditor with a 100-file ticket downloads 150 (ticket exceeded by more than 20%)", "u-042", "15:30:00",
       40, "MEDIUM", ["S1 30", "ticket exceeded +10"],
       [(4 * i, "DOWNLOAD", kyc_dl(f"C-{11300 + i}", purpose="audit", bytes=650_000)) for i in range(150)])
    return out


def scenario_files_dir() -> Path:
    return ROOT / "simulator" / "scenarios"


# ------------------------------------------------------------------ outputs
def build(now, account=ACCOUNT_PLACEHOLDER, stage="dev"):
    from finshield import baselines as bl
    from finshield.config import load_config
    users = make_users(account, stage)
    customers = make_customers(now)
    events = history(users, now)
    base = bl.compute(load_config(), users, events, iso(now))
    return {"Users": users, "Customers": customers, "KycFiles": make_kyc_files(customers), "Consent": make_consent(now),
            "Approvals": make_approvals(now), "Events": events, "Baselines": list(base.values())}


def event_item(e):
    """Events row: PK user_id, SK ts#event_id. Null attributes are left out (GSI keys must not be NULL)."""
    item = {k: v for k, v in e.items() if v is not None}
    item["sk"] = f"{e['ts']}#{e['event_id']}"
    return item


def load(data, stage, only=None):
    """only: logical table names to write (e.g. ["Users", "Customers"]); None writes every table."""
    from finshield import ddb
    if only:
        unknown = sorted(set(only) - set(data))
        if unknown:
            raise SystemExit(f"--only: unknown tables {unknown}; choose from {sorted(data)}")
        data = {k: v for k, v in data.items() if k in only}
    for logical in data:
        os.environ.setdefault(f"TABLE_{logical.upper()}", f"finshield-{stage}-{logical}")
    for logical, rows in data.items():
        tbl = ddb.table(logical)
        with tbl.batch_writer(overwrite_by_pkeys=["user_id", "sk"] if logical == "Events" else None) as bw:
            for r in rows:
                row = event_item(r) if logical == "Events" else {k: v for k, v in r.items() if v is not None}
                bw.put_item(Item=ddb.to_ddb(row))  # null attributes left out: GSI keys must not be NULL
        print(f"{logical}: {len(rows)} rows -> {ddb.table_name(logical)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="write one JSON file per table into this directory")
    ap.add_argument("--load", action="store_true", help="batch-write every table to DynamoDB")
    ap.add_argument("--scenarios", nargs="?", const=str(scenario_files_dir()), help="write the scenario files")
    ap.add_argument("--now", help="ISO time used as 'now' (default: current time)")
    ap.add_argument("--account", help="AWS account id for ARNs (default: STS when --load, else placeholder)")
    ap.add_argument("--stage", default=os.environ.get("STAGE", "dev"))
    ap.add_argument("--only", help="with --load: comma list of tables to write, e.g. Users,Customers (default: all)")
    a = ap.parse_args(argv)
    if not (a.out or a.load or a.scenarios):
        ap.error("give --out, --load and/or --scenarios")
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(IST)
    account = a.account
    if not account and a.load:
        import boto3
        account = boto3.client("sts").get_caller_identity()["Account"]
    account = account or ACCOUNT_PLACEHOLDER
    if a.scenarios:
        d = Path(a.scenarios)
        d.mkdir(parents=True, exist_ok=True)
        for s in scenarios(ACCOUNT_PLACEHOLDER, a.stage):  # files keep the placeholder; the simulator uses Users.iam_principal_arn
            (d / f"{s['scenario_id']}.json").write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
        print(f"scenarios: 11 files -> {d}")
    if a.out or a.load:
        data = build(now, account, a.stage)
        if a.out:
            d = Path(a.out)
            d.mkdir(parents=True, exist_ok=True)
            for logical, rows in data.items():
                (d / f"{logical}.json").write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
            print("out: " + ", ".join(f"{k}={len(v)}" for k, v in data.items()) + f" -> {d}")
        if a.load:
            load(data, a.stage, [t.strip() for t in a.only.split(",") if t.strip()] if a.only else None)


if __name__ == "__main__":
    main()
