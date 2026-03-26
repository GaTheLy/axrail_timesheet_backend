"""One-time migration: re-key Users table userId to match Cognito sub.

Also updates employeeId on all Timesheet_Submissions rows.

Usage:
    python scripts/migrate_user_ids.py
"""

import boto3

REGION = "ap-southeast-1"
USER_POOL_ID = "ap-southeast-1_FCLxuGj3s"
USERS_TABLE = "Timesheet_Users-dev"
SUBMISSIONS_TABLE = "Timesheet_Submissions-dev"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
cognito = boto3.client("cognito-idp", region_name=REGION)


def get_cognito_sub(email):
    """Look up the Cognito sub for a given email."""
    resp = cognito.list_users(
        UserPoolId=USER_POOL_ID,
        Filter=f'email = "{email}"',
        Limit=1,
    )
    users = resp.get("Users", [])
    if not users:
        return None
    for attr in users[0].get("Attributes", []):
        if attr["Name"] == "sub":
            return attr["Value"]
    return None


def scan_all(table):
    """Scan all items from a DynamoDB table."""
    items = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def migrate():
    users_table = dynamodb.Table(USERS_TABLE)
    submissions_table = dynamodb.Table(SUBMISSIONS_TABLE)

    users = scan_all(users_table)
    print(f"Found {len(users)} user(s) in {USERS_TABLE}")

    for user in users:
        old_id = user["userId"]
        email = user.get("email", "")

        cognito_sub = get_cognito_sub(email)
        if not cognito_sub:
            print(f"  SKIP {email}: no Cognito user found")
            continue

        if old_id == cognito_sub:
            print(f"  OK   {email}: userId already matches Cognito sub")
            continue

        print(f"  FIX  {email}: {old_id} -> {cognito_sub}")

        # Create new user item with correct userId
        new_item = dict(user)
        new_item["userId"] = cognito_sub
        users_table.put_item(Item=new_item)

        # Delete old user item
        users_table.delete_item(Key={"userId": old_id})

        # Update submissions: re-key employeeId
        submissions = scan_all(submissions_table)
        for sub in submissions:
            if sub.get("employeeId") == old_id:
                print(f"    Updating submission {sub['submissionId']}")
                submissions_table.update_item(
                    Key={"submissionId": sub["submissionId"]},
                    UpdateExpression="SET employeeId = :new_id",
                    ExpressionAttributeValues={":new_id": cognito_sub},
                )

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
