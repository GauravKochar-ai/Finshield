"""staff_api: the FinLend Ops staff routes of contract/openapi.yaml (Cognito group Staff only), {data, error} envelope.

GET  /v1/staff/me                          who am I (persona from Users.staff_email) + containment state, never 403s for containment
GET  /v1/staff/customers?q=&purpose=       my book (ASSIGNED), marketing-consented customers (marketing), first 50 (ALL)
GET  /v1/staff/customers/{id}?purpose=     customer + KYC files + purpose_consented
GET  /v1/staff/customers/{id}/consent      consent ledger view (read-only)
POST /v1/staff/customers/{id}/kyc-upload   presigned PUT for kyc/<cid>/KYC-<DOC>-<cid>.<png|jpg>
POST /v1/staff/kyc/{id}/url                presigned GET (view inline / download attachment)

Every customer-data request is reported as a Raw Activity event (source "app", the real staff user, the purpose) so the
normal detection pipeline scores it. A staff user with an alert in CONTAINED / AWAITING_APPROVAL / LOCKED gets 403
ACCESS_CONTAINED on those routes and no event is emitted (no data was read). Release restores access.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.config import Config

from finshield import ddb, events, schema
from finshield.config import load_config, region
from finshield.ddb import Key
from finshield.http import HttpError, body, claims, is_http, path_id, require, run
from finshield.log import log
from finshield.scoring import tz_offset

STAFF = ["Staff"]
BLOCKING = ("CONTAINED", "AWAITING_APPROVAL", "LOCKED")
PURPOSES = [p for p in schema._schemas()["event"]["properties"]["purpose"]["enum"] if p]
DOC_TYPES = ("PAN", "AADHAAR", "SELFIE", "ADDRESS")
CONTENT_TYPES = {"image/png": "png", "image/jpeg": "jpg"}
DISPOSITIONS = {"view": "inline", "download": "attachment"}
CUSTOMER_RX = re.compile(r"^C-\d{5}$")
FILE_RX = re.compile(r"^KYC-[A-Z_]+-C-\d{5}$")
CUSTOMER_KEYS = ("customer_id", "city", "loan_id", "assigned_agent", "partner_id")
MAX_ROWS = 50
URL_TTL_S = 300
USERS_TTL_S = 300

_staff_cache: dict[str, tuple[float, dict]] = {}
_s3 = None


def s3_client():  # module-level factory so tests can stub it
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=region(),
                           config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
    return _s3


def _bucket() -> str:
    return os.environ["KYC_BUCKET"]


# ------------------------------------------------------------------ caller and containment
def staff_user(event) -> dict:
    email = (claims(event).get("email") or "").strip().lower()
    hit = _staff_cache.get(email)
    if hit and time.time() - hit[0] < USERS_TTL_S:
        return hit[1]
    row, kw = None, {"FilterExpression": Attr("staff_email").eq(email)}
    tbl = ddb.table("Users")
    while email and row is None:
        r = tbl.scan(**kw)
        if r.get("Items"):
            row = ddb.from_ddb(r["Items"][0])
        if "LastEvaluatedKey" not in r:
            break
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    if not row:
        raise HttpError(403, "STAFF_NOT_MAPPED", "this sign-in is not mapped to a FinLend Ops staff user")
    _staff_cache[email] = (time.time(), row)
    return row


def containment(uid: str) -> dict | None:
    """Newest alert of this user that keeps access blocked, or None."""
    for a in ddb.query("Alerts", Key("user_id").eq(uid), index="user-detected-index", forward=False, limit=20):
        if a.get("status") in BLOCKING:
            live = any(c.get("mode") == "LIVE" for c in a.get("containment") or [])
            return {"alert_id": a["alert_id"], "status": a["status"], "mode": "LIVE" if live else "DRY_RUN"}
    return None


def _gate(event, user) -> None:
    c = containment(user["user_id"])
    if c:
        log("access denied (containment)", user_id=user["user_id"], alert_id=c["alert_id"], status=c["status"],
            mode=c["mode"], route=event.get("routeKey"))
        raise HttpError(403, "ACCESS_CONTAINED",
                        f"access is contained by alert {c['alert_id']} ({c['status']}, {c['mode']}); "
                        "a Security Head must release it")


# ------------------------------------------------------------------ request parsing
def _query(event) -> dict:
    return event.get("queryStringParameters") or {}


def _purpose(user, value) -> str:
    p = value or user.get("default_purpose")
    if p not in PURPOSES:
        raise HttpError(400, "BAD_REQUEST", f"purpose must be one of {PURPOSES}")
    return p


def _customer_id(event) -> str:
    cid = path_id(event)
    if not CUSTOMER_RX.match(cid):
        raise HttpError(400, "BAD_REQUEST", "customer id must look like C-10001")
    return cid


def _now() -> str:
    return datetime.now(tz_offset(load_config())).isoformat(timespec="seconds")


def emit(event, user, action, purpose, data_class, object_id=None, customer_id=None, bytes_=None, resource_arn=None):
    """One Raw Activity event for this request (event_id from the API request id: a retried request is deduplicated)."""
    rc = event.get("requestContext") or {}
    d = {"event_id": f"app-{rc.get('requestId')}", "ts": _now(), "source": "app", "user_id": user["user_id"],
         "principal_arn": user.get("iam_principal_arn"), "action": action, "object_id": object_id,
         "customer_id": customer_id, "data_class": data_class, "purpose": purpose, "bytes": bytes_,
         "ip": (rc.get("http") or {}).get("sourceIp"), "city": None, "device_id": None, "resource_arn": resource_arn}
    schema.validate("event", d)
    events.put_event("Raw Activity", d, source="finshield.app")
    log("staff access reported", event_id=d["event_id"], user_id=d["user_id"], action=action, customer_id=customer_id,
        purpose=purpose)


# ------------------------------------------------------------------ data
def _public_customer(c: dict) -> dict:
    out = {k: c.get(k) for k in CUSTOMER_KEYS}
    last4 = c.get("aadhaar_last4")
    out.update(aadhaar_masked=f"XXXX XXXX {last4}" if last4 else None, pan_fake=c.get("pan_fake"),
               sample=bool(c.get("sample", True)))
    return out


def _scan(logical, **kw):
    out, tbl = [], ddb.table(logical)
    while True:
        r = tbl.scan(**kw)
        out += [ddb.from_ddb(i) for i in r.get("Items", [])]
        if "LastEvaluatedKey" not in r:
            return out
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _batch_customers(ids) -> list[dict]:
    name, out = ddb.table_name("Customers"), []
    for i in range(0, len(ids), 100):
        req = {name: {"Keys": [{"customer_id": c} for c in ids[i:i + 100]]}}
        while req:
            r = ddb.resource().batch_get_item(RequestItems=req)
            out += [ddb.from_ddb(x) for x in r["Responses"].get(name, [])]
            req = r.get("UnprocessedKeys") or None
    return out


def _consent(cid) -> dict:
    return ddb.get_item("Consent", {"customer_id": cid}) or {}


def _consented(consent: dict, purpose: str) -> bool:
    return purpose in (consent.get("purposes") or []) and purpose not in (consent.get("withdrawn") or [])


def _customer(cid) -> dict:
    c = ddb.get_item("Customers", {"customer_id": cid})
    if not c:
        raise HttpError(404, "NOT_FOUND", f"customer {cid} not found")
    return c


def book(user, q) -> list[dict]:
    uid = user["user_id"]
    if q:
        c = ddb.get_item("Customers", {"customer_id": q.strip()}) if CUSTOMER_RX.match(q.strip()) else None
        rows = [c] if c else []
    elif user.get("team") == "marketing":
        ids = sorted(c["customer_id"] for c in _scan("Consent", FilterExpression=Attr("purposes").contains("marketing"),
                                                     ProjectionExpression="customer_id"))[:MAX_ROWS]
        rows = _batch_customers(ids)
    elif user.get("access_scope") == "ASSIGNED":
        if user.get("partner_id"):
            rows = ddb.query("Customers", Key("partner_id").eq(user["partner_id"]), index="partner-index")
        else:
            rows = _scan("Customers", FilterExpression=Attr("assigned_agent").eq(uid))
    else:
        rows = _scan("Customers")
    return [_public_customer(c) for c in sorted(rows, key=lambda c: c["customer_id"])[:MAX_ROWS]]


# ------------------------------------------------------------------ routes
def me(event):
    u = staff_user(event)
    return {"user_id": u["user_id"], "name_pseudo": u.get("name_pseudo"), "team": u.get("team"), "role": u.get("role"),
            "access_scope": u.get("access_scope"), "default_purpose": u.get("default_purpose"),
            "containment": containment(u["user_id"])}


def customers(event):
    u = staff_user(event)
    _gate(event, u)
    q = _query(event)
    purpose = _purpose(u, q.get("purpose"))
    rows = book(u, q.get("q"))
    emit(event, u, "VIEW", purpose, "PII", object_id="customer-list")
    return rows


def customer(event):
    u = staff_user(event)
    _gate(event, u)
    cid = _customer_id(event)
    purpose = _purpose(u, _query(event).get("purpose"))
    c = _customer(cid)
    files = ddb.query("KycFiles", Key("customer_id").eq(cid), index="customer-index")
    out = _public_customer(c)
    out["kyc_files"] = [{"file_id": f["file_id"], "doc_type": f.get("doc_type"), "size_kb": f.get("size_kb"),
                         "ai_label": f.get("ai_label"), "unmasked_aadhaar_flag": bool(f.get("unmasked_aadhaar_flag")),
                         "available": "label_source" in f} for f in sorted(files, key=lambda f: f["file_id"])]
    out["purpose_consented"] = _consented(_consent(cid), purpose)
    emit(event, u, "VIEW", purpose, "PII", object_id=cid, customer_id=cid)
    return out


def consent(event):
    u = staff_user(event)
    _gate(event, u)
    cid = _customer_id(event)
    purpose = _purpose(u, _query(event).get("purpose"))
    _customer(cid)
    c = _consent(cid)
    out = {"customer_id": cid, "purposes": c.get("purposes") or [], "withdrawn": c.get("withdrawn") or [],
           "given_at": c.get("given_at"), "notice_version": c.get("notice_version"), "purpose": purpose,
           "purpose_consented": _consented(c, purpose), "sample": bool(c.get("sample", True))}
    emit(event, u, "VIEW", purpose, "PII", object_id=f"consent-{cid}", customer_id=cid)
    return out


def kyc_url(event):
    u = staff_user(event)
    _gate(event, u)
    fid = path_id(event)
    if not FILE_RX.match(fid):
        raise HttpError(400, "BAD_REQUEST", "file id must look like KYC-PAN-C-10001")
    b = body(event)
    purpose = _purpose(u, b.get("purpose"))
    disposition = b.get("disposition") or "view"
    if disposition not in DISPOSITIONS:
        raise HttpError(400, "BAD_REQUEST", "disposition must be view or download")
    f = ddb.get_item("KycFiles", {"file_id": fid})
    if not f:
        raise HttpError(404, "NOT_FOUND", f"KYC file {fid} not found")
    key, bucket = f["s3_key"], _bucket()
    url = s3_client().generate_presigned_url(
        "get_object", ExpiresIn=URL_TTL_S,
        Params={"Bucket": bucket, "Key": key,
                "ResponseContentDisposition": f'{DISPOSITIONS[disposition]}; filename="{key.rsplit("/", 1)[-1]}"'})
    download = disposition == "download"
    emit(event, u, "DOWNLOAD" if download else "VIEW", purpose, "KYC", object_id=fid, customer_id=f.get("customer_id"),
         bytes_=int(f.get("size_kb") or 0) * 1024 if download else None, resource_arn=f"arn:aws:s3:::{bucket}/{key}")
    return {"file_id": fid, "disposition": disposition, "url": url, "expires_in": URL_TTL_S}


def kyc_upload(event):
    u = staff_user(event)
    _gate(event, u)
    cid = _customer_id(event)
    b = body(event)
    purpose = _purpose(u, b.get("purpose"))
    doc, ctype = b.get("doc_type"), b.get("content_type") or "image/png"
    if doc not in DOC_TYPES:
        raise HttpError(400, "BAD_REQUEST", f"doc_type must be one of {list(DOC_TYPES)}")
    if ctype not in CONTENT_TYPES:
        raise HttpError(400, "BAD_REQUEST", f"content_type must be one of {list(CONTENT_TYPES)}")
    _customer(cid)
    fid = f"KYC-{doc}-{cid}"
    key, bucket = f"kyc/{cid}/{fid}.{CONTENT_TYPES[ctype]}", _bucket()
    url = s3_client().generate_presigned_url("put_object", ExpiresIn=URL_TTL_S,
                                             Params={"Bucket": bucket, "Key": key, "ContentType": ctype})
    emit(event, u, "PRESIGN", purpose, "KYC", object_id=fid, customer_id=cid, resource_arn=f"arn:aws:s3:::{bucket}/{key}")
    return {"file_id": fid, "s3_key": key, "url": url, "method": "PUT", "headers": {"content-type": ctype},
            "expires_in": URL_TTL_S}


ROUTES = {
    "GET /v1/staff/me": (STAFF, me),
    "GET /v1/staff/customers": (STAFF, customers),
    "GET /v1/staff/customers/{id}": (STAFF, customer),
    "GET /v1/staff/customers/{id}/consent": (STAFF, consent),
    "POST /v1/staff/customers/{id}/kyc-upload": (STAFF, kyc_upload),
    "POST /v1/staff/kyc/{id}/url": (STAFF, kyc_url),
}


def handler(event, context=None):
    if not is_http(event):
        return {"status": "SKIPPED", "reason": "staff_api only serves HTTP routes"}
    route = " ".join(event["routeKey"].split())
    if route not in ROUTES:
        return run(event, lambda: (_ for _ in ()).throw(HttpError(404, "NOT_FOUND", f"no route {route}")))
    groups_allowed, fn = ROUTES[route]

    def go():
        require(event, groups_allowed)
        return fn(event)
    return run(event, go)
