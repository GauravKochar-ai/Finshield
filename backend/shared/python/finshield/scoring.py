"""Scoring: warning signs S1-S11 and exceptions E1-E3 as pure functions (M3).

No AWS calls and no scoring numbers in this file. Every point value, threshold and window comes from
contract/config.json (pass ``load_config()`` as ``cfg``). Detection, the accuracy runner and the tests all
call ``score()`` with the same inputs, so a scenario can be checked without AWS.

Inputs
  user       Users row (team, is_service, office_start, office_end, devices, partner_id, access_scope)
  base       Baselines row for the user (p95_15min, avg_daily, usual_hours, cities, devices, p95_disburse_inr)
  team_base  Baselines row for "team:<team>" (p95_15min)
  events     the user's unified events (any order); only those at or before ``now_ts`` are used
  ctx        {"approvals": [...], "consent": {customer_id: row}, "customers": {customer_id: row}}
             consent and customers only need the ids seen in the incident window (see ``needs()``)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

READ_ACTIONS = ("VIEW", "DOWNLOAD")
# actions that count as "doing something" for the off-hours sign (logins and MFA prompts alone do not)
ACTIVITY_ACTIONS = ("VIEW", "DOWNLOAD", "PRESIGN", "UPLOAD_EXTERNAL", "DISBURSE", "BANK_ACCOUNT_CHANGE")
SENSITIVE_CLASSES = ("KYC", "PII")
LEVEL_ORDER = {None: 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# City coordinates for the impossible-travel check (data, not scoring numbers).
CITY_COORDS = {
    "Mumbai": (19.076, 72.878), "Pune": (18.520, 73.857), "Delhi": (28.614, 77.209), "Bengaluru": (12.972, 77.595),
    "Hyderabad": (17.385, 78.487), "Chennai": (13.083, 80.271), "Kolkata": (22.573, 88.364),
    "Ahmedabad": (23.023, 72.571), "Jaipur": (26.912, 75.787), "Lucknow": (26.847, 80.947), "Guwahati": (26.144, 91.736),
}


def t(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def tz_offset(cfg) -> Any:
    """The configured local timezone (e.g. +05:30) as a tzinfo."""
    from datetime import timezone
    sign = -1 if cfg["timezone_offset"].startswith("-") else 1
    hh, mm = cfg["timezone_offset"].lstrip("+-").split(":")
    return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))


def km(a: str, b: str) -> float | None:
    if a not in CITY_COORDS or b not in CITY_COORDS:
        return None
    (la1, lo1), (la2, lo2) = CITY_COORDS[a], CITY_COORDS[b]
    p1, p2, dl, dn = map(math.radians, (la1, la2, la2 - la1, lo2 - lo1))
    h = math.sin(dl / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dn / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def severity(cfg, total: int) -> str | None:
    th = cfg["severity_thresholds"]
    for level in ("CRITICAL", "HIGH", "MEDIUM"):
        if total >= th[level]:
            return level
    return None


def level_name(cfg, total: int) -> str:
    """Severity, or LOGGED below the lowest threshold (accuracy rows use this)."""
    return severity(cfg, total) or "LOGGED"


def window(events, now, minutes):
    lo = now - timedelta(minutes=minutes)
    return [e for e in events if lo < t(e["ts"]) <= now]


def needs(cfg, user, events, now_ts) -> dict[str, set[str]]:
    """Customer ids whose Consent / Customers rows ``score()`` will read, so callers can batch-load only those."""
    now = t(now_ts)
    sig = cfg["signals"]
    w7 = window(events, now, sig["S7"]["window_minutes"])
    w9 = window(events, now, sig["S9"]["window_minutes"])
    w60 = window(events, now, cfg["incident_window_minutes"])
    consent = {e["customer_id"] for e in w9 if e.get("customer_id") and e["action"] in READ_ACTIONS
               and e.get("data_class") in SENSITIVE_CLASSES and e.get("purpose")}
    customers = {e["customer_id"] for e in w60 if e.get("customer_id") and e["action"] == "DISBURSE"}
    if (user or {}).get("access_scope") == "ASSIGNED":
        customers |= {e["customer_id"] for e in w7 if e.get("customer_id") and e["action"] in READ_ACTIONS}
    return {"consent": consent, "customers": customers}


# ------------------------------------------------------------------ approvals (E1, E2, E3)
def _approval_valid(a, now, local_now) -> bool:
    if a.get("valid_from") and now < t(a["valid_from"]):
        return False
    if a.get("valid_to") and now > t(a["valid_to"]):
        return False
    if a.get("window_start") and a.get("window_end"):  # daily job window, local time
        m = local_now.hour * 60 + local_now.minute
        lo, hi = _hm(a["window_start"]), _hm(a["window_end"])
        if not (lo <= m <= hi if lo <= hi else (m >= lo or m <= hi)):
            return False
    return True


def _split_approvals(user_id, approvals, now, local_now, cfg):
    """Return (usable approvals, self-approved ones ignored by E3)."""
    usable, ignored = [], []
    for a in approvals or []:
        if a.get("subject_id") != user_id:
            continue
        if cfg["exceptions"]["E3"]["ignore_self_approval"] and a.get("approver_id") == user_id:
            ignored.append(a)
            continue
        if _approval_valid(a, now, local_now):
            usable.append(a)
    return usable, ignored


# ------------------------------------------------------------------ main entry
def score(cfg, user, base, team_base, events, now_ts, ctx=None) -> dict[str, Any]:
    ctx = ctx or {}
    user = user or {}
    base = base or {}
    team_base = team_base or {}
    sig = cfg["signals"]
    now = t(now_ts)
    local_tz = tz_offset(cfg)
    local_now = now.astimezone(local_tz)
    hist = sorted((e for e in events if t(e["ts"]) <= now), key=lambda e: (e["ts"], e["event_id"]))
    w15 = window(hist, now, sig["S1"]["window_minutes"])
    w24 = window(hist, now, sig["S2"]["window_hours"] * 60)
    w60 = window(hist, now, cfg["incident_window_minutes"])
    uid = user.get("user_id") or (hist[-1]["user_id"] if hist else None)
    signals: list[dict[str, Any]] = []

    def add(code, points, **facts):
        signals.append({"code": code, "points": points, "facts": facts})

    usable, self_approved = _split_approvals(uid, ctx.get("approvals"), now, local_now, cfg)
    jobs = [a for a in usable if a.get("type") == "scheduled_job"]
    tickets = [a for a in usable if a.get("type") == "ticket"]
    role_grants = [a for a in usable if a.get("type") == "emergency_access"]

    # ---- S1 volume spike / S2 slow leak
    s1c, s2c = sig["S1"], sig["S2"]
    downloads = sum(1 for e in w15 if e["action"] == "DOWNLOAD")
    presigns = sum(1 for e in w15 if e["action"] == "PRESIGN")
    counted = downloads + (presigns if presigns > s1c["presign_count_threshold"] else 0)
    divisor = max(base.get("p95_15min") or 0, team_base.get("p95_15min") or 0, s1c["baseline_floor"])
    ratio = counted / divisor
    s1 = next((tier["points"] for tier in sorted(s1c["ratio_tiers"], key=lambda x: -x["min_ratio"])
               if ratio >= tier["min_ratio"]), 0)
    s1 = min(s1, s1c["max_points"])
    daily = sum(1 for e in w24 if e["action"] == "DOWNLOAD")
    avg_daily = base.get("avg_daily") or 0
    s2 = s2c["points"] if daily > s2c["daily_multiple"] * max(avg_daily, 1) and daily > s2c["min_daily_count"] else 0
    if s2 > s1:
        add("S2", s2, downloads_today=daily, avg_daily=avg_daily, daily_multiple=s2c["daily_multiple"])
    elif s1:
        facts = {"downloads_15m": counted, "baseline_p95": _num(divisor), "ratio": _num(round(ratio, 1))}
        if counted != downloads:
            facts["presigns_15m"] = presigns
        add("S1", s1, **facts)

    # ---- S3 privileged role without approval / service account outside its job window
    s3c = sig["S3"]
    roles = [e for e in w60 if e["action"] == "ASSUME_ROLE" and e.get("role") in s3c["emergency_roles"]]
    if roles and not role_grants:
        add("S3", s3c["points"], role=roles[-1]["role"], covering_approval=False)
    elif user.get("is_service"):
        all_jobs = [a for a in (ctx.get("approvals") or []) if a.get("subject_id") == uid and a.get("type") == "scheduled_job"]
        active = [e for e in w60 if e["action"] in ACTIVITY_ACTIONS]
        if all_jobs and not jobs and active:
            add("S3", s3c["points"], job_id=all_jobs[0].get("job_id"), outside_job_window=True,
                local_time=local_now.strftime("%H:%M"))

    # ---- S4 external upload
    s4c = sig["S4"]
    ups = [e for e in w60 if e["action"] == "UPLOAD_EXTERNAL" and e.get("destination") not in s4c["allowlist"]]
    if ups:
        last = ups[-1]
        total_bytes = sum(e.get("bytes") or 0 for e in ups)
        kyc_dl = [e for e in hist if e["action"] == "DOWNLOAD" and e.get("data_class") == "KYC"
                  and timedelta(0) <= t(last["ts"]) - t(e["ts"]) <= timedelta(minutes=s4c["proximity_minutes"])]
        high = total_bytes >= s4c["bytes_threshold"] or bool(kyc_dl)
        facts = {"destination": last.get("destination"), "bytes": total_bytes}
        if kyc_dl:
            facts["minutes_after_downloads"] = int((t(last["ts"]) - t(kyc_dl[-1]["ts"])).total_seconds() // 60)
        add("S4", s4c["points_high"] if high else s4c["points_low"], **facts)

    # ---- S5 risky login
    s5c = sig["S5"]
    s5, facts5 = 0, {}
    known = set(base.get("devices") or []) | set(user.get("devices") or [])
    new_dev = [e.get("device_id") for e in w60 if e.get("device_id") and known and e["device_id"] not in known]
    if new_dev:
        s5 += s5c["new_device_points"]
        facts5["new_device"] = new_dev[-1]
    pushes = [t(e["ts"]) for e in w60 if e["action"] == "MFA_PUSH"]
    span = timedelta(minutes=s5c["mfa_push_window_minutes"])
    burst = max((sum(1 for q in pushes if p <= q <= p + span) for p in pushes), default=0)
    if burst >= s5c["mfa_push_count"]:
        s5 += s5c["mfa_push_points"]
        facts5["mfa_pushes"] = burst
        facts5["mfa_window_minutes"] = s5c["mfa_push_window_minutes"]
    travel = _travel(hist, now, s5c)
    if travel:
        s5 += s5c["impossible_travel_points"]
        facts5.update(travel)
    if s5:
        add("S5", min(s5, s5c["max_points"]), **facts5)

    # ---- S6 off-hours
    s6c = sig["S6"]
    start = base.get("usual_hours", "").split("-")[0] or user.get("office_start")
    end = base.get("usual_hours", "-").split("-")[-1] or user.get("office_end")
    if start and end:
        grace = s6c["grace_hours"] * 60
        lo, hi = _hm(start) - grace, _hm(end) + grace
        off = [e for e in w60 if e["action"] in ACTIVITY_ACTIONS and not _within(t(e["ts"]).astimezone(local_tz), lo, hi)]
        if off:
            add("S6", s6c["points"], local_time=t(off[0]["ts"]).astimezone(local_tz).strftime("%H:%M"),
                usual_hours=f"{start}-{end}")

    # ---- S7 unassigned customers (only for users whose access is limited to assigned customers)
    s7c = sig["S7"]
    if user.get("access_scope") == "ASSIGNED":
        custs = ctx.get("customers") or {}
        seen = {e["customer_id"] for e in window(hist, now, s7c["window_minutes"])
                if e["action"] in READ_ACTIONS and e.get("customer_id")}
        out = sorted(c for c in seen if not _assigned(user, custs.get(c)))
        if len(out) >= s7c["min_customers"]:
            add("S7", s7c["points"], unassigned_customers=len(out), window_minutes=s7c["window_minutes"])

    # ---- S8 logging tampered
    s8c = sig["S8"]
    tamper = [e for e in w60 if e["action"] == "LOGGING_CHANGE"]
    if tamper:
        add("S8", s8c["points"], events=len(tamper), resource=tamper[-1].get("resource_arn"))

    # ---- S9 purpose mismatch
    s9c = sig["S9"]
    consent = ctx.get("consent") or {}
    mism = {}
    for e in window(hist, now, s9c["window_minutes"]):
        if e["action"] in READ_ACTIONS and e.get("data_class") in SENSITIVE_CLASSES and e.get("purpose") and e.get("customer_id"):
            c = consent.get(e["customer_id"])
            if not c or e["purpose"] not in (c.get("purposes") or []) or e["purpose"] in (c.get("withdrawn") or []):
                mism[e["customer_id"]] = e["purpose"]
    if len(mism) >= s9c["min_customers"]:
        add("S9", s9c["points"], customers=len(mism), purpose=sorted(set(mism.values()))[0])

    # ---- S10 abnormal disbursement
    s10c = sig["S10"]
    best, best_facts = 0, {}
    custs = ctx.get("customers") or {}
    for d in (e for e in w60 if e["action"] == "DISBURSE"):
        pts, f = 0, {"amount_inr": d.get("amount_inr"), "customer_id_masked": _mask(d.get("customer_id"))}
        changed = _bank_changed_at(d, hist, custs.get(d.get("customer_id")))
        if changed is not None:
            hours = (t(d["ts"]) - changed).total_seconds() / 3600
            if 0 <= hours < s10c["new_account_hours"]:
                pts += s10c["new_account_points"]
                f["account_changed_hours_ago"] = _num(round(hours, 1))
        p95 = base.get("p95_disburse_inr") or 0
        if p95 and (d.get("amount_inr") or 0) > s10c["amount_multiple_of_p95"] * p95:
            pts += s10c["amount_points"]
            f["p95_disburse_inr"] = p95
            f["multiple"] = _num(round(d["amount_inr"] / p95, 1))
        if pts > best:
            best, best_facts = pts, f
    if best:
        add("S10", min(best, s10c["max_points"]), **best_facts)

    # ---- S11 sensitive resource misconfigured
    s11c = sig["S11"]
    cfgs = [e for e in w60 if e["action"] == "CONFIG_NONCOMPLIANT"]
    if cfgs:
        kyc = [e for e in cfgs if e.get("data_class") == "KYC"]
        pick = (kyc or cfgs)[-1]
        add("S11", min(s11c["kyc_points"] if kyc else s11c["other_points"], s11c["max_points"]),
            resource=pick.get("resource_arn"), data_class=pick.get("data_class"))

    # ---- exceptions
    exceptions = ["E3"] if self_approved else []
    total = sum(s["points"] for s in signals)
    e1, e2 = cfg["exceptions"]["E1"], cfg["exceptions"]["E2"]
    capped = False
    if jobs and user.get("is_service"):
        exceptions.append("E1")
        total = min(total, e1["cap"])
        capped = True
    if tickets and not capped:
        tk = tickets[0]
        files = sum(1 for e in w60 if e["action"] == "DOWNLOAD"
                    and (not tk.get("data_class") or e.get("data_class") == tk["data_class"]))
        limit = (tk.get("max_files") or 0) * (1 + e2["overage_tolerance_pct"] / 100)
        if files <= limit:
            exceptions.append("E2")
            total = min(total, e2["cap"])
        else:  # ticket exceeded: cap void, add overage points to the volume sign (schema allows S1-S11 only)
            target = next((s for s in signals if s["code"] in ("S1", "S2")), None)
            if target is None:
                target = {"code": "S1", "points": 0, "facts": {"downloads_15m": counted}}
                signals.insert(0, target)
            target["points"] += e2["overage_points"]
            target["facts"].update(ticket_id=tk.get("approval_id"), ticket_max_files=tk.get("max_files"),
                                   files_in_window=files, ticket_overage_points=e2["overage_points"])
            total += e2["overage_points"]
    if tamper and sig["S8"].get("instant"):
        total = cfg["score_cap"]
    total = int(min(total, cfg["score_cap"]))

    reads = [e for e in w60 if e["action"] in READ_ACTIONS]
    classes = sorted({e["data_class"] for e in w60 if e.get("data_class") and e["data_class"] != "NONE"})
    return {
        "score": total,
        "severity": severity(cfg, total),
        "signals": signals,
        "exceptions_applied": exceptions,
        "customers_affected": len({e["customer_id"] for e in reads if e.get("customer_id")}),
        "data_classes": classes or ["NONE"],
        "event_ids": [e["event_id"] for e in w60],
        "window_start": w60[0]["ts"] if w60 else now_ts,
        "principal_arn": next((e.get("principal_arn") for e in reversed(w60) if e.get("principal_arn")),
                              user.get("iam_principal_arn")),
        "scenario_id": next((e.get("scenario_id") for e in reversed(w60) if e.get("scenario_id")), None),
    }


# ------------------------------------------------------------------ helpers
def _num(x):
    return int(x) if float(x) == int(x) else x


def _mask(cid):
    return (cid[:2] + "***" + cid[-2:]) if cid else None


def _within(dt, lo, hi) -> bool:
    m = dt.hour * 60 + dt.minute
    return lo <= m <= hi


def _assigned(user, cust) -> bool:
    if not cust:
        return False
    if cust.get("assigned_agent") == user.get("user_id"):
        return True
    return bool(user.get("partner_id")) and cust.get("partner_id") == user.get("partner_id")


def _bank_changed_at(disburse, hist, cust):
    cid = disburse.get("customer_id")
    times = [t(e["ts"]) for e in hist if e["action"] == "BANK_ACCOUNT_CHANGE" and e.get("customer_id") == cid
             and t(e["ts"]) <= t(disburse["ts"])]
    if cust and cust.get("bank_account_changed_at"):
        times.append(t(cust["bank_account_changed_at"]))
    return max(times) if times else None


def _travel(hist, now, s5c):
    w = window(hist, now, s5c["impossible_travel_window_minutes"])
    pts = [(t(e["ts"]), e["city"]) for e in w if e.get("city")]
    best = None
    for i, (ta, ca) in enumerate(pts):
        for tb, cb in pts[i + 1:]:
            if ca == cb or abs((tb - ta).total_seconds()) > s5c["impossible_travel_window_minutes"] * 60:
                continue
            d = km(ca, cb)
            if d is not None and d > s5c["impossible_travel_km"] and (best is None or d > best[0]):
                best = (d, ca, cb, abs(int((tb - ta).total_seconds() // 60)))
    if not best:
        return None
    return {"cities": [best[1], best[2]], "distance_km": int(round(best[0])), "window_minutes": best[3]}
