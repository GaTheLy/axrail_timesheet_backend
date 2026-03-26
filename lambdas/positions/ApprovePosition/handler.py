"""ApprovePosition Lambda resolver for AppSync.

Environment variables:
    POSITIONS_TABLE: DynamoDB Positions table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

POSITIONS_TABLE = os.environ.get("POSITIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return approve_position(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def approve_position(event):
    """Approve a Pending_Approval position. Validates: Requirements 4.2, 4.7, 4.8, 4.9"""
    caller = require_user_type(event, ["superadmin"])
    position_id = event["arguments"]["positionId"]
    table = dynamodb.Table(POSITIONS_TABLE)

    existing = table.get_item(Key={"positionId": position_id}).get("Item")
    if not existing:
        raise ValueError(f"Position '{position_id}' not found")

    if existing["approval_status"] != "Pending_Approval":
        raise ValueError(
            f"Cannot approve position with approval_status "
            f"'{existing['approval_status']}'. "
            f"Only Pending_Approval positions can be approved"
        )

    now = datetime.now(timezone.utc).isoformat()
    result = table.update_item(
        Key={"positionId": position_id},
        UpdateExpression=(
            "SET #approval_status = :approval_status, "
            "#updatedAt = :updatedAt, #updatedBy = :updatedBy"
        ),
        ExpressionAttributeNames={
            "#approval_status": "approval_status",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":approval_status": "Approved",
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
