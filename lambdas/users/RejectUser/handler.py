"""RejectUser Lambda resolver for AppSync.

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
        return reject_user(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def reject_user(event):
    """Reject a Pending_Approval user. Validates: Requirements 4.6, 4.7, 4.8, 4.9"""
    caller = require_user_type(event, ["superadmin"])
    user_id = event["arguments"]["userId"]
    reason = event["arguments"].get("reason", "")

    if not reason or not reason.strip():
        raise ValueError("Rejection reason is required")

    table = dynamodb.Table(USERS_TABLE)
    existing = table.get_item(Key={"userId": user_id}).get("Item")
    if not existing:
        raise ValueError(f"User '{user_id}' not found")

    if existing["approval_status"] != "Pending_Approval":
        raise ValueError(
            f"Cannot reject user with approval_status "
            f"'{existing['approval_status']}'. "
            f"Only Pending_Approval users can be rejected"
        )

    now = datetime.now(timezone.utc).isoformat()

    result = table.update_item(
        Key={"userId": user_id},
        UpdateExpression=(
            "SET #approval_status = :approval_status, "
            "#rejectionReason = :rejectionReason, "
            "#updatedAt = :updatedAt, #updatedBy = :updatedBy"
        ),
        ExpressionAttributeNames={
            "#approval_status": "approval_status",
            "#rejectionReason": "rejectionReason",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":approval_status": "Rejected",
            ":rejectionReason": reason.strip(),
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
