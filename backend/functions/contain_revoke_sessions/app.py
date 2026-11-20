"""contain_revoke_sessions: inline deny on aws:TokenIssueTime earlier than now (kills existing sessions).

Input  {alert_id, principal_arn, mode, user_id?, execution?}
Output {action: REVOKE_SESSIONS, mode, result, detail}
Release deletes the inline policy POLICY_NAME.
"""
import json
from datetime import datetime, timezone

from finshield import containment

ACTION = "REVOKE_SESSIONS"
POLICY_NAME = "FinShieldRevokeSessions"


def plan(principal, ctx, event):
    if principal.kind not in ("role", "user"):
        return containment.Plan(not_applicable=f"no IAM role or user for principal {principal.arn or '(none)'}")
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "FinShieldRevokeOlderSessions",
            "Effect": "Deny",
            "Action": "*",
            "Resource": "*",
            "Condition": {"DateLessThan": {"aws:TokenIssueTime": cutoff}},
        }],
    })
    if principal.kind == "role":
        c = containment.call("iam", "put_role_policy", RoleName=principal.name, PolicyName=POLICY_NAME, PolicyDocument=doc)
    else:
        c = containment.call("iam", "put_user_policy", UserName=principal.name, PolicyName=POLICY_NAME, PolicyDocument=doc)
    return containment.Plan(calls=[c], detail={"policy_name": POLICY_NAME, "token_issued_before": cutoff, "target": principal.name})


def handler(event, context):
    return containment.contain(ACTION, event, plan, actor="contain_revoke_sessions")
