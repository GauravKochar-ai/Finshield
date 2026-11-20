"""contain_revoke_sessions, contain_deactivate_keys, contain_bucket_deny, contain_dns_block."""
import json

import pytest

from conftest import fixture, load_fn, put_alert
from finshield import ddb, evidence, schema

AID = "ALR-20261120-0007"
ROLE = "finshield-dev-demo-ops-admin"
USER = "finshield-dev-demo-kyc-user"
BUCKET = "finshield-dev-kyc-docs"


@pytest.fixture
def env(aws, monkeypatch):
    boto3 = aws
    monkeypatch.setenv("KYC_BUCKET", BUCKET)
    monkeypatch.delenv("DNS_DOMAIN_LIST_ID", raising=False)
    iam = boto3.client("iam")
    trust = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::123456789012:root"}, "Action": "sts:AssumeRole"}]})
    role_arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=trust)["Role"]["Arn"]
    user_arn = iam.create_user(UserName=USER)["User"]["Arn"]
    key = iam.create_access_key(UserName=USER)["AccessKey"]["AccessKeyId"]
    boto3.client("s3").create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "ap-south-1"})
    alert = put_alert(principal_arn=role_arn)
    return {"iam": iam, "s3": boto3.client("s3"), "role_arn": role_arn, "user_arn": user_arn, "key": key, "alert": alert}


def _event(principal_arn, mode="DRY_RUN", execution="ALR-20261120-0007-CRITICAL"):
    raised = fixture("alert_raised_critical")
    return {"alert_id": raised["alert_id"], "principal_arn": principal_arn, "user_id": raised["user_id"], "mode": mode, "execution": execution}


def _mode(monkeypatch, mode):
    monkeypatch.setenv("FINSHIELD_SETTING_CONTAINMENT_MODE", mode)


def test_dry_run_records_exact_call_and_changes_nothing(env, monkeypatch):
    _mode(monkeypatch, "DRY_RUN")
    out = load_fn("contain_revoke_sessions").handler(_event(env["role_arn"]), None)
    assert out["action"] == "REVOKE_SESSIONS" and out["mode"] == "DRY_RUN" and out["result"] == "OK"
    call = out["detail"]["would_call"][0]
    assert call["operation"] == "iam:PutRolePolicy" and call["params"]["RoleName"] == ROLE
    assert "aws:TokenIssueTime" in call["params"]["PolicyDocument"]
    assert env["iam"].list_role_policies(RoleName=ROLE)["PolicyNames"] == []
    entry = evidence.chain(AID)[-1]
    assert entry["type"] == "CONTAIN_REVOKE_SESSIONS" and entry["payload"]["mode"] == "DRY_RUN"
    assert schema.is_valid("evidence_entry", entry)


def test_ssm_mode_wins_over_input(env, monkeypatch):
    _mode(monkeypatch, "DRY_RUN")
    out = load_fn("contain_revoke_sessions").handler(_event(env["role_arn"], mode="LIVE"), None)
    assert out["mode"] == "DRY_RUN"


def test_live_revoke_puts_inline_deny_on_role(env, monkeypatch):
    _mode(monkeypatch, "LIVE")
    out = load_fn("contain_revoke_sessions").handler(_event(env["role_arn"], mode="LIVE"), None)
    assert out["mode"] == "LIVE" and out["result"] == "OK"
    assert env["iam"].list_role_policies(RoleName=ROLE)["PolicyNames"] == ["FinShieldRevokeSessions"]


def test_assumed_role_session_maps_to_role(env, monkeypatch):
    _mode(monkeypatch, "LIVE")
    session = f"arn:aws:sts::123456789012:assumed-role/{ROLE}/night-session"
    out = load_fn("contain_revoke_sessions").handler(_event(session, mode="LIVE"), None)
    assert out["result"] == "OK"
    assert env["iam"].list_role_policies(RoleName=ROLE)["PolicyNames"] == ["FinShieldRevokeSessions"]


