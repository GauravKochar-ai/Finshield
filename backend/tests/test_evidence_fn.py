"""evidence Lambda: append (idempotent), verify, export to the Object Lock bucket."""
import json

import pytest

from conftest import fixture, load_fn
from finshield import evidence

AID = "ALR-20261120-0007"
BUCKET = "finshield-dev-evidence"


@pytest.fixture
def fn(aws, monkeypatch):
    monkeypatch.setenv("EVIDENCE_BUCKET", BUCKET)
    s3 = aws.client("s3")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "ap-south-1"}, ObjectLockEnabledForBucket=True)
    s3.put_object_lock_configuration(Bucket=BUCKET, ObjectLockConfiguration={"ObjectLockEnabled": "Enabled", "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 365}}})
    return load_fn("evidence")


def test_append_is_idempotent_per_execution(fn):
    raised = fixture("alert_raised_critical")
    ev = {"action": "append", "alert_id": AID, "type": "ALERT_RAISED", "payload": raised, "execution": "ALR-20261120-0007-CRITICAL"}
    first = fn.handler(ev, None)
    second = fn.handler(ev, None)
    assert first == second and first["seq"] == 1
    assert len(evidence.chain(AID)) == 1


def test_verify(fn):
    fn.handler({"action": "append", "alert_id": AID, "type": "A"}, None)
    fn.handler({"action": "append", "alert_id": AID, "type": "B"}, None)
    assert fn.handler({"action": "verify", "alert_id": AID}, None) == {"valid": True, "broken_at_seq": None}


def test_export_writes_locked_bundle_and_records_it(fn, aws):
    for t in ("ALERT_RAISED", "DEADLINES_SET", "CLOSED_STEP"):
        fn.handler({"action": "append", "alert_id": AID, "type": t, "execution": "e1"}, None)
    out = fn.handler({"action": "export", "alert_id": AID, "execution": "e1"}, None)
    assert out["entries"] == 3 and out["verify"]["valid"] is True
    obj = aws.client("s3").get_object(Bucket=BUCKET, Key=out["s3_key"])
    bundle = json.loads(obj["Body"].read())
    assert [e["type"] for e in bundle["entries"]] == ["ALERT_RAISED", "DEADLINES_SET", "CLOSED_STEP"]
    assert obj.get("ObjectLockMode") == "COMPLIANCE"
    chain = evidence.chain(AID)
    assert chain[-1]["type"] == "EVIDENCE_EXPORTED" and evidence.verify(AID)["valid"] is True


def test_unknown_action_raises(fn):
    with pytest.raises(ValueError):
        fn.handler({"action": "delete", "alert_id": AID}, None)
