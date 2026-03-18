"""ListMainDatabase Lambda resolver for AppSync.

Environment variables:
    MAIN_DATABASE_TABLE: DynamoDB Main_Database table name
"""

import os

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, get_caller_identity

MAIN_DATABASE_TABLE = os.environ.get("MAIN_DATABASE_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return list_main_database(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def list_main_database(event):
    """List all records. Validates: Requirements 14.1"""
    caller = get_caller_identity(event)
    allowed = caller["userType"] == "superadmin" or caller["role"] == "Project_Manager"
    if not allowed:
        raise ForbiddenError("Only Superadmin or Project_Manager can access the main database")

    table = dynamodb.Table(MAIN_DATABASE_TABLE)
    items = []
    scan_kwargs = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return items
