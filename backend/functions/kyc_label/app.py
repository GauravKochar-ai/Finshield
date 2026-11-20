"""kyc_label: a KYC file lands in the KYC bucket (S3 Object Created via EventBridge) -> label it in KycFiles and
put a KYC_FILE_UPLOADED event on the bus.

Key pattern kyc/<customer_id>/KYC-<DOC>-<customer_id>.<ext>. The document type comes from the key. With a Bedrock
model configured, image files are sent to the model (finshield.bedrock.converse: image block, Guardrail) to read the document type and whether a
full 12-digit Aadhaar number is visible (unmasked_aadhaar_flag, shown on the Privacy screen). Without Bedrock, or when
the call fails, the label comes from the key and the flag stays false.
"""
from __future__ import annotations

import re
from datetime import datetime

import boto3

from finshield import bedrock, ddb, events
from finshield.config import get_setting, load_config, region
from finshield.log import log
from finshield.scoring import tz_offset

KEY_RX = re.compile(r"^kyc/(?P<cid>[^/]+)/(?P<name>KYC-(?P<doc>[A-Z_]+)-[^/.]+)\.(?P<ext>\w+)$")
IMAGE = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "webp": "webp", "gif": "gif"}
PROMPT = ('This is a SAMPLE Indian KYC document image. Reply only with JSON {"doc_type": "PAN|AADHAAR|SELFIE|ADDRESS|OTHER", '
          '"full_aadhaar_visible": true|false}. full_aadhaar_visible is true only if a complete 12-digit Aadhaar number is readable.')
SYSTEM = "You classify SAMPLE KYC document images for a privacy check. Never transcribe numbers or names. Reply with JSON only."
MAX_IMAGE_BYTES = 3_500_000


def s3_client():  # module-level factory so tests can stub it
    return boto3.client("s3", region_name=region())


def _vision(bucket, key, ext, client=None):
    """Converse through finshield.bedrock (Guardrail, temperature 0). None -> label from the key."""
    model = get_setting("bedrock_model_id", "NONE")
    if not model or model == "NONE" or ext not in IMAGE:
        return None
    data = s3_client().get_object(Bucket=bucket, Key=key)["Body"].read()
    if len(data) > MAX_IMAGE_BYTES:
        return None
    try:
        r = bedrock.converse(SYSTEM, PROMPT, image=(IMAGE[ext], data), timeout_s=30, max_tokens=100, client=client)
    except bedrock.BedrockUnavailable as exc:
        log("bedrock unavailable, label from the key", key=key, reason=str(exc)[:200])
        return None
    if r["guardrail_intervened"]:
        return None
    return bedrock.extract_json(r["text"])


def label(bucket, key, size=None):
    m = KEY_RX.match(key)
    if not m:
        log("key does not match the KYC pattern, skipped", key=key)
        return {"status": "SKIPPED", "key": key}
    doc, cid, fid = m["doc"], m["cid"], m["name"]
    ai_label, flag, source = doc, False, "key"
    try:
        v = _vision(bucket, key, m["ext"].lower())
        if v:
            ai_label, flag, source = v.get("doc_type") or doc, bool(v.get("full_aadhaar_visible")), "bedrock"
    except Exception as exc:  # never block the upload on AI
        log("vision label failed, using the key", level="WARNING", key=key, error=str(exc)[:200])
    row = {"file_id": fid, "customer_id": cid, "doc_type": doc, "s3_key": key, "ai_label": ai_label,
           "unmasked_aadhaar_flag": flag, "label_source": source, "sample": True}
    if size:
        row["size_kb"] = int(size) // 1024
    ddb.put_item("KycFiles", row)
    now = datetime.now(tz_offset(load_config())).isoformat(timespec="seconds")
    events.put_event("Raw Activity", {"event_id": f"kyc-{fid}-{now[:19].replace(':', '')}", "ts": now, "source": "app",
                                      "user_id": "svc-kyc-upload", "action": "KYC_FILE_UPLOADED", "object_id": fid,
                                      "customer_id": cid, "data_class": "KYC",
                                      "resource_arn": f"arn:aws:s3:::{bucket}/{key}"}, source="finshield.app")
    log("kyc file labelled", file_id=fid, ai_label=ai_label, unmasked_aadhaar=flag, source=source)
    return {"status": "OK", "file_id": fid, "ai_label": ai_label, "unmasked_aadhaar_flag": flag}


def handler(event, context=None):
    d = event.get("detail") or {}
    return label(d.get("bucket", {}).get("name") or event.get("bucket"), d.get("object", {}).get("key") or event.get("key"),
                 d.get("object", {}).get("size"))
