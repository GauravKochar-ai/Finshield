"""start_incident: execution name <alert_id>-<severity>, duplicates ignored, execution_arn on the alert."""
import json

import pytest

from conftest import fixture, load_fn, put_alert
from finshield import ddb

AID = "ALR-20261120-0007"


@pytest.fixture
def fn(aws, monkeypatch):
    sfn = aws.client("stepfunctions")
    arn = sfn.create_state_machine(
        name="finshield-dev-incident",
        definition=json.dumps({"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}),
        roleArn="arn:aws:iam::123456789012:role/sfn",
    )["stateMachineArn"]
    monkeypatch.setenv("STATE_MACHINE_ARN", arn)
    put_alert()
    return load_fn("start_incident")


def _event():
    return {"detail-type": "Alert Raised", "source": "finshield.detection", "detail": fixture("alert_raised_critical")}


def test_starts_with_contract_name_and_records_arn(fn):
    out = fn.handler(_event(), None)
    assert out["status"] == "STARTED" and out["execution_arn"].endswith(":ALR-20261120-0007-CRITICAL")
    assert ddb.get_item("Alerts", {"alert_id": AID})["execution_arn"] == out["execution_arn"]


def test_duplicate_start_is_ignored(fn, monkeypatch):
    # AWS raises ExecutionAlreadyExists for a closed execution or different input (moto does not emulate it).
    from botocore.exceptions import ClientError

    real_client = fn.boto3.client

    class Sfn:
        def start_execution(self, **kw):
            raise ClientError({"Error": {"Code": "ExecutionAlreadyExists", "Message": "exists"}}, "StartExecution")

    monkeypatch.setattr(fn.boto3, "client", lambda svc, **kw: Sfn() if svc == "stepfunctions" else real_client(svc, **kw))
    out = fn.handler(_event(), None)
    assert out == {"status": "DUPLICATE", "alert_id": AID, "execution_name": "ALR-20261120-0007-CRITICAL"}


def test_new_severity_starts_new_execution(fn):
    fn.handler(_event(), None)
    ev = _event()
    ev["detail"].update(severity="HIGH")
    assert fn.handler(ev, None)["status"] == "STARTED"


def test_missing_fields_are_rejected(fn):
    ev = _event()
    del ev["detail"]["user_id"]
    with pytest.raises(ValueError):
        fn.handler(ev, None)
