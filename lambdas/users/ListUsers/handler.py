"""ListUsers Lambda resolver for AppSync.

Lists users with optional filtering.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

USERS_TABLE = os.environ.get("USERS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point for listUsers."""
    return list_users(event)


def list_users(event):
    """List users with optional filtering.

    Supports filtering by departmentId, userType, role, and supervisorId.

    Validates: Requirements 2.1, 2.4
    """
    table = dynamodb.Table(USERS_TABLE)
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

    if "departmentId" in filter_input:
        response = table.query(
            IndexName="departmentId-index",
            KeyConditionExpression=Key("departmentId").eq(
                filter_input["departmentId"]
            ),
        )
        items = response.get("Items", [])
    elif "supervisorId" in filter_input:
        response = table.query(
            IndexName="supervisorId-index",
            KeyConditionExpression=Key("supervisorId").eq(
                filter_input["supervisorId"]
            ),
        )
        items = response.get("Items", [])
    else:
        response = table.scan()
        items = response.get("Items", [])

    # Apply additional client-side filters
    if "userType" in filter_input:
        items = [i for i in items if i.get("userType") == filter_input["userType"]]
    if "role" in filter_input:
        items = [i for i in items if i.get("role") == filter_input["role"]]

    return {"items": items}
