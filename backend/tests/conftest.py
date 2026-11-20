import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "shared" / "python"))
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("FINSHIELD_CONTRACT_DIR", str(ROOT / "contract"))
os.environ.setdefault("STAGE", "dev")

FIXTURES = ROOT / "contract" / "fixtures"


def fixture(name: str):
    """Fresh copy of contract/fixtures/<name>.json."""
    return copy.deepcopy(json.loads((FIXTURES / f"{name}.json").read_text()))


def load_fn(name: str):
    """Import backend/functions/<name>/app.py under a unique module name."""
    spec = importlib.util.spec_from_file_location(f"fn_{name}", ROOT / "backend" / "functions" / name / "app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _template_tables():
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    def tag(loader, suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return {suffix: loader.construct_scalar(node)}
        if isinstance(node, yaml.SequenceNode):
            return {suffix: loader.construct_sequence(node, deep=True)}
        return {suffix: loader.construct_mapping(node, deep=True)}

    Loader.add_multi_constructor("!", tag)
    t = yaml.load((ROOT / "infra" / "template.yaml").read_text(), Loader=Loader)
    out = {}
    for logical, res in t["Resources"].items():
        if res["Type"] == "AWS::DynamoDB::Table":
            out[logical[: -len("Table")]] = res["Properties"]
    return out


@pytest.fixture
def aws(monkeypatch):
    """moto account with every DynamoDB table from infra/template.yaml, TABLE_* env vars set, and clean SDK clients."""
    from moto import mock_aws

    import boto3
    from finshield import config, ddb, events

    with mock_aws():
        ddb.reset_resource()
        events.reset_client()
        config.clear_cache()
        client = boto3.client("dynamodb", region_name="ap-south-1")
        for logical, p in _template_tables().items():
            name = f"finshield-dev-{logical}"
            monkeypatch.setenv(f"TABLE_{logical.upper()}", name)
            kwargs = {
                "TableName": name,
                "KeySchema": p["KeySchema"],
                "AttributeDefinitions": p["AttributeDefinitions"],
                "BillingMode": "PAY_PER_REQUEST",
            }
            if p.get("GlobalSecondaryIndexes"):
                kwargs["GlobalSecondaryIndexes"] = p["GlobalSecondaryIndexes"]
            client.create_table(**kwargs)
        yield boto3
        ddb.reset_resource()
        events.reset_client()
        config.clear_cache()


def put_alert(alert=None, **overrides):
    """Write the SC-01 alert fixture (or a given alert) into the Alerts table, reset to a fresh OPEN state."""
    from finshield import ddb

    a = alert or fixture("alert_sc01")
    a.update({"status": "OPEN", "containment": [], "ai": None, "ai_status": "PENDING", "execution_arn": None, "deadlines": []})
    a.update(overrides)
    ddb.put_item("Alerts", a)
    return a
