#!/usr/bin/env python3
"""Show cases.

  python3 tools/status.py                         # one line per case
  python3 tools/status.py --case-id case-ADM-07-20261120   # full details
"""
import argparse
import json

from common import cases_table, plain

HIDE = {"approval_token"}   # long and sensitive, never print it


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case-id")
    args = p.parse_args()
    table = cases_table()

    if args.case_id:
        item = table.get_item(Key={"case_id": args.case_id}).get("Item")
        if not item:
            print("not found")
            return
        has_token = bool(item.get("approval_token"))
        item = {k: v for k, v in plain(item).items() if k not in HIDE}
        item["has_approval_token"] = has_token
        print(json.dumps(item, indent=2, default=str))
        return

    items = sorted(plain(table.scan()["Items"]), key=lambda x: x.get("updated_at", ""))
    print(f"{'CASE':<30} {'SCORE':<6} {'RULE':<9} {'AI':<9} {'STATUS':<18} SIGNALS")
    for c in items:
        print(f"{c['case_id']:<30} {str(c.get('case_score')):<6} {c.get('severity_rule', ''):<9} "
              f"{c.get('severity', '-'):<9} {c.get('status', ''):<18} {','.join(c.get('signals', []))}")


if __name__ == "__main__":
    main()
