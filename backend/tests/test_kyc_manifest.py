"""Checks the synthetic KYC manifest (simulator/seed/kyc-docs/manifest.csv).

The seed loads KycFiles and Customers from this file, and the backend parses the S3 keys,
so the columns, key format and document mix must not drift.
"""
import csv
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "simulator" / "seed" / "kyc-docs" / "manifest.csv"
COLUMNS = ["file_id", "customer_id", "doc_type", "s3_key", "size_kb",
           "aadhaar_last4", "pan_fake", "unmasked_aadhaar", "synthetic_name"]
KEY = re.compile(r"kyc/(C-\d{5})/KYC-(PAN|AADHAAR|SELFIE)-\1\.png")


@pytest.fixture(scope="module")
def rows():
    if not MANIFEST.exists():
        pytest.skip("manifest.csv not generated yet")
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS
        return list(reader)


def test_document_mix(rows):
    standard = rows[:200]
    mix = Counter((r["doc_type"], r["unmasked_aadhaar"]) for r in standard)
    assert mix == {("PAN", "false"): 80, ("AADHAAR", "false"): 80,
                   ("AADHAAR", "true"): 10, ("SELFIE", "false"): 30}
    assert [r["customer_id"] for r in standard] == [f"C-{n}" for n in range(10001, 10201)]


def test_keys_and_ids(rows):
    for r in rows:
        m = KEY.fullmatch(r["s3_key"])
        assert m, r["s3_key"]
        assert m.group(1) == r["customer_id"] and m.group(2) == r["doc_type"]
        assert r["file_id"] == Path(r["s3_key"]).stem
    assert len({r["file_id"] for r in rows}) == len(rows)


def test_only_masked_values_stored(rows):
    text = MANIFEST.read_text(encoding="utf-8")
    assert not re.search(r"\d{4}\s?\d{4}\s?\d{4}", text), "full Aadhaar number in manifest"
    for r in rows:
        assert re.fullmatch(r"SAMPL\d{4}A", r["pan_fake"])
        if r["doc_type"] == "AADHAAR":
            assert re.fullmatch(r"\d{4}", r["aadhaar_last4"])
        else:
            assert r["aadhaar_last4"] == ""
    assert sum(r["unmasked_aadhaar"] == "true" for r in rows) == 10


def test_sizes(rows):
    assert all(0 < float(r["size_kb"]) < 200 for r in rows)
