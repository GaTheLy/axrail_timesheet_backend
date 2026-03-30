"""CreatePosition Lambda resolver for AppSync.

Environment variables:
    POSITIONS_TABLE: DynamoDB Positions table name
"""

import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

POSITIONS_TABLE = os.environ.get("POSITIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return create_position(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _check_position_name_unique(table, position_name):
    """Check for case-insensitive duplicate position names."""
    response = table.scan(ProjectionExpression="positionId, positionName")
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(
            ProjectionExpression="positionId, positionName",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    for item in items:
        if item.get("positionName", "").lower() == position_name.lower():
            raise ValueError(f"Position name '{position_name}' is already in use")


def create_position(event):
    """Create a new position. Validates: Requirements 2.2, 2.6, 2.9, 3.2"""
    caller = require_user_type(event, ["superadmin", "admin"])
    args = event["arguments"]["input"]
    position_name = args["positionName"]
    department_id = args.get("departmentId", "")
    if not department_id:
        raise ValueError("departmentId is required for positions")
    table = dynamodb.Table(POSITIONS_TABLE)
    _check_position_name_unique(table, position_name)

    now = datetime.now(timezone.utc).isoformat()
    position_id = str(uuid.uuid4())

    approval_status = "Approved" if caller["userType"] == "superadmin" else "Pending_Approval"

    item = {
        "positionId": position_id,
        "positionName": position_name,
        "approval_status": approval_status,
        "rejectionReason": "",
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }
    if department_id:
        item["departmentId"] = department_id
    table.put_item(Item=item)
    return item
