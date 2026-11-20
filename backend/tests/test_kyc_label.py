"""kyc_label: the vision call goes through finshield.bedrock (Guardrail + image block); fallback labels from the key."""
import io
import json

import pytest

from conftest import fixture, load_fn

BUCKET = "finshield-dev-kyc-docs"
KEY = "kyc/C-10161/KYC-AADHAAR-C-10161.png"


class FakeS3:
    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(b"\x89PNG-sample")}


class FakeBedrock:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def converse(self, **kw):
        self.calls.append(kw)
        return {"output": {"message": {"content": [{"text": json.dumps(self.reply)}]}}, "stopReason": "end_turn", "usage": {}}


@pytest.fixture
def kyc(aws, monkeypatch):
    from finshield import bedrock
    mod = load_fn("kyc_label")
    sent = []
    monkeypatch.setattr(mod, "s3_client", lambda: FakeS3())
    monkeypatch.setattr(mod.events, "put_event", lambda dt, d, source=None, bus_name=None: sent.append((dt, d, source)) or "id")
    monkeypatch.setenv("FINSHIELD_SETTING_GUARDRAIL_ID", "gr-test")
    monkeypatch.setenv("FINSHIELD_SETTING_GUARDRAIL_VERSION", "1")
    fake = FakeBedrock({"doc_type": "AADHAAR", "full_aadhaar_visible": True})
    monkeypatch.setattr(bedrock, "_client", lambda timeout_s: fake)
    return mod, fake, sent


def test_vision_call_has_guardrail_and_image_and_sets_the_flag(kyc, monkeypatch):
    from finshield import ddb
    mod, fake, sent = kyc
    monkeypatch.setenv("FINSHIELD_SETTING_BEDROCK_MODEL_ID", "mistral.mistral-large-3-675b-instruct")
    out = mod.handler({"detail": {"bucket": {"name": BUCKET}, "object": {"key": KEY, "size": 150 * 1024}}})
    assert out["status"] == "OK" and out["unmasked_aadhaar_flag"] is True
    call = fake.calls[0]
    assert call["guardrailConfig"]["guardrailIdentifier"] == "gr-test"
    assert call["inferenceConfig"]["temperature"] == 0
    content = call["messages"][0]["content"]
    assert content[0]["image"]["format"] == "png" and content[0]["image"]["source"]["bytes"].startswith(b"\x89PNG")
    assert "text" in content[1]
    row = ddb.get_item("KycFiles", {"file_id": "KYC-AADHAAR-C-10161"})
    assert row["label_source"] == "bedrock" and row["unmasked_aadhaar_flag"] is True and row["size_kb"] == 150


def test_no_model_labels_from_the_key(kyc, monkeypatch):
    from finshield import ddb
    mod, fake, sent = kyc
    monkeypatch.setenv("FINSHIELD_SETTING_BEDROCK_MODEL_ID", "NONE")
    out = mod.handler({"bucket": BUCKET, "key": KEY})
    assert out["unmasked_aadhaar_flag"] is False and fake.calls == []
    assert ddb.get_item("KycFiles", {"file_id": "KYC-AADHAAR-C-10161"})["label_source"] == "key"


def test_emitted_event_matches_the_event_schema(kyc, monkeypatch):
    from finshield import schema
    mod, fake, sent = kyc
    monkeypatch.setenv("FINSHIELD_SETTING_BEDROCK_MODEL_ID", "NONE")
    mod.handler({"bucket": BUCKET, "key": KEY})
    (dt, d, source), = sent
    assert dt == "Raw Activity" and source == "finshield.app"
    schema.validate("event", d)
    assert d["action"] == "KYC_FILE_UPLOADED" and d["data_class"] == fixture("event")["data_class"]
    assert set(d) <= set(fixture("event"))  # same field names as the contract example
