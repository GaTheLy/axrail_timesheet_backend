"""One-time migration: backfill status='active' on Users missing the status field.

The auto-provisioning Lambda filters by status='active' to create timesheet
submissions. Users created before the status field was added will be missing
it, causing them to be skipped.

Usage:
    python scripts/migrate_user_status.py
    python scripts/migrate_user_status.py --env staging
"""

import argparse
import boto3

REGION = "ap-southeast-1"


def scan_all(table):
    items = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def main():
    parser = argparse.ArgumentParser(
        description="Backfill status='active' on Users missing the status field."
    )
    parser.add_argument(
        "--env", default="dev", choices=["dev", "staging", "prod"],
        help="Target environment (default: dev)",
    )
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table_name = f"Timesheet_Users-{args.env}"
    table = dynamodb.Table(table_name)

    print(f"Scanning {table_name}...")
    items = scan_all(table)
    updated = 0

    for item in items:
        if not item.get("status"):
            table.update_item(
                Key={"userId": item["userId"]},
                UpdateExpression="SET #s = :status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":status": "active"},
            )
            updated += 1
            print(f"  Set status='active' on user {item.get('email', item['userId'])}")

    print(f"\nDone. Updated {updated} of {len(items)} users.")


if __name__ == "__main__":
    main()
