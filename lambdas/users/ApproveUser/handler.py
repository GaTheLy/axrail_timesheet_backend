"""ApproveUser Lambda resolver for AppSync.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

USERS_TABLE = os.environ.get("USERS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return approve_user(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def approve_user(event):
    """Approve a Pending_Approval user. Validates: Requirements 4.3, 4.7, 4.8, 4.9"""
    caller = require_user_type(event, ["superadmin"])
    user_id = event["arguments"]["userId"]
    table = dynamodb.Table(USERS_TABLE)

    existing = table.get_item(Key={"userId": user_id}).get("Item")
    if not existing:
        raise ValueError(f"User '{user_id}' not found")

    if existing["approval_status"] != "Pending_Approval":
        raise ValueError(
            f"Cannot approve user with approval_status "
            f"'{existing['approval_status']}'. "
            f"Only Pending_Approval users can be approved"
        )

    now = datetime.now(timezone.utc).isoformat()
    result = table.update_item(
        Key={"userId": user_id},
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
