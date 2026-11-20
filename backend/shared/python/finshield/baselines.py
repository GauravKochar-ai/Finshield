"""Baseline computation as pure functions (M3). Used by the baseline Lambda and by the seed generator.

Per user: p95 downloads per 15-minute bucket (buckets with activity), average daily downloads, usual hours,
cities, devices and p95 disbursement amount. Per team: the same p95 over all members' buckets.
Replay events (``is_replay`` true or a ``scenario_id``) never count. Users with less history than
``baselines.min_history_days`` take their team's numbers. Windows and percentiles come from config.json.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .scoring import t, tz_offset


def percentile(values, pct) -> float:
    if not values:
        return 0
    xs = sorted(values)
    k = max(0, math.ceil(pct / 100 * len(xs)) - 1)  # nearest-rank
    return xs[k]


def is_normal(e) -> bool:
    return not e.get("is_replay") and not e.get("scenario_id")


def compute(cfg, users, events, now_iso=None) -> dict[str, dict[str, Any]]:
    """users: Users rows. events: unified events (any order). Returns {subject_id: Baselines row}."""
    bcfg = cfg["baselines"]
    bucket_min = cfg["signals"]["S1"]["window_minutes"]
    tz = tz_offset(cfg)
    pct = bcfg["percentile"]
    buckets = defaultdict(lambda: defaultdict(int))     # uid -> bucket -> downloads
    daily = defaultdict(lambda: defaultdict(int))       # uid -> date -> downloads
    days_seen = defaultdict(set)                        # uid -> dates with any event
    cities = defaultdict(set)
    devices = defaultdict(set)
    disb = defaultdict(list)
    if now_iso:
        lo = t(now_iso).timestamp() - bcfg["lookback_days"] * 86400
        events = [e for e in events if t(e["ts"]).timestamp() >= lo]
    for e in events:
        if not is_normal(e):
            continue
        uid = e["user_id"]
        local = t(e["ts"]).astimezone(tz)
        day = local.date().isoformat()
        days_seen[uid].add(day)
        if e.get("city"):
            cities[uid].add(e["city"])
        if e.get("device_id"):
            devices[uid].add(e["device_id"])
        if e["action"] == "DOWNLOAD":
            b = local.replace(minute=(local.minute // bucket_min) * bucket_min, second=0, microsecond=0).isoformat()
            buckets[uid][b] += 1
            daily[uid][day] += 1
        if e["action"] == "DISBURSE" and e.get("amount_inr"):
            disb[uid].append(e["amount_inr"])

    out: dict[str, dict[str, Any]] = {}
    team_vals = defaultdict(list)
    team_disb = defaultdict(list)
    by_team = defaultdict(list)
    for u in users:
        uid = u["user_id"]
        vals = list(buckets[uid].values())
        team_vals[u.get("team")].extend(vals)
        team_disb[u.get("team")].extend(disb[uid])
        by_team[u.get("team")].append(uid)
        n_days = len(days_seen[uid])
        out[uid] = {
            "subject_id": uid, "kind": "user", "team": u.get("team"),
            "p95_15min": _int(percentile(vals, pct)),
            "avg_daily": round(sum(daily[uid].values()) / n_days, 1) if n_days else 0,
            "usual_hours": f"{u.get('office_start', '09:00')}-{u.get('office_end', '18:00')}",
            "cities": sorted(cities[uid] or {u.get("home_city")} - {None}),
            "devices": sorted(devices[uid] or set(u.get("devices") or [])),
            "p95_disburse_inr": _int(percentile(disb[uid], pct)),
            "days_of_history": n_days, "source": "user",
        }
    for team, vals in team_vals.items():
        members = [out[m] for m in by_team[team]]
        out[f"team:{team}"] = {
            "subject_id": f"team:{team}", "kind": "team", "team": team,
            "p95_15min": _int(percentile(vals, pct)),
            "avg_daily": round(sum(m["avg_daily"] for m in members) / len(members), 1) if members else 0,
            "p95_disburse_inr": _int(percentile(team_disb[team], pct)),
            "members": len(members), "source": "team",
        }
    for u in users:  # too little history: use the team's numbers, keep the user's own hours, cities and devices
        row = out[u["user_id"]]
        if row["days_of_history"] < bcfg["min_history_days"]:
            team = out.get(f"team:{u.get('team')}", {})
            row.update(p95_15min=team.get("p95_15min", 0), avg_daily=team.get("avg_daily", 0),
                       p95_disburse_inr=team.get("p95_disburse_inr", 0), source="team")
    if now_iso:
        for row in out.values():
            row["computed_at"] = now_iso
    return out


def _int(x):
    return int(x) if float(x) == int(x) else x
