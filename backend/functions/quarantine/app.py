"""quarantine: after the CISO approves, lock the principal (Step Functions task).
Input {alert_id, principal_arn, user_id, mode, execution}. Adds the inline deny-all policy FinShieldQuarantine to the
role or user and, for an IAM user, removes the console password. Same safety rules as containment (LIVE only for
finshield-<stage>-demo-* principals and only when SSM containment_mode is LIVE). Release removes the policy.
"""
from finshield import containment, ddb

ACTION = "QUARANTINE"
POLICY_NAME = "FinShieldQuarantine"
DENY_ALL = '{"Version":"2012-10-17","Statement":[{"Sid":"FinShieldQuarantine","Effect":"Deny","Action":"*","Resource":"*"}]}'


def plan(principal, ctx, event):
    if principal.kind == "role":
        return containment.Plan(calls=[containment.call("iam", "put_role_policy", RoleName=principal.name,
                                                        PolicyName=POLICY_NAME, PolicyDocument=DENY_ALL)],
                                detail={"policy_name": POLICY_NAME, "target": principal.name})
    if principal.kind == "user":
        return containment.Plan(calls=[containment.call("iam", "put_user_policy", UserName=principal.name,
                                                        PolicyName=POLICY_NAME, PolicyDocument=DENY_ALL),
                                       containment.call("iam", "delete_login_profile", UserName=principal.name)],
                                detail={"policy_name": POLICY_NAME, "target": principal.name})
    return containment.Plan(not_applicable=f"no IAM role or user for principal {principal.arn or '(none)'}")


def handler(event, context=None):
    out = containment.contain(ACTION, event, plan, actor="quarantine")
    try:
        ddb.update_item("Alerts", {"alert_id": event["alert_id"]}, "SET #s = :s", {":s": "LOCKED"}, names={"#s": "status"},
                        condition="attribute_exists(alert_id)")
    except ddb.ConditionFailed:
        pass
    return out
