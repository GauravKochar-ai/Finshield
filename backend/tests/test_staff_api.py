"""staff_api (FinLend Ops): Staff-only routes, persona mapping, containment gate, Raw Activity events, presigned URLs,
and the console-only meaning of x-groups "all". Data comes from the seed generator and the contract fixtures."""
from __future__ import annotations

import sys
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import ROOT, fixture, load_fn, put_alert
from test_contract import API_FIXTURES, _inline_registry, _resolve_response, _spec

from finshield import schema

sys.path.insert(0, str(ROOT / "simulator" / "seed"))
BUCKET = "finshield-dev-kyc-docs"
COLL, OPS, MKT = "collections.agent@finlend.example", "ops.admin@finlend.example", "marketing.user@finlend.example"


def http(route, email=COLL, groups="[Staff]", path=None, query=None, body=None, request_id="req-1"):
    claims = {"cognito:groups": groups, "email": email} if email else {}
    ev = {"routeKey": route, "rawPath": route.split()[1],
          "requestContext": {"requestId": request_id, "http": {"sourceIp": "49.36.1.2"},
                             "authorizer": {"jwt": {"claims": claims}}},
          "pathParameters": path, "queryStringParameters": query}
    if body is not None:
        import json
        ev["body"] = json.dumps(body)
    return ev


def call(fn, *a, **kw):
    import json
    r = fn.handler(http(*a, **kw))
    return r["statusCode"], json.loads(r["body"])


@pytest.fixture
def staff(aws, monkeypatch):
    import generate
    from datetime import datetime

    from finshield import ddb, events

    monkeypatch.setenv("KYC_BUCKET", BUCKET)
    now = datetime.fromisoformat("2026-11-20T12:00:00+05:30")
    data = {"Users": generate.make_users("123456789012"), "Customers": generate.make_customers(now),
            "Consent": generate.make_consent(now)}
    for logical, rows in data.items():
        with ddb.table(logical).batch_writer() as bw:
            for r in rows:
                if logical != "Customers" or r["customer_id"] < "C-10300" or r["customer_id"] in ("C-11002",):
                    bw.put_item(Item=ddb.to_ddb({k: v for k, v in r.items() if v is not None}))
    for doc, flag in (("PAN", None), ("AADHAAR", None)):
        row = {"file_id": f"KYC-{doc}-C-10001", "customer_id": "C-10001", "doc_type": doc,
               "s3_key": f"kyc/C-10001/KYC-{doc}-C-10001.png", "size_kb": 49, "ai_label": doc,
               "unmasked_aadhaar_flag": False, "sample": True}
        if doc == "PAN":
            row["label_source"] = "bedrock"
        ddb.put_item("KycFiles", row)
    sent = []
    monkeypatch.setattr(events, "put_event", lambda dt, d, source=None, bus_name=None: sent.append((dt, d, source)) or "id")
    fn = load_fn("staff_api")
    fn._staff_cache.clear()
    return fn, sent


def _matches_openapi(op, body):
    from jsonschema import Draft202012Validator
    from referencing import Resource
    from referencing.jsonschema import DRAFT202012

    spec = _spec()
    sch = _resolve_response(spec, spec["paths"][op[0]][op[1]]["responses"]["200"])
    wrapper = {"$id": "https://finshield.local/contract/openapi.yaml", "components": spec["components"], **sch}
    reg = _inline_registry().with_resource(wrapper["$id"], Resource.from_contents(wrapper, default_specification=DRAFT202012))
    errs = [e.message for e in Draft202012Validator(wrapper, registry=reg).iter_errors(body)]
    assert not errs, errs


def test_collections_agent_lists_its_book_and_reports_one_view(staff):
    fn, sent = staff
    st, b = call(fn, "GET /v1/staff/me")
    assert st == 200 and b["data"]["user_id"] == "u-031" and b["data"]["default_purpose"] == "collections"
    assert b["data"]["containment"] is None and not sent
    _matches_openapi(API_FIXTURES["api_staff_me"], b)
    st, b = call(fn, "GET /v1/staff/customers", query={"purpose": "collections"})
    rows = b["data"]
    assert st == 200 and len(rows) == 50 and rows[0]["customer_id"] == "C-10001"
    assert all(r["assigned_agent"] == "u-031" for r in rows) and rows == sorted(rows, key=lambda r: r["customer_id"])
    assert rows[0]["pan_fake"] == "SAMPL0001A" and rows[0]["aadhaar_masked"].startswith("XXXX XXXX ")
    assert set(rows[0]) == set(fixture("api_staff_customers")["data"][0])
    _matches_openapi(API_FIXTURES["api_staff_customers"], b)
    (dt, d, src), = sent
    assert (dt, src, d["source"], d["action"], d["object_id"], d["customer_id"], d["data_class"]) == \
        ("Raw Activity", "finshield.app", "app", "VIEW", "customer-list", None, "PII")
    assert d["user_id"] == "u-031" and d["principal_arn"].endswith("user/sample-u-031") and d["ip"] == "49.36.1.2"
    schema.validate("event", d)


