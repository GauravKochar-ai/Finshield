import copy
import hashlib
import json
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

from finshield import ddb, evidence, schema

AID = "ALR-20261120-0007"


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("TABLE_EVIDENCE", "finshield-dev-Evidence")
    with mock_aws():
        ddb.reset_resource()
        boto3.client("dynamodb", region_name="ap-south-1").create_table(
            TableName="finshield-dev-Evidence",
            KeySchema=[{"AttributeName": "alert_id", "KeyType": "HASH"}, {"AttributeName": "seq", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "alert_id", "AttributeType": "S"}, {"AttributeName": "seq", "AttributeType": "N"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield ddb.table("Evidence")
        ddb.reset_resource()


def _fill(n=4):
    return [evidence.append(AID, f"STEP_{i}", "tester", {"i": i, "ratio": 1.5}, ts=f"2026-11-20T23:49:0{i}+05:30") for i in range(1, n + 1)]


def test_canonical_json_sorted_compact_utf8():
    assert evidence.canonical_json({"b": 1, "a": {"d": [1, 2], "c": "₹"}}) == '{"a":{"c":"₹","d":[1,2]},"b":1}'
    assert evidence.canonical_json({"x": Decimal("3"), "y": Decimal("1.5")}) == '{"x":3,"y":1.5}'


def test_first_entry_chains_from_genesis_and_hash_matches_spec(table):
    e = evidence.append(AID, "ALERT_RAISED", "detection", {"score": 96}, ts="2026-11-20T23:49:02+05:30")
    assert e["seq"] == 1 and e["prev_hash"] == f"GENESIS:{AID}"
    body = {k: v for k, v in e.items() if k != "hash"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert e["hash"] == hashlib.sha256((f"GENESIS:{AID}" + canon).encode("utf-8")).hexdigest()
    assert schema.is_valid("evidence_entry", e)


def test_chain_links_and_verifies(table):
    entries = _fill(5)
    for prev, cur in zip(entries, entries[1:]):
        assert cur["prev_hash"] == prev["hash"] and cur["seq"] == prev["seq"] + 1
    assert evidence.verify(AID) == {"valid": True, "broken_at_seq": None}


def test_empty_chain_is_valid(table):
    assert evidence.verify("ALR-20261120-0099") == {"valid": True, "broken_at_seq": None}


def test_modified_payload_reports_first_broken_seq(table):
    _fill(5)
    table.update_item(Key={"alert_id": AID, "seq": 3}, UpdateExpression="SET payload = :p", ExpressionAttributeValues={":p": {"i": 99}})
    assert evidence.verify(AID) == {"valid": False, "broken_at_seq": 3}


def test_forged_entry_with_recomputed_hash_breaks_next_link(table):
    entries = _fill(4)
    forged = copy.deepcopy(entries[1])
    forged["payload"] = {"i": 42}
    forged["hash"] = evidence.compute_hash(forged["prev_hash"], forged)
    chain = [entries[0], forged, entries[2], entries[3]]
    assert evidence.verify_entries(AID, chain) == {"valid": False, "broken_at_seq": 3}


def test_deleted_entry_is_detected(table):
    entries = _fill(4)
    assert evidence.verify_entries(AID, [entries[0], entries[2], entries[3]]) == {"valid": False, "broken_at_seq": 2}


def test_wrong_genesis_detected(table):
    entries = _fill(2)
    assert evidence.verify_entries("ALR-20261120-0001", entries)["valid"] is False


def test_seq_conflict_is_retried(table, monkeypatch):
    _fill(2)
    real = evidence._last_entry
    first = evidence.chain(AID)[0]  # stale view: only seq 1 visible, as if another writer just took seq 2
    calls = {"n": 0}

    def stale_then_real(alert_id):
        calls["n"] += 1
        return first if calls["n"] == 1 else real(alert_id)

    monkeypatch.setattr(evidence, "_last_entry", stale_then_real)
    e = evidence.append(AID, "LATE", "tester", {})
    assert e["seq"] == 3 and calls["n"] == 2  # first try wanted seq 2 (taken), retry got seq 3
    assert evidence.verify(AID)["valid"] is True


def test_conditional_put_refuses_overwrite(table):
    _fill(1)
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        table.put_item(Item={"alert_id": AID, "seq": 1}, ConditionExpression="attribute_not_exists(seq)")


def test_ddb_helper_blocks_evidence_updates(table):
    with pytest.raises(PermissionError):
        ddb.update_item("Evidence", {"alert_id": AID, "seq": 1}, "SET x = :x", {":x": 1})


def test_fixture_chain_verifies():
    from pathlib import Path

    fx = Path(__file__).resolve().parents[2] / "contract" / "fixtures"
    chain = json.loads((fx / "api_alert_evidence.json").read_text())["data"]
    assert evidence.verify_entries(AID, chain) == {"valid": True, "broken_at_seq": None}
    tampered = copy.deepcopy(chain)
    tampered[2]["payload"]["result"] = "FAILED"
    assert evidence.verify_entries(AID, tampered) == {"valid": False, "broken_at_seq": 3}
