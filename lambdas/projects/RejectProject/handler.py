"""RejectProject Lambda resolver for AppSync.

Environment variables:
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return reject_project(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def reject_project(event):
    """Reject a Pending_Approval project. Validates: Requirements 4.4, 4.7"""
    caller = require_user_type(event, ["superadmin"])
    project_id = event["arguments"]["projectId"]
    reason = event["arguments"].get("reason", "")

    if not reason or not reason.strip():
        raise ValueError("Rejection reason is required")

    table = dynamodb.Table(PROJECTS_TABLE)
    existing = table.get_item(Key={"projectId": project_id}).get("Item")
    if not existing:
        raise ValueError(f"Project '{project_id}' not found")

    if existing["approval_status"] != "Pending_Approval":
        raise ValueError(
            f"Cannot reject project with approval_status "
            f"'{existing['approval_status']}'. "
            f"Only Pending_Approval projects can be rejected"
        )

    now = datetime.now(timezone.utc).isoformat()

    result = table.update_item(
        Key={"projectId": project_id},
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