def test_query_by_exact_id_and_marketing_book(staff):
    fn, sent = staff
    st, b = call(fn, "GET /v1/staff/customers", query={"q": "C-11002"})
    assert st == 200 and [r["customer_id"] for r in b["data"]] == ["C-11002"]
    st, b = call(fn, "GET /v1/staff/customers", email=MKT)
    ids = [r["customer_id"] for r in b["data"]]
    assert st == 200 and ids and all(int(i[2:]) % 2 == 0 and int(i[2:]) % 10 for i in ids)
    assert sent[-1][1]["purpose"] == "marketing"


def test_customer_detail_consent_and_purpose(staff):
    fn, sent = staff
    st, b = call(fn, "GET /v1/staff/customers/{id}", path={"id": "C-10001"}, query={"purpose": "collections"})
    assert st == 200 and b["data"]["purpose_consented"] is True
    files = {f["file_id"]: f for f in b["data"]["kyc_files"]}
    assert files["KYC-PAN-C-10001"]["available"] is True and files["KYC-AADHAAR-C-10001"]["available"] is False
    _matches_openapi(API_FIXTURES["api_staff_customer"], b)
    assert (sent[-1][1]["action"], sent[-1][1]["customer_id"], sent[-1][1]["data_class"]) == ("VIEW", "C-10001", "PII")
    # C-10001 is odd: no marketing consent
    st, b = call(fn, "GET /v1/staff/customers/{id}/consent", path={"id": "C-10001"}, query={"purpose": "marketing"})
    assert st == 200 and b["data"]["purpose_consented"] is False and b["data"]["purpose"] == "marketing"
    _matches_openapi(API_FIXTURES["api_staff_consent"], b)
    st, b = call(fn, "GET /v1/staff/customers/{id}/consent", path={"id": "C-10002"}, query={"purpose": "marketing"})
    assert b["data"]["purpose_consented"] is True
    st, b = call(fn, "GET /v1/staff/customers/{id}/consent", path={"id": "C-10010"}, query={"purpose": "marketing"})
    assert b["data"]["withdrawn"] == ["marketing"] and b["data"]["purpose_consented"] is False
    assert all(schema.is_valid("event", d) and d["purpose"] == "marketing" for _t, d, _s in sent[-3:])
    st, b = call(fn, "GET /v1/staff/customers/{id}", path={"id": "C-10001"}, query={"purpose": "fun"})
    assert st == 400 and b["error"]["code"] == "BAD_REQUEST"
    st, b = call(fn, "GET /v1/staff/customers/{id}", path={"id": "C-19999"})
    assert st == 404


