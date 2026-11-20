"""Template, stub and state machine consistency checks."""
import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "infra" / "template.yaml"
FUNCS = ROOT / "backend" / "functions"


class L(yaml.SafeLoader):
    pass


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {suffix: loader.construct_sequence(node, deep=True)}
    return {suffix: loader.construct_mapping(node, deep=True)}


L.add_multi_constructor("!", _tag)
T = yaml.load(TEMPLATE.read_text(), Loader=L)
RES = T["Resources"]
FN_RES = {k: v for k, v in RES.items() if v["Type"] == "AWS::Serverless::Function"}


def _fn_dirs():
    return sorted(p.name for p in FUNCS.iterdir() if (p / "app.py").is_file())


def _stub_dirs():
    return [n for n in _fn_dirs() if "stub.handle(" in (FUNCS / n / "app.py").read_text()]


def test_every_function_dir_is_registered_and_vice_versa():
    registered = sorted(v["Properties"]["CodeUri"].rstrip("/").split("/")[-1] for v in FN_RES.values())
    assert registered == _fn_dirs()


def test_parameters_present():
    assert {"Stage", "AlertEmail", "ContainmentMode", "CreateGuardDutyDetector", "EnableConfigRules", "EnableDnsFirewall"} <= set(T["Parameters"])


def test_thirteen_tables_and_five_main_buckets():
    tables = [k for k, v in RES.items() if v["Type"] == "AWS::DynamoDB::Table"]
    assert len(tables) == 13
    for k in tables:
        p = RES[k]["Properties"]
        assert p["BillingMode"] == "PAY_PER_REQUEST"
        assert p["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True
        assert p["SSESpecification"]["SSEType"] == "KMS"
    for b in ("KycBucket", "RawBucket", "RulesBucket", "EvidenceBucket", "WebBucket"):
        assert RES[b]["Type"] == "AWS::S3::Bucket"
    lock = RES["EvidenceBucket"]["Properties"]
    assert lock["ObjectLockEnabled"] is True and lock["ObjectLockConfiguration"]["Rule"]["DefaultRetention"] == {"Mode": "COMPLIANCE", "Days": 365}


def test_required_outputs():
    assert {"ApiUrl", "UserPoolId", "UserPoolClientId", "BusName", "StateMachineArn", "WebBucket", "CloudFrontUrl", "KycBucket", "EvidenceBucket"} <= set(T["Outputs"])


def test_all_functions_python312_arm64_via_globals():
    g = T["Globals"]["Function"]
    assert g["Runtime"] == "python3.12" and g["Architectures"] == ["arm64"] and g["Handler"] == "app.handler"
    for v in FN_RES.values():
        assert "Runtime" not in v["Properties"] and "Handler" not in v["Properties"]


def test_no_role_can_update_or_delete_evidence():
    for name, v in FN_RES.items():
        for pol in v["Properties"].get("Policies", []):
            if "DynamoDBCrudPolicy" in pol:
                assert pol["DynamoDBCrudPolicy"]["TableName"] != {"Ref": "EvidenceTable"}, name
            for st in pol.get("Statement", []):
                res = json.dumps(st.get("Resource"))
                actions = st["Action"] if isinstance(st["Action"], list) else [st["Action"]]
                if "EvidenceTable" in res:
                    assert not {a for a in actions if a.startswith("dynamodb:") and a not in ("dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query")}, name
    assert "EvidenceTable" not in json.dumps({k: v for k, v in RES.items() if v["Type"] == "AWS::IAM::Role"})


def test_every_api_operation_has_a_route():
    spec = yaml.safe_load((ROOT / "contract" / "openapi.yaml").read_text())
    want = {(m.upper(), "/v1" + p) for p, item in spec["paths"].items() for m in item if m in ("get", "post")}
    have = set()
    for v in FN_RES.values():
        for ev in v["Properties"].get("Events", {}).values():
            if ev["Type"] == "HttpApi":
                have.add((ev["Properties"]["Method"], ev["Properties"]["Path"]))
    assert want == have


def test_state_machine_is_wired():
    asl = json.loads((ROOT / "backend" / "statemachines" / "incident.asl.json").read_text())

    def walk(sm):
        states = sm["States"]
        assert sm["StartAt"] in states
        for name, s in states.items():
            targets = [s.get("Next")] + [c["Next"] for c in s.get("Choices", [])] + [s.get("Default")] + [c["Next"] for c in s.get("Catch", [])]
            for t in filter(None, targets):
                assert t in states, f"{name} -> {t}"
            for br in s.get("Branches", []):
                walk(br)

    walk(asl)
    used = set(re.findall(r"\$\{(\w+)\}", json.dumps(asl)))
    provided = set(RES["IncidentStateMachine"]["Properties"]["DefinitionSubstitutions"])
    assert used <= provided, used - provided
    assert asl["States"]["BranchOnSeverity"]["Choices"][0]["Next"] == "CriticalParallel"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"fn_{name}", FUNCS / name / "app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", _stub_dirs())
def test_stub_logs_and_returns_ok(name, caplog):
    out = _load(name).handler({"alert_id": "ALR-20261120-0007", "event_id": "evt-1"}, None)
    assert out == {"status": "OK", "function": name, "stub": True}


def test_http_stub_returns_contract_fixture():
    out = _load("api").handler({"routeKey": "GET /v1/alerts", "requestContext": {"http": {}}}, None)
    body = json.loads(out["body"])
    assert out["statusCode"] == 200 and body["error"] is None and body["data"][0]["score"] == 96
