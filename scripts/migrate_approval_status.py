"""One-time migration: backfill approval_status on Departments, Positions, and Users.

Existing records created before the approval workflow feature do not have
an `approval_status` field.  This script scans each table and sets
`approval_status = "Approved"` and `rejectionReason = ""` on every record
that is missing the field.

Usage:
    python scripts/migrate_approval_status.py
    python scripts/migrate_approval_status.py --env staging
"""

import argparse
import boto3

REGION = "ap-southeast-1"

# Table name prefix → partition key
TABLES = {
    "Timesheet_Departments": "departmentId",
    "Timesheet_Positions": "positionId",
    "Timesheet_Users": "userId",
}


def scan_all(table):
    """Scan all items from a DynamoDB table, handling pagination."""
    items = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def migrate_table(dynamodb, table_name, key_field):
    """Set approval_status='Approved' and rejectionReason='' on records missing approval_status."""
    print(f"Scanning {table_name}...")
    table = dynamodb.Table(table_name)
    items = scan_all(table)
    updated = 0

    for item in items:
        if "approval_status" not in item:
            table.update_item(
                Key={key_field: item[key_field]},
                UpdateExpression="SET approval_status = :status, rejectionReason = :reason",
                ExpressionAttributeValues={
                    ":status": "Approved",
                    ":reason": "",
                },
            )
            updated += 1

    print(f"Updated {updated} records in {table_name}")
    return updated


def main():
    parser = argparse.ArgumentParser(
        description="Backfill approval_status on Departments, Positions, and Users tables."
    )
    parser.add_argument(
        "--env",
        default="dev",
        choices=["dev", "staging", "prod"],
        help="Target environment (default: dev)",
    )
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    total = 0

    for prefix, key_field in TABLES.items():
        table_name = f"{prefix}-{args.env}"
        total += migrate_table(dynamodb, table_name, key_field)

    print(f"\nMigration complete. Total records updated: {total}")


if __name__ == "__main__":
    main()