def test_kyc_view_download_and_upload_urls(staff):
    fn, sent = staff
    kyc_label = load_fn("kyc_label")
    st, b = call(fn, "POST /v1/staff/kyc/{id}/url", path={"id": "KYC-PAN-C-10001"}, body={"disposition": "view"})
    u = urlparse(b["data"]["url"])
    assert st == 200 and u.netloc == f"{BUCKET}.s3.ap-south-1.amazonaws.com" and u.path == "/kyc/C-10001/KYC-PAN-C-10001.png"
    q = parse_qs(u.query)
    assert q["response-content-disposition"][0].startswith("inline") and q["X-Amz-Expires"] == ["300"]
    _matches_openapi(API_FIXTURES["api_staff_kyc_url"], b)
    d = sent[-1][1]
    assert (d["action"], d["data_class"], d["object_id"], d["customer_id"], d["bytes"]) == ("VIEW", "KYC", "KYC-PAN-C-10001", "C-10001", None)
    assert d["resource_arn"] == f"arn:aws:s3:::{BUCKET}/kyc/C-10001/KYC-PAN-C-10001.png"
    st, b = call(fn, "POST /v1/staff/kyc/{id}/url", path={"id": "KYC-PAN-C-10001"}, body={"disposition": "download"},
                 request_id="req-2")
    assert parse_qs(urlparse(b["data"]["url"]).query)["response-content-disposition"][0].startswith("attachment")
    assert (sent[-1][1]["action"], sent[-1][1]["bytes"]) == ("DOWNLOAD", 49 * 1024)
    st, b = call(fn, "POST /v1/staff/customers/{id}/kyc-upload", path={"id": "C-10001"},
                 body={"doc_type": "SELFIE", "content_type": "image/jpeg"}, request_id="req-3")
    data = b["data"]
    assert st == 200 and data["s3_key"] == "kyc/C-10001/KYC-SELFIE-C-10001.jpg" and data["method"] == "PUT"
    assert data["headers"] == {"content-type": "image/jpeg"} and data["file_id"] == "KYC-SELFIE-C-10001"
    m = kyc_label.KEY_RX.match(data["s3_key"])
    assert m and (m["cid"], m["name"], m["doc"]) == ("C-10001", "KYC-SELFIE-C-10001", "SELFIE")
    assert urlparse(data["url"]).path == "/" + data["s3_key"]
    _matches_openapi(API_FIXTURES["api_staff_kyc_upload"], b)
    assert (sent[-1][1]["action"], sent[-1][1]["data_class"]) == ("PRESIGN", "KYC")
    st, b = call(fn, "POST /v1/staff/customers/{id}/kyc-upload", path={"id": "C-10001"}, body={"doc_type": "PASSPORT"})
    assert st == 400
    assert all(schema.is_valid("event", d) and d["source"] == "app" for _t, d, _s in sent)


def test_same_request_id_gives_the_same_event_id(staff):
    fn, sent = staff
    for _ in range(2):
        call(fn, "GET /v1/staff/customers/{id}", path={"id": "C-10001"}, request_id="abc")
    assert [d["event_id"] for _t, d, _s in sent] == ["app-abc", "app-abc"]


def test_groups_staff_only_on_staff_routes_and_console_only_elsewhere(staff):
    fn, _sent = staff
    for route in fn.ROUTES:
        st, b = call(fn, route, email="securityhead@finshield.example", groups="[SecurityHead]",
                     path={"id": "C-10001"}, body={})
        assert st == 403 and b["error"]["code"] == "FORBIDDEN", route
    api = load_fn("api")
    for route in ("GET /v1/alerts", "GET /v1/posture", "GET /v1/privacy"):
        st, b = call(api, route)
        assert st == 403 and b["error"]["code"] == "FORBIDDEN", route
    st, _b = call(api, "GET /v1/rules", email="auditor@finshield.example", groups="[Auditor]")
    assert st == 200
    st, _b = call(api, "GET /v1/rules", email=None)
    assert st == 401


def test_unmapped_staff_email(staff):
    fn, sent = staff
    st, b = call(fn, "GET /v1/staff/me", email="someone@finlend.example")
    assert st == 403 and b["error"]["code"] == "STAFF_NOT_MAPPED" and not sent


def test_containment_blocks_customer_data_until_release(staff):
    fn, sent = staff
    a = put_alert(status="LOCKED", containment=[{"action": "REVOKE_SESSIONS", "mode": "DRY_RUN", "result": "OK"}])
    assert a["user_id"] == "u-017"
    st, b = call(fn, "GET /v1/staff/me", email=OPS)
    assert st == 200 and b["data"]["containment"] == {"alert_id": a["alert_id"], "status": "LOCKED", "mode": "DRY_RUN"}
    _matches_openapi(API_FIXTURES["api_staff_me"], b)
    for route in [r for r in fn.ROUTES if r != "GET /v1/staff/me"]:
        st, b = call(fn, route, email=OPS, path={"id": "C-10001" if "customers/" in route else "KYC-PAN-C-10001"},
                     body={"doc_type": "PAN"})
        assert st == 403 and b["error"]["code"] == "ACCESS_CONTAINED", route
        assert a["alert_id"] in b["error"]["message"] and "DRY_RUN" in b["error"]["message"]
    assert not sent  # a denied request reads nothing and reports nothing
    put_alert(status="AWAITING_APPROVAL", containment=[{"action": "BUCKET_DENY", "mode": "LIVE", "result": "OK"}])
    assert call(fn, "GET /v1/staff/me", email=OPS)[1]["data"]["containment"]["mode"] == "LIVE"
    put_alert(status="RELEASED")
    st, b = call(fn, "GET /v1/staff/customers", email=OPS)
    assert st == 200 and len(b["data"]) == 50 and sent[-1][1]["user_id"] == "u-017"
    assert sent[-1][1]["principal_arn"].endswith("role/finshield-dev-demo-ops-admin")
