"""Sync Cognito User Pool users into the DynamoDB Users table.

For each Cognito user, if they don't exist in DynamoDB, creates a record
with their fullName, email, userType, role, etc. from Cognito attributes.

Usage:
    AWS_PROFILE=AdministratorAccess-815254799325 python scripts/sync_cognito_users_to_dynamodb.py
"""

import boto3
from datetime import datetime, timezone

USER_POOL_ID = "ap-southeast-1_FCLxuGj3s"
USERS_TABLE = "Timesheet_Users-dev"
REGION = "ap-southeast-1"

cognito = boto3.client("cognito-idp", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(USERS_TABLE)


def get_all_cognito_users():
    users = []
    params = {"UserPoolId": USER_POOL_ID, "Limit": 60}
    while True:
        response = cognito.list_users(**params)
        users.extend(response.get("Users", []))
        token = response.get("PaginationToken")
        if not token:
            break
        params["PaginationToken"] = token
    return users


def get_attr(user, name):
    for attr in user.get("Attributes", []):
        if attr["Name"] == name:
            return attr["Value"]
    return ""


def get_existing_user_ids():
    ids = set()
    response = table.scan(ProjectionExpression="userId")
    for item in response.get("Items", []):
        ids.add(item["userId"])
    while "LastEvaluatedKey" in response:
        response = table.scan(
            ProjectionExpression="userId",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        for item in response.get("Items", []):
            ids.add(item["userId"])
    return ids


def main():
    print("Fetching Cognito users...")
    cognito_users = get_all_cognito_users()
    print(f"Found {len(cognito_users)} Cognito users")

    print("Fetching existing DynamoDB users...")
    existing_ids = get_existing_user_ids()
    print(f"Found {len(existing_ids)} existing DynamoDB users")

    now = datetime.now(timezone.utc).isoformat()
    created = 0

    for user in cognito_users:
        sub = get_attr(user, "sub")
        if not sub:
            continue
        if sub in existing_ids:
            continue

        email = get_attr(user, "email")
        name = get_attr(user, "name") or email.split("@")[0] if email else "Unknown"
        user_type = get_attr(user, "custom:userType") or "user"
        role = get_attr(user, "custom:role") or ""
        dept_id = get_attr(user, "custom:departmentId") or ""
        pos_id = get_attr(user, "custom:positionId") or ""

        item = {
            "userId": sub,
            "email": email,
            "fullName": name,
            "userType": user_type,
            "status": "active",
            "approval_status": "Approved",
            "rejectionReason": "",
            "createdAt": now,
            "createdBy": "MIGRATION",
            "updatedAt": now,
            "updatedBy": "MIGRATION",
        }
        if role:
            item["role"] = role
        if dept_id:
            item["departmentId"] = dept_id
        if pos_id:
            item["positionId"] = pos_id

        table.put_item(Item=item)
        print(f"  Created: {sub}  {name}  {email}")
        created += 1

    print(f"\nDone. Created {created} new DynamoDB user records.")


if __name__ == "__main__":
    main()
