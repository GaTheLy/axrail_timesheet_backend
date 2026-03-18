"""GetUser Lambda resolver for AppSync.

Retrieves a single user by userId.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
"""

import os

import boto3

USERS_TABLE = os.environ.get("USERS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point for getUser."""
    return get_user(event)


def get_user(event):
    """Retrieve a single user by userId.

    Validates: Requirements 2.1
    """
    user_id = event["arguments"]["userId"]
    table = dynamodb.Table(USERS_TABLE)

    result = table.get_item(Key={"userId": user_id})
    item = result.get("Item")
    if not item:
        return None
    return item
