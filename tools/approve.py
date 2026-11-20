#!/usr/bin/env python3
"""Approve or reject a case that is waiting for the CISO (same call the dashboard makes).

Examples:
  python3 tools/approve.py --latest
  python3 tools/approve.py --case-id case-ADM-07-20261120 --decision APPROVED
  python3 tools/approve.py --case-id case-ADM-07-20261120 --decision REJECTED --comment "authorised DR test"
"""
import argparse
import json
import sys

import boto3
from boto3.dynamodb.conditions import Attr

from common import cases_table


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--case-id")
    g.add_argument("--latest", action="store_true", help="pick the newest PENDING_APPROVAL case")
    p.add_argument("--decision", choices=["APPROVED", "REJECTED"], default="APPROVED")
    p.add_argument("--approver", default="ciso@finshield.in")
    p.add_argument("--comment", default="")
    args = p.parse_args()

    table = cases_table()
    if args.latest:
        items = table.scan(FilterExpression=Attr("status").eq("PENDING_APPROVAL"))["Items"]
        if not items:
            sys.exit("No case is waiting for approval.")
        case = sorted(items, key=lambda x: x.get("approval_requested_at", ""))[-1]
    else:
        case = table.get_item(Key={"case_id": args.case_id}).get("Item")
        if not case:
            sys.exit(f"Case {args.case_id} not found.")

    token = case.get("approval_token")
    if not token:
        sys.exit(f"Case {case['case_id']} has no approval token (status: {case.get('status')}).")

    output = {"decision": args.decision, "approver": args.approver, "comment": args.comment}
    boto3.client("stepfunctions").send_task_success(taskToken=token, output=json.dumps(output))
    print(f"✅ Sent {args.decision} for {case['case_id']} (approver: {args.approver})")


if __name__ == "__main__":
    main()