def test_live_is_refused_for_non_demo_principal(env, monkeypatch):
    _mode(monkeypatch, "LIVE")
    env["iam"].create_role(RoleName="real-employee-role", AssumeRolePolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": []}))
    arn = "arn:aws:iam::123456789012:role/real-employee-role"
    out = load_fn("contain_revoke_sessions").handler(_event(arn, mode="LIVE"), None)
    assert out["mode"] == "DRY_RUN"
    assert any("not a finshield-dev-demo" in n for n in out["detail"]["notes"])
    assert env["iam"].list_role_policies(RoleName="real-employee-role")["PolicyNames"] == []


def test_live_deactivates_user_keys_and_records_ids(env, monkeypatch):
    _mode(monkeypatch, "LIVE")
    out = load_fn("contain_deactivate_keys").handler(_event(env["user_arn"], mode="LIVE"), None)
    assert out["result"] == "OK" and out["detail"]["deactivated_keys"] == [env["key"]]
    keys = env["iam"].list_access_keys(UserName=USER)["AccessKeyMetadata"]
    assert [k["Status"] for k in keys] == ["Inactive"]


def test_deactivate_keys_not_applicable_for_role(env, monkeypatch):
    _mode(monkeypatch, "LIVE")
    out = load_fn("contain_deactivate_keys").handler(_event(env["role_arn"], mode="LIVE"), None)
    assert out["result"] == "NOT_APPLICABLE"


def test_live_bucket_deny_adds_sid_and_keeps_existing_statements(env, monkeypatch):
    _mode(monkeypatch, "LIVE")
    existing = {"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
                "Resource": [f"arn:aws:s3:::{BUCKET}", f"arn:aws:s3:::{BUCKET}/*"], "Condition": {"Bool": {"aws:SecureTransport": "false"}}}
    env["s3"].put_bucket_policy(Bucket=BUCKET, Policy=json.dumps({"Version": "2012-10-17", "Statement": [existing]}))
    fn = load_fn("contain_bucket_deny")
    out = fn.handler(_event(env["role_arn"], mode="LIVE"), None)
    assert out["result"] == "OK" and out["detail"]["sid"] == "FinShieldDenyu017"
    fn.handler(_event(env["role_arn"], mode="LIVE", execution="second-run"), None)  # re-run must not duplicate the Sid
    sids = [s["Sid"] for s in json.loads(env["s3"].get_bucket_policy(Bucket=BUCKET)["Policy"])["Statement"]]
    assert sids == ["DenyInsecureTransport", "FinShieldDenyu017"]


def test_dns_block_is_dry_run_without_firewall_and_uses_destination(env, monkeypatch):
    _mode(monkeypatch, "LIVE")
    out = load_fn("contain_dns_block").handler(_event(env["role_arn"], mode="LIVE"), None)
    assert out["mode"] == "DRY_RUN" and out["result"] == "OK"
    assert out["detail"]["would_call"][0]["params"]["Domains"] == ["files.example-share.com"]


def test_alert_containment_list_and_schema(env, monkeypatch):
    _mode(monkeypatch, "DRY_RUN")
    for name in ("contain_revoke_sessions", "contain_deactivate_keys", "contain_bucket_deny", "contain_dns_block"):
        load_fn(name).handler(_event(env["role_arn"]), None)
    alert = ddb.get_item("Alerts", {"alert_id": AID})
    assert [c["action"] for c in alert["containment"]] == ["REVOKE_SESSIONS", "DEACTIVATE_KEYS", "BUCKET_DENY", "DNS_BLOCK"]
    schema.validate("alert", alert)
    assert [e["type"] for e in evidence.chain(AID)] == ["CONTAIN_REVOKE_SESSIONS", "CONTAIN_DEACTIVATE_KEYS", "CONTAIN_BUCKET_DENY", "CONTAIN_DNS_BLOCK"]
    assert evidence.verify(AID)["valid"] is True


def test_retry_of_same_execution_does_not_duplicate_evidence(env, monkeypatch):
    _mode(monkeypatch, "DRY_RUN")
    fn = load_fn("contain_revoke_sessions")
    fn.handler(_event(env["role_arn"]), None)
    fn.handler(_event(env["role_arn"]), None)
    assert len(evidence.chain(AID)) == 1


def test_missing_alert_still_contains_and_records_evidence(aws, monkeypatch):
    _mode(monkeypatch, "DRY_RUN")
    monkeypatch.setenv("KYC_BUCKET", BUCKET)
    out = load_fn("contain_bucket_deny").handler(_event(f"arn:aws:iam::123456789012:role/{ROLE}"), None)
    assert out["mode"] == "DRY_RUN"
    assert evidence.chain(AID)[0]["type"] == "CONTAIN_BUCKET_DENY"
