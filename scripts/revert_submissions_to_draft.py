"""Revert all submissions for a specific period back to Draft status.

Usage:
    AWS_PROFILE=AdministratorAccess-815254799325 python scripts/revert_submissions_to_draft.py
"""

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = "Timesheet_Submissions-dev"
PERIOD_ID = "8793648d-31cf-4d7c-a009-4d7bb8046d59"
REGION = "ap-southeast-1"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def get_submissions_for_period(period_id):
    items = []
    response = table.query(
        IndexName="periodId-status-index",
        KeyConditionExpression=Key("periodId").eq(period_id),
    )
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="periodId-status-index",
            KeyConditionExpression=Key("periodId").eq(period_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def main():
    print(f"Fetching submissions for period {PERIOD_ID}...")
    submissions = get_submissions_for_period(PERIOD_ID)
    print(f"Found {len(submissions)} submissions")

    updated = 0
    for sub in submissions:
        sid = sub["submissionId"]
        status = sub.get("status", "")
        if status == "Draft":
            print(f"  {sid} — already Draft, skipping")
            continue

        table.update_item(
            Key={"submissionId": sid},
            UpdateExpression="SET #s = :draft",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":draft": "Draft"},
        )
        print(f"  {sid} — {status} → Draft")
        updated += 1

    print(f"\nDone. Updated {updated} submissions to Draft.")


if __name__ == "__main__":
    main()
