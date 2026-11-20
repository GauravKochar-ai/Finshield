"""Fast checks without AWS: every scenario file scores its expected score and level with the pure scoring module,
7 normal days give 0 alerts, and no scoring number is hard-coded in scoring.py."""
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "simulator" / "seed"))
import generate  # noqa: E402
from finshield import baselines, scoring  # noqa: E402
from finshield.config import load_config  # noqa: E402

CFG = load_config()
NOW = datetime(2026, 11, 21, 10, 0, tzinfo=generate.IST)
USERS = {u["user_id"]: u for u in generate.make_users()}
BASE = baselines.compute(CFG, list(USERS.values()), generate.history(list(USERS.values()), NOW), generate.iso(NOW))
CTX = {"approvals": generate.make_approvals(NOW), "consent": {c["customer_id"]: c for c in generate.make_consent(NOW)},
       "customers": {c["customer_id"]: c for c in generate.make_customers(NOW)}}
FILES = sorted((ROOT / "simulator" / "scenarios").glob("SC-*.json"))


def replay(sc):
    u = USERS[sc["user_id"]]
    hh, mm, ss = map(int, sc["start_time_ist"].split(":"))
    start = NOW.replace(hour=hh, minute=mm, second=ss)
    if start + timedelta(seconds=max(e["offset_seconds"] for e in sc["events"])) > NOW:
        start -= timedelta(days=1)
    evs, best = [], None
    for raw in sc["events"]:
        e = {k: v for k, v in raw.items() if k != "offset_seconds"}
        e.update(ts=(start + timedelta(seconds=raw["offset_seconds"])).isoformat(timespec="seconds"),
                 user_id=sc["user_id"], scenario_id=sc["scenario_id"], is_replay=True)
        evs.append(e)
        r = scoring.score(CFG, u, BASE[u["user_id"]], BASE[f"team:{u['team']}"], evs, e["ts"], CTX)
        if best is None or r["score"] >= best["score"]:
            best = r
    return best


def test_eleven_scenario_files():
    assert len(FILES) == 11


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_scenario_scores_expected(path):
    sc = json.loads(path.read_text())
    r = replay(sc)
    assert (r["score"], scoring.level_name(CFG, r["score"])) == (sc["expected_score"], sc["expected_level"]), r["signals"]


def test_sc01_facts_match_contract():
    r = replay(json.loads((ROOT / "simulator/scenarios/SC-01.json").read_text()))
    s1 = next(s for s in r["signals"] if s["code"] == "S1")
    assert s1["facts"] == {"downloads_15m": 212, "baseline_p95": 2, "ratio": 106}
    assert r["customers_affected"] == 198


def test_seven_normal_days_zero_alerts():
    seen, alerts = {}, 0
    for day in generate.accuracy_normal_days(list(USERS.values()), NOW):
        for e in day:
            evs = seen.setdefault(e["user_id"], [])
            evs.append(e)
            u = USERS[e["user_id"]]
            alerts += bool(scoring.score(CFG, u, BASE[u["user_id"]], BASE[f"team:{u['team']}"], evs, e["ts"], CTX)["severity"])
    assert alerts == 0


def test_no_scoring_numbers_in_scoring_code():
    """Every point value and threshold must come from config.json; only 0, 1, 60, 100 and unit constants may appear."""
    code = (ROOT / "backend/shared/python/finshield/scoring.py").read_text()
    body = code.split("CITY_COORDS = {")[0] + code.split("# ------------------------------------------------------------------ main entry")[1]
    nums = {int(n) for n in re.findall(r"(?<![\w.])(\d+)(?![\w.])", body)}
    assert nums <= {0, 1, 2, 3, 6371, 60, 3600, 100}, sorted(nums)
