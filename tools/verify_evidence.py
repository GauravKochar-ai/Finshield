#!/usr/bin/env python3
"""Verify a case's evidence pack (the "Verify integrity" demo).

  python3 tools/verify_evidence.py --case-id case-ADM-07-20261120
  python3 tools/verify_evidence.py --case-id case-ADM-07-20261120 --tamper   # shows a tampered copy failing

--tamper only changes a LOCAL copy in memory; the real pack in S3 is untouched.
"""
import argparse
import copy
import json
import sys

import boto3

from chain import verify_pack
from common import cases_table


def load_pack(case_id):
    case = cases_table().get_item(Key={"case_id": case_id}).get("Item")
    if not case or not case.get("evidence_key"):
        sys.exit(f"No evidence pack recorded for {case_id}.")
    uri = case["evidence_key"]
    bucket, key = uri.replace("s3://", "").split("/", 1)
    body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    return json.loads(body), case.get("evidence_hash"), uri


def report(title, pack, expected_hash=None):
    ok, problems = verify_pack(pack)
    if expected_hash and pack.get("pack_sha256") != expected_hash:
        ok = False
        problems.append("pack hash differs from the hash stored on the case")
    print(f"\n{title}")
    print(f"  records: {len(pack.get('records', []))}   pack_sha256: {pack.get('pack_sha256', '')[:16]}...")
    if ok:
        print("  ✅ INTEGRITY VERIFIED - evidence chain is intact")
    else:
        print("  ❌ TAMPERING DETECTED")
        for prob in problems:
            print("     -", prob)
    return ok


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case-id", required=True)
    p.add_argument("--tamper", action="store_true")
    args = p.parse_args()

    pack, stored_hash, uri = load_pack(args.case_id)
    print("Evidence pack:", uri)
    report("Original pack from S3", pack, stored_hash)

    if args.tamper:
        bad = copy.deepcopy(pack)
        target = bad["records"][-1] if bad.get("records") else bad
        target["description"] = "Transferred 48 documents to s3://fs-audit-vault"   # attacker edit
        report("Tampered copy (one record edited)", bad, stored_hash)


if __name__ == "__main__":
    main()
