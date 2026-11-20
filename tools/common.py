"""Shared helpers for the test tools: reads resource names from the
CloudFormation stack outputs, so nobody has to copy ARNs by hand."""
import os
import sys
from decimal import Decimal
from pathlib import Path

import boto3

STACK_NAME = os.environ.get("FS_STACK", "fs-stack")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "evidence"))   # so tools can import chain.py

_outputs = None


def outputs():
    global _outputs
    if _outputs is None:
        try:
            cf = boto3.client("cloudformation")
            stack = cf.describe_stacks(StackName=STACK_NAME)["Stacks"][0]
            _outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
        except Exception as exc:
            print(f"(could not read stack '{STACK_NAME}' outputs: {exc}; using defaults)")
            _outputs = {}
    return _outputs


def api_url():
    url = os.environ.get("API_URL") or outputs().get("ApiUrl")
    if not url:
        sys.exit("API URL not found. Deploy the stack first or set API_URL=...")
    return url


def cases_table():
    return boto3.resource("dynamodb").Table(outputs().get("CasesTableName", "fs-cases"))


def events_table():
    return boto3.resource("dynamodb").Table(outputs().get("EventsTableName", "fs-events"))


def plain(obj):
    """DynamoDB Decimal -> int/float so json.dumps works."""
    if isinstance(obj, list):
        return [plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    return obj
