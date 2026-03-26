"""DeletePosition Lambda resolver for AppSync.

Environment variables:
    POSITIONS_TABLE: DynamoDB Positions table name
"""

import os

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

POSITIONS_TABLE = os.environ.get("POSITIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return delete_position(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def delete_position(event):
    """Delete a position. Validates: Requirements 3.2, 3.6"""
    caller = require_user_type(event, ["superadmin", "admin"])
    position_id = event["arguments"]["positionId"]
    table = dynamodb.Table(POSITIONS_TABLE)

    existing = table.get_item(Key={"positionId": position_id}).get("Item")
    if not existing:
        raise ValueError(f"Position '{position_id}' not found")

    if existing.get("approval_status") == "Approved" and caller["userType"] != "superadmin":
        raise ValueError("Cannot delete position: approved entities cannot be deleted")

    table.delete_item(Key={"positionId": position_id})
    return True
