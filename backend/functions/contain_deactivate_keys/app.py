"""contain_deactivate_keys: set the principal's active access keys to Inactive.

Roles have no long-term keys, so a role principal gives NOT_APPLICABLE.
The deactivated key ids go into evidence so release can reactivate exactly those keys.
"""
from finshield import containment
from finshield.log import log

ACTION = "DEACTIVATE_KEYS"


def _active_keys(user_name):
    try:
        resp = containment.execute(containment.call("iam", "list_access_keys", UserName=user_name))
        return [k["AccessKeyId"] for k in resp.get("AccessKeyMetadata", []) if k.get("Status") == "Active"]
    except Exception as exc:  # DRY_RUN in a locked-down sandbox: plan without the list
        log("list_access_keys failed", level="WARNING", user=user_name, error=str(exc))
        return None


def plan(principal, ctx, event):
    if principal.kind != "user":
        return containment.Plan(not_applicable="principal is not an IAM user; roles have no long-term access keys")
    keys = _active_keys(principal.name)
    if keys is None:
        return containment.Plan(
            calls=[containment.call("iam", "update_access_key", UserName=principal.name, AccessKeyId="<each active key>", Status="Inactive")],
            detail={"target": principal.name, "keys": "unknown (list_access_keys denied)"},
        )
    if not keys:
        return containment.Plan(not_applicable=f"{principal.name} has no active access keys")
    calls = [containment.call("iam", "update_access_key", UserName=principal.name, AccessKeyId=k, Status="Inactive") for k in keys]
    return containment.Plan(calls=calls, detail={"target": principal.name, "deactivated_keys": keys})


def handler(event, context):
    return containment.contain(ACTION, event, plan, actor="contain_deactivate_keys")
