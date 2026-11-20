"""contain_bucket_deny: add statement Sid FinShieldDeny<user> to the KYC bucket policy.

Existing statements are kept; a previous FinShield statement for the same user is replaced.
Release removes that Sid. Note: a later `sam deploy` resets the bucket policy to the template.
"""
import json
import os
import re

from finshield import containment
from finshield.log import log

ACTION = "BUCKET_DENY"


def sid_for(user_id, principal):
    raw = user_id or principal.name or "unknown"
    return "FinShieldDeny" + re.sub(r"[^A-Za-z0-9]", "", raw)


def _current_policy(bucket):
    try:
        resp = containment.execute(containment.call("s3", "get_bucket_policy", Bucket=bucket))
        return json.loads(resp["Policy"])
    except Exception as exc:
        if "NoSuchBucketPolicy" in str(exc) or exc.__class__.__name__ == "NoSuchBucketPolicy":
            return {"Version": "2012-10-17", "Statement": []}
        log("get_bucket_policy failed", level="WARNING", bucket=bucket, error=str(exc))
        return None


def plan(principal, ctx, event):
    bucket = os.environ.get("KYC_BUCKET")
    if not bucket:
        return containment.Plan(not_applicable="KYC_BUCKET is not configured")
    if principal.kind not in ("role", "user"):
        return containment.Plan(not_applicable=f"no IAM role or user for principal {principal.arn or '(none)'}")
    sid = sid_for(ctx.get("user_id"), principal)
    deny = {
        "Sid": sid,
        "Effect": "Deny",
        "Principal": {"AWS": principal.iam_arn},
        "Action": "s3:*",
        "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
    }
    policy = _current_policy(bucket)
    if policy is None:  # could not read: show the statement we would add
        return containment.Plan(
            calls=[containment.call("s3", "put_bucket_policy", Bucket=bucket, Policy=json.dumps({"Version": "2012-10-17", "Statement": ["<existing statements>", deny]}))],
            detail={"bucket": bucket, "sid": sid, "note": "current policy unreadable"},
        )
    statements = [s for s in policy.get("Statement", []) if s.get("Sid") != sid] + [deny]
    new_policy = json.dumps({"Version": policy.get("Version", "2012-10-17"), "Statement": statements})
    return containment.Plan(calls=[containment.call("s3", "put_bucket_policy", Bucket=bucket, Policy=new_policy)], detail={"bucket": bucket, "sid": sid})


def handler(event, context):
    return containment.contain(ACTION, event, plan, actor="contain_bucket_deny")
