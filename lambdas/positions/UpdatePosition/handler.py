"""UpdatePosition Lambda resolver for AppSync.

Environment variables:
    POSITIONS_TABLE: DynamoDB Positions table name
"""

import os
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
        return update_position(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _check_position_name_unique(table, position_name, exclude_position_id=None):
def _check_position_name_unique(table, position_name, exclude_position_id=None):
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
            if item["positionId"] != exclude_position_id:
                raise ValueError(f"Position name '{position_name}' is already in use")


def update_position(event):
    """Update an existing position. Validates: Requirements 3.2, 3.4, 3.6"""
    caller = require_user_type(event, ["superadmin", "admin"])
    position_id = event["arguments"]["positionId"]
    args = event["arguments"]["input"]
    table = dynamodb.Table(POSITIONS_TABLE)

    existing = table.get_item(Key={"positionId": position_id}).get("Item")
    if not existing:
        raise ValueError(f"Position '{position_id}' not found")

    if existing.get("approval_status") == "Approved" and caller["userType"] != "superadmin":
        raise ValueError("Cannot update position: approved entities cannot be edited")

    new_name = args.get("positionName")
    if new_name and new_name != existing["positionName"]:
        _check_position_name_unique(table, new_name, exclude_position_id=position_id)

    now = datetime.now(timezone.utc).isoformat()
    update_parts = []
    expr_names = {}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}
    update_parts.append("#updatedAt = :updatedAt")
    update_parts.append("#updatedBy = :updatedBy")
    expr_names["#updatedAt"] = "updatedAt"
    expr_names["#updatedBy"] = "updatedBy"

    if new_name:
        expr_values[":positionName"] = new_name
        expr_names["#positionName"] = "positionName"
        update_parts.append("#positionName = :positionName")

    new_department_id = args.get("departmentId")
    if new_department_id is not None:
        expr_values[":departmentId"] = new_department_id
        expr_names["#departmentId"] = "departmentId"
        update_parts.append("#departmentId = :departmentId")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"positionId": position_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
