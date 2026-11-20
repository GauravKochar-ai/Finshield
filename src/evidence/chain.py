"""Hash-chain helpers shared by fs-evidence (build) and tools / dashboard (verify).

Each record stores the SHA-256 of its raw log and the hash of the previous
record. Changing any record (or reordering them) breaks every hash after it.
"""
import hashlib
import json

GENESIS = "0" * 64


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def record_hash(record):
    body = {k: v for k, v in record.items() if k != "record_hash"}
    return sha256(canonical(body))


def pack_hash(pack):
    body = {k: v for k, v in pack.items() if k != "pack_sha256"}
    return sha256(canonical(body))


def verify_pack(pack):
    """Returns (ok, list_of_problems)."""
    problems = []
    prev = GENESIS
    for rec in pack.get("records", []):
        if rec.get("prev_hash") != prev:
            problems.append(f"record {rec.get('seq')}: prev_hash does not match previous record")
        if record_hash(rec) != rec.get("record_hash"):
            problems.append(f"record {rec.get('seq')}: content was modified (hash mismatch)")
        prev = rec.get("record_hash")
    if pack.get("chain_head") != prev:
        problems.append("chain_head does not match the last record")
    if pack_hash(pack) != pack.get("pack_sha256"):
        problems.append("pack_sha256 mismatch (pack was modified)")
    return (len(problems) == 0), problems
