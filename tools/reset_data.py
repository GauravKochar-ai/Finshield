#!/usr/bin/env python3
"""Delete ALL items from fs-events and fs-cases (run before every demo).

  python3 tools/reset_data.py --yes

S3 raw logs and evidence packs are kept (they are versioned evidence).
"""
import argparse
import sys

from common import cases_table, events_table


def wipe(table, keys):
    count, kwargs = 0, {"ProjectionExpression": ", ".join(f"#k{i}" for i in range(len(keys))),
                        "ExpressionAttributeNames": {f"#k{i}": k for i, k in enumerate(keys)}}
    with table.batch_writer() as batch:
        while True:
            page = table.scan(**kwargs)
            for item in page["Items"]:
                batch.delete_item(Key={k: item[k] for k in keys})
                count += 1
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return count


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--yes", action="store_true", help="confirm deletion")
    if not p.parse_args().yes:
        sys.exit("This deletes every event and case. Re-run with --yes to confirm.")
    print("fs-events deleted:", wipe(events_table(), ["actor_id", "ts"]))
    print("fs-cases  deleted:", wipe(cases_table(), ["case_id"]))
    print("✅ Clean. Note: a workflow still waiting for approval keeps running until it times out.")


if __name__ == "__main__":
    main()
